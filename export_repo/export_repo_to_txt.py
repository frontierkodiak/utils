import platform
import os
import json
import sys
import nbformat
from nbconvert import MarkdownExporter
from nbconvert.preprocessors import ClearOutputPreprocessor
import xml.etree.ElementTree as ET
from xml.dom import minidom # For pretty printing XML

# Base paths for different operating systems
BASE_PATHS = {
    "Darwin": "/Users/carbon/repo",  # macOS
    "Windows": r"C:\Users\front\Documents\GitHub",
    "Linux": "/home/caleb/repo"  # Linux default
}

# Known Unix-style paths to convert
UNIX_PATHS_TO_CONVERT = [
    "/home/caleb/repo",
    "/home/caleb/Documents/GitHub/",
    "/Users/caleb/Documents/GitHub"
]

class PathConverter:
    @staticmethod
    def to_system_path(path: str) -> str:
        """
        Convert the given path to the current system's native format.
        On Windows, forward slashes become backslashes, etc.
        """
        if not isinstance(path, str): # Ensure path is a string
             return path # Or handle error appropriately

        if platform.system() == "Windows":
            # Convert forward slashes to backslashes and handle drive letter
            if path.startswith("/"):
                 # Simple check for Unix-like absolute paths (e.g. /home/user)
                 # More robust checking might be needed for edge cases like /c/Users...
                is_likely_unix_abs = len(path) > 1 and path[1] != ':'
                if is_likely_unix_abs:
                    path = path.lstrip("/")
                    if ":" not in path:  # If no drive letter, assume C:? Might be risky. Let's require absolute paths for external dirs on Windows to have drive letters or be UNC.
                       # For repo_root relative paths, this should be okay.
                       # Let's assume for now it's relative to C if no drive letter found after stripping /
                       # This part is tricky and might need refinement based on common user paths.
                       # A safer bet might be to require explicit drive letters in configs for Windows.
                       # For now, let's stick to the C: assumption if needed.
                       if not os.path.splitdrive(path)[0]:
                           path = "C:\\" + path # This was original logic, keep it
            return path.replace("/", "\\")
        else:
            # Convert backslashes to forward slashes for Unix-like systems
            return path.replace("\\", "/")

    @staticmethod
    def normalize_config_paths(config: dict) -> dict:
        """
        Normalize all relevant paths in the config to the current system's format.
        Also normalizes paths within lists.
        """
        if 'repo_root' in config and config['repo_root']:
            base_path = get_base_path()
            # Try to resolve repo_root relative to base_path if it's not absolute
            # This logic might need refinement based on how repo_root is specified
            potential_repo_root = PathConverter.to_system_path(config['repo_root'])
            if not os.path.isabs(potential_repo_root):
                 # Assuming repo_root might be relative to the script or a known base
                 # Let's stick to the existing logic of resolving against known GitHub paths
                 pass # Keep existing logic below

            if platform.system() == "Windows":
                # Replace known Unix-style base paths with Windows GitHub path
                for unix_path in UNIX_PATHS_TO_CONVERT:
                    if config['repo_root'].startswith(unix_path):
                        relative_path = config['repo_root'][len(unix_path):].lstrip("/")
                        config['repo_root'] = os.path.join(base_path, relative_path)
                        break
            elif platform.system() == "Darwin":
                 # Replace known Linux-style base paths with macOS GitHub path
                 for linux_path in ["/home/caleb/repo"]:
                     if config['repo_root'].startswith(linux_path):
                         relative_path = config['repo_root'][len(linux_path):].lstrip("/")
                         config['repo_root'] = os.path.join(base_path, relative_path)
                         break
            # Add similar logic for Linux if needed (e.g., replacing Windows/Mac paths)

            config['repo_root'] = PathConverter.to_system_path(config['repo_root'])
            config['repo_root'] = os.path.abspath(config['repo_root']) # Ensure repo_root is absolute

        # Convert path lists
        path_keys = ['dirs_to_traverse', 'subdirs_to_exclude', 'files_to_exclude',
                     'files_to_include', 'additional_dirs_to_traverse', 'dirs_for_tree']
        for key in path_keys:
            if key in config and isinstance(config[key], list):
                normalized_paths = []
                for p in config[key]:
                    # Don't normalize absolute paths meant for external inclusion if they look like URLs or special formats
                    if isinstance(p, str) and not p.startswith(('http:', 'https:')):
                         # If it's an absolute path, just normalize its format
                         if os.path.isabs(p):
                              normalized_paths.append(PathConverter.to_system_path(p))
                         # If it's relative, assume it's relative to repo_root (except for additional_dirs?)
                         # Let's assume all list paths are relative to repo_root unless explicitly absolute
                         # For additional_dirs_to_traverse, they MUST be absolute.
                         elif key != 'additional_dirs_to_traverse':
                             # Normalize relative path format, but keep it relative
                             normalized_paths.append(PathConverter.to_system_path(p))
                         else:
                              # This case (relative path in additional_dirs_to_traverse) is an error or needs definition
                              # For now, let's just normalize format, but it likely won't work as expected.
                              # We should enforce absolute paths for additional_dirs_to_traverse later.
                              print(f"Warning: Path '{p}' in 'additional_dirs_to_traverse' is relative. It should be absolute. Normalizing format only.")
                              normalized_paths.append(PathConverter.to_system_path(p))
                    else:
                         normalized_paths.append(p) # Keep non-strings or URLs as is
                config[key] = normalized_paths


        # Ensure additional_dirs_to_traverse contains absolute paths
        if 'additional_dirs_to_traverse' in config:
            abs_additional_dirs = []
            for p in config.get('additional_dirs_to_traverse', []):
                 if isinstance(p, str) and os.path.isabs(p):
                      abs_additional_dirs.append(p)
                 elif isinstance(p, str):
                      print(f"Error: Path '{p}' in 'additional_dirs_to_traverse' is not absolute. Skipping.")
            config['additional_dirs_to_traverse'] = abs_additional_dirs

        return config

