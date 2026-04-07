# QuestionBridge

A service that lets Claude ask you questions asynchronously — via Telegram and a web dashboard — instead of blocking the IDE chat.

When Claude needs a decision (authorization, clarification, confirmation), it checks whether you're away. If you are, it sends the question to Telegram and waits for your reply. If you're not, it asks in the IDE chat as normal.

```
Claude  →  GET /api/status           →  {"away": true}
Claude  →  POST /api/ask             →  question sent to Telegram
You     →  reply on Telegram or dashboard
Claude  ←  GET /api/questions/{id}/wait  unblocks, continues
```

## Requirements

- Python 3.11+
- [Poetry](https://python-poetry.org/docs/#installation)
- A Telegram bot token and your chat ID

## Setup

```bash
git clone <repo>
cd questionbridge

# Install dependencies (creates .venv automatically)
poetry install

# Run
poetry run start
```

Three services start on the same port:

| URL | Description |
|---|---|
| `http://localhost:8000/` | Web dashboard |
| `http://localhost:8000/api/…` | REST API |
| `http://localhost:8000/mcp` | MCP endpoint (for Claude Code) |
| `http://localhost:8000/health` | Health check |

## Configuration

Defaults are pre-filled in `config.py`. Override via `.env` or environment variables:

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | *(set)* | Telegram bot token |
| `OWNER_CHAT_ID` | *(set)* | Your Telegram user ID |
| `API_PORT` | `8000` | HTTP port |
| `API_HOST` | `0.0.0.0` | Bind address |

## Claude Code integration

Two files in your home directory wire Claude Code to use the bridge:

### `~/.claude/CLAUDE.md`

Instructs Claude to check away status before asking questions:

```markdown
# Global instructions for Claude Code

## Asking questions

Before asking anything that requires a human decision, check whether the owner is away:

    curl -sf http://localhost:8000/api/status

- `{"away": true}` — use the bridge (ask_owner MCP tool, or POST /api/ask + GET /api/questions/{id}/wait). Do not ask in chat.
- `{"away": false}` or service unreachable — ask in chat as normal.

The owner sets away mode via /away and /back Telegram bot commands, or the dashboard toggle.
```

### `~/.claude/mcp.json`

Registers the `ask_owner` tool so Claude can call it natively:

```json
{
  "mcpServers": {
    "questionbridge": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

After adding this file, restart Claude Code. Verify with `/mcp` — you should see `questionbridge` with the `ask_owner` tool listed.

## Away mode

Set yourself as away so Claude uses the bridge instead of the IDE chat:

| Method | Action |
|---|---|
| Telegram `/away` | Away ON |
| Telegram `/back` | Away OFF |
| Dashboard toggle | 🟢 Here / 🌙 Away |
| `POST /api/status` `{"away": true}` | Programmatic |

## Telegram bot commands

| Command | Description |
|---|---|
| `/start` `/help` | Show usage |
| `/away` | Switch Claude to bridge mode |
| `/back` | Switch Claude back to chat |
| `/pending` | List pending questions |

Answering a question:
- **Reply** to the question message with free text
- Tap **✅ Yes** or **❌ No** inline buttons
- Use the **web dashboard** at `http://localhost:8000`

## REST API reference

```
POST /api/ask                        create a question, send to Telegram
GET  /api/questions                  list all (?status=pending to filter)
GET  /api/questions/{id}             get current state
GET  /api/questions/{id}/wait        long-poll until answered (default 300s)
GET  /api/questions/{id}/stream      SSE: fires when resolved
POST /api/questions/{id}/answer      {"answer": "..."}
POST /api/questions/{id}/cancel      cancel a pending question
GET  /api/status                     {"away": true/false}
POST /api/status                     {"away": true/false}
GET  /health                         {"status":"ok","pending_questions":N}
POST /mcp                            MCP Streamable HTTP endpoint
```

## Architecture

```
main.py          entry point — asyncio.gather(uvicorn, aiogram polling)
├── store.py     in-memory store: questions dict + asyncio.Event per question + away flag
├── bot.py       aiogram 3.x — /away /back /pending, inline buttons, reply handling
├── api.py       FastAPI — REST endpoints + MCP Streamable HTTP transport at /mcp
└── dashboard.py NiceGUI — live dashboard mounted on the FastAPI app
```

State is in-memory only and resets on restart.
