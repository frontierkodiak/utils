# Export Repository to Text File

## Overview

This tool exports repository content to a text file, including directory structures and file contents. It provides flexible configuration options to control what is included in the export.

## Usage

```bash
python export_repo_to_txt.py <config_file>.json [--dump-config]
```

or

```bash
python export_repo_to_txt.py <repo_root> [--dump-config]
```

## Configuration Parameters

- `repo_root`: Path to the repository's root directory.
- `export_name`: Name or path for the export file. If a path, exports there; if a name, exports to `repo_root`.
- `delimiter`: Separator string for entries in the export file.
- `dirs_to_traverse`: List of directories within `repo_root` for full traversal and export.
- `dirs_for_tree`: List of specific directories to include in the directory tree output. If empty, includes all non-hidden directories.
- `files_to_include`: List of specific files to include in the export, regardless of their location in the repository.
- `include_top_level_files`: Specifies top-level files for inclusion. Set to `"all"` for all files, or list specific files.
- `included_extensions`: File extensions to include. Use `"all"` for all extensions.
- `subdirs_to_exclude`: List of subdirectory names or paths to exclude from traversal.
- `files_to_exclude`: List of file names to exclude from the export.
- `always_exclude_patterns`: List of filename patterns to always exclude (e.g., ["export.txt"]).
- `depth`: Depth of directory traversal. `-1` for full traversal (default).
- `exhaustive_dir_tree`: If `true`, exports full directory tree regardless of other settings.
- `dump_config`: If `true`, dumps the export configuration JSON at the top of the output file.

## Example Configuration

```json
{
  "repo_root": "/home/user/myrepo",
  "export_name": "repo_export.txt",
  "delimiter": "----",
  "dirs_to_traverse": ["src", "docs"],
  "files_to_include": ["README.md", "config.json"],
  "include_top_level_files": "all",
  "included_extensions": [".py", ".md", ".json"],
  "subdirs_to_exclude": ["tests", "build"],
  "files_to_exclude": ["secrets.yaml"],
  "always_exclude_patterns": ["export.txt", "*.log"],
  "depth": -1,
  "exhaustive_dir_tree": false,
  "dump_config": false
}
```

## Notes

- The tool will automatically exclude the output file from the export.
- If no config file is provided, default settings will be used.
- The `subdirs_to_exclude` option supports partial paths (e.g., "foo/bar" will exclude all "bar" directories under any "foo" directory).
- Use `always_exclude_patterns` for files you want to exclude regardless of their location or other inclusion rules.
- To include the export configuration in the output file, use the `--dump-config` flag when running the script.
- Hidden directories (starting with '.') are automatically excluded from the directory tree.
- Use `dirs_for_tree` to explicitly specify which directories should appear in the directory tree output. If not specified, all non-hidden directories will be included.


## Example Configurations

### NextJS Project

```json
{
  "repo_root": "/home/user/nextjs-project",
  "export_name": "nextjs_project_export.txt",
  "delimiter": "----",
  "dirs_to_traverse": ["components", "pages", "styles", "public"],
  "dirs_for_tree": ["components", "pages", "styles"],  // Only show main app directories
  "include_top_level_files": ["package.json", "next.config.js"],
  "included_extensions": [".js", ".jsx", ".ts", ".tsx", ".css"]
}
```

### Python Project

```json
{
  "repo_root": "/home/user/python-project",
  "export_name": "python_project_export.txt",
  "delimiter": "----",
  "dirs_to_traverse": ["src", "tests", "docs"],
  "dirs_for_tree": ["src", "docs"],  // Only show source and documentation
  "files_to_include": ["requirements.txt", "setup.py"],
  "include_top_level_files": "all",
  "included_extensions": [".py", ".md", ".yml"],
  "subdirs_to_exclude": ["__pycache__", ".venv"]
}
```

## Setting up the `export_repo` alias

### On macOS

1. Open your terminal.

2. Open your shell configuration file (for zsh, it's usually `~/.zshrc`):
   ```bash
   nano ~/.zshrc
   ```

3. Add the following line at the end of the file:
   ```bash
   alias export_repo='/Users/carbon/repo/utils/.venv/bin/python /Users/carbon/repo/utils/export_repo/export_repo_to_txt.py'
   ```

4. Save the file and exit the editor (in nano, press Ctrl+X, then Y, then Enter).

5. Reload your shell configuration:
   ```bash
   source ~/.zshrc
   ```

### On PopOS (Linux)

1. Open your terminal.

2. Open your shell configuration file (for bash, it's usually `~/.bashrc`):
   ```bash
   nano ~/.bashrc
   ```

3. Add the following line at the end of the file:
   ```bash
   alias export_repo='/home/caleb/Documents/GitHub/utils/.venv/bin/python /home/caleb/Documents/GitHub/utils/export_repo/export_repo_to_txt.py --pop'
   ```

4. Save the file and exit the editor (in nano, press Ctrl+X, then Y, then Enter).

5. Reload your shell configuration:
   ```bash
   source ~/.bashrc
   ```

### On Windows (PowerShell)

1. Open PowerShell.

2. First, check if you already have a PowerShell profile:
   ```powershell
   Test-Path $PROFILE
   ```

3. If it returns False, create one:
   ```powershell
   New-Item -Path $PROFILE -Type File -Force
   ```

4. Open your PowerShell profile in a text editor:
   ```powershell
   notepad $PROFILE
   ```

5. Add this function to your profile:
   ```powershell
   function export_repo {
       & "C:\Users\front\Documents\GitHub\utils\.venv\Scripts\python.exe" "C:\Users\front\Documents\GitHub\utils\export_repo\export_repo_to_txt.py" $args
   }
   ```

6. Save the file and reload your profile:
   ```powershell
   . $PROFILE
   ```

Now you can use the `export_repo` command from anywhere in your terminal on macOS, PopOS, or Windows PowerShell. For example:

```bash
export_repo hFormer-codeOnly
# or 
export_repo /path/to/your/repo --dump-config
```

Notes: 
- On PopOS, the `--pop` flag is automatically included in the alias to ensure the correct base path is used
- On Windows, make sure you're using PowerShell and not Command Prompt (cmd.exe) as this alias will only work in PowerShell