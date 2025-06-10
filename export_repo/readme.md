# Export Repository to Text File

## Overview

This tool exports repository content to a text file, including directory structures and file contents. It provides flexible configuration options to control what is included in the export, with support for line numbering, token counting, and rich formatting.

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/utils.git
cd utils
```

2. Create and activate a virtual environment using `uv`:
```bash
uv venv
source .venv/bin/activate
```

3. Install the package in editable mode:
```bash
uv pip install -e .
```

4. Add the alias to your shell configuration file:

### On PopOS/Ubuntu (Linux)

1. Open your shell configuration file:
```bash
nano ~/.bashrc
```

2. Add the following line at the end of the file:
```bash
alias export_repo='/home/caleb/repo/utils/.venv/bin/python /home/caleb/repo/utils/export_repo/export_repo_to_txt.py --pop'
```

3. Save the file and reload your shell configuration:
```bash
source ~/.bashrc
```

### On macOS

1. Open your shell configuration file:
```bash
nano ~/.zshrc
```

2. Add the following line at the end of the file:
```bash
alias export_repo="/Users/yourusername/venvs/export_repo/bin/python /Users/yourusername/repo/utils/export_repo/export_repo_to_txt.py"
```

3. Save the file and reload your shell configuration:
```bash
source ~/.zshrc
```

### On Windows (PowerShell)

1. Open PowerShell and check if you have a profile:
```powershell
Test-Path $PROFILE
```

2. If it returns False, create one:
```powershell
New-Item -Path $PROFILE -Type File -Force
```

3. Open your PowerShell profile:
```powershell
notepad $PROFILE
```

4. Add this function:
```powershell
function export_repo {
    & "C:\Users\yourusername\repo\utils\.venv\Scripts\python.exe" "C:\Users\yourusername\repo\utils\export_repo\export_repo_to_txt.py" $args
}
```

5. Save and reload your profile:
```powershell
. $PROFILE
```

## Usage

```bash
export_repo <config_file>.json [--dump-config]
```

or

```bash
export_repo <repo_root> [--dump-config]
```

## Configuration Parameters

- `repo_root`: Path to the repository's root directory.
- `export_name`: Name or path for the export file. If a path, exports there; if a name, exports to `repo_root`.
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
- `output_dir`: Optional directory for output file. If not specified, uses repo_root.
- `additional_dirs_to_traverse`: List of additional directories outside repo_root to include.

### Line Numbering Configuration

- `line_number_interval`: Interval for line number markers (default: 25)
- `line_number_min_length`: Minimum file length (in lines) to add line numbers (default: 150)
- `annotate_extensions`: List of file extensions to annotate with line numbers (default: [".py", ".js", ".ts", ".tsx", ".java", ".cpp", ".c", ".go", ".rs", ".sh", ".sql"])
- `line_number_prefix`: Prefix for line number markers (default: "|LN|")

## Output Format

The tool generates an XML-formatted output file with the following structure:

```xml
<codebase_context>
  <config source="config_filename">...</config>
  <dirtree root="/path/to/repo">
    directory_tree_with_stats
  </dirtree>
  <files>
    <file path="relative/path/to/file.py" line_interval="25">
      #|LN|25|
      actual code line
      #|LN|50|
      another code line
    </file>
    <dir path="subdirectory">
      <file path="nested/file.py">...</file>
    </dir>
    <external_files>
      <file path="/absolute/path/to/file.py">...</file>
    </external_files>
  </files>
</codebase_context>
```

### Features

1. **Directory Tree**
   - Shows hierarchical structure with line/token counts
   - Supports depth limiting
   - Excludes hidden directories by default
   - Configurable via `dirs_for_tree`

2. **File Content**
   - Preserves original file structure
   - Supports nested directories
   - Handles external files separately
   - Converts Jupyter notebooks to markdown

3. **Line Numbering**
   - Sparse line numbers for code files
   - Configurable interval and minimum length
   - Extension-specific annotation
   - Preserves original code formatting

4. **Statistics**
   - Line counts per file and directory
   - Token counts (using tiktoken)
   - Summary by file extension
   - Rich table output if available

5. **Path Handling**
   - Cross-platform path normalization
   - Support for relative and absolute paths
   - Automatic path conversion between systems

## Example Configuration

```json
{
  "repo_root": "/home/user/myrepo",
  "export_name": "repo_export.txt",
  "dirs_to_traverse": ["src", "docs"],
  "files_to_include": ["README.md", "config.json"],
  "include_top_level_files": "all",
  "included_extensions": [".py", ".md", ".json"],
  "subdirs_to_exclude": ["tests", "build"],
  "files_to_exclude": ["secrets.yaml"],
  "always_exclude_patterns": ["export.txt", "*.log"],
  "depth": -1,
  "exhaustive_dir_tree": false,
  "dump_config": false,
  "line_number_interval": 25,
  "line_number_min_length": 150,
  "annotate_extensions": [".py", ".js", ".ts"],
  "line_number_prefix": "|LN|"
}
```

## Example Configurations

### NextJS Project

```json
{
  "repo_root": "/home/user/nextjs-project",
  "export_name": "nextjs_project_export.txt",
  "dirs_to_traverse": ["components", "pages", "styles", "public"],
  "dirs_for_tree": ["components", "pages", "styles"],
  "include_top_level_files": ["package.json", "next.config.js"],
  "included_extensions": [".js", ".jsx", ".ts", ".tsx", ".css"],
  "line_number_interval": 25,
  "line_number_min_length": 150,
  "annotate_extensions": [".js", ".jsx", ".ts", ".tsx"]
}
```

### Python Project

```json
{
  "repo_root": "/home/user/python-project",
  "export_name": "python_project_export.txt",
  "dirs_to_traverse": ["src", "tests", "docs"],
  "dirs_for_tree": ["src", "docs"],
  "files_to_include": ["requirements.txt", "setup.py"],
  "include_top_level_files": "all",
  "included_extensions": [".py", ".md", ".yml"],
  "subdirs_to_exclude": ["__pycache__", ".venv"],
  "line_number_interval": 25,
  "line_number_min_length": 150,
  "annotate_extensions": [".py"]
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
   alias export_repo="/Users/carbon/venvs/export_repo/bin/python /Users/carbon/repo/utils/export_repo/export_repo_to_txt.py"
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
   alias export_repo='/home/caleb/repo/utils/.venv/bin/python /home/caleb/repo/utils/export_repo/export_repo_to_txt.py --pop'
   ```

   ```bash
   alias export_repo="/Users/carbon/venvs/export_repo/bin/python /Users/carbon/repo/utils/export_repo/export_repo_to_txt.py"
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