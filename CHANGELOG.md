# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-05-16

### Added
- **Symbol-Level Indexing**: Integrated **Tree-sitter** for deep code parsing. Extracted functions, classes, and methods are now indexed as nodes in the project brain.
- **Semantic Search**: Implemented local vector embeddings using `sentence-transformers`. The `query_memory` tool now supports natural language semantic search over the entire memory graph.
- **Framework-Specific Entities**: Auto-detection and indexing of architectural patterns:
  - **Flutter**: Cubits, Blocs, Providers, and Pages.
  - **React**: Components and Hooks.
  - **FastAPI**: API Routes and endpoints.
- **Bug Tracking Layer**: Added dedicated `dimagx bug` commands (`report`, `fix`, `list`) to track project issues and link them to files and commits.
- **Agentic Memory Automation**: MCP server now automatically detects if a prompt relates to a Bug Fix or Feature implementation and logs it accordingly.
- **Hierarchical Graph View**: New `dimagx graph` command provides a structural ASCII visualization of PRDs, Features, Files, and Architecture.
- **Git Branch Integration**: Automatic feature name detection from git branch names when starting a new feature.
- **Interactive CLI Splash**: A modern, futuristic terminal entry screen powered by `rich` and `pyfiglet`.
- **Background File Watcher**: Support for background daemonization with `dimagx watch --background`.

### Changed
- Improved `get_context` MCP tool to provide a more concise and structured overview of project status, active features, and recent agentic history.
- Enhanced `dimagx init` to perform deep symbol and entity scanning during the initial project setup.

---

## [0.1.0] - 2026-05-15

### Added
- Initial project release.
- Core graph memory system using **Kuzu DB**.
- Basic CLI for project initialization (`init`) and status tracking (`status`).
- Feature management (`dimagx feature start/done/list`).
- PRD ingestion and AI-powered summarization using Anthropic Claude.
- File indexing and stack detection.
- Git history scanning and automated post-commit hook.
- MCP (Model Context Protocol) server for coding agent integration.
- Real-time file system watcher.

[0.2.0]: https://github.com/shmehdi01/dimagx/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/shmehdi01/dimagx/releases/tag/v0.1.0
