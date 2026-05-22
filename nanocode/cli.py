#!/usr/bin/env python3
"""Main CLI for nanocode."""

import json
import os
import urllib.request
from .config import API_URL, MODEL, NVIDIA_KEY, RESET, BOLD, DIM, BLUE, CYAN, GREEN, RED
from .tools import make_schema, run_tool, TOOLS
from .session import load_session, save_session, delete_session


def separator():
    try:
        return f"{DIM}{'─' * min(os.get_terminal_size().columns, 80)}{RESET}"
    except OSError:
        return f"{DIM}{'─' * 80}{RESET}"


def render_markdown(text):
    import re
    return re.sub(r"\*\*(.+?)\*\*", f"{BOLD}\\1{RESET}", text)


def call_api(messages, system_prompt):
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(
            {
                "model": MODEL,
                "max_tokens": 8192,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    *messages,
                ],
                "tools": make_schema(),
                "tool_choice": "auto",
            }
        ).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {NVIDIA_KEY}",
        },
    )
    response = urllib.request.urlopen(request)
    return json.loads(response.read())


def main():
    # Try to load existing session
    messages = load_session() or []
    resumed = messages and " (resumed)" or ""
    
    print(f"{BOLD}nanocode{RESET} | {DIM}{MODEL} (NVIDIA){RESET} | {os.getcwd()}{resumed}\n")
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

            messages.append({"role": "user", "content": user_input})

            while True:
                response = call_api(messages, system_prompt)
                choice = response.get("choices", [{}])[0]
                msg = choice.get("message", {})
                tool_calls = msg.get("tool_calls") or []
                content = msg.get("content") or ""

                if content:
                    print(f"\n{CYAN}⏺{RESET} {render_markdown(content)}")

                tool_results = []
                for tc in tool_calls:
                    if tc and "function" in tc:
                        tool_name = tc["function"]["name"]
                        tool_args = json.loads(tc["function"]["arguments"])
                        arg_preview = str(list(tool_args.values())[0])[:50] if tool_args else ""
                        print(
                            f"\n{GREEN}⏺ {tool_name.capitalize()}{RESET}({DIM}{arg_preview}{RESET})"
                        )

                        result = run_tool(tool_name, tool_args)
                        result_lines = result.split("\n")
                        preview = result_lines[0][:60]
                        if len(result_lines) > 1:
                            preview += f" ... +{len(result_lines) - 1} lines"
                        elif len(result_lines[0]) > 60:
                            preview += "..."
                        print(f"  {DIM}⎿  {preview}{RESET}")

                        tool_results.append(
                            {
                                "role": "tool",
                                "content": result,
                            }
                        )

                if not tool_calls:
                    break
                messages.append({"role": "assistant", "content": "", "tool_calls": tool_calls})
                for tr in tool_results:
                    messages.append(tr)

            # Auto-save session after each turn
            save_session(messages)
            print()

        except (KeyboardInterrupt, EOFError):
            break
        except Exception as err:
            print(f"{RED}⏺ Error: {err}{RESET}")
    
    # Final save on exit
    save_session(messages)


if __name__ == "__main__":
    main()