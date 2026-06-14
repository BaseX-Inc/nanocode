#!/usr/bin/env python3
"""Tool implementations for nanocode."""

import glob as globlib
import os
import subprocess
import re
import json
from .config import DIM, RESET


def read(args):
    """Read file with line numbers."""
    path = args["path"]
    if os.path.isdir(path):
        # If it's a directory, list contents instead
        entries = os.listdir(path)
        return "\n".join(f"{'d ' if os.path.isdir(os.path.join(path, e)) else '  '}{e}" for e in sorted(entries))
    lines = open(path).readlines()
    offset = args.get("offset", 0)
    limit = args.get("limit", len(lines))
    selected = lines[offset : offset + limit]
    return "".join(f"{offset + idx + 1:4}| {line}" for idx, line in enumerate(selected))


def write(args):
    """Write content to file."""
    os.makedirs(os.path.dirname(args["path"]) or ".", exist_ok=True)
    with open(args["path"], "w") as f:
        f.write(args["content"])
    return "ok"


def edit(args):
    """Replace old with new in file."""
    text = open(args["path"]).read()
    old, new = args["old"], args["new"]
    if old not in text:
        return "error: old_string not found"
    count = text.count(old)
    if not args.get("all") and count > 1:
        return f"error: old_string appears {count} times, must be unique (use all=true)"
    replacement = (
        text.replace(old, new) if args.get("all") else text.replace(old, new, 1)
    )
    with open(args["path"], "w") as f:
        f.write(replacement)
    return "ok"


def glob_find(args):
    """Find files by pattern recursively."""
    base = args.get("path", ".")
    pat = args.get("pat", "**/*")
    pattern = os.path.join(base, pat)
    files = globlib.glob(pattern, recursive=True)
    # Filter out dirs, sort by mtime
    files = [f for f in files if os.path.isfile(f)]
    files = sorted(files, key=lambda f: os.path.getmtime(f), reverse=True)
    return "\n".join(files[:50]) or "none"


def ls(args):
    """List directory contents with file sizes."""
    path = args.get("path", ".")
    try:
        entries = os.listdir(path)
    except Exception as e:
        return f"error: {e}"
    result = []
    for e in sorted(entries):
        full = os.path.join(path, e)
        if os.path.isdir(full):
            result.append(f"  {e}/")
        else:
            size = os.path.getsize(full)
            result.append(f"  {e} ({size}b)")
    return "\n".join(result) or "(empty)"


def grep(args):
    """Search files for regex pattern."""
    pattern = re.compile(args["pat"])
    base = args.get("path", ".")
    hits = []
    for filepath in globlib.glob(base + "/**", recursive=True):
        if not os.path.isfile(filepath):
            continue
        try:
            for line_num, line in enumerate(open(filepath), 1):
                if pattern.search(line):
                    hits.append(f"{filepath}:{line_num}:{line.rstrip()}")
        except Exception:
            pass
    return "\n".join(hits[:50]) or "none"


def bash(args):
    """Run shell command."""
    proc = subprocess.Popen(
        args["cmd"], shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True
    )
    output_lines = []
    try:
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                print(f"  {DIM}│ {line.rstrip()}{RESET}", flush=True)
                output_lines.append(line)
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        output_lines.append("\n(timed out after 30s)")
    return "".join(output_lines).strip() or "(empty)"


TOOLS = {
    "read": (
        "Read a file (with line numbers) or list directory contents",
        {"path": "string", "offset": "number?", "limit": "number?"},
        read,
    ),
    "write": (
        "Write content to file (creates dirs if needed)",
        {"path": "string", "content": "string"},
        write,
    ),
    "edit": (
        "Replace old with new in file (old must be unique unless all=true)",
        {"path": "string", "old": "string", "new": "string", "all": "boolean?"},
        edit,
    ),
    "ls": (
        "List directory contents with sizes",
        {"path": "string?"},
        ls,
    ),
    "glob": (
        "Find files recursively by pattern (default **/*)",
        {"pat": "string?", "path": "string?"},
        glob_find,
    ),
    "grep": (
        "Search files for regex pattern",
        {"pat": "string", "path": "string?"},
        grep,
    ),
    "bash": (
        "Run shell command",
        {"cmd": "string"},
        bash,
    ),
}


def run_tool(name, args):
    """Execute a tool by name."""
    try:
        return TOOLS[name][2](args)
    except Exception as err:
        return f"error: {err}"


def make_schema():
    """Generate OpenAI-compatible tool schema."""
    result = []
    for name, (description, params, _fn) in TOOLS.items():
        properties = {}
        required = []
        for param_name, param_type in params.items():
            is_optional = param_type.endswith("?")
            base_type = param_type.rstrip("?")
            properties[param_name] = {
                "type": "integer" if base_type == "number" else base_type
            }
            if not is_optional:
                required.append(param_name)
        result.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
        )
    return result
