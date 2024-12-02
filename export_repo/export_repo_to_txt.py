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
        self.blacklisted_files = []  # Blacklist of files to always omit
        self.files_to_include = config.get('files_to_include', [])  # Additional files to include explicitly
        self.output_file = self.get_output_file_path()
        self.files_to_exclude.append(os.path.basename(self.output_file))  # Add output file to exclude list
        self.always_exclude_patterns = config.get('always_exclude_patterns', ['export.txt'])
        self.exported_files_count = {}
        self.dirs_for_tree = config.get('dirs_for_tree', [])  # New: specific dirs to include in tree
        self.total_lines = 0
        
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
        return (any(relative_path.endswith(exclude) for exclude in self.files_to_exclude) or
                any(filename.endswith(pattern) for pattern in self.always_exclude_patterns))

    def should_exclude_dir(self, dir_path):
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
        for root, dirs, files in os.walk(root_dir):
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, root_dir)
                if any(relative_path.endswith(include_file) for include_file in self.files_to_include):
                    if not self.should_exclude_file(file_path):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        self.write_to_file(content, relative_path)

    def should_include_in_tree(self, dir_path):
        """Determine if a directory should be included in the tree output."""
        dir_name = os.path.basename(dir_path)
        
        # Check blacklisted dirs first
        if dir_name in self.blacklisted_dirs:
            return False
            
        # Never include hidden directories (starting with .)
        if dir_name.startswith('.'):
            return False
            
        # If specific dirs are specified, only include those
        if self.dirs_for_tree:
            relative_path = os.path.relpath(dir_path, self.repo_root)
            return any(relative_path == d or relative_path.startswith(d + os.sep) 
                    for d in self.dirs_for_tree)
                    
        return True

    def get_directory_tree(self, directory, prefix='', current_depth=0):
        """Generate a string representation of the directory tree."""
        if self.depth != -1 and current_depth > self.depth:
            return f"{prefix}│   └── (omitted)\n"

        tree_str = ''
        items = sorted(os.listdir(directory))
        
        # Filter items based on visibility rules
        visible_items = []
        for item in items:
            path = os.path.join(directory, item)
            # For files, exclude hidden files and those matching exclude patterns
            if os.path.isfile(path):
                if not item.startswith('.') and not self.should_exclude_file(path):
                    visible_items.append(item)
            # For directories, use should_include_in_tree
            elif os.path.isdir(path):
                if self.should_include_in_tree(path):
                    visible_items.append(item)
        
        for i, item in enumerate(visible_items):
            path = os.path.join(directory, item)
            connector = '├── ' if i < len(visible_items) - 1 else '└── '
            
            tree_str += f"{prefix}{connector}{item}\n"
            if os.path.isdir(path):
                extension = '' if i < len(visible_items) - 1 else '    '
                tree_str += self.get_directory_tree(path, prefix + extension + '│   ', current_depth + 1)
                
        return tree_str

    def export_repo(self):
        # Clear the output file before starting
        with open(self.output_file, 'w', encoding='utf-8') as f:
            pass

        # Write the export configuration to the output file if dump_config is True
        if self.dump_config:
            self.write_to_file(f"Export Configuration:\n{json.dumps(vars(self), indent=2)}", mode='w')

        # Generate and write the directory tree structure starting from the repo_root
        tree_structure = f"Directory tree, stemming from root \"{self.repo_root}\":\n"
        tree_structure += self.get_directory_tree(self.repo_root, current_depth=0)
        self.write_to_file(tree_structure, mode='w' if not self.dump_config else 'a')

        # Handle top-level files
        if self.include_top_level_files == 'all':
            for item in os.listdir(self.repo_root):
                if item in self.files_to_exclude:  # Skip files in files_to_exclude
                    continue
                item_path = os.path.join(self.repo_root, item)
                if os.path.isfile(item_path):
                    item_extension = os.path.splitext(item)[1]
                    if self.included_extensions == 'all' or item_extension in self.included_extensions:
                        with open(item_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        self.write_to_file(content, os.path.relpath(item_path, self.repo_root))
        elif isinstance(self.include_top_level_files, list):
            for file_name in self.include_top_level_files:
                if file_name in self.files_to_exclude:  # Skip files in files_to_exclude
                    continue
                file_path = os.path.join(self.repo_root, file_name)
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    self.write_to_file(content, file_name)

        # Start traversal from each specified directory in dirs_to_traverse
        for dir in self.dirs_to_traverse:
            self.traverse_directory(dir)

        # Include specific files by traversing from the root directory
        self.include_specific_files(self.repo_root)

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
        return '/home/caleb/Documents/GitHub/' # our pop-xps popOS system
    elif platform.system() == "Darwin":  # macOS
        return "/Users/caleb/Documents/GitHub"
    else:  # Linux or other (our dev server, or polliserve instances)
        return "/home/caleb/repo"

def load_config(config_filename):
    """
    Load configuration from a JSON file and adjust paths if necessary.
    """
    base_path = get_base_path()
    
    config_path = os.path.join(base_path, "utils/export_repo/configs", config_filename)
    
    with open(config_path, 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)
    
    # Adjust repo_root path if it exists in the config
    if 'repo_root' in config:
        if '--pop' in sys.argv:
            config['repo_root'] = config['repo_root'].replace("/home/caleb/repo", '/home/caleb/Documents/GitHub/')
        elif platform.system() == "Darwin":
            config['repo_root'] = config['repo_root'].replace("/home/caleb/repo", "/Users/caleb/Documents/GitHub")
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