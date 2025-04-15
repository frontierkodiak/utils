# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands
- Run script: `python export_repo_to_txt.py <config_file>.json [--dump-config]`
- Run with direct repo: `python export_repo_to_txt.py <repo_root> [--dump-config]`
- Validate config: Check JSON structure against parameters in readme.md

## Code Style
- Indentation: 4 spaces
- Naming: snake_case for variables/functions, PascalCase for classes, ALL_CAPS for constants
- Imports: Standard library first, third-party second, local modules last
- Type hints: Use in function signatures
- Error handling: Use specific exceptions with descriptive messages
- Documentation: Docstrings for functions/classes, inline comments for complex logic
- Path handling: Use PathConverter methods for cross-platform compatibility

## Architecture
The codebase exports repository content to XML/text files with filtering capabilities.
Key components: RepoExporter (main class), PathConverter (path normalization), config loading helpers.