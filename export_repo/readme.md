### Brief Documentation for `export_repo_to_txt.py`

```bash
export_repo hFormer-serve.json
```

**Quick Start:**
- **Purpose**: Export repository content to a text file, including directory structures and file contents.
- **Usage**: `python export_repo_to_txt.py <config_file>.json`

**Configuration Parameters:**
- `repo_root`: Path to the repository's root directory.
- `export_name`: Export file name or path. If a path, exports there; if a name, exports to `repo_root`.
- `delimiter`: Separator string for entries in the export file.
- `dirs_to_traverse`: Directories within `repo_root` for full traversal and export.
- `include_top_level_files`: Specifies top-level files for inclusion in export. Set to `"all"` for all files, or list specific files. Does not affect dir tree.
- `included_extensions`: File extensions to include. Applies to files in `dirs_to_traverse` and top-level files if `"all"` is selected.
- `depth`: Specifies the depth of directory traversal relative to each directory in `dirs_to_traverse`. `-1` for full traversal, `0` for the directory itself, and any positive integer for that many levels deep.
- `subdirs_to_exclude`: List of subdirectory names to exclude from traversal. Directories with these names will not be traversed.
- `files_to_exclude`: List of file names to exclude from the export. Files with these names will not be included in the export file.
- `exhaustive_dir_tree`: If set to `true`, the exported directory tree will include all top-level files and recurse through all subdirectories, regardless of `dirs_to_traverse` and `subdirs_to_exclude`. If `false` (default), the directory tree will only include the top-level files and the directories specified in `dirs_to_traverse`.

**Example Config:**
```json
{
  "repo_root": "/path/to/repo",
  "export_name": "exported_repo_summary.txt",
  "delimiter": "----",
  "dirs_to_traverse": ["src", "docs"],
  "include_top_level_files": "all",
  "included_extensions": [".py", ".md"]
}
```

### Example Configuration Files

**nextjs.json:**
```json
{
  "repo_root": "/home/caleb/repo/polli-labs-mantine/",
  "export_name": "polli_labs_nextjs_repo_export.txt",
  "delimiter": "----",
  "dirs_to_traverse": ["components", "content", "pages", "public", "theme", "types"],
  "include_top_level_files": ["package.json", "tsconfig.json"],
  "included_extensions": [".ts", ".js", ".tsx", ".jsx", ".json"]
}
```

**metaformer.json:**
```json
{
  "repo_root": "/home/caleb/repo/Polli-Brain/metaformer",
  "export_name": "metaformer_repo_export.txt",
  "delimiter": "----",
  "dirs_to_traverse": ["data", "models"],
  "include_top_level_files": "all",
  "included_extensions": [".py", ".yaml", ".md"]
}
```