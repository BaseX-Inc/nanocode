#!/usr/bin/env python3
"""Main CLI for nanocode."""

import json
import os
import sys
import urllib.request
from .config import (
    API_URL, API_KEY, MODEL, MODELS,
    RESET, BOLD, DIM, BLUE, CYAN, GREEN, RED
)
from .tools import make_schema, run_tool, TOOLS
from .session import load_session, save_session, delete_session


def separator():
    try:
        return f"{DIM}{'─' * min(os.get_terminal_size().columns, 80)}{RESET}"
    except OSError:
        return f"{DIM}{'─' * 80}{RESET}"


def render_markdown(text):
    import re
    # Strip <think> blocks from output
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return re.sub(r"\*\*(.+?)\*\*", f"{BOLD}\\1{RESET}", text)


def pick_model(messages):
    """Auto-route: use fast model for short exchanges, quality for complex."""
    if MODEL != "auto":
        return MODEL
    total_chars = sum(len(m.get("content", "")) for m in messages)
    tool_count = sum(1 for m in messages if m.get("role") == "tool")
    if total_chars > 4000 or tool_count > 3:
        return MODELS["quality"]
    return MODELS["fast"]


def call_api_stream(messages, system_prompt):
    """Call API with streaming, yield content chunks and tool calls."""
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
        API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
    )
    resp = urllib.request.urlopen(req)

    content_buf = ""
    tool_calls = []
    current_tc = {}

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

        # Content streaming
        if delta.get("content"):
            content_buf += delta["content"]
            yield ("content", delta["content"])

        # Tool call streaming
        if delta.get("tool_calls"):
            for tc_delta in delta["tool_calls"]:
                idx = tc_delta.get("index", 0)
                while len(tool_calls) <= idx:
                    tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                if tc_delta.get("id"):
                    tool_calls[idx]["id"] = tc_delta["id"]
                fn = tc_delta.get("function", {})
                if fn.get("name"):
                    tool_calls[idx]["function"]["name"] = fn["name"]
                if fn.get("arguments"):
                    tool_calls[idx]["function"]["arguments"] += fn["arguments"]

    if tool_calls:
        yield ("tool_calls", tool_calls)
    if content_buf:
        yield ("content_done", content_buf)


def call_api(messages, system_prompt):
    """Non-streaming fallback."""
    model = pick_model(messages)
    body = json.dumps({
        "model": model,
        "max_tokens": 8192,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "tools": make_schema(),
        "tool_choice": "auto",
    }).encode()

    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
    )
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())


def main():
    if not API_KEY:
        print(f"{RED}Error: Set NANOCODE_API_KEY or AEGIS_API_KEY{RESET}")
        sys.exit(1)

    messages = load_session() or []
    resumed = " (resumed)" if messages else ""
    model_display = MODEL if MODEL != "auto" else f"auto ({MODELS['fast']}/{MODELS['quality']})"

    print(f"{BOLD}nanocode{RESET} | {DIM}{model_display}{RESET} | {os.getcwd()}{resumed}\n")
    system_prompt = f"Concise coding assistant. cwd: {os.getcwd()}"

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
                print(f"{GREEN}⏺ Cleared conversation{RESET}")
                continue
            if user_input == "/m":
                print(f"{DIM}Model: {pick_model(messages)}{RESET}")
                continue

            messages.append({"role": "user", "content": user_input})

            while True:
                # Try streaming first
                content = ""
                tool_calls = []
                try:
                    printed_prefix = False
                    in_think = False
                    for event_type, event_data in call_api_stream(messages, system_prompt):
                        if event_type == "content":
                            # Filter out <think>...</think> blocks from stream
                            if "<think>" in event_data:
                                in_think = True
                                event_data = event_data.split("<think>")[0]
                            if "</think>" in event_data:
                                in_think = False
                                event_data = event_data.split("</think>")[-1]
                                continue
                            if in_think:
                                continue
                            if event_data:
                                if not printed_prefix:
                                    sys.stdout.write(f"\n{CYAN}⏺{RESET} ")
                                    printed_prefix = True
                                sys.stdout.write(event_data)
                                sys.stdout.flush()
                        elif event_type == "content_done":
                            content = event_data
                        elif event_type == "tool_calls":
                            tool_calls = event_data
                    if printed_prefix:
                        print()
                except Exception:
                    # Fallback to non-streaming
                    response = call_api(messages, system_prompt)
                    choice = response.get("choices", [{}])[0]
                    msg = choice.get("message", {})
                    tool_calls = msg.get("tool_calls") or []
                    content = msg.get("content") or ""
                    if content:
                        print(f"\n{CYAN}⏺{RESET} {render_markdown(content)}")

                # Handle tool calls
                tool_results = []
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    tool_name = fn.get("name", "")
                    try:
                        tool_args = json.loads(fn.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        tool_args = {}

                    arg_preview = str(list(tool_args.values())[0])[:50] if tool_args else ""
                    print(f"\n{GREEN}⏺ {tool_name}{RESET}({DIM}{arg_preview}{RESET})")

                    result = run_tool(tool_name, tool_args)
                    result_lines = result.split("\n")
                    preview = result_lines[0][:60]
                    if len(result_lines) > 1:
                        preview += f" ... +{len(result_lines) - 1} lines"
                    elif len(result_lines[0]) > 60:
                        preview += "..."
                    print(f"  {DIM}⎿  {preview}{RESET}")

                    tool_results.append({"role": "tool", "content": result, "tool_call_id": tc.get("id", "")})

                if not tool_calls:
                    break

                messages.append({"role": "assistant", "content": content or "", "tool_calls": tool_calls})
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