class RepoExporter:
    def __init__(self, config: dict, config_filename: str = None):
        """
        Initialize the RepoExporter with the given config dictionary.
        :param config: The loaded or constructed configuration object.
        :param config_filename: Optional name of the config file used, for output labeling.
        """
        config = PathConverter.normalize_config_paths(config) # Apply normalization early

        self.repo_root = config['repo_root']
        self.export_name = config['export_name']
        # self.delimiter = config['delimiter'] # No longer needed for XML
        self.dirs_to_traverse = config.get('dirs_to_traverse', [])
        self.include_top_level_files = config.get('include_top_level_files', 'none') # Default to none if missing
        self.included_extensions = config.get('included_extensions', []) # Default empty list
        self.subdirs_to_exclude = config.get('subdirs_to_exclude', [])
        self.files_to_exclude = config.get('files_to_exclude', [])
        self.depth = config.get('depth', -1)
        self.dump_config = config.get('dump_config', False)
        self.exhaustive_dir_tree = config.get('exhaustive_dir_tree', False)
        self.files_to_include = config.get('files_to_include', [])
        self.additional_dirs_to_traverse = config.get('additional_dirs_to_traverse', []) # New field
        self.always_exclude_patterns = config.get('always_exclude_patterns', ['export.txt'])
        self.dirs_for_tree = config.get('dirs_for_tree', [])

        # Hardcoded blacklists
        self.blacklisted_dirs = ['__pycache__', '.git', '.venv', '.vscode']
        self.blacklisted_files = ['uv.lock', 'LICENSE']

        # Runtime attributes
        self.config_filename = config_filename
        self.output_file = self.get_output_file_path()
        self.files_to_exclude.append(os.path.basename(self.output_file)) # Exclude self

        # --- Content Buffering ---
        # Store tuples: (display_path, absolute_path, content, is_ipynb_converted)
        # display_path is relative for files under repo_root, absolute otherwise
        self.buffered_files = []
        self.exported_files_count = {}
        self.total_lines = 0
        self.line_counts_by_file = {} # Uses display_path as key
        self.line_counts_by_dir = {}  # Uses display_path segments as keys

    def get_output_file_path(self) -> str:
        """
        Return the absolute path for the export file, handling relative/absolute export_name.
        """
        path = PathConverter.to_system_path(self.export_name)
        if os.path.isabs(path):
            return path
        else:
            # Ensure repo_root is valid before joining
            if not self.repo_root or not os.path.isdir(self.repo_root):
                 raise ValueError(f"Repo root '{self.repo_root}' is invalid or not specified.")
            return os.path.abspath(os.path.join(self.repo_root, path))

    def convert_ipynb_to_md(self, notebook_content: str) -> str:
        """
        Convert an IPython notebook JSON string to Markdown, clearing outputs.
        """
        try:
            notebook = nbformat.reads(notebook_content, as_version=4)
            clear_output = ClearOutputPreprocessor()
            processed_notebook, _ = clear_output.preprocess(notebook, {})
            markdown_exporter = MarkdownExporter()
            markdown_content, _ = markdown_exporter.from_notebook_node(processed_notebook)
            return markdown_content
        except Exception as e:
            print(f"Error converting ipynb: {e}")
            return f"<!-- Error converting notebook: {e} -->\n{notebook_content}" # Return original content with error comment

    def buffer_file_content(self, absolute_path: str):
        """
        Reads, processes (ipynb), and stores file content in memory buffer.
        Updates line counts and statistics.
        Determines the display path (relative or absolute).
        """
        if not os.path.isfile(absolute_path):
            print(f"Warning: Skipping non-file path provided to buffer_file_content: {absolute_path}")
            return

        # Determine display path (relative if under repo_root, else absolute)
        display_path = absolute_path
        if absolute_path.startswith(self.repo_root + os.sep):
            display_path = os.path.relpath(absolute_path, self.repo_root)
        display_path = PathConverter.to_system_path(display_path) # Normalize for consistency

        # --- Apply Filters ---
        if self.should_exclude_file(absolute_path, display_path):
             # print(f"Debug: Excluding file based on rules: {display_path}") # Debugging line
             return

        file_extension = os.path.splitext(absolute_path)[1]
        if self.included_extensions != 'all' and file_extension not in self.included_extensions:
             # print(f"Debug: Excluding file based on extension: {display_path}") # Debugging line
             return
        # --- End Filters ---

        try:
            with open(absolute_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            is_ipynb_converted = False
            if file_extension == '.ipynb':
                content = self.convert_ipynb_to_md(content)
                is_ipynb_converted = True

            # Check if already buffered (can happen with files_to_include)
            if any(bf[1] == absolute_path for bf in self.buffered_files):
                 return # Already processed

            # Update stats
            extension = os.path.splitext(absolute_path)[1] or "._no_extension_"
            self.exported_files_count[extension] = self.exported_files_count.get(extension, 0) + 1
            line_count = content.count('\n') + 1
            self.total_lines += line_count
            self.line_counts_by_file[display_path] = line_count

            # Store
            self.buffered_files.append((display_path, absolute_path, content, is_ipynb_converted))
            # print(f"Debug: Buffering file: {display_path}") # Debugging line

        except Exception as e:
            print(f"Error reading file {absolute_path}: {e}")

    def should_exclude_file(self, absolute_path: str, display_path: str) -> bool:
        """
        Check if a file should be excluded based on various rules.
        Uses absolute_path for existence checks, display_path for pattern matching if relative.
        """
        filename = os.path.basename(absolute_path)

        # 1. Hardcoded blacklist (basename)
        if filename in self.blacklisted_files:
            return True

        # 2. Always exclude patterns (basename suffix)
        if any(filename.endswith(pattern) for pattern in self.always_exclude_patterns):
            return True

        # 3. files_to_exclude (relative path suffix match *if* display_path is relative)
        # This rule is tricky for external files. Let's apply it only if the display_path looks relative.
        is_relative = not os.path.isabs(display_path)
        if is_relative and any(display_path.endswith(exclude) for exclude in self.files_to_exclude):
             return True

        # 4. Output file check (basename) - redundant? Added to files_to_exclude in init.
        if filename == os.path.basename(self.output_file):
             return True

        return False

    def should_exclude_dir(self, absolute_dir_path: str) -> bool:
        """
        Check if a directory should be excluded during traversal.
        Relies on paths relative to repo_root for subdirs_to_exclude.
        """
        dir_name = os.path.basename(absolute_dir_path)

        # 1. Hardcoded blacklist (basename)
        if dir_name in self.blacklisted_dirs:
            return True

        # 2. subdirs_to_exclude (relative path prefix match *if* under repo_root)
        # This won't reliably exclude external dirs based on relative patterns.
        if absolute_dir_path.startswith(self.repo_root + os.sep):
            relative_path = os.path.relpath(absolute_dir_path, self.repo_root)
            relative_path = PathConverter.to_system_path(relative_path) # Normalize for comparison
            if any(relative_path.startswith(PathConverter.to_system_path(exclude.rstrip('*' + os.sep)))
                   for exclude in self.subdirs_to_exclude):
                return True

        return False

    def traverse_directory(self, relative_start_dir: str):
        """
        Walk through a directory *relative* to repo_root, buffering eligible files.
        """
        abs_start_dir = os.path.join(self.repo_root, relative_start_dir)
        abs_start_dir = os.path.abspath(abs_start_dir) # Ensure absolute

        if not os.path.isdir(abs_start_dir):
            print(f"Warning: Directory '{relative_start_dir}' ({abs_start_dir}) does not exist relative to repo root. Skipping.")
            return

        print(f"Traversing internal dir: {relative_start_dir}")
        initial_depth = abs_start_dir.count(os.sep)

        for root, dirs, files in os.walk(abs_start_dir, topdown=True):
            # Depth limiting
            current_depth = root.count(os.sep) - initial_depth
            if self.depth != -1 and current_depth >= self.depth:
                dirs[:] = [] # Don't recurse further
                continue # Skip files at this level too if depth limit is strict

            # Directory exclusion
            # Must check based on absolute path for reliability
            dirs[:] = [d for d in dirs if not self.should_exclude_dir(os.path.join(root, d))]

            # Buffer eligible files
            for file in files:
                abs_file_path = os.path.join(root, file)
                self.buffer_file_content(abs_file_path)


    def traverse_external_directory(self, abs_start_dir: str):
        """
        Walk through an *absolute* external directory path, buffering eligible files.
        """
        abs_start_dir = os.path.abspath(PathConverter.to_system_path(abs_start_dir)) # Ensure absolute and normalized

        if not os.path.isdir(abs_start_dir):
            print(f"Warning: External directory '{abs_start_dir}' does not exist or is not a directory. Skipping.")
            return

        print(f"Traversing external dir: {abs_start_dir}")
        initial_depth = abs_start_dir.count(os.sep)

        for root, dirs, files in os.walk(abs_start_dir, topdown=True):
            # Depth limiting
            current_depth = root.count(os.sep) - initial_depth
            if self.depth != -1 and current_depth >= self.depth:
                dirs[:] = []
                continue

            # Directory exclusion (using same logic, limited for external paths)
            dirs[:] = [d for d in dirs if not self.should_exclude_dir(os.path.join(root, d))]

            # Buffer eligible files
            for file in files:
                abs_file_path = os.path.join(root, file)
                self.buffer_file_content(abs_file_path)


    def include_specific_files(self):
        """
        Process the `files_to_include` list, buffering eligible files.
        Supports absolute paths and paths relative to repo_root.
        """
        if not self.files_to_include:
            return

        print("Processing specific files to include...")
        for file_path_config in self.files_to_include:
             # Handle potential normalization issues if path wasn't normalized correctly
             file_path_config = PathConverter.to_system_path(file_path_config)

             if os.path.isabs(file_path_config):
                 # Absolute path directly
                 abs_path = os.path.abspath(file_path_config)
                 if os.path.isfile(abs_path):
                     self.buffer_file_content(abs_path)
                 else:
                     print(f"Warning: Specified absolute file to include not found or not a file: {abs_path}")
             else:
                 # Relative path (assume relative to repo_root)
                 abs_path = os.path.abspath(os.path.join(self.repo_root, file_path_config))
                 if os.path.isfile(abs_path):
                     self.buffer_file_content(abs_path)
                 else:
                     # Maybe it was intended as relative but is outside? The old walk logic was flawed.
                     # Let's just check if it exists relative to repo_root.
                     print(f"Warning: Specified relative file to include not found relative to repo root: {file_path_config} (resolved to {abs_path})")


    def should_include_in_tree(self, abs_dir_path: str) -> bool:
        """
        Determine if a directory should appear in the directory tree output.
        Only considers directories under repo_root for now.
        """
        # Only include dirs under repo_root in the tree for now
        if not abs_dir_path.startswith(self.repo_root + os.sep) and abs_dir_path != self.repo_root:
             return False

        dir_name = os.path.basename(abs_dir_path)

        # Basic exclusions
        if dir_name in self.blacklisted_dirs or dir_name.startswith('.'):
            return False

        # Apply filtering only if not exhaustive
        if not self.exhaustive_dir_tree:
            if self.should_exclude_dir(abs_dir_path):
                return False

            # Check if it's under a traversed path OR is a top-level dir containing included files
            is_under_traversed = False
            if self.dirs_to_traverse:
                 for d in self.dirs_to_traverse:
                      allowed_dir = os.path.abspath(os.path.join(self.repo_root, d))
                      if abs_dir_path == allowed_dir or abs_dir_path.startswith(allowed_dir + os.sep):
                           is_under_traversed = True
                           break
            else:
                 # If dirs_to_traverse is empty, maybe default to including all non-excluded? Or only top-level?
                 # Let's assume if dirs_to_traverse is empty, only top-level things explicitly included count.
                 # This behavior needs refinement. For now, let's require it to be under a traversed path if specified.
                 # If dirs_to_traverse is empty, maybe allow if files were included from it?
                 # Let's default to False if dirs_to_traverse is specified and it's not under one.
                 if self.dirs_to_traverse and not is_under_traversed:
                      # Check if top level files were included from this dir (only applies if abs_dir_path is repo_root)
                      if abs_dir_path == self.repo_root and self.include_top_level_files != 'none':
                           pass # Allow root if top level files are included
                      else:
                           return False


        # Specific tree filtering
        if self.dirs_for_tree:
            relative_path = os.path.relpath(abs_dir_path, self.repo_root)
            relative_path = PathConverter.to_system_path(relative_path)
            if not any(relative_path == d or relative_path.startswith(d + os.sep)
                       for d in self.dirs_for_tree):
                 # Check if it IS one of the dirs_for_tree exactly
                 if relative_path not in self.dirs_for_tree and relative_path != '.': # Allow root if '.' is not excluded
                      return False


        # Final check: Does this directory contain any exported files or subdirs that do?
        rel_dir_path = os.path.relpath(abs_dir_path, self.repo_root)
        rel_dir_path = PathConverter.to_system_path(rel_dir_path)
        if rel_dir_path == '.': rel_dir_path = '' # Root representation

        has_exported_content = False
        for display_path in self.line_counts_by_file.keys():
             if display_path.startswith(rel_dir_path + os.sep) or (rel_dir_path == '' and os.sep not in display_path):
                  has_exported_content = True
                  break
        if not has_exported_content:
             # Check subdirs recursively? This could be slow. Let's rely on line_counts_by_dir.
             if rel_dir_path not in self.line_counts_by_dir or self.line_counts_by_dir[rel_dir_path] == 0:
                  # If the dir itself has no lines counted, check if any *sub*dirs listed have counts
                  # This is getting complex. Let's simplify: A dir appears if it wasn't excluded AND
                  # it contains an exported file OR it's an ancestor of a dir that contains an exported file.
                  # The line count aggregation should capture this.
                  # A dir MUST have a line count > 0 in self.line_counts_by_dir OR contain a file with count > 0
                  # directly within it.
                  direct_file_count = sum(count for path, count in self.line_counts_by_file.items()
                                          if os.path.dirname(path) == rel_dir_path or (rel_dir_path == '' and os.sep not in path))

                  if self.line_counts_by_dir.get(rel_dir_path, 0) == 0 and direct_file_count == 0:
                       return False # No content ultimately included from here

        return True


    def compute_directory_line_counts(self):
        """
        Compute aggregated line counts for directories based on buffered files.
        Uses display_path keys.
        """
        self.line_counts_by_dir = {}
        # print("Computing line counts from buffered files:") # Debug
        # for display_path, _, _, _ in self.buffered_files: # Debug
        #      print(f"- {display_path}: {self.line_counts_by_file.get(display_path, 0)}") # Debug

        for display_path, lines in self.line_counts_by_file.items():
            # Only compute for relative paths within the repo root for the tree
            if os.path.isabs(display_path):
                 continue

            parts = display_path.split(os.sep)
            # Aggregate counts up the directory chain
            for i in range(1, len(parts)):
                dir_path_key = os.sep.join(parts[:i])
                self.line_counts_by_dir[dir_path_key] = self.line_counts_by_dir.get(dir_path_key, 0) + lines

        # print("Computed directory line counts:", self.line_counts_by_dir) # Debug


    def get_line_count_for_path(self, display_path: str) -> int:
        """
        Return the line count for a file (from line_counts_by_file)
        or directory (from line_counts_by_dir) using its display_path.
        """
        # Check if it's likely a directory path based on the structure or presence in line_counts_by_dir
        # This is heuristic. A file could have the same name as a directory key.
        # Let's prioritize file count if it exists, otherwise dir count.
        count = self.line_counts_by_file.get(display_path, 0)
        if count > 0:
            return count
        return self.line_counts_by_dir.get(display_path, 0)


    def get_directory_tree(self, abs_directory: str, prefix: str = '', current_depth: int = 0, lines_word_used: bool = False):
        """
        Generate the ASCII directory tree string, showing only included items.
        Operates on paths relative to repo_root for display.
        """
        # Tree generation limited by self.depth relative to repo_root start
        if self.depth != -1 and current_depth > self.depth:
            return f"{prefix}   (...max depth reached...)\n", lines_word_used

        tree_str = ''
        try:
            items = sorted(os.listdir(abs_directory))
        except FileNotFoundError:
            return "", lines_word_used # Directory doesn't exist

        visible_items = []
        for item in items:
            item_abs_path = os.path.join(abs_directory, item)
            if os.path.isdir(item_abs_path):
                if self.should_include_in_tree(item_abs_path):
                     visible_items.append(item)
            elif os.path.isfile(item_abs_path):
                 # Check if this file was actually buffered (meaning it passed all filters)
                 item_display_path = os.path.relpath(item_abs_path, self.repo_root)
                 item_display_path = PathConverter.to_system_path(item_display_path)
                 if item_display_path in self.line_counts_by_file:
                     visible_items.append(item)

        for i, item in enumerate(visible_items):
            item_abs_path = os.path.join(abs_directory, item)
            item_rel_path = os.path.relpath(item_abs_path, self.repo_root) # Path relative to repo root for display
            item_rel_path = PathConverter.to_system_path(item_rel_path)

            line_count = self.get_line_count_for_path(item_rel_path)

            # Use ASCII connectors
            connector = '|-- ' if i < len(visible_items) - 1 else '\\-- '

            # Add line count info
            line_str = ""
            if line_count > 0:
                 if not lines_word_used:
                     line_str = f" ({line_count} lines)"
                     lines_word_used = True
                 else:
                     line_str = f" ({line_count})"
            elif os.path.isdir(item_abs_path): # Show (0) for dirs known to be empty
                 line_str = " (0)"


            tree_str += f"{prefix}{connector}{item}{line_str}\n"

            if os.path.isdir(item_abs_path):
                sub_prefix = prefix + ("|   " if i < len(visible_items) - 1 else "    ")
                subtree_str, lines_word_used = self.get_directory_tree(item_abs_path, sub_prefix, current_depth + 1, lines_word_used)
                tree_str += subtree_str

        return tree_str, lines_word_used

    def _build_files_xml_recursive(self, parent_element, path_prefix, files_in_dir):
        """Helper to recursively build nested XML for files."""
        # Separate files and directories at the current level
        current_level_files = {}
        subdirs = {}
        prefix_len = len(path_prefix) if path_prefix else -1

        for display_path, abs_path, content, is_ipynb in files_in_dir:
             # Check if file is directly in this directory or in a subdirectory
             if os.sep in display_path[prefix_len+1:]:
                 # Subdirectory file
                 subdir_name = display_path[prefix_len+1:].split(os.sep)[0]
                 subdir_key = os.path.join(path_prefix, subdir_name) if path_prefix else subdir_name
                 if subdir_key not in subdirs:
                     subdirs[subdir_key] = []
                 subdirs[subdir_key].append((display_path, abs_path, content, is_ipynb))
             else:
                 # File in current directory
                 current_level_files[display_path] = (abs_path, content, is_ipynb)

        # Add files at the current level
        for display_path, (abs_path, content, is_ipynb) in sorted(current_level_files.items()):
             file_elem = ET.SubElement(parent_element, "file", path=display_path)
             if is_ipynb:
                 file_elem.set("converted_from_ipynb", "true")
             file_elem.text = content # Consider CDATA if content has XML special chars

        # Recurse into subdirectories
        for subdir_key, files_list in sorted(subdirs.items()):
             subdir_name = os.path.basename(subdir_key)
             # Use 'dir' tag for directories within repo_root, maybe 'external_dir' otherwise?
             # For simplicity, let's just use 'dir' for now.
             dir_elem = ET.SubElement(parent_element, "dir", path=subdir_key)
             self._build_files_xml_recursive(dir_elem, subdir_key, files_list)


    def export_repo(self):
        """
        Main export routine: Gathers files, computes counts, generates XML output.
        """
        print(f"Starting export for repo: {self.repo_root}")

        # 1. Process top-level files if requested
        if self.include_top_level_files != 'none':
            print("Processing top-level files...")
            try:
                 items = os.listdir(self.repo_root)
                 for item in items:
                     abs_item_path = os.path.join(self.repo_root, item)
                     if os.path.isfile(abs_item_path):
                         # Check if specific files listed or 'all'
                         is_included_top_level = (
                             self.include_top_level_files == 'all' or
                             (isinstance(self.include_top_level_files, list) and item in self.include_top_level_files)
                         )
                         if is_included_top_level:
                             self.buffer_file_content(abs_item_path)
            except FileNotFoundError:
                 print(f"Error: Repo root directory not found: {self.repo_root}")
                 return
            except Exception as e:
                 print(f"Error processing top-level files: {e}")


        # 2. Traverse internal directories
        if self.dirs_to_traverse:
            for rel_dir in self.dirs_to_traverse:
                self.traverse_directory(rel_dir)

        # 3. Traverse additional external directories
        if self.additional_dirs_to_traverse:
            for abs_dir in self.additional_dirs_to_traverse:
                self.traverse_external_directory(abs_dir)

        # 4. Include specific files
        self.include_specific_files() # This now uses buffer_file_content

        # --- Post-Gathering Steps ---
        print("File gathering complete. Computing stats and generating output...")

        # 5. Compute directory line counts (based on buffered files)
        self.compute_directory_line_counts()

        # 6. Build the directory tree string (only for repo_root content)
        directory_tree_str, _ = self.get_directory_tree(self.repo_root, current_depth=0, lines_word_used=False)

        # 7. Generate XML Output
        root_xml = ET.Element("codebase_context")

        # Config (Optional)
        if self.dump_config:
            config_tag_label = self.config_filename if self.config_filename else "dynamic-config"
            config_elem = ET.SubElement(root_xml, "config", source=config_tag_label)
            try:
                 # Create a serializable version of the config
                 config_data = {k: v for k, v in self.__dict__.items() if not k.startswith('_') and k not in ['buffered_files']}
                 config_elem.text = json.dumps(config_data, indent=2)
            except Exception as e:
                 config_elem.text = f"Error serializing config: {e}"


        # Directory Tree
        dirtree_elem = ET.SubElement(root_xml, "dirtree", root=self.repo_root)
        dirtree_elem.text = directory_tree_str

        # Files (Nested Structure)
        files_root_elem = ET.SubElement(root_xml, "files")

        # Separate files by origin for potential grouping
        repo_files = []
        external_files = []
        for bf in self.buffered_files:
             display_path, abs_path, _, _ = bf
             if abs_path.startswith(self.repo_root + os.sep) or abs_path == self.repo_root: # Should handle files in root itself
                 repo_files.append(bf)
             else:
                 external_files.append(bf)

        # Add repo files nested under repo_root structure
        self._build_files_xml_recursive(files_root_elem, "", repo_files)

        # Add external files (maybe under a separate tag or just top-level in <files>?)
        if external_files:
             # Option 1: Flat list for external
             # for display_path, abs_path, content, is_ipynb in sorted(external_files):
             #     file_elem = ET.SubElement(files_root_elem, "external_file", path=display_path) # Use display_path (which is absolute here)
             #     if is_ipynb:
             #         file_elem.set("converted_from_ipynb", "true")
             #     file_elem.text = content

             # Option 2: Group by external root (more complex, requires tracking origin root)
             # Let's stick to flat list for external files for simplicity now.
             ext_group = ET.SubElement(files_root_elem, "external_files")
             for display_path, abs_path, content, is_ipynb in sorted(external_files, key=lambda x: x[0]):
                  file_elem = ET.SubElement(ext_group, "file", path=display_path) # display_path is absolute here
                  if is_ipynb:
                       file_elem.set("converted_from_ipynb", "true")
                  file_elem.text = content


        # Pretty print XML
        try:
            rough_string = ET.tostring(root_xml, 'utf-8')
            reparsed = minidom.parseString(rough_string)
            pretty_xml_str = reparsed.toprettyxml(indent="  ", encoding='utf-8')
            xml_content_to_write = pretty_xml_str.decode('utf-8')
        except Exception as e:
             print(f"Warning: Could not pretty-print XML, writing raw. Error: {e}")
             xml_content_to_write = ET.tostring(root_xml, encoding='unicode')


        # Write to file
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(xml_content_to_write)
            print(f"\nExported to: {self.output_file}")
        except Exception as e:
            print(f"\nError writing output file {self.output_file}: {e}")


        # Final Summary
        print(f"Total number of lines exported: {self.total_lines}")
        print("Exported file counts by extension:")
        if self.exported_files_count:
             for ext, count in sorted(self.exported_files_count.items()):
                 print(f"  {ext}: {count}")
        else:
             print("  (No files exported)")


# --- Helper Functions ---

def get_base_path() -> str:
    """Determine the base path for resolving relative repo_root paths."""
    if '--pop' in sys.argv:
        return PathConverter.to_system_path('/home/caleb/Documents/GitHub/')
    elif platform.system() == "Darwin":
        return PathConverter.to_system_path(BASE_PATHS["Darwin"])
    elif platform.system() == "Windows":
        return PathConverter.to_system_path(BASE_PATHS["Windows"])
    else: # Linux default
        return PathConverter.to_system_path(BASE_PATHS["Linux"])

def load_config(config_filename: str) -> dict:
    """Load configuration from a JSON file."""
    # Assume config file is relative to the configs dir under the script's base util dir
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "configs", config_filename)
    config_path = PathConverter.to_system_path(config_path)

    # Fallback: check relative to base_path if not found near script
    if not os.path.exists(config_path):
         base_path = get_base_path()
         # This assumes a structure like base_path/utils/export_repo/configs
         utils_path = os.path.join(base_path, "utils") if base_path.endswith("GitHub") else base_path
         config_path_alt = os.path.join(utils_path, "export_repo", "configs", config_filename)
         config_path_alt = PathConverter.to_system_path(config_path_alt)
         if os.path.exists(config_path_alt):
              config_path = config_path_alt
         else:
              # Last try: relative to current working directory
              config_path_cwd = PathConverter.to_system_path(config_filename)
              if os.path.exists(config_path_cwd):
                    config_path = config_path_cwd
              else:
                   raise FileNotFoundError(f"Config file not found: {config_filename} (checked near script, in base path structure, and CWD)")

    try:
        with open(config_path, 'r', encoding='utf-8') as config_file:
            config = json.load(config_file)
        # Normalize paths within the loaded config *before* returning
        # config = PathConverter.normalize_config_paths(config) # Moved normalization to init
        return config
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {config_path}: {e}")
        raise
    except Exception as e:
        print(f"Error loading config {config_path}: {e}")
        raise

