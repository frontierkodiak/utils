import os
import json
import sys

exported_files_count = {}
total_lines = 0

def load_config(config_filename):
    """
    Load configuration from a JSON file located in the specified configs directory.
    """
    config_path = os.path.join('/home/caleb/repo/utils/export_repo/configs', config_filename)
    with open(config_path, 'r', encoding='utf-8') as config_file:
        return json.load(config_file)

config_filename = sys.argv[1]
config = load_config(config_filename)

repo_root = config['repo_root']
export_name = config['export_name']
delimiter = config['delimiter']
dirs_to_traverse = config['dirs_to_traverse']
include_top_level_files = config['include_top_level_files']
included_extensions = config['included_extensions']
subdirs_to_exclude = config.get('subdirs_to_exclude', [])
files_to_exclude = config.get('files_to_exclude', [])
depth = config.get('depth', -1)  # Default to -1 for full traversal

# Determine export file path
if os.path.isabs(export_name):
    output_file = export_name
else:
    output_file = os.path.join(repo_root, export_name)

def write_to_file(content, file_path=None, mode='a'):
    global total_lines, exported_files_count
    with open(output_file, mode, encoding='utf-8') as f:
        if file_path:
            extension = os.path.splitext(file_path)[1]
            exported_files_count[extension] = exported_files_count.get(extension, 0) + 1
            lines = content.count('\n') + 1  # Counting lines in the content
            total_lines += lines
            f.write(f"{delimiter}\nFull Path: {file_path}\n\n{content}\n\n")
        else:
            f.write(f"{content}\n")

def traverse_directory(directory, current_depth=0):
    """
    Traverse the directory to process files and directories as per the configuration.
    Adjust traversal based on the specified depth and exclude specified directories and files.
    """
    global depth, dirs_to_traverse, subdirs_to_exclude, files_to_exclude, included_extensions, repo_root

    if depth != -1 and current_depth > depth:
        return  # Stop recursion if the current depth exceeds the specified depth

    for root, dirs, files in os.walk(directory, topdown=True):
        # Exclude subdirectories if they are in subdirs_to_exclude
        dirs[:] = [d for d in dirs if d not in subdirs_to_exclude]

        # No need to further filter dirs based on dirs_to_traverse here, as traversal starts explicitly from those dirs

        for file in files:
            if file in files_to_exclude:  # Skip files in files_to_exclude
                continue
            file_extension = os.path.splitext(file)[1]
            if file_extension in included_extensions or included_extensions == 'all':
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, repo_root)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                write_to_file(content, relative_path)

        # Recursively traverse subdirectories, adjusting depth
        for dir in dirs:
            traverse_directory(os.path.join(root, dir), current_depth + 1)

        break  # Ensure we don't double-traverse directories

def get_directory_tree(directory, prefix=''):
    """
    Generate a string representation of the directory tree.
    """
    tree_str = ''
    items = sorted(os.listdir(directory))
    for i, item in enumerate(items):
        path = os.path.join(directory, item)
        connector = '├── ' if i < len(items) - 1 else '└── '
        tree_str += f"{prefix}{connector}{item}\n"
        if os.path.isdir(path):
            extension = '' if i < len(items) - 1 else '    '
            tree_str += get_directory_tree(path, prefix + extension + '│   ')
    return tree_str

# Clear the output file before starting
with open(output_file, 'w', encoding='utf-8') as f:
    pass

# Write the export configuration to the output file, starting fresh
write_to_file(f"Export Configuration for {export_name} with root {repo_root}:", mode='w')

# Generate and write the directory tree structure for dirs_to_traverse at the top
for dir in dirs_to_traverse:
    dir_path = os.path.join(repo_root, dir)
    tree_structure = f"Directory Tree for {dir}:\n"
    tree_structure += get_directory_tree(dir_path)
    write_to_file(tree_structure)  # Default mode='a' appends the content


# Handle top-level files
if include_top_level_files == 'all':
    for item in os.listdir(repo_root):
        if item in files_to_exclude:  # Skip files in files_to_exclude
            continue
        item_path = os.path.join(repo_root, item)
        if os.path.isfile(item_path):
            item_extension = os.path.splitext(item)[1]
            if included_extensions == 'all' or item_extension in included_extensions:
                with open(item_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                write_to_file(content, os.path.relpath(item_path, repo_root))
elif isinstance(include_top_level_files, list):
    for file_name in include_top_level_files:
        if file_name in files_to_exclude:  # Skip files in files_to_exclude
            continue
        file_path = os.path.join(repo_root, file_name)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            write_to_file(content, file_name)

# Start traversal from each specified directory in dirs_to_traverse
for dir in dirs_to_traverse:
    dir_path = os.path.join(repo_root, dir)
    traverse_directory(dir_path, current_depth=0)
    
# At the end of the script, after all processing
print(f"Exported to: {output_file}")
print(f"Total number of lines: {total_lines}")
print("Number of exported files by extension:")
for ext, count in exported_files_count.items():
    print(f"{ext}: {count}") 