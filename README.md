# nanocode

Minimal agentic coding CLI. Zero dependencies, ~200 lines of core logic. Streams responses in real-time.

![screenshot](screenshot.png)

## Features

- Full agentic loop with tool use (read, write, edit, glob, grep, bash)
- **Streaming** responses with real-time output
- **Auto model routing** — picks fast or quality model based on context complexity
- Conversation persistence per-project
- Colored terminal output

## Setup

```bash
pip install -e .
export AEGIS_API_KEY="your-key"
nanocode
```

Or without installing:

```bash
export AEGIS_API_KEY="your-key"
python -m nanocode
```

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `AEGIS_API_KEY` or `NANOCODE_API_KEY` | — | API key (required) |
| `NANOCODE_API_BASE` | `https://api.basex.stanl.ink` | API base URL |
| `NANOCODE_MODEL` | `auto` | Model ID or `auto` |

### Models

When `NANOCODE_MODEL=auto` (default):
- **qwen3-30b-moe** — used for short/simple tasks (fast, MoE)
- **qwen3-32b** — used for complex multi-step tasks (dense, higher quality)

Override with any model ID: `NANOCODE_MODEL=qwen3-32b`

## Commands

- `/c` — Clear conversation
- `/m` — Show current model
- `/q` or `exit` — Quit

## Tools

| Tool | Description |
|------|-------------|
| `read` | Read file with line numbers, offset/limit |
| `write` | Write content to file |
| `edit` | Replace string in file (must be unique) |
| `glob` | Find files by pattern, sorted by mtime |
| `grep` | Search files for regex |
| `bash` | Run shell command |

## License

MIT
