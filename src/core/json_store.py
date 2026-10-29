"""Safe reading and writing of Quartz's JSON files (workspace registry, settings, subcollections)

These files are rewritten wholesale on every save, so two failure modes lose data:
a crash mid-write leaves a truncated file, and loading an unreadable file as
"empty" lets the next save overwrite whatever it held. Writes here are atomic,
and an unreadable file is moved aside instead of being overwritten.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def write_json_atomic(path: Path, data: Any) -> None:
    """Write *data* as JSON so *path* holds either the old or the new contents, never a partial file"""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def read_json(path: Path, expected_type: type = dict) -> tuple[Any | None, Path | None]:
    """Load JSON from *path*.

    Returns ``(data, None)`` on success and ``(None, None)`` if the file doesn't exist.
    If it exists but can't be read, or doesn't hold an *expected_type*, it's renamed to
    ``<name>.corrupt-<timestamp>`` so a later save can't overwrite it, and
    ``(None, backup_path)`` is returned.
    """
    path = Path(path)
    if not path.exists():
        return None, None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, expected_type):
            raise ValueError(f"expected a JSON {expected_type.__name__}, got {type(data).__name__}")
        return data, None
    except (OSError, ValueError) as e:
        backup = path.with_name(f"{path.name}.corrupt-{datetime.now():%Y%m%d-%H%M%S}")
        try:
            os.replace(path, backup)
        except OSError:
            logger.exception("Could not read %s and could not move it aside", path)
            raise
        logger.error("Could not read %s (%s); moved it to %s", path, e, backup)
        return None, backup