def get_default_config(repo_root_path: str) -> dict:
    """Provide a default config for direct repository path usage."""
    repo_root_path = PathConverter.to_system_path(os.path.abspath(repo_root_path))
    return {
        'repo_root': repo_root_path,
        'export_name': f"{os.path.basename(repo_root_path)}_export.xml", # Default to xml
        'dirs_to_traverse': ['.'], # Traverse all from root by default
        'include_top_level_files': 'none', # Let dirs_to_traverse = ['.'] handle it
        'included_extensions': 'all',
        'subdirs_to_exclude': [], # Start minimal
        'files_to_exclude': [],
        'depth': 10, # Sensible default depth
        'exhaustive_dir_tree': False,
        'files_to_include': [],
        'additional_dirs_to_traverse': [],
        'always_exclude_patterns': ['export.xml', '.DS_Store', '*.pyc', '*.swp', '*.swo'], # Basic defaults
        'dump_config': False
    }

def main():
    args = sys.argv[1:]
    config_arg = None
    pop_flag = '--pop' in args
    dump_config_flag = '--dump-config' in args

    # Find the first non-flag argument
    for arg in args:
        if not arg.startswith('--'):
            config_arg = arg
            break

    if not config_arg:
        print("Usage: python export_repo_to_txt.py [--pop] [--dump-config] <config_filename | repo_root_path>")
        sys.exit(1)

    config = {}
    config_filename_label = None

    # Detect if arg is a directory or a config file name
    potential_path = PathConverter.to_system_path(config_arg)
    if os.path.isdir(potential_path):
        print(f"Argument '{config_arg}' is a directory. Using default config.")
        config = get_default_config(potential_path)
        config_filename_label = f"default_for_{os.path.basename(potential_path)}"
    else:
        # Assume it's a config file name
        config_filename = config_arg
        if not config_filename.lower().endswith('.json'):
            config_filename += '.json'
        try:
            config = load_config(config_filename)
            config_filename_label = config_filename
            print(f"Loaded config file: {config_filename}")
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error loading or parsing config: {e}")
            sys.exit(1)

    # --pop flag is now handled internally by get_base_path, but we might need
    # to re-normalize if the repo_root was changed by it AFTER initial load/normalize.
    # Let's ensure repo_root is absolute and correct *before* RepoExporter init.
    # Normalization now happens inside RepoExporter.__init__

    # Set dump_config based on flag, potentially overriding config file value
    if dump_config_flag:
        config['dump_config'] = True

    try:
        exporter = RepoExporter(config, config_filename=config_filename_label)
        exporter.export_repo()
    except ValueError as e:
         print(f"Configuration Error: {e}")
         sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()