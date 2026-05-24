"""Application version information"""

import sys
from importlib.metadata import PackageNotFoundError, version

try:
    VERSION = version("quartz")
except PackageNotFoundError:
    import tomllib
    from pathlib import Path

    try:
        # PyInstaller stores bundled files under sys._MEIPASS
        _base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    except AttributeError:
        # Normal development / editable-install run
        _base = Path(__file__).parent.parent.parent

    _pyproject = _base / "pyproject.toml"
    with open(_pyproject, "rb") as _f:
        VERSION = tomllib.load(_f)["project"]["version"]

