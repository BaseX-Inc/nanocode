#!/usr/bin/env python3
"""Configuration and constants for nanocode."""

import os

NVIDIA_KEY = os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVIDIA_API_KEY_FALLBACK")
API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL = os.environ.get("MODEL", "moonshotai/kimi-k2.6")

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