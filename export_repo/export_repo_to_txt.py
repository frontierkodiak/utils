import platform
import os
import json
import sys
import nbformat
from nbconvert import MarkdownExporter
from nbconvert.preprocessors import ClearOutputPreprocessor

class PathConverter:
    @staticmethod
    def to_system_path(path: str) -> str:
        """
        Convert the given path to the current system's native format.
        On Windows, forward slashes become backslashes, etc.
        """
        if platform.system() == "Windows":
            # Convert forward slashes to backslashes and handle drive letter
            if path.startswith("/"):
                # Remove leading slash and convert to Windows path
                path = path.lstrip("/")
                if ":" not in path:  # If no drive letter, assume C:
                    path = "C:\\" + path
            return path.replace("/", "\\")
        else:
            # Convert backslashes to forward slashes for Unix-like systems
            return path.replace("\\", "/")

    @staticmethod
    def normalize_config_paths(config: dict) -> dict:
        """
        Normalize all relevant paths in the config to the current system's format.
        """
        if 'repo_root' in config:
            base_path = get_base_path()
            if platform.system() == "Windows":
                # Replace Unix-style base paths with Windows GitHub path
                for unix_path in ["/home/caleb/repo", "/home/caleb/Documents/GitHub/", "/Users/caleb/Documents/GitHub"]:
                    if config['repo_root'].startswith(unix_path):
                        relative_path = config['repo_root'][len(unix_path):].lstrip("/")
                        config['repo_root'] = os.path.join(base_path, relative_path)
                        break
            
            config['repo_root'] = PathConverter.to_system_path(config['repo_root'])
        
        # Convert path lists
        for key in ['dirs_to_traverse', 'subdirs_to_exclude', 'files_to_exclude']:
            if key in config and isinstance(config[key], list):
                config[key] = [PathConverter.to_system_path(p) for p in config[key]]
        
        return config

