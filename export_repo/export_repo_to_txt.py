import platform
import os
import json
import sys
import nbformat
from nbconvert import MarkdownExporter
from nbconvert.preprocessors import ClearOutputPreprocessor

class PathConverter:
    @staticmethod
    def to_system_path(path):
        """Convert path to the current system's format."""
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
    def normalize_config_paths(config):
        """Normalize all paths in config to system-specific format."""
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
        
        # Convert paths in lists
        for key in ['dirs_to_traverse', 'subdirs_to_exclude', 'files_to_exclude']:
            if key in config and isinstance(config[key], list):
                config[key] = [PathConverter.to_system_path(p) for p in config[key]]
        
        return config

class RepoExporter:
    def __init__(self, config):
        # Convert all paths in config to system-specific format
        config = PathConverter.normalize_config_paths(config)
        self.repo_root = config['repo_root']
        self.export_name = config['export_name']
        self.delimiter = config['delimiter']
        self.dirs_to_traverse = config['dirs_to_traverse']
        self.include_top_level_files = config['include_top_level_files']
        self.included_extensions = config['included_extensions']
        self.subdirs_to_exclude = config.get('subdirs_to_exclude', [])
        self.files_to_exclude = config.get('files_to_exclude', [])
        self.depth = config.get('depth', -1)  # Default to -1 for full traversal
        self.dump_config = config.get('dump_config', False)
        self.exhaustive_dir_tree = config.get('exhaustive_dir_tree', False)
        self.blacklisted_dirs = ['__pycache__']  # Blacklist of subdirs to always omit
        self.blacklisted_dirs.extend(['.git', '.venv', '.vscode'])  # Add common hidden dirs
        self.blacklisted_files = ['uv.lock']  # Blacklist of files to always omit
        self.files_to_include = config.get('files_to_include', [])  # Additional files to include explicitly
        self.output_file = self.get_output_file_path()
        self.files_to_exclude.append(os.path.basename(self.output_file))  # Add output file to exclude list
        self.always_exclude_patterns = config.get('always_exclude_patterns', ['export.txt'])
        self.exported_files_count = {}
        self.dirs_for_tree = config.get('dirs_for_tree', [])
        self.total_lines = 0
        self.line_counts_by_file = {}  # Store line counts by relative file path
        self.line_counts_by_dir = {}   # Store aggregated line counts by directory

    def convert_ipynb_to_md(self, notebook_content):
        notebook = nbformat.reads(notebook_content, as_version=4)
        
        # Clear outputs
        clear_output = ClearOutputPreprocessor()
        clear_output.preprocess(notebook, {})
        
        markdown_exporter = MarkdownExporter()
        markdown_content, _ = markdown_exporter.from_notebook_node(notebook)
        return markdown_content
    
    def get_output_file_path(self):
        if os.path.isabs(self.export_name):
            return PathConverter.to_system_path(self.export_name)
        else:
            return PathConverter.to_system_path(os.path.join(self.repo_root, self.export_name))

    def write_to_file(self, content, file_path=None, mode='a'):
        with open(self.output_file, mode, encoding='utf-8') as f:
            if file_path:
                extension = os.path.splitext(file_path)[1]
                self.exported_files_count[extension] = self.exported_files_count.get(extension, 0) + 1
                lines = content.count('\n') + 1
                self.total_lines += lines
                
                # Store line count for this file
                self.line_counts_by_file[file_path] = lines
                
                # Add a note for converted ipynb files
                if extension == '.ipynb':
                    f.write(f"{self.delimiter}\nFull Path: {file_path}\n(NOTE: ipynb notebook converted to md)\n\n{content}\n\n")
                else:
                    f.write(f"{self.delimiter}\nFull Path: {file_path}\n\n{content}\n\n")
            else:
                f.write(f"{content}\n")

    def should_exclude_file(self, file_path):
        relative_path = os.path.relpath(file_path, self.repo_root)
        filename = os.path.basename(file_path)
        
        # First check blacklisted files
        if filename in self.blacklisted_files:
            return True
        
        # Then check always_exclude_patterns
        if any(filename.endswith(pattern) for pattern in self.always_exclude_patterns):
            return True
        
        # Finally check configured exclusions
        return any(relative_path.endswith(exclude) for exclude in self.files_to_exclude)

    def should_exclude_dir(self, dir_path):
        dir_name = os.path.basename(dir_path)
        
        # First check blacklisted dirs
        if dir_name in self.blacklisted_dirs:
            return True
        
        # Then check configured exclusions
        relative_path = os.path.relpath(dir_path, self.repo_root)
        relative_path = PathConverter.to_system_path(relative_path)
        return any(relative_path.startswith(PathConverter.to_system_path(exclude.rstrip('*'))) 
                  for exclude in self.subdirs_to_exclude)

    def traverse_directory(self, directory):
        # Ensure the directory path is absolute
        abs_directory = os.path.join(self.repo_root, directory)

        if not os.path.exists(abs_directory):
            print(f"Warning: Directory {abs_directory} does not exist. Skipping.")
            return

        for root, dirs, files in os.walk(abs_directory):
            dirs[:] = [d for d in dirs if not self.should_exclude_dir(os.path.join(root, d))]

            for file in files:
                file_path = os.path.join(root, file)
                if self.should_exclude_file(file_path):
                    continue
                file_extension = os.path.splitext(file)[1]
                if self.included_extensions == 'all' or file_extension in self.included_extensions:
                    relative_path = os.path.relpath(file_path, self.repo_root)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Convert ipynb to markdown if necessary
                        if file_extension == '.ipynb':
                            content = self.convert_ipynb_to_md(content)
                        
                        self.write_to_file(content, relative_path)
                    except Exception as e:
                        print(f"Error reading file {file_path}: {str(e)}")

    def include_specific_files(self, root_dir):
        """Include specific files, supporting both relative and absolute paths."""
        for file_path in self.files_to_include:
            if os.path.isabs(file_path):
                # Handle absolute paths directly
                if os.path.exists(file_path) and not self.should_exclude_file(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        relative_path = os.path.relpath(file_path, self.repo_root)
                        self.write_to_file(content, relative_path)
                    except Exception as e:
                        print(f"Error reading file {file_path}: {str(e)}")
            else:
                # Original behavior for relative paths
                for root, _, files in os.walk(root_dir):
                    for file in files:
                        curr_path = os.path.join(root, file)
                        relative_path = os.path.relpath(curr_path, root_dir)
                        if relative_path == file_path and not self.should_exclude_file(curr_path):
                            try:
                                with open(curr_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                self.write_to_file(content, relative_path)
                            except Exception as e:
                                print(f"Error reading file {curr_path}: {str(e)}")

    def should_include_in_tree(self, dir_path):
        """Determine if a directory should be included in the tree output."""
        dir_name = os.path.basename(dir_path)

        # Check blacklisted dirs first - make this an immediate return
        if dir_name in self.blacklisted_dirs:
            return False

        # Never include hidden directories (starting with .)
        if dir_name.startswith('.'):
            return False

        # If exhaustive_dir_tree is False, filter directories as they would be during traversal
        if not self.exhaustive_dir_tree:
            # Exclude directories that match subdirs_to_exclude
            if self.should_exclude_dir(dir_path):
                return False
            
            # Also ensure this directory is within one of our allowed traversal directories
            abs_dir_path = os.path.abspath(dir_path)
            allowed = False
            for d in self.dirs_to_traverse:
                allowed_dir = os.path.abspath(os.path.join(self.repo_root, d))
                if os.path.commonprefix([abs_dir_path, allowed_dir]) == allowed_dir:
                    allowed = True
                    break
            if not allowed:
                return False

        # If specific dirs are specified, only include those
        if self.dirs_for_tree:
            relative_path = os.path.relpath(dir_path, self.repo_root)
            return any(relative_path == d or relative_path.startswith(d + os.sep) 
                    for d in self.dirs_for_tree)

        return True

    def compute_directory_line_counts(self):
        """
        Compute the total line counts for each directory.
        We'll sum the line counts of all files under each directory.
        """
        self.line_counts_by_dir = {}

        # Initialize directories found from the exported files
        for rel_file_path, lines in self.line_counts_by_file.items():
            # Add line counts up the chain of directories
            parts = rel_file_path.split(os.sep)
            for i in range(1, len(parts)):
                dir_path = os.sep.join(parts[:i])  # partial path representing directory
                self.line_counts_by_dir[dir_path] = self.line_counts_by_dir.get(dir_path, 0) + lines

    def get_line_count_for_path(self, rel_path):
        """
        Return the line count for a given file or directory relative path.
        If it's a file, look up in line_counts_by_file.
        If it's a directory, look up in line_counts_by_dir.
        If not found, return 0.
        """
        if os.path.isfile(os.path.join(self.repo_root, rel_path)):
            return self.line_counts_by_file.get(rel_path, 0)
        else:
            return self.line_counts_by_dir.get(rel_path, 0)

    def get_directory_tree(self, directory, prefix='', current_depth=0, lines_word_used=False):
        """Generate a string representation of the directory tree with line counts."""
        if self.depth != -1 and current_depth > self.depth:
            return f"{prefix}│   └── (omitted)\n", lines_word_used

        tree_str = ''
        items = sorted(os.listdir(directory))
        
        # Filter items based on visibility rules
        visible_items = []
        for item in items:
            path = os.path.join(directory, item)
            if os.path.isfile(path):
                # Check if file was exported
                rel_file_path = os.path.relpath(path, self.repo_root)
                if rel_file_path in self.line_counts_by_file:  # only include if exported
                    visible_items.append(item)
            elif os.path.isdir(path):
                if self.should_include_in_tree(path):
                    visible_items.append(item)
        
        for i, item in enumerate(visible_items):
            path = os.path.join(directory, item)
            connector = '├── ' if i < len(visible_items) - 1 else '└── '
            rel_path = os.path.relpath(path, self.repo_root)
            line_count = self.get_line_count_for_path(rel_path)
            
            # Determine how to print line counts
            if not lines_word_used:
                # Print lines_word once
                line_str = f"({line_count} lines)" if line_count > 0 else "(0 lines)"
                lines_word_used = True
            else:
                line_str = f"({line_count})"
            
            tree_str += f"{prefix}{connector}{item} {line_str}\n"
            if os.path.isdir(path):
                extension = '' if i < len(visible_items) - 1 else '    '
                subtree_str, lines_word_used = self.get_directory_tree(path, prefix + extension + '│   ', current_depth + 1, lines_word_used)
                tree_str += subtree_str

        return tree_str, lines_word_used

    def export_repo(self):
        # Clear the output file before starting
        with open(self.output_file, 'w', encoding='utf-8') as f:
            pass

        # Write the export configuration to the output file if dump_config is True
        if self.dump_config:
            self.write_to_file(f"Export Configuration:\n{json.dumps(vars(self), indent=2)}", mode='w')

        # Export top-level files (if requested)
        if self.include_top_level_files == 'all':
            for item in os.listdir(self.repo_root):
                item_path = os.path.join(self.repo_root, item)
                if os.path.isfile(item_path):
                    # Add exclusion check before processing the file
                    if self.should_exclude_file(item_path):
                        continue
                    item_extension = os.path.splitext(item)[1]
                    if self.included_extensions == 'all' or item_extension in self.included_extensions:
                        with open(item_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        self.write_to_file(content, os.path.relpath(item_path, self.repo_root))
        elif isinstance(self.include_top_level_files, list):
            for file_name in self.include_top_level_files:
                if file_name in self.files_to_exclude:
                    continue
                file_path = os.path.join(self.repo_root, file_name)
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    self.write_to_file(content, file_name)

        # Start traversal from each specified directory in dirs_to_traverse
        for dir in self.dirs_to_traverse:
            self.traverse_directory(dir)

        # Include specific files
        self.include_specific_files(self.repo_root)

        # Compute directory line counts
        self.compute_directory_line_counts()

        # Finally, write the directory tree with line counts
        directory_tree_str, _ = self.get_directory_tree(self.repo_root, current_depth=0, lines_word_used=False)
        header = f"Directory tree, stemming from root \"{self.repo_root}\":\n"
        # Overwrite the file with the directory tree at the top, then append exported files below
        # Actually, the user might prefer directory tree at the top. If so, we can prepend it:
        # Let's prepend it:
        with open(self.output_file, 'r', encoding='utf-8') as original:
            original_content = original.read()
        with open(self.output_file, 'w', encoding='utf-8') as modified:
            modified.write(header)
            modified.write(directory_tree_str)
            if original_content.strip():
                modified.write(self.delimiter + "\n" + original_content)

        # At the end of the script, after all processing
        print(f"Exported to: {self.output_file}")
        print(f"Total number of lines: {self.total_lines}")
        print("Number of exported files by extension:")
        for ext, count in self.exported_files_count.items():
            print(f"{ext}: {count}")

def get_base_path():
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

def load_config(config_filename):
    """
    Load configuration from a JSON file and adjust paths if necessary.
    """
    base_path = get_base_path()
    config_path = os.path.join(base_path, "utils/export_repo/configs", config_filename)
    config_path = PathConverter.to_system_path(config_path)
    
    with open(config_path, 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)
    
    # Normalize all paths in config to system-specific format
    config = PathConverter.normalize_config_paths(config)
    return config

def get_default_config(repo_root):
    """
    Return a default configuration when no config file is provided.
    """
    return {
        'repo_root': repo_root,
        'export_name': f"{os.path.basename(repo_root)}_export.txt",
        'delimiter': '---',
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
    args = sys.argv[1:]
    config_filename = None
    pop_flag = False
    dump_config = False

    for arg in args:
        if arg == '--pop':
            pop_flag = True
        elif arg == '--dump-config':
            dump_config = True
        elif not arg.startswith('--'):
            config_filename = arg

    if not config_filename:
        print("Usage: python script.py [--pop] [--dump-config] <config_filename> or <repo_root>")
        sys.exit(1)

    if os.path.isdir(config_filename):
        # If the argument is a directory, use it as repo_root with default config
        config = get_default_config(config_filename)
    else:
        # If not a directory, treat it as a config file name
        if not config_filename.endswith('.json'):
            config_filename += '.json'
        config = load_config(config_filename)

    # Adjust repo_root based on pop_flag
    if pop_flag:
        base_path = '/home/caleb/Documents/GitHub/'
        config['repo_root'] = config['repo_root'].replace("/home/caleb/repo", base_path)

    # Set dump_config based on command-line flag
    config['dump_config'] = dump_config

    exporter = RepoExporter(config)
    exporter.export_repo()

if __name__ == "__main__":
    main()