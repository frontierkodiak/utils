# --- START OF FILE export_repo_to_txt.py ---
import json
import math
import os
import platform
import sys
import xml.sax.saxutils as saxutils  # For escaping attribute values safely

import nbformat
from nbconvert import MarkdownExporter
from nbconvert.preprocessors import ClearOutputPreprocessor

# Attempt to import rich, provide guidance if missing
try:
    from rich.console import Console
    from rich.table import Table

    console = Console()
except ImportError:
    print("Rich library not found. Tables will use basic formatting.")
    print("Please install it: pip install rich")
    console = None

# Attempt to import tiktoken, provide guidance if missing
try:
    import tiktoken
except ImportError:
    print("Tiktoken library not found. Token counts will not be generated.")
    print("Please install it: pip install tiktoken")
    tiktoken = None

# Base paths for different operating systems
BASE_PATHS = {
    "Darwin": "/Users/carbon/repo",  # macOS
    "Windows": r"C:\Users\front\Documents\GitHub",
    "Linux": "/home/caleb/repo",  # Linux default
}

# Known Unix-style paths to convert
UNIX_PATHS_TO_CONVERT = [
    "/home/caleb/repo",
    "/home/caleb/Documents/GitHub/",
    "/Users/caleb/Documents/GitHub",
]


def convert_absolute_path(path: str) -> str:
    """
    Convert an absolute path from one system's format to another.
    Handles known path patterns and converts them appropriately.
    """
    if not isinstance(path, str) or not os.path.isabs(path):
        return path

    # Get the appropriate base path for the current system
    target_base = get_base_path()

    # Try to convert from known Unix paths
    for unix_path in UNIX_PATHS_TO_CONVERT:
        if path.startswith(unix_path):
            relative_path = path[len(unix_path) :].lstrip("/")
            return os.path.join(target_base, relative_path)

    # If path starts with C:\Users\front\Documents\GitHub and we are on macOS/Linux, convert it
    windows_base = r"C:\Users\front\Documents\GitHub"
    if path.startswith(windows_base) and platform.system() != "Windows":
        relative_path = path[len(windows_base) :].lstrip("\\")
        return os.path.join(target_base, relative_path.replace("\\", "/"))

    # If path starts with /Users/carbon/repo and we are on Windows/Linux, convert it
    macos_base = "/Users/carbon/repo"
    if path.startswith(macos_base) and platform.system() != "Darwin":
        relative_path = path[len(macos_base) :].lstrip("/")
        return os.path.join(target_base, relative_path)

    # If path starts with /home/caleb/repo and we are on Windows/macOS, convert it
    linux_base = "/home/caleb/repo"
    if path.startswith(linux_base) and platform.system() not in [
        "Linux",
        "Pop!_OS",
    ]:  # Assuming Pop!_OS reports as Linux
        relative_path = path[len(linux_base) :].lstrip("/")
        return os.path.join(target_base, relative_path)

    # If no specific conversion matched, assume it's already in a usable format or doesn't need conversion
    return path


class PathConverter:
    @staticmethod
    def to_system_path(path: str) -> str:
        """
        Convert the given path to the current system's native format.
        On Windows, forward slashes become backslashes, etc.
        Uses os.path.normpath for robustness.
        """
        if not isinstance(path, str):
            return path

        # Normalize separators first
        if platform.system() == "Windows":
            # Prioritize converting known Unix roots if they somehow slipped through
            if path.startswith("/"):
                is_likely_unix_abs = len(path) > 1 and path[1] != ":"
                if is_likely_unix_abs:
                    # Attempt conversion based on known patterns first might be needed here too
                    # For simplicity, assuming initial conversion handled most cases.
                    # Just normalize for now.
                    pass  # The normpath should handle this if it's like /c/Users/...

            normalized_path = path.replace("/", "\\")
        else:
            normalized_path = path.replace("\\", "/")

        # Use os.path.normpath to clean up separators, handle ., .. etc.
        # This can change the path semantics slightly if not careful (e.g., removing trailing slash)
        # but generally makes paths more canonical.
        try:
            # normpath can fail on invalid Windows paths like 'C:file.txt'
            final_path = os.path.normpath(normalized_path)
        except ValueError:
            # Handle cases where normpath might fail on Windows
            print(
                f"Warning: os.path.normpath failed for path: {normalized_path}. Using original."
            )
            final_path = normalized_path

        return final_path

    @staticmethod
    def normalize_config_paths(config: dict) -> dict:
        """
        Normalize all relevant paths in the config to the current system's format.
        Also normalizes paths within lists. Ensures repo_root is absolute.
        """
        if "repo_root" in config and config["repo_root"]:
            # 1. Convert known absolute paths from other systems
            config["repo_root"] = convert_absolute_path(config["repo_root"])
            # 2. Convert slashes/backslashes to native format and normalize
            config["repo_root"] = PathConverter.to_system_path(config["repo_root"])
            # 3. Ensure it's absolute
            config["repo_root"] = os.path.abspath(config["repo_root"])

        path_keys = [
            "dirs_to_traverse",
            "subdirs_to_exclude",
            "files_to_exclude",
            "files_to_include",
            "additional_dirs_to_traverse",
            "dirs_for_tree",
        ]
        for key in path_keys:
            if key in config and isinstance(config[key], list):
                normalized_paths = []
                for p in config[key]:
                    if isinstance(p, str) and not p.startswith(("http:", "https:")):
                        path_to_normalize = p
                        # Convert absolute paths first if possible
                        if os.path.isabs(p):
                            path_to_normalize = convert_absolute_path(p)
                        # Normalize format (slashes) and structure
                        normalized_paths.append(
                            PathConverter.to_system_path(path_to_normalize)
                        )
                    else:
                        normalized_paths.append(p)  # Keep non-strings or URLs as is
                config[key] = normalized_paths

        # Handle output_dir similarly
        if "output_dir" in config and config["output_dir"]:
            config["output_dir"] = convert_absolute_path(config["output_dir"])
            config["output_dir"] = PathConverter.to_system_path(config["output_dir"])
            # Ensure output_dir is absolute *after* potential joining later
            # We don't make it absolute here because it might be relative to repo_root

        # Ensure additional_dirs_to_traverse contains absolute paths
        if "additional_dirs_to_traverse" in config:
            abs_additional_dirs = []
            for p in config.get("additional_dirs_to_traverse", []):
                if isinstance(p, str):
                    path_to_process = p
                    if not os.path.isabs(path_to_process):
                        # Resolve relative to Current Working Directory (CWD)
                        print(
                            f"Warning: Path '{p}' in 'additional_dirs_to_traverse' is relative. Resolving relative to CWD: {os.getcwd()}"
                        )
                        path_to_process = os.path.abspath(p)

                    # Existing normalization steps
                    path_to_process = convert_absolute_path(path_to_process)
                    path_to_process = PathConverter.to_system_path(path_to_process)
                    # Ensure canonical absolute path (e.g., resolves '..')
                    final_abs_path = os.path.abspath(path_to_process)
                    abs_additional_dirs.append(final_abs_path)
            config["additional_dirs_to_traverse"] = abs_additional_dirs

        return config


