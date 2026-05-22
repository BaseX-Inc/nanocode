#!/usr/bin/env python3
"""Entry point for nanocode."""
import sys
import os

# Add parent directory to path for nanocode package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nanocode.cli import main

if __name__ == "__main__":
    main()