class RepoExporter:
    def __init__(self, config: dict, config_filename: str = None):
        """
        Initialize the RepoExporter with the given config dictionary.
        :param config: The loaded or constructed configuration object.
        :param config_filename: Optional name of the config file (if used), 
                               for placing in the output XML tags.
        """
        # Convert all paths in config to system-specific format
        config = PathConverter.normalize_config_paths(config)
        self.repo_root = config['repo_root']
        self.export_name = config['export_name']
        self.dirs_to_traverse = config['dirs_to_traverse']
        self.include_top_level_files = config['include_top_level_files']
        self.included_extensions = config['included_extensions']
        self.subdirs_to_exclude = config.get('subdirs_to_exclude', [])
        self.files_to_exclude = config.get('files_to_exclude', [])
        self.depth = config.get('depth', -1)  # Default to -1 for full traversal
        self.dump_config = config.get('dump_config', False)
        self.exhaustive_dir_tree = config.get('exhaustive_dir_tree', False)

        # Additional rules and blacklists
        self.blacklisted_dirs = ['__pycache__', '.git', '.venv', '.vscode']
        self.blacklisted_files = ['uv.lock', 'LICENSE']
        self.files_to_include = config.get('files_to_include', [])
        self.always_exclude_patterns = config.get('always_exclude_patterns', ['export.txt'])
        self.dirs_for_tree = config.get('dirs_for_tree', [])

        # Bookkeeping
        self.config_filename = config_filename
        self.exported_files_count = {}
        self.total_lines = 0
        self.line_counts_by_file = {}
        self.line_counts_by_dir = {}
        
        # Make sure the final output path is correct
        self.output_file = self.get_output_file_path()
        # Avoid re-exporting the output file
        self.files_to_exclude.append(os.path.basename(self.output_file))

        # Memory buffer for file contents (rather than writing them incrementally)
        # Each entry is a tuple: (rel_path, content, is_ipynb_converted)
        self.file_contents = []

    def get_output_file_path(self) -> str:
        """
        Return the absolute path for the export file, 
        converting paths if necessary.
        """
        if os.path.isabs(self.export_name):
            return PathConverter.to_system_path(self.export_name)
        else:
            return PathConverter.to_system_path(os.path.join(self.repo_root, self.export_name))

    def convert_ipynb_to_md(self, notebook_content: str) -> str:
        """
        Convert an IPython notebook JSON string to Markdown by clearing outputs
        and using nbconvert's MarkdownExporter.
        """
        notebook = nbformat.reads(notebook_content, as_version=4)
        
        # Clear outputs
        clear_output = ClearOutputPreprocessor()
        clear_output.preprocess(notebook, {})

        # Convert to markdown
        markdown_exporter = MarkdownExporter()
        markdown_content, _ = markdown_exporter.from_notebook_node(notebook)
        return markdown_content

    def store_file_content(self, content: str, file_path: str, ipynb_converted: bool = False):
        """
        Cache the file's content in memory, track line counts, 
        and update the total lines + extension stats.
        """
        extension = os.path.splitext(file_path)[1]
        self.exported_files_count[extension] = self.exported_files_count.get(extension, 0) + 1
        
        line_count = content.count('\n') + 1
        self.total_lines += line_count
        self.line_counts_by_file[file_path] = line_count

        # Store the file content in memory for final output
        self.file_contents.append((file_path, content, ipynb_converted))

    def should_exclude_file(self, file_path: str) -> bool:
        """
        Return True if the file_path should be skipped 
        based on blacklists, always_exclude_patterns, and user config.
        """
        relative_path = os.path.relpath(file_path, self.repo_root)
        filename = os.path.basename(file_path)
        
        # Check blacklisted files
        if filename in self.blacklisted_files:
            return True
        
        # Patterns
        if any(filename.endswith(pattern) for pattern in self.always_exclude_patterns):
            return True
        
        # Config-based exclude
        return any(relative_path.endswith(exclude) for exclude in self.files_to_exclude)

    def should_exclude_dir(self, dir_path: str) -> bool:
        """
        Return True if the directory should be skipped 
        based on blacklists and user config.
        """
        dir_name = os.path.basename(dir_path)

        # Blacklisted names
        if dir_name in self.blacklisted_dirs:
            return True
        
        # Config-based excludes
        relative_path = os.path.relpath(dir_path, self.repo_root)
        relative_path = PathConverter.to_system_path(relative_path)
        return any(relative_path.startswith(PathConverter.to_system_path(exclude.rstrip('*'))) 
                   for exclude in self.subdirs_to_exclude)

    def traverse_directory(self, directory: str):
        """
        Walk through 'directory' within the repo_root, 
        read all matching files, and store their contents in memory.
        """
        abs_directory = os.path.join(self.repo_root, directory)

        if not os.path.exists(abs_directory):
            print(f"Warning: Directory {abs_directory} does not exist. Skipping.")
            return

        for root, dirs, files in os.walk(abs_directory):
            # Filter out excluded subdirs
            dirs[:] = [d for d in dirs if not self.should_exclude_dir(os.path.join(root, d))]

            # Check each file
            for file in files:
                file_path = os.path.join(root, file)
                if self.should_exclude_file(file_path):
                    continue
                file_extension = os.path.splitext(file)[1]
                # Check if extension is included
                if self.included_extensions == 'all' or file_extension in self.included_extensions:
                    relative_path = os.path.relpath(file_path, self.repo_root)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        # Convert .ipynb to .md if necessary
                        if file_extension == '.ipynb':
                            content = self.convert_ipynb_to_md(content)
                            self.store_file_content(content, relative_path, ipynb_converted=True)
                        else:
                            self.store_file_content(content, relative_path, ipynb_converted=False)
                    except Exception as e:
                        print(f"Error reading file {file_path}: {str(e)}")

    def include_specific_files(self):
        """
        Include user-specified files in self.files_to_include, 
        supporting absolute or relative paths.
        """
        for file_path in self.files_to_include:
            # Check absolute vs. relative
            if os.path.isabs(file_path):
                # Handle absolute path directly
                if os.path.exists(file_path) and not self.should_exclude_file(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        relative_path = os.path.relpath(file_path, self.repo_root)
                        extension = os.path.splitext(file_path)[1]
                        if extension == '.ipynb':
                            content = self.convert_ipynb_to_md(content)
                            self.store_file_content(content, relative_path, ipynb_converted=True)
                        else:
                            self.store_file_content(content, relative_path, ipynb_converted=False)
                    except Exception as e:
                        print(f"Error reading file {file_path}: {str(e)}")
            else:
                # It's a relative path from repo_root
                abs_root = os.path.abspath(self.repo_root)
                for root, _, files in os.walk(abs_root):
                    for file in files:
                        curr_path = os.path.join(root, file)
                        rel_path = os.path.relpath(curr_path, abs_root)
                        if rel_path == file_path and not self.should_exclude_file(curr_path):
                            try:
                                with open(curr_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                extension = os.path.splitext(curr_path)[1]
                                if extension == '.ipynb':
                                    content = self.convert_ipynb_to_md(content)
                                    self.store_file_content(content, file_path, ipynb_converted=True)
                                else:
                                    self.store_file_content(content, file_path, ipynb_converted=False)
                            except Exception as e:
                                print(f"Error reading file {curr_path}: {str(e)}")

    def should_include_in_tree(self, dir_path: str) -> bool:
        """
        Return True if 'dir_path' should appear in the directory tree.
        This logic respects blacklists, user excludes, and (optionally) self.exhaustive_dir_tree.
        """
        dir_name = os.path.basename(dir_path)

        # Immediately drop blacklisted or hidden
        if dir_name in self.blacklisted_dirs or dir_name.startswith('.'):
            return False

        # If exhaustive_dir_tree is off, filter further
        if not self.exhaustive_dir_tree:
            if self.should_exclude_dir(dir_path):
                return False
            # Also ensure directory is within dirs_to_traverse
            abs_dir_path = os.path.abspath(dir_path)
            allowed = False
            for d in self.dirs_to_traverse:
                allowed_dir = os.path.abspath(os.path.join(self.repo_root, d))
                if os.path.commonprefix([abs_dir_path, allowed_dir]) == allowed_dir:
                    allowed = True
                    break
            if not allowed:
                return False

        # If dirs_for_tree is specified, only include matches
        if self.dirs_for_tree:
            relative_path = os.path.relpath(dir_path, self.repo_root)
            return any(
                relative_path == d or relative_path.startswith(d + os.sep)
                for d in self.dirs_for_tree
            )

        return True

    def compute_directory_line_counts(self):
        """
        After reading all file contents, sum up the line counts
        for each directory that contains them.
        """
        self.line_counts_by_dir = {}
        for rel_file_path, lines in self.line_counts_by_file.items():
            parts = rel_file_path.split(os.sep)
            # Add line counts up the chain of directories
            for i in range(1, len(parts)):
                dir_path = os.sep.join(parts[:i])
                self.line_counts_by_dir[dir_path] = self.line_counts_by_dir.get(dir_path, 0) + lines

    def get_line_count_for_path(self, rel_path: str) -> int:
        """
        Return the line count for the given rel_path 
        (if file) or sum for all files under that directory.
        """
        full_path = os.path.join(self.repo_root, rel_path)
        if os.path.isfile(full_path):
            return self.line_counts_by_file.get(rel_path, 0)
        else:
            return self.line_counts_by_dir.get(rel_path, 0)

    def get_directory_tree(self, directory: str, prefix: str = '', current_depth: int = 0, lines_word_used: bool = False):
        """
        Produce a string representation of 'directory' in an ASCII tree format, 
        labeling each item with either "(X lines)" or "(X)" (once "lines" has appeared).
        """
        if self.depth != -1 and current_depth > self.depth:
            return f"{prefix}   (omitted)\n", lines_word_used

        tree_str = ''
        items = sorted(os.listdir(directory))
        visible_items = []
        for item in items:
            path = os.path.join(directory, item)
            if os.path.isfile(path):
                # Show file if it was actually exported
                rel_file_path = os.path.relpath(path, self.repo_root)
                if rel_file_path in self.line_counts_by_file:
                    visible_items.append(item)
            elif os.path.isdir(path):
                if self.should_include_in_tree(path):
                    visible_items.append(item)

        for i, item in enumerate(visible_items):
            path = os.path.join(directory, item)
            rel_path = os.path.relpath(path, self.repo_root)
            line_count = self.get_line_count_for_path(rel_path)

            # Use ASCII connectors
            connector = '|-- ' if i < len(visible_items) - 1 else '\\-- '

            if not lines_word_used:
                # first time we show line counts, add the word "lines"
                line_str = f"({line_count} lines)" if line_count > 0 else "(0 lines)"
                lines_word_used = True
            else:
                line_str = f"({line_count})"

            tree_str += f"{prefix}{connector}{item} {line_str}\n"
            if os.path.isdir(path):
                # Subtree indentation: align with the connector
                sub_prefix = prefix + ("|   " if i < len(visible_items) - 1 else "    ")
                subtree_str, lines_word_used = self.get_directory_tree(path, sub_prefix, current_depth + 1, lines_word_used)
                tree_str += subtree_str

        return tree_str, lines_word_used

    def export_repo(self):
        """
        Main routine:
        1) Possibly gather top-level files,
        2) Recursively gather all files from dirs_to_traverse,
        3) Include any extra user-specified files,
        4) Compute line counts,
        5) Write a final output file that uses XML-style tags:
           <codebase_context> 
              <repo export config: ...> ... </repo export config: ...>
              <dirtree: ...> ... </dirtree: ...>
              <file: ...> ... </file: ...>
           </codebase_context>
        """
        # 1) Optionally include top-level files
        if self.include_top_level_files == 'all':
            for item in os.listdir(self.repo_root):
                item_path = os.path.join(self.repo_root, item)
                if os.path.isfile(item_path) and not self.should_exclude_file(item_path):
                    file_extension = os.path.splitext(item)[1]
                    if self.included_extensions == 'all' or file_extension in self.included_extensions:
                        try:
                            with open(item_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            if file_extension == '.ipynb':
                                content = self.convert_ipynb_to_md(content)
                                self.store_file_content(content, os.path.relpath(item_path, self.repo_root), True)
                            else:
                                self.store_file_content(content, os.path.relpath(item_path, self.repo_root), False)
                        except Exception as e:
                            print(f"Error reading top-level file {item_path}: {str(e)}")
        elif isinstance(self.include_top_level_files, list):
            for file_name in self.include_top_level_files:
                if file_name in self.files_to_exclude:
                    continue
                file_path = os.path.join(self.repo_root, file_name)
                if os.path.exists(file_path) and not self.should_exclude_file(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        extension = os.path.splitext(file_name)[1]
                        if extension == '.ipynb':
                            content = self.convert_ipynb_to_md(content)
                            self.store_file_content(content, file_name, True)
                        else:
                            self.store_file_content(content, file_name, False)
                    except Exception as e:
                        print(f"Error reading file {file_path}: {str(e)}")

        # 2) Traverse specified directories
        for dir_to_traverse in self.dirs_to_traverse:
            self.traverse_directory(dir_to_traverse)

        # 3) Include specific user-specified files
        self.include_specific_files()

        # 4) Compute directory line counts
        self.compute_directory_line_counts()

        # 5) Build the directory tree string
        directory_tree_str, _ = self.get_directory_tree(self.repo_root, current_depth=0, lines_word_used=False)

        # 6) Now write the final output with XML-style tags
        with open(self.output_file, 'w', encoding='utf-8') as out:
            out.write("<codebase_context>\n\n")

            # (optional) export config block
            if self.dump_config:
                # We'll label with the config filename if it exists
                # or just 'inline-config' if it doesn't
                config_tag_label = self.config_filename if self.config_filename else "inline-config"
                out.write(f"<repo export config: {config_tag_label}>\n")
                # For debugging, we can dump a JSON version of the object's fields.
                # Typically you'd store something more minimal. 
                # We'll replicate the older logic:
                config_data = {
                    # self.* variables that might be relevant to see
                    "repo_root": self.repo_root,
                    "export_name": self.export_name,
                    "dirs_to_traverse": self.dirs_to_traverse,
                    "include_top_level_files": self.include_top_level_files,
                    "included_extensions": self.included_extensions,
                    "subdirs_to_exclude": self.subdirs_to_exclude,
                    "files_to_exclude": self.files_to_exclude,
                    "depth": self.depth,
                    "dump_config": self.dump_config,
                    "exhaustive_dir_tree": self.exhaustive_dir_tree,
                    "blacklisted_dirs": self.blacklisted_dirs,
                    "blacklisted_files": self.blacklisted_files,
                    "files_to_include": self.files_to_include,
                    "always_exclude_patterns": self.always_exclude_patterns,
                    "dirs_for_tree": self.dirs_for_tree
                }
                out.write(json.dumps(config_data, indent=2))
                out.write(f"\n</repo export config: {config_tag_label}>\n\n")

            # Directory tree block
            out.write(f"<dirtree: {self.repo_root}>\n")
            out.write(directory_tree_str)
            out.write(f"</dirtree: {self.repo_root}>\n\n")

            # Files
            for (rel_path, content, ipynb_converted) in self.file_contents:
                out.write(f"<file: {rel_path}>\n")
                if ipynb_converted:
                    out.write("(NOTE: ipynb notebook converted to md)\n")
                out.write(content.rstrip('\n'))
                out.write(f"\n</file: {rel_path}>\n\n")

            out.write("</codebase_context>\n")

        # Console summary
        print(f"Exported to: {self.output_file}")
        print(f"Total number of lines: {self.total_lines}")
        print("Number of exported files by extension:")
        for ext, count in self.exported_files_count.items():
            print(f"  {ext}: {count}")

def get_base_path() -> str:
    """
    Determine the base path based on the host platform or command-line argument.
    """
    if '--pop' in sys.argv:
        return '/home/caleb/Documents/GitHub/'  # pop-xps popOS system
    elif platform.system() == "Darwin":  # macOS
        return "/Users/caleb/Documents/GitHub"
    elif platform.system() == "Windows":  # Windows
        return r"C:\Users\front\Documents\GitHub"
    else:  # Linux or other (dev server, or polliserve instances)
        return "/home/caleb/repo"

def load_config(config_filename: str) -> dict:
    """
    Load configuration from a JSON file located in `utils/export_repo/configs`,
    normalizing all paths inside.
    """
    base_path = get_base_path()
    config_path = os.path.join(base_path, "utils/export_repo/configs", config_filename)
    config_path = PathConverter.to_system_path(config_path)
    
    with open(config_path, 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)
    
    # Normalize
    config = PathConverter.normalize_config_paths(config)
    return config

def get_default_config(repo_root: str) -> dict:
    """
    Provide a default config if the user passes a directory path 
    instead of a config file.
    """
    return {
        'repo_root': repo_root,
        'export_name': f"{os.path.basename(repo_root)}_export.txt",
        'dirs_to_traverse': ['.'],
        'include_top_level_files': 'all',
        'included_extensions': 'all',
        'subdirs_to_exclude': ['__pycache__'],
        'files_to_exclude': [],
        'depth': 10,
        'exhaustive_dir_tree': False,
        'files_to_include': [],
        'always_exclude_patterns': ['export.txt'],
        'dump_config': False
    }

def main():
    """
    Command-line entry point.
    Usage:
      python export_repo_to_txt.py [--pop] [--dump-config] <config_filename|repo_root>
    """
    args = sys.argv[1:]
    config_filename = None
    pop_flag = False
    dump_config_flag = False

    for arg in args:
        if arg == '--pop':
            pop_flag = True
        elif arg == '--dump-config':
            dump_config_flag = True
        elif not arg.startswith('--'):
            config_filename = arg

    if not config_filename:
        print("Usage: python export_repo_to_txt.py [--pop] [--dump-config] <config_filename or repo_root>")
        sys.exit(1)

    # Distinguish whether the user gave us a directory or a config file
    if os.path.isdir(config_filename):
        # Use a default config if a directory was passed
        config = get_default_config(config_filename)
        # We'll embed the actual path in config_filename for labeling if we want
        config_filename_label = f"default-for-{os.path.basename(config_filename)}"
    else:
        # If not a directory, treat it as a config file name
        if not config_filename.endswith('.json'):
            config_filename += '.json'
        config = load_config(config_filename)
        config_filename_label = config_filename

    # If pop_flag was set, do any path transformations
    if pop_flag:
        base_path = '/home/caleb/Documents/GitHub/'
        config['repo_root'] = config['repo_root'].replace("/home/caleb/repo", base_path)

    # If --dump-config was requested, set in config
    config['dump_config'] = dump_config_flag

    # Create and run exporter
    exporter = RepoExporter(config, config_filename=config_filename_label)
    exporter.export_repo()

if __name__ == "__main__":
    main()