class RepoExporter:
    def __init__(self, config: dict, config_filename: str | None = None):
        """
        Initialize the RepoExporter with the given config dictionary.
        :param config: The loaded or constructed configuration object.
        :param config_filename: Optional name of the config file used, for output labeling.
        """
        config = PathConverter.normalize_config_paths(
            config
        )  # Apply normalization early

        self.repo_root = config["repo_root"]
        self.export_name = config["export_name"]
        self.dirs_to_traverse = config.get("dirs_to_traverse", [])
        self.include_top_level_files = config.get("include_top_level_files", "none")
        self.included_extensions = config.get("included_extensions", [])
        self.subdirs_to_exclude = config.get("subdirs_to_exclude", [])
        self.files_to_exclude = config.get("files_to_exclude", [])
        self.depth = config.get("depth", -1)
        self.dump_config = config.get("dump_config", False)
        self.exhaustive_dir_tree = config.get("exhaustive_dir_tree", False)
        self.files_to_include = config.get("files_to_include", [])
        # Keep a _set_ of the absolute paths after initial normalisation so that we
        # can recognise "forced" inclusions later, even after further processing.
        self._explicit_includes: set[str] = {
            os.path.abspath(PathConverter.to_system_path(p))
            for p in self.files_to_include
        }
        self.additional_dirs_to_traverse = config.get("additional_dirs_to_traverse", [])
        self.always_exclude_patterns = config.get(
            "always_exclude_patterns", ["export.txt"]
        )
        self.dirs_for_tree = config.get("dirs_for_tree", [])

        # New config options for line numbering
        self.line_number_interval = config.get("line_number_interval", 25)  # Default 25
        self.line_number_min_length = config.get("line_number_min_length", 150)
        default_annotate_extensions = list(
            dict.fromkeys(
                [  # Ensure unique extensions
                    ".py",
                    ".js",
                    ".ts",
                    ".tsx",
                    ".java",
                    ".cpp",
                    ".c",
                    ".go",
                    ".rs",
                    ".sh",
                    ".sql",
                ]
            )
        )
        raw_annotate_extensions = config.get(
            "annotate_extensions", default_annotate_extensions
        )
        # Normalize extensions to be lowercase and start with a dot
        self.annotate_extensions = [
            ext.lower() if ext.startswith(".") else f".{ext.lower()}"
            for ext in raw_annotate_extensions
        ]
        self.line_number_prefix = config.get("line_number_prefix", "|LN|")

        # Map of file extensions to their single-line comment tokens
        self.comment_tokens_map = {
            ".py": "#",
            ".sh": "#",
            ".rb": "#",
            ".pl": "#",
            ".yaml": "#",
            ".yml": "#",
            ".dockerfile": "#",
            ".r": "#",
            ".ps1": "#",
            ".js": "//",
            ".ts": "//",
            ".tsx": "//",
            ".java": "//",
            ".c": "//",
            ".cpp": "//",
            ".h": "//",
            ".hpp": "//",
            ".cs": "//",
            ".go": "//",
            ".rs": "//",
            ".kt": "//",
            ".kts": "//",
            ".scala": "//",
            ".swift": "//",
            ".php": "//",
            ".sql": "--",
            ".lua": "--",
            ".hs": "--",
            ".ada": "--",
            # Add more as needed. HTML/XML/CSS use block comments, Markdown <!-- -->.
        }

        # Add data file extensions that should be treated as non-code
        self.data_file_extensions = {
            ".tsv",
            ".csv",
            ".json",
            ".xml",
            ".yaml",
            ".yml",
            ".toml",
        }

        # Hardcoded blacklists
        self.blacklisted_dirs = [
            "__pycache__",
            ".git",
            ".venv",
            ".vscode",
            "node_modules",
            "build",
            "dist",
        ]
        self.blacklisted_files = [
            "uv.lock",
            "LICENSE",
            ".DS_Store",
            "*.pyc",
            "*.swp",
            "*.swo",
        ]  # Added common ignores

        # Runtime attributes
        self.config_filename = config_filename
        self.output_dir = config.get("output_dir", None)
        if self.output_dir:
            # Ensure output_dir is absolute. If it wasn't absolute in config, assume relative to CWD.
            if not os.path.isabs(self.output_dir):
                self.output_dir = os.path.abspath(
                    os.path.join(os.getcwd(), self.output_dir)
                )
            else:
                self.output_dir = os.path.abspath(
                    self.output_dir
                )  # Handles normalization if already absolute

        self.output_file = self.get_output_file_path()

        # Add output file itself to exclusion patterns dynamically
        output_filename = os.path.basename(self.output_file)
        if output_filename not in self.always_exclude_patterns:
            self.always_exclude_patterns.append(output_filename)

        # Tiktoken Initializer
        self.tokenizer = None
        if tiktoken:
            try:
                self.tokenizer = tiktoken.get_encoding("o200k_base")
            except Exception as e:
                print(
                    f"Warning: Failed to initialize tiktoken tokenizer 'o200k_base'. Token counts unavailable. Error: {e}"
                )
                self.tokenizer = None

        # --- Content Buffering & Stats ---
        # Store tuples: (display_path, absolute_path, annotated_content, is_ipynb_converted, line_interval_used)
        self.buffered_files = []
        self.exported_files_count = {}
        self.total_lines = 0
        self.total_tokens = 0
        self.line_counts_by_file = {}  # Uses display_path as key
        self.token_counts_by_file = {}  # Uses display_path as key
        self.line_counts_by_dir = {}  # Uses display_path segments as keys
        self.token_counts_by_dir = {}  # Uses display_path segments as keys
        # NEW: Dictionary to store aggregate stats per extension
        # Structure: { ".py": {"files": 0, "lines": 0, "tokens": 0}, ... }
        self.stats_by_extension = {}

    def get_output_file_path(self) -> str:
        """
        Return the absolute path for the export file, handling relative/absolute export_name
        and optional output_dir.
        """
        # Normalize export_name path separators first
        path = PathConverter.to_system_path(self.export_name)

        if os.path.isabs(path):
            print(
                f"Warning: 'export_name' ({self.export_name}) is absolute. Ignoring 'output_dir' if set."
            )
            output_path = os.path.abspath(
                path
            )  # Ensure it's truly absolute and normalized
        elif self.output_dir:
            if not os.path.exists(self.output_dir):
                print(f"Creating output directory: {self.output_dir}")
                try:
                    os.makedirs(self.output_dir, exist_ok=True)
                except OSError as e:
                    raise ValueError(
                        f"Failed to create output directory '{self.output_dir}': {e}"
                    )
            output_path = os.path.abspath(os.path.join(self.output_dir, path))
        else:
            if not self.repo_root or not os.path.isdir(self.repo_root):
                raise ValueError(
                    f"Repo root '{self.repo_root}' is invalid or not specified, and no 'output_dir' was provided for relative export_name."
                )
            output_path = os.path.abspath(os.path.join(self.repo_root, path))

        # Ensure the directory for the output file exists
        output_file_dir = os.path.dirname(output_path)
        if not os.path.exists(output_file_dir):
            print(f"Creating directory for output file: {output_file_dir}")
            try:
                os.makedirs(output_file_dir, exist_ok=True)
            except OSError as e:
                raise ValueError(
                    f"Failed to create directory for output file '{output_path}': {e}"
                )

        return output_path

    def convert_ipynb_to_md(self, notebook_content: str) -> str:
        """
        Convert an IPython notebook JSON string to Markdown, clearing outputs.
        """
        try:
            notebook = nbformat.reads(notebook_content, as_version=4)
            clear_output = ClearOutputPreprocessor()
            processed_notebook, _ = clear_output.preprocess(notebook, {})
            markdown_exporter = MarkdownExporter()
            markdown_content, _ = markdown_exporter.from_notebook_node(
                processed_notebook
            )
            return markdown_content
        except Exception as e:
            print(f"Error converting ipynb: {e}")
            return f"<!-- Error converting notebook: {e} -->\n{notebook_content}"

    def buffer_file_content(
        self,
        absolute_path: str,
        *,
        force_include: bool = False,
    ):
        """
        Reads, processes (ipynb), calculates stats, and stores file content in memory buffer.
        Updates line/token counts and statistics.
        Determines the display path (relative or absolute).
        """
        if not os.path.isfile(absolute_path):
            print(
                f"Warning: Skipping non-file path provided to buffer_file_content: {absolute_path}"
            )
            return

        # Determine display path (relative if under repo_root, else absolute normalized)
        display_path = absolute_path
        try:
            # Use normpath to handle potential differences in how paths are constructed (e.g. //)
            norm_repo_root = os.path.normpath(self.repo_root)
            norm_abs_path = os.path.normpath(absolute_path)

            # Check prefix using normalized paths
            if norm_abs_path.startswith(norm_repo_root + os.sep):
                display_path = os.path.relpath(norm_abs_path, norm_repo_root)
            # Ensure display_path uses consistent separators
            display_path = PathConverter.to_system_path(display_path)
        except ValueError as e:
            # Handle potential errors if paths are malformed (e.g., on Windows with mixed separators)
            print(
                f"Warning: Could not determine relative path for {absolute_path} against {self.repo_root}. Using absolute path. Error: {e}"
            )
            display_path = PathConverter.to_system_path(absolute_path)

        if self.should_exclude_file(absolute_path, display_path):
            return

        file_extension = os.path.splitext(absolute_path)[
            1
        ].lower()  # Use lower for case-insensitivity
        # Normalize included extensions if it's a list
        normalized_included_extensions = self.included_extensions
        if isinstance(normalized_included_extensions, list):
            normalized_included_extensions = [
                ext.lower() for ext in normalized_included_extensions
            ]

        if (
            not force_include
            and normalized_included_extensions != "all"
            and file_extension not in normalized_included_extensions
        ):
            return

        try:
            with open(absolute_path, "r", encoding="utf-8", errors="ignore") as f:
                content_for_stats = f.read()  # This is the original content for stats

            is_ipynb_converted = False
            if file_extension == ".ipynb":
                content_for_stats = self.convert_ipynb_to_md(content_for_stats)
                is_ipynb_converted = True

            if any(bf[1] == absolute_path for bf in self.buffered_files):
                return  # Already processed

            # --- Calculate stats on original (or .ipynb converted) content BEFORE annotation ---
            line_count = content_for_stats.count("\n") + 1
            token_count = 0
            if self.tokenizer:
                try:
                    token_count = len(self.tokenizer.encode(content_for_stats))
                except Exception as e:
                    print(
                        f"Warning: Tiktoken failed to encode content for {display_path}. Error: {e}"
                    )

            # --- Annotate content for output (stats are already captured from original) ---
            # Use original file_extension for determining annotation rules, even if converted from ipynb
            annotated_content, line_interval_used = (
                self._annotate_content_with_line_numbers(
                    content_for_stats, file_extension
                )
            )

            # Update Overall and Per-Extension Stats (using original counts)
            ext_key = file_extension or "._no_extension_"
            if ext_key not in self.stats_by_extension:
                self.stats_by_extension[ext_key] = {"files": 0, "lines": 0, "tokens": 0}
            self.stats_by_extension[ext_key]["files"] += 1
            self.stats_by_extension[ext_key]["lines"] += line_count
            self.stats_by_extension[ext_key]["tokens"] += token_count

            self.total_lines += line_count
            self.total_tokens += token_count
            self.line_counts_by_file[display_path] = line_count
            self.token_counts_by_file[display_path] = token_count

            # Store file info with *annotated* content for final output generation
            self.buffered_files.append(
                (
                    display_path,
                    absolute_path,
                    annotated_content,
                    is_ipynb_converted,
                    line_interval_used,
                )
            )

        except Exception as e:
            print(f"Error reading or processing file {absolute_path}: {e}")

    def should_exclude_file(self, absolute_path: str, display_path: str) -> bool:
        """Check if a file should be excluded based on various rules."""
        filename = os.path.basename(absolute_path)

        # 1. Hardcoded blacklist (basename)
        if filename in self.blacklisted_files:
            return True

        # 2. Always exclude patterns (basename or suffix matching)
        if any(
            filename == pattern or filename.endswith(pattern.lstrip("*"))
            for pattern in self.always_exclude_patterns
        ):
            return True

        # 3. files_to_exclude (match against display_path)
        # This checks if the display_path *ends with* one of the exclusion paths.
        # Normalize separators for comparison.
        norm_display_path = PathConverter.to_system_path(display_path)
        if any(
            norm_display_path == PathConverter.to_system_path(exclude)
            or norm_display_path.endswith(
                os.sep + PathConverter.to_system_path(exclude)
            )
            for exclude in self.files_to_exclude
        ):
            return True

        return False

    def should_exclude_dir(self, absolute_dir_path: str) -> bool:
        """Check if a directory should be excluded during traversal."""
        dir_name = os.path.basename(absolute_dir_path)

        if dir_name in self.blacklisted_dirs:
            return True

        # subdirs_to_exclude check (relative path prefix match *if* under repo_root)
        try:
            norm_repo_root = os.path.normpath(self.repo_root)
            norm_abs_dir_path = os.path.normpath(absolute_dir_path)

            if norm_abs_dir_path.startswith(norm_repo_root + os.sep):
                relative_path = os.path.relpath(norm_abs_dir_path, norm_repo_root)
                relative_path = PathConverter.to_system_path(
                    relative_path
                )  # Normalize for comparison

                for exclude in self.subdirs_to_exclude:
                    norm_exclude = PathConverter.to_system_path(exclude.rstrip(os.sep))
                    # Check exact match or if it's a parent directory
                    if relative_path == norm_exclude or relative_path.startswith(
                        norm_exclude + os.sep
                    ):
                        return True
        except ValueError as e:
            print(
                f"Warning: Error calculating relative path for exclusion check: {absolute_dir_path} vs {self.repo_root}. Error: {e}"
            )
            # Decide behavior: exclude or include? Let's be conservative and not exclude if unsure.
            return False

        return False

    def traverse_directory(self, relative_start_dir: str):
        """Walk through a directory *relative* to repo_root, buffering eligible files."""
        # Ensure relative_start_dir uses native separators for join
        relative_start_dir_norm = PathConverter.to_system_path(relative_start_dir)
        abs_start_dir = os.path.abspath(
            os.path.join(self.repo_root, relative_start_dir_norm)
        )

        if not os.path.isdir(abs_start_dir):
            print(
                f"Warning: Directory '{relative_start_dir}' ({abs_start_dir}) does not exist relative to repo root. Skipping."
            )
            return

        print(f"Traversing internal dir: {relative_start_dir}")
        initial_depth = abs_start_dir.count(os.sep)

        for root, dirs, files in os.walk(abs_start_dir, topdown=True):
            current_abs_depth = root.count(os.sep)
            relative_depth = current_abs_depth - initial_depth

            # Depth limiting (relative to start of traversal)
            if self.depth != -1 and relative_depth >= self.depth:
                dirs[:] = []  # Don't recurse further in this branch
                continue  # Skip files at this depth too

            # Directory exclusion
            original_dirs = list(dirs)  # Copy before modifying dirs[:]
            dirs[:] = [
                d
                for d in original_dirs
                if not self.should_exclude_dir(os.path.join(root, d))
            ]

            # Buffer eligible files
            for file in files:
                abs_file_path = os.path.join(root, file)
                self.buffer_file_content(abs_file_path)

    def traverse_external_directory(self, abs_start_dir: str):
        """Walk through an *absolute* external directory path, buffering eligible files."""
        abs_start_dir = os.path.abspath(PathConverter.to_system_path(abs_start_dir))

        if not os.path.isdir(abs_start_dir):
            print(
                f"Warning: External directory '{abs_start_dir}' does not exist or is not a directory. Skipping."
            )
            return

        print(f"Traversing external dir: {abs_start_dir}")
        initial_depth = abs_start_dir.count(os.sep)

        for root, dirs, files in os.walk(abs_start_dir, topdown=True):
            current_abs_depth = root.count(os.sep)
            relative_depth = current_abs_depth - initial_depth

            # Depth limiting
            if self.depth != -1 and relative_depth >= self.depth:
                dirs[:] = []
                continue

            # Directory exclusion (using same logic, checks basename and relative-to-repo if applicable)
            original_dirs = list(dirs)
            dirs[:] = [
                d
                for d in original_dirs
                if not self.should_exclude_dir(os.path.join(root, d))
            ]

            # Buffer eligible files
            for file in files:
                abs_file_path = os.path.join(root, file)
                self.buffer_file_content(
                    abs_file_path
                )  # This handles display path correctly

    def include_specific_files(self):
        """Process the `files_to_include` list, buffering eligible files."""
        if not self.files_to_include:
            return

        print("Processing specific files to include...")
        for file_path_config in self.files_to_include:
            # *Keep* the value that the normaliser stored in self._explicit_includes
            # but run a last‑chance cross‑platform conversion in case the list was
            # re‑loaded from disk without normalisation.
            normalized_file_path = convert_absolute_path(
                PathConverter.to_system_path(file_path_config)
            )

            if os.path.isabs(normalized_file_path):
                abs_path = os.path.abspath(
                    normalized_file_path
                )  # Ensure canonical absolute path
                if os.path.isfile(abs_path):
                    self.buffer_file_content(abs_path, force_include=True)
                else:
                    print(
                        f"Warning: Specified absolute file to include not found or not a file: {abs_path}"
                    )
            else:
                # Assume relative path is relative to repo_root
                abs_path = os.path.abspath(
                    os.path.join(self.repo_root, normalized_file_path)
                )
                if os.path.isfile(abs_path):
                    self.buffer_file_content(abs_path, force_include=True)
                else:
                    print(
                        f"Warning: Specified relative file to include not found relative to repo root: {normalized_file_path} (resolved to {abs_path})"
                    )

    def should_include_in_tree(self, abs_dir_path: str, tree_root_abs_path: str) -> bool:
        """Determine if a directory should appear in the directory tree output."""
        if not abs_dir_path.startswith(tree_root_abs_path):
            return False  # Only show dirs within the current tree_root_abs_path

        dir_name = os.path.basename(abs_dir_path)

        if dir_name.startswith(
            "."
        ):  # Exclude hidden dirs unless explicitly included elsewhere?
            # Let's allow hidden dirs if they contain included files or are part of traversal/tree lists
            # Need to refine this check
            pass  # Revisit simple hidden dir exclusion later if needed

        if dir_name in self.blacklisted_dirs:
            return False

        # Apply subdirs_to_exclude filter unless exhaustive
        if not self.exhaustive_dir_tree:
            if self.should_exclude_dir(abs_dir_path):
                return False

        # Check against dirs_for_tree if specified
        if self.dirs_for_tree:
            try:
                relative_path = os.path.relpath(abs_dir_path, tree_root_abs_path)
                relative_path_norm = PathConverter.to_system_path(relative_path)

                # Check if this dir is exactly listed OR is a child of a listed dir
                is_explicitly_or_implicitly_in_tree = False
                for tree_dir in self.dirs_for_tree:
                    norm_tree_dir = PathConverter.to_system_path(tree_dir)
                    if (
                        relative_path_norm == norm_tree_dir
                        or relative_path_norm.startswith(norm_tree_dir + os.sep)
                    ):
                        is_explicitly_or_implicitly_in_tree = True
                        break
                if (
                    not is_explicitly_or_implicitly_in_tree and relative_path != "."
                ):  # Allow root implicitly
                    return False
            except ValueError:
                return False  # Cannot determine relative path

        # Final check: Does this directory contain any exported files OR non-empty subdirs?
        try:
            rel_dir_path = os.path.relpath(abs_dir_path, tree_root_abs_path)
            rel_dir_path_norm = PathConverter.to_system_path(rel_dir_path)
            if rel_dir_path_norm == ".":
                rel_dir_path_norm = "" # Root representation

            # Check files directly within this directory
            has_direct_exported_files = False
            norm_abs_dir_path = os.path.normpath(abs_dir_path)
            for disp_path_key, abs_path_for_key, _, _, _ in self.buffered_files: # Assuming buffered_files has (display_path, abs_path, ...)
                if os.path.isfile(abs_path_for_key) and os.path.normpath(os.path.dirname(abs_path_for_key)) == norm_abs_dir_path:
                    # Check if this file (by its display_path_key) has line counts
                    if disp_path_key in self.line_counts_by_file:
                         has_direct_exported_files = True
                         break
            if has_direct_exported_files:
                return True

            # Check aggregated stats for the directory (includes content from subdirs)
            _, token_count = self.get_stats_for_path(
                rel_dir_path_norm, tree_root_abs_path
            )
            if token_count > 0:  # Check token count as primary indicator of content
                return True

            # If no direct files and no aggregated content, exclude
            return False

        except ValueError:
            return False  # Error getting relative path

    def compute_directory_stats(self):
        """
        Compute aggregated line and token counts for directories based on buffered files.
        Uses display_path keys.
        """
        self.line_counts_by_dir = {}
        self.token_counts_by_dir = {}

        # Iterate through files with counts
        for display_path, lines in self.line_counts_by_file.items():
            tokens = self.token_counts_by_file.get(display_path, 0)

            # Only aggregate for relative paths within the repo root
            if os.path.isabs(display_path):
                continue

            parts = display_path.split(os.sep)
            # Aggregate counts up the directory chain (to parent dirs)
            for i in range(1, len(parts)):  # Stop before the filename itself
                dir_path_key = os.sep.join(parts[:i])
                self.line_counts_by_dir[dir_path_key] = (
                    self.line_counts_by_dir.get(dir_path_key, 0) + lines
                )
                self.token_counts_by_dir[dir_path_key] = (
                    self.token_counts_by_dir.get(dir_path_key, 0) + tokens
                )

        # Add root counts (sum of all relative files) - handles files directly in root
        root_lines = sum(
            l for dp, l in self.line_counts_by_file.items() if not os.path.isabs(dp)
        )
        root_tokens = sum(
            t for dp, t in self.token_counts_by_file.items() if not os.path.isabs(dp)
        )
        self.line_counts_by_dir[""] = (
            root_lines  # Use empty string for root aggregate? Or '.'? Let's use ''
        )
        self.token_counts_by_dir[""] = root_tokens

    def get_aggregated_stats_for_abs_dir(self, abs_dir_path: str) -> tuple[int, int]:
        # Placeholder implementation:
        # This method will sum up lines/tokens for all files within this external directory.
        total_lines = 0
        total_tokens = 0

        norm_abs_external_dir_path = os.path.normpath(abs_dir_path)

        # Iterate through the files we've actually processed and stored stats for
        for display_path_key, line_count in self.line_counts_by_file.items():
            token_count = self.token_counts_by_file.get(display_path_key, 0)

            file_abs_path = None
            # Find the absolute path corresponding to this display_path_key
            # This is crucial because display_path_key might be relative for repo files
            # but absolute for external files. We need the original absolute path.
            for dp_bf, abs_p_bf, _, _, _ in self.buffered_files:
                if dp_bf == display_path_key: # display_path_key is unique
                    file_abs_path = abs_p_bf
                    break

            if file_abs_path: # Ensure we found a corresponding absolute path
                norm_file_abs_path = os.path.normpath(file_abs_path)
                # Check if this file's absolute path is within the given external directory
                # and that it is indeed a file (though buffer_file_content should ensure this)
                if norm_file_abs_path.startswith(norm_abs_external_dir_path + os.sep) and os.path.isfile(norm_file_abs_path):
                    total_lines += line_count
                    total_tokens += token_count
            # If file_abs_path is None, it means the display_path_key from line_counts_by_file
            # didn't match any display_path in buffered_files. This shouldn't happen
            # if line_counts_by_file is populated correctly from buffered_files.

        return total_lines, total_tokens

    def get_stats_for_path(self, display_path_from_tree: str, tree_root_abs_path: str) -> tuple[int, int]:
        item_abs_path = os.path.normpath(os.path.join(tree_root_abs_path, display_path_from_tree))

        # Check if it's a file we have stats for
        for bf_display_path, bf_abs_path, _, _, _ in self.buffered_files:
            if os.path.normpath(bf_abs_path) == item_abs_path:
                return (
                    self.line_counts_by_file.get(bf_display_path, 0),
                    self.token_counts_by_file.get(bf_display_path, 0),
                )

        # If it's not a file found in buffered_files, assume it's a directory or a file not included
        # If it's a directory, we need to aggregate its stats.
        # We rely on should_include_in_tree to have filtered out irrelevant items.
        # If os.path.isdir(item_abs_path) is true, then it's a directory we want stats for.
        if os.path.isdir(item_abs_path):
            return self.get_aggregated_stats_for_abs_dir(item_abs_path)

        # Otherwise, it's something not exported or an empty dir not caught by isdir above
        return 0, 0

    def _format_count(self, count: int) -> str:
        """Formats counts >= 1000 with 'k' suffix, rounded to one decimal."""
        if count >= 1000:
            return f"{math.floor(count / 100) / 10:.1f}k"
        else:
            return str(count)

    def _get_comment_token_for_extension(self, ext: str) -> str | None:
        """Returns the single-line comment token for a given file extension (case-insensitive)."""
        return self.comment_tokens_map.get(ext.lower())

    def _annotate_content_with_line_numbers(
        self, content: str, file_extension: str
    ) -> tuple[str, int]:
        """
        Annotates content with sparse line numbers if applicable.
        Returns the annotated content and the interval used (0 if not annotated).
        Line/token counts for stats should be calculated on the *original* content.
        """
        ext_lower = file_extension.lower()  # Ensure consistent matching

        # Skip annotation for data files
        if ext_lower in self.data_file_extensions:
            return content, 0

        # Check if annotation is enabled globally and for this specific extension
        if not self.line_number_interval or self.line_number_interval <= 0:
            return content, 0
        if ext_lower not in self.annotate_extensions:
            return content, 0

        comment_token = self._get_comment_token_for_extension(ext_lower)
        if not comment_token:  # No comment style defined for this extension
            return content, 0

        lines = content.splitlines()
        if len(lines) < self.line_number_min_length:
            return content, 0  # File too short to annotate

        interval = self.line_number_interval
        # Construct the core part of the marker, e.g., "#|LN|"
        marker_prefix_core = f"{comment_token}{self.line_number_prefix}"

        annotated_lines = []
        for i, line_content in enumerate(lines):
            current_line_number = i + 1  # Line numbers are 1-indexed
            if current_line_number % interval == 0:
                # Emit marker on its own line before the code line
                annotated_lines.append(f"{marker_prefix_core}{current_line_number}|")
            annotated_lines.append(line_content)

        return "\n".join(annotated_lines), interval

    def get_directory_tree(
        self,
        abs_directory: str,
        tree_root_abs_path: str,
        prefix: str = "",
        current_depth: int = 0,
        stats_units_printed: bool = False,
    ):
        """
        Generate the ASCII directory tree string, showing only included items
        with line and token counts.
        Operates on paths relative to the current tree_root_abs_path for display.
        """
        if self.depth != -1 and current_depth > self.depth:
            # Only add (...) if there might have been more content deeper
            # This is hard to know for sure without listing one level deeper
            # Let's omit the (...) for simplicity unless we actually truncated visible items
            return "", stats_units_printed

        tree_str = ""
        try:
            items = sorted(os.listdir(abs_directory))
        except FileNotFoundError:
            return "", stats_units_printed  # Directory doesn't exist

        visible_items = []
        for item in items:
            item_abs_path = os.path.join(abs_directory, item)
            if os.path.isdir(item_abs_path):
                if self.should_include_in_tree(item_abs_path, tree_root_abs_path): # Pass tree_root_abs_path
                    visible_items.append(item)
            elif os.path.isfile(item_abs_path):
                # Check if this absolute file path exists in our buffered_files (meaning it was processed and included)
                is_file_buffered = any(bf_abs == item_abs_path for _, bf_abs, _, _, _ in self.buffered_files)
                if is_file_buffered:
                    visible_items.append(item)

        for i, item in enumerate(visible_items):
            item_abs_path = os.path.join(abs_directory, item)
            try:
                item_rel_path = os.path.relpath(item_abs_path, tree_root_abs_path) # Relative to current tree root
                item_rel_path_norm = PathConverter.to_system_path(item_rel_path)
            except ValueError:
                # This can happen if item_abs_path is not under tree_root_abs_path,
                # though should_include_in_tree and visible_item logic should prevent this.
                # If it does, it's safer to skip.
                print(f"Warning: Could not form relative path for {item_abs_path} against {tree_root_abs_path}. Skipping in tree.")
                continue

            line_count, token_count = self.get_stats_for_path(item_rel_path_norm, tree_root_abs_path)

            connector = "|-- " if i < len(visible_items) - 1 else "\\-- "

            # Format stats string
            stats_str = ""
            # Check if item has content OR is a directory (even if empty)
            is_dir = os.path.isdir(item_abs_path)
            if line_count > 0 or token_count > 0 or is_dir:
                line_str = self._format_count(line_count)
                token_str = self._format_count(token_count)
                if not stats_units_printed and (line_count > 0 or token_count > 0):
                    stats_str = f" ({line_str} lines/{token_str} tokens)"
                    stats_units_printed = True  # Set flag after first use
                else:
                    stats_str = f" ({line_str}/{token_str})"

            tree_str += f"{prefix}{connector}{item}{stats_str}\n"

            if is_dir:
                sub_prefix = prefix + ("|   " if i < len(visible_items) - 1 else "    ")
                # Recurse, passing the current state of stats_units_printed
                subtree_str, stats_units_printed = self.get_directory_tree(
                    item_abs_path, tree_root_abs_path, sub_prefix, current_depth + 1, stats_units_printed
                )
                tree_str += subtree_str

        # If depth limit was hit AND we omitted visible items, add indicator
        # This check is tricky. Let's skip the indicator for now.

        return tree_str, stats_units_printed

    def _build_files_string_recursive(
        self, path_prefix: str, files_in_dir: list, indent_level: int
    ) -> str:
        """
        Helper to recursively build the <files> section string with nested <dir> and <file> tags.
        Embeds raw file content.
        """
        indent = "  " * indent_level
        parts = []

        # Separate files and sub-directories at the current level
        current_level_files = {}  # display_path -> (abs_path, content, is_ipynb, line_interval_used)
        subdirs = {}  # subdir_key (relative path) -> list of file tuples

        # --- Normalise the prefix and prepare it for os.path.relpath ---
        # PathConverter ensures consistent separators ("/" vs "\").
        norm_prefix = PathConverter.to_system_path(path_prefix)

        # relpath() requires a non-empty *start* argument; treat root as ".".
        base_for_relpath = norm_prefix if norm_prefix not in {"", "."} else "."

        for file_tuple in files_in_dir:
            display_path, abs_path, content, is_ipynb, line_interval_used = file_tuple
            # Ensure display_path uses system separators for splitting logic
            norm_display_path = PathConverter.to_system_path(display_path)

            # Determine path **relative** to the current recursion prefix.
            # Example:  norm_display_path = "tests/conftest.py"
            #           norm_prefix      = "."   (root call)
            #           → relative_to_prefix = "tests/conftest.py"
            relative_to_prefix = os.path.relpath(
                norm_display_path, start=base_for_relpath
            )

            if os.sep in relative_to_prefix:
                # Subdirectory file
                subdir_name = relative_to_prefix.split(os.sep)[0]
                # Construct key using the *original* (potentially non-normalized) prefix + separator + subdir_name
                # This preserves the intended structure from display_path
                subdir_key = (
                    os.path.join(path_prefix, subdir_name)
                    if path_prefix
                    else subdir_name
                )
                if subdir_key not in subdirs:
                    subdirs[subdir_key] = []
                subdirs[subdir_key].append(file_tuple)
            else:
                # File in current directory
                current_level_files[display_path] = (
                    abs_path,
                    content,
                    is_ipynb,
                    line_interval_used,
                )

        # --------  Emit <file> tags at the current level  --------
        for display_path, file_data_tuple in sorted(current_level_files.items()):
            abs_path, content, is_ipynb, line_interval_used = file_data_tuple
            # Escape path attribute value ONLY
            escaped_path_attr = saxutils.quoteattr(display_path)
            ipynb_attr = ' converted_from_ipynb="true"' if is_ipynb else ""
            line_interval_attr = (
                f' line_interval="{line_interval_used}"'
                if line_interval_used > 0
                else ""
            )
            parts.append(
                f"{indent}<file path={escaped_path_attr}{ipynb_attr}{line_interval_attr}>"
            )
            # --- Embed raw content directly ---
            parts.append(content)
            # ---                            ---
            parts.append(f"{indent}</file>")

        # Recurse into subdirectories
        for subdir_key, files_list in sorted(subdirs.items()):
            # Escape subdir path attribute value ONLY
            escaped_subdir_path_attr = saxutils.quoteattr(subdir_key)
            parts.append(f"{indent}<dir path={escaped_subdir_path_attr}>")
            # Recursively build content for this subdir
            parts.append(
                self._build_files_string_recursive(
                    subdir_key, files_list, indent_level + 1
                )
            )
            parts.append(f"{indent}</dir>")

        return "\n".join(parts)

    def export_repo(self):
        """
        Main export routine: Gathers files, computes stats, generates output string.
        """
        print(f"Starting export for repo: {self.repo_root}")

        # 1. Process top-level files if requested
        if self.include_top_level_files != "none":
            print("Processing top-level files...")
            try:
                items = os.listdir(self.repo_root)
                for item in items:
                    abs_item_path = os.path.join(self.repo_root, item)
                    if os.path.isfile(abs_item_path):
                        is_included_top_level = (
                            self.include_top_level_files == "all"
                            or (
                                isinstance(self.include_top_level_files, list)
                                and item in self.include_top_level_files
                            )
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
        self.include_specific_files()

        # --- Post-Gathering Steps ---
        print("File gathering complete. Computing stats and generating output...")

        # 5. Compute aggregated directory stats
        self.compute_directory_stats()

        # --- Build Output String Manually ---
        output_parts = []
        output_parts.append("<codebase_context>")

        # Config (Optional) - Still dump as JSON string inside tag
        if self.dump_config:
            config_tag_label = (
                self.config_filename if self.config_filename else "dynamic-config"
            )
            escaped_label = saxutils.escape(
                config_tag_label
            )  # Escape label just in case
            output_parts.append(f'  <config source="{escaped_label}">')
            try:
                config_data = {
                    k: v
                    for k, v in self.__dict__.items()
                    if not k.startswith("_")
                    and k not in ["buffered_files", "tokenizer"]
                }  # Exclude non-serializable
                # Convert Path objects to strings for JSON serialization
                serializable_config = {}
                for k, v in config_data.items():
                    if isinstance(v, Path):
                        serializable_config[k] = str(v)
                    elif isinstance(v, set): # Convert set to list
                        serializable_config[k] = list(v)
                    else:
                        serializable_config[k] = v
                config_json = json.dumps(serializable_config, indent=2)
                # Escape JSON content for XML text node (optional but safer)
                output_parts.append(saxutils.escape(config_json))
            except Exception as e:
                output_parts.append(f"<!-- Error serializing config: {e} -->")
            output_parts.append("  </config>")

        # Directory Tree for repo_root
        print("Generating directory tree...")
        escaped_repo_root_attr = saxutils.quoteattr(self.repo_root)
        output_parts.append(f"  <dirtree root={escaped_repo_root_attr}>")
        # Call get_directory_tree for the main repo, passing self.repo_root as the tree_root_abs_path
        directory_tree_str, units_already_printed_in_main_tree = self.get_directory_tree(
            self.repo_root,
            prefix="|",
            stats_units_printed=False, # Reset for each new tree
            tree_root_abs_path=self.repo_root # New parameter
        )

        root_lines, root_tokens = self.get_stats_for_path("", self.repo_root)
        root_line_str = self._format_count(root_lines)
        root_token_str = self._format_count(root_tokens)

        root_stats_display_str = ""
        if not units_already_printed_in_main_tree and (root_lines > 0 or root_tokens > 0):
            root_stats_display_str = f" ({root_line_str} lines/{root_token_str} tokens)"
        elif root_lines > 0 or root_tokens > 0:
            root_stats_display_str = f" ({root_line_str}/{root_token_str})"

        output_parts.append(
            f"{os.path.basename(self.repo_root) or self.repo_root}{root_stats_display_str}"
        )
        output_parts.append(
            directory_tree_str.rstrip()
        )
        output_parts.append("  </dirtree>")

        # Directory Trees for additional_dirs_to_traverse
        for external_dir_abs_path in self.additional_dirs_to_traverse:
            if not os.path.isdir(external_dir_abs_path):
                print(f"Warning: External directory {external_dir_abs_path} not found or not a directory. Skipping tree generation.")
                continue

            print(f"Generating directory tree for external dir: {external_dir_abs_path}")
            escaped_external_dir_attr = saxutils.quoteattr(external_dir_abs_path)
            output_parts.append(f"  <dirtree root={escaped_external_dir_attr}>")

            ext_dir_tree_str, units_printed_in_ext_tree = self.get_directory_tree(
                external_dir_abs_path,
                prefix="|",
                stats_units_printed=False,
                tree_root_abs_path=external_dir_abs_path
            )

            ext_root_lines, ext_root_tokens = self.get_aggregated_stats_for_abs_dir(external_dir_abs_path)
            ext_root_line_str = self._format_count(ext_root_lines)
            ext_root_token_str = self._format_count(ext_root_tokens)

            ext_root_stats_display_str = ""
            if not units_printed_in_ext_tree and (ext_root_lines > 0 or ext_root_tokens > 0):
                ext_root_stats_display_str = f" ({ext_root_line_str} lines/{ext_root_token_str} tokens)"
            elif ext_root_lines > 0 or ext_root_tokens > 0:
                ext_root_stats_display_str = f" ({ext_root_line_str}/{ext_root_token_str})"

            output_parts.append(
                f"{os.path.basename(external_dir_abs_path) or external_dir_abs_path}{ext_root_stats_display_str}"
            )
            output_parts.append(ext_dir_tree_str.rstrip())
            output_parts.append("  </dirtree>")

        # Files (Nested Structure)
        print("Generating files section...")
        output_parts.append("  <files>")

        # Separate files by origin
        repo_files = []
        external_files = []
        norm_repo_root = os.path.normpath(self.repo_root)
        for bf in self.buffered_files:
            display_path, abs_path, content, is_ipynb, line_interval_used = bf
            norm_abs_path = os.path.normpath(abs_path)
            # Check if the file's directory is the repo root or a subdirectory of it
            if norm_abs_path.startswith(norm_repo_root):
                repo_files.append(bf)
            else:
                external_files.append(bf)

        # Add repo files nested structure
        output_parts.append(
            self._build_files_string_recursive("", sorted(repo_files), indent_level=2)
        )

        # Add external files (under a separate tag)
        if external_files:
            output_parts.append("    <external_files>")
            # Sort external files by their absolute path for consistent ordering
            sorted_external = sorted(external_files, key=lambda x: x[1])
            for (
                display_path,
                abs_path,
                content,
                is_ipynb,
                line_interval_used,
            ) in sorted_external:
                escaped_path_attr = saxutils.quoteattr(
                    display_path
                )  # display_path is absolute here
                ipynb_attr = ' converted_from_ipynb="true"' if is_ipynb else ""
                line_interval_attr = (
                    f' line_interval="{line_interval_used}"'
                    if line_interval_used > 0
                    else ""
                )
                output_parts.append(
                    f"      <file path={escaped_path_attr}{ipynb_attr}{line_interval_attr}>"
                )
                output_parts.append(content)
                output_parts.append("      </file>")
            output_parts.append("    </external_files>")

        output_parts.append("  </files>")
        output_parts.append("</codebase_context>")

        # --- Write Output ---
        final_output_string = "\n".join(output_parts)
        try:
            with open(self.output_file, "w", encoding="utf-8") as f:
                f.write(final_output_string)
            print(f"\nExported to: {self.output_file}")
        except Exception as e:
            print(f"\nError writing output file {self.output_file}: {e}")

        # --- Final Summary ---
        print(f"\nExported to: {self.output_file}")
        print(f"Total number of lines exported: {self.total_lines}")
        if self.tokenizer:
            print(
                f"Total number of tokens exported (estimated, o200k_base): {self.total_tokens} ({self._format_count(self.total_tokens)})"
            )

        print("\nExported content summary by extension:")
        if self.stats_by_extension:
            if console:  # If Rich is available, use Rich table
                table = Table(show_header=True, header_style="bold")
                table.add_column("Extension", style="cyan")
                table.add_column("Files", justify="right")
                table.add_column("Lines", justify="right")
                table.add_column("Tokens", justify="right")

                sorted_extensions = sorted(self.stats_by_extension.items())
                for ext, stats in sorted_extensions:
                    table.add_row(
                        ext,
                        str(stats["files"]),
                        self._format_count(stats["lines"]),
                        self._format_count(stats["tokens"]),
                    )
                console.print(table)
            else:  # Fall back to basic formatting
                # Determine max width for alignment
                max_ext_len = (
                    max(len(ext) for ext in self.stats_by_extension.keys())
                    if self.stats_by_extension
                    else 0
                )
                max_files_len = (
                    max(len(str(s["files"])) for s in self.stats_by_extension.values())
                    if self.stats_by_extension
                    else 0
                )
                max_lines_len = (
                    max(
                        len(self._format_count(s["lines"]))
                        for s in self.stats_by_extension.values()
                    )
                    if self.stats_by_extension
                    else 0
                )
                max_tokens_len = (
                    max(
                        len(self._format_count(s["tokens"]))
                        for s in self.stats_by_extension.values()
                    )
                    if self.stats_by_extension
                    else 0
                )

                header = f"  {'Extension'.ljust(max_ext_len)}  {'Files'.rjust(max_files_len)}  {'Lines'.rjust(max_lines_len)}  {'Tokens'.rjust(max_tokens_len)}"
                print(header)
                print(
                    f"  {'-' * max_ext_len}  {'-' * max(5, max_files_len)}  {'-' * max(5, max_lines_len)}  {'-' * max(6, max_tokens_len)}"
                )

                sorted_extensions = sorted(self.stats_by_extension.items())
                for ext, stats in sorted_extensions:
                    files_str = str(stats["files"]).rjust(max_files_len)
                    lines_str = self._format_count(stats["lines"]).rjust(max_lines_len)
                    tokens_str = self._format_count(stats["tokens"]).rjust(
                        max_tokens_len
                    )
                    print(
                        f"  {ext.ljust(max_ext_len)}  {files_str}  {lines_str}  {tokens_str}"
                    )
        else:
            print("  (No files exported)")


# --- Helper Functions ---


def get_base_path() -> str:
    """Determine the base path for resolving relative repo_root paths."""
    system = platform.system()
    if "--pop" in sys.argv:
        # Specific Pop!_OS path structure if flag is present
        return PathConverter.to_system_path("/home/caleb/Documents/GitHub/")
    elif system == "Darwin":
        return PathConverter.to_system_path(BASE_PATHS["Darwin"])
    elif system == "Windows":
        return PathConverter.to_system_path(BASE_PATHS["Windows"])
    else:  # Linux default
        return PathConverter.to_system_path(BASE_PATHS["Linux"])


def load_config(config_filename: str) -> dict:
    """Load configuration from a JSON file."""
    # Append .json if not present
    if not config_filename.lower().endswith(".json"):
        config_filename_json = config_filename + ".json"
    else:
        config_filename_json = config_filename

    potential_paths = []

    # 1. Relative to script's dir/configs
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        potential_paths.append(
            os.path.join(script_dir, "configs", config_filename_json)
        )
    except NameError:  # __file__ might not be defined (e.g. interactive)
        script_dir = os.getcwd()
        potential_paths.append(
            os.path.join(script_dir, "configs", config_filename_json)
        )

    # 2. Relative to base_path/utils/export_repo/configs structure
    base_path = get_base_path()
    # Adjust base path if it points directly to the repo folder structure expected
    utils_parent_dir = base_path  # Default assumption
    if base_path.endswith("GitHub") or base_path.endswith("repo"):
        utils_parent_dir = os.path.dirname(
            base_path
        )  # Go up one level if base is GitHub or repo

    potential_paths.append(
        os.path.join(
            utils_parent_dir, "utils", "export_repo", "configs", config_filename_json
        )
    )

    # 3. Relative to current working directory
    potential_paths.append(os.path.join(os.getcwd(), config_filename_json))

    # 4. The original filename (maybe it was absolute or correctly relative already)
    potential_paths.append(config_filename)

    # Try loading from potential paths
    config_to_load = None
    loaded_path = None
    for p in potential_paths:
        p_normalized = PathConverter.to_system_path(p)
        # print(f"Debug: Trying config path: {p_normalized}") # Debugging line
        if os.path.exists(p_normalized):
            config_to_load = p_normalized
            loaded_path = p  # Store the path from which it was loaded
            break

    if not config_to_load:
        checked_paths_str = "\n - ".join(potential_paths)
        raise FileNotFoundError(
            f"Config file '{config_filename}' not found. Checked:\n - {checked_paths_str}"
        )

    try:
        print(f"Loading config from: {config_to_load}")
        with open(config_to_load, "r", encoding="utf-8") as config_file:
            config = json.load(config_file)
        # Store the actual path loaded from, relative to CWD if possible
        try:
            config["_loaded_from_path"] = os.path.relpath(loaded_path)
        except ValueError:
            config["_loaded_from_path"] = (
                loaded_path  # Keep absolute if on different drive
            )
        return config
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {config_to_load}: {e}")
        raise
    except Exception as e:
        print(f"Error loading config {config_to_load}: {e}")
        raise


def get_default_config(repo_root_path: str) -> dict:
    """Provide a default config for direct repository path usage."""
    repo_root_path = PathConverter.to_system_path(os.path.abspath(repo_root_path))
    repo_name = (
        os.path.basename(repo_root_path) or "repo"
    )  # Handle case where path ends in separator
    default_export_name = f"{repo_name}_export.txt"
    return {
        "repo_root": repo_root_path,
        "export_name": default_export_name,
        "dirs_to_traverse": ["."],  # Traverse all from root by default
        "include_top_level_files": "all",  # Include top-level files by default when traversing '.'
        "included_extensions": "all",
        "subdirs_to_exclude": [],  # Start minimal
        "files_to_exclude": [],
        "depth": 10,
        "exhaustive_dir_tree": False,
        "files_to_include": [],
        "additional_dirs_to_traverse": [],
        "always_exclude_patterns": [
            default_export_name,
            ".DS_Store",
            "*.pyc",
            "*.swp",
            "*.swo",
            "node_modules/",
            "build/",
            "dist/",
            ".venv/",
            ".git/",
            "__pycache__/",
            ".pytest_cache/",
            ".mypy_cache/",
            ".coverage",
        ],
        "dump_config": False,
        "dirs_for_tree": [],  # Default to showing all non-excluded dirs in tree
        "output_dir": None,  # Default to outputting in repo_root
        "line_number_interval": 25,  # Default 25
        "line_number_min_length": 150,
        "annotate_extensions": [
            ".py",
            ".js",
            ".ts",
            ".tsx",
            ".java",
            ".cpp",
            ".c",
            ".go",
            ".rs",
            ".sh",
            ".sql",
        ],
        "line_number_prefix": "|LN|",
    }


# Need Path from pathlib for type hinting in RepoExporter if needed
from pathlib import Path


def main():
    args = sys.argv[1:]
    config_arg = None
    pop_flag = "--pop" in args  # Handled in get_base_path
    dump_config_flag = "--dump-config" in args

    # Filter out flags to find the main argument
    non_flag_args = [arg for arg in args if not arg.startswith("--")]

    if len(non_flag_args) != 1:
        print(
            "Usage: python export_repo_to_txt.py [--pop] [--dump-config] <config_filename | repo_root_path>"
        )
        sys.exit(1)

    config_arg = non_flag_args[0]

    config = {}
    config_filename_label = None

    # Detect if arg is a directory or a config file name
    potential_path = PathConverter.to_system_path(config_arg)
    # Check if it's a directory *first*
    if os.path.isdir(potential_path):
        print(f"Argument '{config_arg}' is a directory. Using default config.")
        config = get_default_config(potential_path)
        config_filename_label = f"default_for_{os.path.basename(potential_path)}"
    else:
        # Assume it's a config file name
        try:
            config = load_config(config_arg)
            # Use the original arg as label unless loaded path is very different?
            config_filename_label = config.get("_loaded_from_path", config_arg)
        except FileNotFoundError as e:
            print(f"Error: {e}")
            # Fallback: Maybe it's a directory path that *looks* like a filename? Check again.
            # This case is less likely if isdir failed before, but handles edge cases.
            if os.path.isdir(potential_path):
                print(
                    f"Argument '{config_arg}' resolved to a directory after failed config load. Using default config."
                )
                config = get_default_config(potential_path)
                config_filename_label = (
                    f"default_for_{os.path.basename(potential_path)}"
                )
            else:
                print(
                    f"Argument '{config_arg}' is not a valid directory or loadable config file."
                )
                sys.exit(1)
        except Exception as e:
            print(f"Error loading or parsing config: {e}")
            import traceback

            traceback.print_exc()
            sys.exit(1)

    # Override dump_config from command line flag
    if dump_config_flag:
        config["dump_config"] = True

    try:
        exporter = RepoExporter(config, config_filename=config_filename_label)
        exporter.export_repo()
    except ValueError as e:
        print(f"Configuration or Execution Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
# --- END OF FILE export_repo_to_txt.py ---
