#!/usr/bin/env python3
"""Configuration and constants for nanocode."""

import os

API_KEY = os.environ.get("NANOCODE_API_KEY") or os.environ.get("AEGIS_API_KEY", "")
API_BASE = os.environ.get("NANOCODE_API_BASE", "https://stanlinktechhub--aegis-inference-fastapi-app.modal.run")
API_URL = f"{API_BASE}/v1/chat/completions"
MODEL = os.environ.get("NANOCODE_MODEL", "auto")

# Auto-routing models
MODELS = {
    "fast": "qwen3-30b-moe",
    "quality": "qwen3-32b",
}

# Session config
SESSION_DIR = os.path.expanduser("~/.nanocode/sessions")

# ANSI colors
RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
BLUE, CYAN, GREEN, YELLOW, RED = (
    "\033[34m",
    "\033[36m",
    "\033[32m",
    "\033[33m",
    "\033[31m",
)
