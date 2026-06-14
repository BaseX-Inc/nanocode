#!/usr/bin/env python3
"""nanocode — agentic coding CLI. Claude Code architecture with proper tool loop."""

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
    total_chars = sum(len(m.get("content", "")) for m in messages if isinstance(m.get("content"), str))
    tool_count = sum(1 for m in messages if m.get("role") == "tool")
    if total_chars > 6000 or tool_count > 5:
        return MODELS["quality"]
    return MODELS["fast"]


SYSTEM = (
    "/no_think\n"
    f"You are a coding agent at {os.getcwd()}. "
    "Use tools to solve tasks. Act, don't explain. "
    "When you need information, use tools immediately. "
    "Do not ask for permission. Do not ask clarifying questions when you can just look."
)


def api_call(messages, tools):
    """Call API, return parsed response."""
    model = pick_model(messages)
    body = json.dumps({
        "model": model,
        "max_tokens": 16384,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
    }).encode()

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "nanocode/0.3",
    }
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    req = urllib.request.Request(API_URL, data=body, headers=headers)
    resp = urllib.request.urlopen(req, timeout=300)
    return json.loads(resp.read())


def agent_loop(messages, tools_schema):
    """Core agent loop: call LLM → execute tools → repeat until no more tool calls."""
    max_iterations = 15

    for _ in range(max_iterations):
        # Show spinner while waiting
        stop_event = threading.Event()
        def spin():
            frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            i = 0
            t0 = time.time()
            while not stop_event.is_set():
                elapsed = time.time() - t0
                sys.stdout.write(f"\r{DIM}{frames[i % len(frames)]} thinking ({elapsed:.0f}s){RESET}   ")
                sys.stdout.flush()
                time.sleep(0.08)
                i += 1
            sys.stdout.write(f"\r{' ' * 40}\r")
            sys.stdout.flush()

        t = threading.Thread(target=spin, daemon=True)
        t.start()

        try:
            response = api_call(messages, tools_schema)
        finally:
            stop_event.set()
            t.join(timeout=0.3)

        choice = response["choices"][0]
        msg = choice["message"]
        finish_reason = choice.get("finish_reason", "stop")

        # Append assistant message to history
        messages.append(msg)

        # Print any text content
        content = msg.get("content", "")
        if content:
            # Stream-simulate the output
            sys.stdout.write(f"\n{CYAN}⏺{RESET} ")
            for ch in content:
                sys.stdout.write(ch)
                sys.stdout.flush()
                time.sleep(0.005)
            print()

        # Check for tool calls
        tool_calls = msg.get("tool_calls", [])
        if not tool_calls:
            break

        # Execute tools
        for tc in tool_calls:
            fn = tc["function"]
            name = fn["name"]
            try:
                args = json.loads(fn["arguments"])
            except json.JSONDecodeError:
                args = {}

            # Display
            arg_preview = str(list(args.values())[0])[:50] if args else ""
            print(f"\n{GREEN}⏺ {name}{RESET}({DIM}{arg_preview}{RESET})")

            result = run_tool(name, args)
            lines = result.split("\n")
            preview = lines[0][:70]
            if len(lines) > 1:
                preview += f" {DIM}+{len(lines)-1} lines{RESET}"
            print(f"  {DIM}⎿ {preview}{RESET}")

            # Append tool result
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result[:10000],  # cap tool output
            })

    return messages


def main():
    if not API_KEY and "modal.run" not in API_URL:
        print(f"{RED}Set NANOCODE_API_KEY or AEGIS_API_KEY{RESET}")
        sys.exit(1)

    messages = load_session() or [{"role": "system", "content": SYSTEM}]
    if messages and messages[0].get("role") != "system":
        messages.insert(0, {"role": "system", "content": SYSTEM})

    resumed = " (resumed)" if len(messages) > 1 else ""
    model_display = MODEL if MODEL != "auto" else f"auto ({MODELS['fast']}/{MODELS['quality']})"
    print(f"{BOLD}nanocode{RESET} | {DIM}{model_display}{RESET} | {os.getcwd()}{resumed}\n")

    tools_schema = make_schema()

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
                messages = [{"role": "system", "content": SYSTEM}]
                delete_session()
                print(f"{GREEN}⏺ Cleared{RESET}")
                continue
            if user_input == "/m":
                print(f"{DIM}{pick_model(messages)}{RESET}")
                continue

            messages.append({"role": "user", "content": user_input})
            messages = agent_loop(messages, tools_schema)
            save_session(messages)
            print()

        except (KeyboardInterrupt, EOFError):
            break
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:200]
            print(f"{RED}⏺ HTTP {e.code}: {body}{RESET}")
        except Exception as err:
            print(f"{RED}⏺ Error: {err}{RESET}")

    save_session(messages)


if __name__ == "__main__":
    main()
