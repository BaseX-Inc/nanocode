#!/usr/bin/env python3
"""Session persistence for nanocode."""

import json
import os
import hashlib
from datetime import datetime
from .config import SESSION_DIR


def get_project_hash():
    """Get a hash of the current working directory."""
    cwd = os.getcwd()
    return hashlib.md5(cwd.encode()).hexdigest()[:12]


def get_session_path():
    """Get the session file path for current project."""
    project_hash = get_project_hash()
    os.makedirs(os.path.join(SESSION_DIR, project_hash), exist_ok=True)
    return os.path.join(SESSION_DIR, project_hash, "session.json")


def load_session():
    """Load session from disk. Returns None if no session exists."""
    path = get_session_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            data = json.load(f)
            return data.get("messages", [])
    except Exception:
        return None


def save_session(messages):
    """Save session to disk."""
    path = get_session_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({
                "messages": messages,
                "savedAt": datetime.now().isoformat(),
                "cwd": os.getcwd()
            }, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save session: {e}")


def delete_session():
    """Delete the current session file."""
    path = get_session_path()
    if os.path.exists(path):
        os.remove(path)