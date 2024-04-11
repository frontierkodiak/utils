import os

root_dir = '/home/caleb/repo/polli-labs-mantine/'
output_file = os.path.join(root_dir, 'exported_files_summary.txt')
delimiter = '----'

# Specify the top-level directories and files to include
included_dirs = ['components', 'content', 'pages', 'public', 'theme', 'types']
included_files = ['package.json', 'tsconfig.json']
included_extensions = ['.ts', '.js', '.tsx', '.jsx', '.json']

def write_to_file(content, file_path=None):
    with open(output_file, 'a', encoding='utf-8') as f:
        if file_path:
            f.write(f"{delimiter}\nFull Path: {file_path}\n\n{content}\n\n")
        else:
            f.write(f"{content}\n")

def get_directory_tree(directory, prefix=''):
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

def traverse_directory(directory, is_root_level=True):
    for root, dirs, files in os.walk(directory, topdown=True):
        # Skip non-included top-level directories only at the root level
        if is_root_level:
            dirs[:] = [d for d in dirs if d in included_dirs or os.path.join(root, d).replace('\\','/').startswith(tuple(os.path.join(root_dir, d).replace('\\','/') for d in included_dirs))]

        for file in files:
            if os.path.splitext(file)[1] in included_extensions:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, root_dir)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                write_to_file(content, relative_path)

        # Only the initial call is at the root level
        is_root_level = False


# Ensure the output file is empty before starting
with open(output_file, 'w', encoding='utf-8') as f:
    pass

# Print the tree structure for included directories
for dir in included_dirs:
    dir_path = os.path.join(root_dir, dir)
    tree_structure = f"Directory Tree for {dir}:\n"
    tree_structure += get_directory_tree(dir_path)
    write_to_file(tree_structure)

# Traverse each specified top-level directory
for dir in included_dirs:
    traverse_directory(os.path.join(root_dir, dir), is_root_level=True)

# Directly add specified top-level files if they exist
for file_name in included_files:
    file_path = os.path.join(root_dir, file_name)
    if os.path.exists(file_path):
        # Treat top-level files as root level but ensure their inclusion by handling them as special cases
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        write_to_file(content, file_name)
