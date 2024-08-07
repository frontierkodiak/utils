# Export Repository to Text File

## Overview

This tool exports repository content to a text file, including directory structures and file contents. It provides flexible configuration options to control what is included in the export.

## Usage

```bash
python export_repo_to_txt.py <config_file>.json
```

or

```bash
python export_repo_to_txt.py <repo_root>
```

## Configuration Parameters

- `repo_root`: Path to the repository's root directory.
- `export_name`: Name or path for the export file. If a path, exports there; if a name, exports to `repo_root`.
- `delimiter`: Separator string for entries in the export file.
- `dirs_to_traverse`: List of directories within `repo_root` for full traversal and export.
- `files_to_include`: List of specific files to include in the export, regardless of their location in the repository.
- `include_top_level_files`: Specifies top-level files for inclusion. Set to `"all"` for all files, or list specific files.
- `included_extensions`: File extensions to include. Use `"all"` for all extensions.
- `subdirs_to_exclude`: List of subdirectory names or paths to exclude from traversal.
- `files_to_exclude`: List of file names to exclude from the export.
- `always_exclude_patterns`: List of filename patterns to always exclude (e.g., ["export.txt"]).
- `depth`: Depth of directory traversal. `-1` for full traversal (default).
- `exhaustive_dir_tree`: If `true`, exports full directory tree regardless of other settings.

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
  "exhaustive_dir_tree": false
}
```

## Notes

- The tool will automatically exclude the output file from the export.
- If no config file is provided, default settings will be used.
- The `subdirs_to_exclude` option supports partial paths (e.g., "foo/bar" will exclude all "bar" directories under any "foo" directory).
- Use `always_exclude_patterns` for files you want to exclude regardless of their location or other inclusion rules.

## Example Configurations

### NextJS Project

```json
{
  "repo_root": "/home/user/nextjs-project",
  "export_name": "nextjs_project_export.txt",
  "delimiter": "----",
  "dirs_to_traverse": ["components", "pages", "styles", "public"],
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
  "files_to_include": ["requirements.txt", "setup.py"],
  "include_top_level_files": "all",
  "included_extensions": [".py", ".md", ".yml"],
  "subdirs_to_exclude": ["__pycache__", ".venv"]
}
```