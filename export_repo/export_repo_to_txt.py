import os
import json
import sys

class RepoExporter:
    def __init__(self, config):
        self.repo_root = config['repo_root']
        self.export_name = config['export_name']
        self.delimiter = config['delimiter']
        self.dirs_to_traverse = config['dirs_to_traverse']
        self.include_top_level_files = config['include_top_level_files']
        self.included_extensions = config['included_extensions']
        self.subdirs_to_exclude = config.get('subdirs_to_exclude', [])
        self.files_to_exclude = config.get('files_to_exclude', [])
        self.depth = config.get('depth', -1)  # Default to -1 for full traversal
        self.exhaustive_dir_tree = config.get('exhaustive_dir_tree', False)
        self.blacklisted_dirs = ['__pycache__']  # Blacklist of subdirs to always omit
        self.files_to_include = config.get('files_to_include', [])  # Additional files to include explicitly
        self.output_file = self.get_output_file_path()
        self.files_to_exclude.append(os.path.basename(self.output_file))  # Add output file to exclude list
        self.exported_files_count = {}
        self.total_lines = 0

    def get_output_file_path(self):
        if os.path.isabs(self.export_name):
            return self.export_name
        else:
            return os.path.join(self.repo_root, self.export_name)

    def write_to_file(self, content, file_path=None, mode='a'):
        with open(self.output_file, mode, encoding='utf-8') as f:
            if file_path:
                extension = os.path.splitext(file_path)[1]
                self.exported_files_count[extension] = self.exported_files_count.get(extension, 0) + 1
                lines = content.count('\n') + 1  # Counting lines in the content
                self.total_lines += lines
                f.write(f"{self.delimiter}\nFull Path: {file_path}\n\n{content}\n\n")
            else:
                f.write(f"{content}\n")

    def traverse_directory(self, directory, current_depth=0):
        if self.depth != -1 and current_depth > self.depth:
            return  # Stop recursion if the current depth exceeds the specified depth

        for root, dirs, files in os.walk(directory, topdown=True):
            # Exclude subdirectories if they are in subdirs_to_exclude
            dirs[:] = [d for d in dirs if d not in self.subdirs_to_exclude]

            for file in files:
                if file in self.files_to_exclude:  # Skip files in files_to_exclude
                    continue
                file_extension = os.path.splitext(file)[1]
                if file_extension in self.included_extensions or self.included_extensions == 'all':
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, self.repo_root)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    self.write_to_file(content, relative_path)

            # Recursively traverse subdirectories, adjusting depth
            for dir in dirs:
                self.traverse_directory(os.path.join(root, dir), current_depth + 1)

            break  # Ensure we don't double-traverse directories

    def include_specific_files(self, root_dir):
        """
        Traverse the entire directory tree from the root to include specific files.
        """
        for root, dirs, files in os.walk(root_dir):
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, root_dir)
                for include_file in self.files_to_include:
                    if relative_path.endswith(include_file):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        self.write_to_file(content, relative_path)

    def get_directory_tree(self, directory, prefix='', current_depth=0):
        """
        Generate a string representation of the directory tree.
        """
        if self.depth != -1 and current_depth > self.depth:
            return f"{prefix}│   └── (omitted)\n"

        tree_str = ''
        items = sorted(os.listdir(directory))
        for i, item in enumerate(items):
            path = os.path.join(directory, item)
            connector = '├── ' if i < len(items) - 1 else '└── '
            if os.path.isdir(path) and item in self.blacklisted_dirs:
                tree_str += f"{prefix}{connector}{item}\n"
                tree_str += f"{prefix}│   └── (omitted)\n"
            else:
                tree_str += f"{prefix}{connector}{item}\n"
                if os.path.isdir(path):
                    extension = '' if i < len(items) - 1 else '    '
                    tree_str += self.get_directory_tree(path, prefix + extension + '│   ', current_depth + 1)
        return tree_str

    def export_repo(self):
        # Clear the output file before starting
        with open(self.output_file, 'w', encoding='utf-8') as f:
            pass

        # Write the export configuration to the output file, starting fresh
        self.write_to_file(f"Export Configuration:\n{json.dumps(vars(self), indent=2)}", mode='w')

        # Generate and write the directory tree structure starting from the repo_root
        tree_structure = f"Directory tree, stemming from root \"{self.repo_root}\":\n"
        tree_structure += self.get_directory_tree(self.repo_root, current_depth=0)
        self.write_to_file(tree_structure)

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
            dir_path = os.path.join(self.repo_root, dir)
            self.traverse_directory(dir_path, current_depth=0)

        # Include specific files by traversing from the root directory
        self.include_specific_files(self.repo_root)

        # At the end of the script, after all processing
        print(f"Exported to: {self.output_file}")
        print(f"Total number of lines: {self.total_lines}")
        print("Number of exported files by extension:")
        for ext, count in self.exported_files_count.items():
            print(f"{ext}: {count}")

def load_config(config_filename):
    """
    Load configuration from a JSON file located in the specified configs directory.
    """
    config_path = os.path.join('/home/caleb/repo/utils/export_repo/configs', config_filename)
    with open(config_path, 'r', encoding='utf-8') as config_file:
        return json.load(config_file)

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
        'files_to_include': []
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: python script.py <config_filename> or <repo_root>")
        sys.exit(1)

    arg = sys.argv[1]
    if arg.endswith('.json'):
        config = load_config(arg)
    else:
        repo_root = arg
        config = get_default_config(repo_root)

    exporter = RepoExporter(config)
    exporter.export_repo()

if __name__ == "__main__":
    main()
