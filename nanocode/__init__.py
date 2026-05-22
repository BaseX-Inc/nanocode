#!/usr/bin/env python3
"""nanocode - minimal claude code alternative"""

from .cli import main
from .session import load_session, save_session, delete_session
from .tools import TOOLS, run_tool, make_schema

__all__ = ["main", "load_session", "save_session", "delete_session", "TOOLS", "run_tool", "make_schema"]

if __name__ == "__main__":
    main()