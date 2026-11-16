"""Where the app keeps its data when CAREER_BUDDY_DATA is not set: the user's data folder for this OS."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def default_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "career-buddy"
