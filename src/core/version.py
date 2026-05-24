"""Application version information"""

from importlib.metadata import PackageNotFoundError, version

try:
    VERSION = version("quartz")
except PackageNotFoundError:
    import tomllib
    from pathlib import Path

    _pyproject = Path(__file__).parent.parent.parent / "pyproject.toml"
    with open(_pyproject, "rb") as _f:
        VERSION = tomllib.load(_f)["project"]["version"]

