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
    """Animated spinner shown during <think> blocks."""
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
            sys.stdout.write(f"\r{DIM}{frames[i % len(frames)]} thinking ({self._elapsed:.0f}s){RESET}  ")
            sys.stdout.flush()
            time.sleep(0.08)
            i += 1

    def stop(self):
        self._active = False
        if self._thread:
            self._thread.join(timeout=0.2)
        sys.stdout.write(f"\r{DIM}● thought for {self._elapsed:.1f}s{RESET}      \n")
        sys.stdout.flush()


def call_api_stream(messages, system_prompt):
    """Call API with streaming. Handles think blocks and content."""
    model = pick_model(messages)
    body = json.dumps({
        "model": model,
        "max_tokens": 8192,
        "stream": True,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
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

    full_content = ""
    in_think = False
    spinner = ThinkingSpinner()
    content_started = False

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

        delta = chunk.get("choices", [{}])[0].get("delta", {})
        text = delta.get("content", "")
        if not text:
            continue

        full_content += text

        # Handle <think> blocks
        if "<think>" in text:
            in_think = True
            spinner.start()
            continue
        if "</think>" in text:
            in_think = False
            spinner.stop()
            continue
        if in_think:
            continue

        # Stream visible content
        if not content_started:
            sys.stdout.write(f"\n{CYAN}⏺{RESET} ")
            content_started = True
        sys.stdout.write(text)
        sys.stdout.flush()

    if content_started:
        print()

    # Extract tool calls from content (model uses <tool_call> tags)
    tool_calls = []
    tc_matches = re.findall(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", full_content, re.DOTALL)
    for i, tc_json in enumerate(tc_matches):
        try:
            tc = json.loads(tc_json)
            tool_calls.append({
                "id": f"call_{i}",
                "type": "function",
                "function": {"name": tc["name"], "arguments": json.dumps(tc.get("arguments", {}))},
            })
        except (json.JSONDecodeError, KeyError):
            pass

    # Strip thinking and tool_call tags from content for history
    clean = re.sub(r"<think>.*?</think>", "", full_content, flags=re.DOTALL)
    clean = re.sub(r"<tool_call>.*?</tool_call>", "", clean, flags=re.DOTALL).strip()

    return clean, tool_calls


def main():
    if not API_KEY:
        print(f"{RED}Error: Set NANOCODE_API_KEY or AEGIS_API_KEY{RESET}")
        sys.exit(1)

    messages = load_session() or []
    resumed = " (resumed)" if messages else ""
    model_display = MODEL if MODEL != "auto" else f"auto ({MODELS['fast']}/{MODELS['quality']})"

    print(f"{BOLD}nanocode{RESET} | {DIM}{model_display}{RESET} | {os.getcwd()}{resumed}\n")
    system_prompt = f"Concise coding assistant. cwd: {os.getcwd()}. When using tools, output a tool_call block."

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

            while True:
                content, tool_calls = call_api_stream(messages, system_prompt)

                # Execute tool calls
                tool_results = []
                for tc in tool_calls:
                    fn = tc["function"]
                    tool_name = fn["name"]
                    try:
                        tool_args = json.loads(fn["arguments"])
                    except json.JSONDecodeError:
                        tool_args = {}

                    arg_preview = str(list(tool_args.values())[0])[:50] if tool_args else ""
                    print(f"\n{GREEN}⏺ {tool_name}{RESET}({DIM}{arg_preview}{RESET})")

                    result = run_tool(tool_name, tool_args)
                    lines = result.split("\n")
                    preview = lines[0][:60]
                    if len(lines) > 1:
                        preview += f" ... +{len(lines)-1} lines"
                    print(f"  {DIM}⎿  {preview}{RESET}")

                    tool_results.append({"role": "tool", "content": result, "tool_call_id": tc["id"]})

                if not tool_calls:
                    break

                messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
                messages.extend(tool_results)

            save_session(messages)
            print()

        except (KeyboardInterrupt, EOFError):
            break
        except Exception as err:
            print(f"{RED}⏺ Error: {err}{RESET}")

    save_session(messages)


if __name__ == "__main__":
    main()
