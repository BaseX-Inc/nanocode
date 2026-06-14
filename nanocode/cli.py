#!/usr/bin/env python3
"""Main CLI for nanocode."""

import json
import os
import sys
import time
import re
import threading
import urllib.request
from .config import (
    API_URL, API_KEY, MODEL, MODELS,
    RESET, BOLD, DIM, BLUE, CYAN, GREEN, YELLOW, RED
)
from .tools import make_schema, run_tool, TOOLS
from .session import load_session, save_session, delete_session


def separator():
    try:
        return f"{DIM}{'─' * min(os.get_terminal_size().columns, 80)}{RESET}"
    except OSError:
        return f"{DIM}{'─' * 80}{RESET}"


def pick_model(messages):
    if MODEL != "auto":
        return MODEL
    total_chars = sum(len(m.get("content", "")) for m in messages)
    tool_count = sum(1 for m in messages if m.get("role") == "tool")
    if total_chars > 4000 or tool_count > 3:
        return MODELS["quality"]
    return MODELS["fast"]


class ThinkingSpinner:
    def __init__(self):
        self._active = False
        self._thread = None
        self._elapsed = 0

    def start(self):
        self._active = True
        self._elapsed = 0
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def _spin(self):
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        i = 0
        t0 = time.time()
        while self._active:
            self._elapsed = time.time() - t0
            sys.stdout.write(f"\r{DIM}{frames[i % len(frames)]} thinking ({self._elapsed:.0f}s){RESET}   ")
            sys.stdout.flush()
            time.sleep(0.08)
            i += 1

    def stop(self):
        self._active = False
        if self._thread:
            self._thread.join(timeout=0.2)
        sys.stdout.write(f"\r{DIM}● thought for {self._elapsed:.1f}s{RESET}        \n")
        sys.stdout.flush()


def stream_request(messages, system_prompt):
    """Stream from API, return full raw content."""
    model = pick_model(messages)
    # Build messages for API — flatten tool results into assistant context
    api_messages = [{"role": "system", "content": system_prompt}]
    for m in messages:
        if m.get("role") == "tool":
            # Pack tool results as assistant context
            api_messages.append({"role": "assistant", "content": f"[tool result]: {m['content']}"})
        elif m.get("role") == "assistant":
            # Strip tool_calls metadata, just keep content
            api_messages.append({"role": "assistant", "content": m.get("content", "")})
        else:
            api_messages.append({"role": m["role"], "content": m.get("content", "")})

    body = json.dumps({
        "model": model,
        "max_tokens": 8192,
        "stream": True,
        "messages": api_messages,
        "tools": make_schema(),
        "tool_choice": "auto",
    }).encode()

    req = urllib.request.Request(
        API_URL, data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
            "User-Agent": "nanocode/0.2",
        },
    )
    resp = urllib.request.urlopen(req)

    # Collect full response, then process
    full = ""
    for raw_line in resp:
        line = raw_line.decode("utf-8").strip()
        if not line.startswith("data: "):
            continue
        data = line[6:]
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        text = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
        full += text

    return full


def display_response(full_content):
    """Display response with think animation and streamed content."""
    # Split into think and visible parts
    think_match = re.search(r"<think>(.*?)</think>", full_content, re.DOTALL)

    if think_match:
        # Show thinking animation
        think_text = think_match.group(1)
        # Simulate thinking time based on content length
        spinner = ThinkingSpinner()
        spinner.start()
        # Wait proportional to think content (simulate)
        duration = min(len(think_text) * 0.005, 3.0)
        time.sleep(max(duration, 0.5))
        spinner.stop()

    # Get visible content (after </think>, without tool_call tags)
    visible = re.sub(r"<think>.*?</think>", "", full_content, flags=re.DOTALL)
    visible = re.sub(r"<tool_call>.*?</tool_call>", "", visible, flags=re.DOTALL).strip()

    # Stream visible content char by char
    if visible:
        sys.stdout.write(f"\n{CYAN}⏺{RESET} ")
        for ch in visible:
            sys.stdout.write(ch)
            sys.stdout.flush()
            time.sleep(0.008)
        print()


def extract_tool_calls(content):
    """Extract tool calls from <tool_call> tags."""
    tool_calls = []
    for i, match in enumerate(re.finditer(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", content, re.DOTALL)):
        try:
            tc = json.loads(match.group(1))
            tool_calls.append({
                "id": f"call_{i}",
                "name": tc["name"],
                "args": tc.get("arguments", {}),
            })
        except (json.JSONDecodeError, KeyError):
            pass
    return tool_calls


def main():
    if not API_KEY:
        print(f"{RED}Error: Set NANOCODE_API_KEY or AEGIS_API_KEY{RESET}")
        sys.exit(1)

    messages = load_session() or []
    resumed = " (resumed)" if messages else ""
    model_display = MODEL if MODEL != "auto" else f"auto ({MODELS['fast']}/{MODELS['quality']})"

    print(f"{BOLD}nanocode{RESET} | {DIM}{model_display}{RESET} | {os.getcwd()}{resumed}\n")
    system_prompt = (
        f"/no_think\nConcise coding assistant. cwd: {os.getcwd()}\n"
        "When you need to use a tool, output ONLY a <tool_call> block with JSON.\n"
        "Do NOT explain before calling tools. Just call them."
    )

    while True:
        try:
            print(separator())
            user_input = input(f"{BOLD}{BLUE}❯{RESET} ").strip()
            print(separator())
            if not user_input:
                continue
            if user_input in ("/q", "exit"):
                break
            if user_input == "/c":
                messages = []
                delete_session()
                print(f"{GREEN}⏺ Cleared{RESET}")
                continue
            if user_input == "/m":
                print(f"{DIM}Model: {pick_model(messages)}{RESET}")
                continue

            messages.append({"role": "user", "content": user_input})

            # Agentic loop
            for _ in range(10):  # max 10 tool iterations
                full_content = stream_request(messages, system_prompt)
                tool_calls = extract_tool_calls(full_content)

                # Display thinking + visible content
                display_response(full_content)

                if not tool_calls:
                    # Clean content for history
                    clean = re.sub(r"<think>.*?</think>", "", full_content, flags=re.DOTALL)
                    clean = re.sub(r"<tool_call>.*?</tool_call>", "", clean, flags=re.DOTALL).strip()
                    messages.append({"role": "assistant", "content": clean})
                    break

                # Execute tools
                messages.append({"role": "assistant", "content": full_content})
                for tc in tool_calls:
                    arg_preview = str(list(tc["args"].values())[0])[:50] if tc["args"] else ""
                    print(f"\n{GREEN}⏺ {tc['name']}{RESET}({DIM}{arg_preview}{RESET})")

                    result = run_tool(tc["name"], tc["args"])
                    lines = result.split("\n")
                    preview = lines[0][:60]
                    if len(lines) > 1:
                        preview += f" ... +{len(lines)-1} lines"
                    print(f"  {DIM}⎿  {preview}{RESET}")

                    messages.append({"role": "tool", "content": result})

            save_session(messages)
            print()

        except (KeyboardInterrupt, EOFError):
            break
        except Exception as err:
            print(f"{RED}⏺ Error: {err}{RESET}")

    save_session(messages)


if __name__ == "__main__":
    main()
