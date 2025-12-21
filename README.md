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
- See `requirements.txt` for full dependency list

## Installation

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
pip install -r requirements.txt
```

3. **Run the application**:

```bash
python main.py
```

### Development Installation

For development with testing and linting tools:

```bash
pip install -r requirements-dev.txt
```

Or using the project in editable mode:

```bash
pip install -e ".[dev]"
```

## Dependencies

### Core Runtime
- **PySide6**: Qt6 bindings for the desktop UI
- **jsonschema**: Schema validation for fields and plugins
- **lark**: Search query parsing (field queries, boolean logic)

### Data Handling
- **pandas**: CSV import/export and bulk data operations
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
├── main.py              # Application entry point
├── src/
│   ├── core/            # Core business logic
│   │   ├── config.py     # Configuration management
│   │   ├── workspace.py # Workspace and collection registry
│   │   └── collection_store.py # Database operations
│   └── ui/               # UI components
│       ├── main_window.py # Main application window
│       ├── table_view.py  # Table/spreadsheet view
│       └── form_view.py   # Form data entry view
└── requirements.txt      # Python dependencies
```

## Usage

1. **Create a Collection**: File → New Collection
2. **Add Fields**: Right-click collection → Properties (or use the form designer)
3. **Enter Data**: Use Form view for focused entry or Table view for bulk editing
4. **Search**: Use the search box in the top-right to filter records
5. **Export**: Use the Export button to save data in various formats

## Development Status

This is an active development project. Current milestone: **Milestone 0 - Skeleton**

## License

[To be determined]
