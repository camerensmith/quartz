# Quartz - Personal Database Desktop Application

A cross-platform desktop application for managing personal databases, inspired by Symphytum but with modern features and extensibility.

## Features

- **Collections Management**: Create and manage multiple collections, each stored as a separate SQLite database
- **TableView**: Spreadsheet-like interface with inline editing
- **FormView**: Customizable form layout for data entry
- **Form Designer**: Grid-snapped form designer for custom layouts
- **Search**: Fast full-text search using SQLite FTS5
- **Export/Import**: Export to CSV, JSON, or copy the database file
- **Plugin System**: Extensible field types and validators
- **Advanced Mode**: SQL console for power users

## Requirements

- **Python 3.11+** (required for modern typing and performance)
- Dependencies are listed in `pyproject.toml`


## How to Use

Download under "Releases"

Run quartz.exe


<img width="1382" height="878" alt="image" src="https://github.com/user-attachments/assets/d65ed729-7d3d-4888-baaf-a1b59fd42a03" />


## Dev Installation

### Quick Start

1. **Create and activate virtual environment** (recommended):

```powershell
# Windows PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1

# Or Windows CMD
python -m venv venv
venv\Scripts\activate.bat
```

2. **Install dependencies**:

```bash
pip install .
```

3. **Run the application**:

```bash
python main.py
```

### Development Installation

For development with testing and linting tools, install the project in editable mode:

```bash
pip install -e ".[dev]"
```

Run the checks CI runs:

```bash
ruff check src/ main.py tests/
pytest
```

Run with `--debug` (or set `QUARTZ_DEBUG=1`) for debug-level logs in `~/.quartz/logs/quartz.log`.

## Dependencies

### Core Runtime
- **PySide6**: Qt6 bindings for the desktop UI
- **jsonschema**: Schema validation for fields and plugins
- **lark**: Search query parsing (field queries, boolean logic)

### Data Handling
- **openpyxl**: Excel import/export
- **python-dateutil**: Date parsing and normalization
- **Pillow**: Image thumbnails and previews

### Validation & Utilities
- **pydantic**: Strong validation models for field configs
- **typing-extensions**: Forward compatibility for typing features

### Advanced Features
- **sqlparse**: SQL formatting and safety checks (SQL console)
- **tabulate**: Pretty-print SQL results

### Development Tools
- **pytest**: Testing framework
- **ruff**: Fast linting and formatting
- **mypy**: Static type checking
- **PyInstaller**: Packaging for distribution

## Project Structure

```
Quartz/
├── main.py                  # Application entry point
├── pyproject.toml           # Version, dependencies, tool config
├── quartz.spec              # PyInstaller build
├── assets/                  # Toolbar and menu icons
├── src/
│   ├── core/                # Business logic (no UI)
│   │   ├── collection_store.py  # Collection database, fields, search index
│   │   ├── field_keys.py        # Field key sanitization and validation
│   │   ├── workspace.py         # Workspace and collection registry
│   │   ├── query_parser.py      # Search query parsing
│   │   ├── export_service.py    # CSV / JSON / Excel export
│   │   ├── update_checker.py    # GitHub release checks
│   │   └── update_downloader.py # Checksum-verified update downloads
│   └── ui/                  # PySide6 windows and dialogs
│       ├── main_window.py
│       ├── table_view.py
│       └── form_view.py
└── tests/                   # pytest suite
```

## Usage

1. **Create a Collection**: File → New Collection
2. **Add Fields**: Right-click collection → Properties (or use the form designer)
3. **Enter Data**: Use Form view for focused entry or Table view for bulk editing
4. **Search**: Use the search box in the top-right to filter records
5. **Export**: Use the Export button to save data in various formats

## Development Status

This is an active development project; see [Releases](https://github.com/camerensmith/quartz/releases) for the latest version.

## License

MIT, see [LICENSE](LICENSE).
