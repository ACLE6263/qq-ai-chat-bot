# QQ AI Chat Bot

A modular, LLM-powered QQ chatbot built on [NoneBot2](https://github.com/nonebot/nonebot2) and the OneBot v11 protocol. Supports Claude, OpenAI, and any OpenAI-compatible API (DeepSeek, Ollama, vLLM, etc.).

## Architecture

```
QQ Desktop App (with NapCat plugin)
  └── Reverse WebSocket → ws://127.0.0.1:8080/onebot/v11/

NoneBot2 (this project)
  ├── bot.py (entry point)
  ├── src/config.py (configuration via .env)
  ├── src/plugins/admin/commands.py (/status, /ping)
  └── src/plugins/ai_chat/
      ├── chat_handler.py   ← Message routing & processing
      ├── llm_client.py     ← LLM API client (Claude / OpenAI / Custom)
      ├── session_manager.py ← In-memory conversation history
      └── rate_limiter.py   ← Per-user/group rate limiting
```

## Features

- **Private & Group Chat** — Responds to all private messages; in groups, responds when @mentioned (configurable)
- **Multi-Provider LLM** — Claude, OpenAI, or any OpenAI-compatible endpoint (DeepSeek, Ollama, etc.)
- **Automatic Model Fallback** — Custom provider supports backup models when the primary is unavailable
- **Conversation History** — Sliding-window memory with LRU eviction per session
- **Rate Limiting** — Configurable per-user and per-group limits to prevent spam
- **Basic Injection Protection** — Regex-based detection of common prompt injection patterns
- **Long Message Splitting** — Auto-splits responses exceeding QQ's character limit
- **Admin Commands** — `/status` and `/ping` for the bot owner

## Prerequisites

- **Python 3.10+**
- **A QQ account** for the bot (separate from your personal account)
- **NapCat** (or another OneBot v11 bridge) connected to your QQ client
- **An LLM API key** (DeepSeek, Claude, or OpenAI)

### Setting up NapCat

NapCat is a OneBot v11 bridge that connects QQ to NoneBot2. See the [NapCat documentation](https://github.com/NapNeko/NapCatQQ) for installation instructions.

After installing NapCat, configure it to connect to NoneBot2 via reverse WebSocket:

```json
{
  "ws_reverse": [{
    "url": "ws://127.0.0.1:8080/onebot/v11/",
    "access_token": ""
  }]
}
```

> **Important:** Both NapCat and NoneBot2 should have empty access tokens. If you set a token, the auth mechanisms differ (NoneBot2 checks the HTTP header, NapCat sends it as a URL parameter), which causes 403 errors.

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/qq-ai-chat-bot.git
cd qq-ai-chat-bot

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env with your API key, model, and bot owner QQ number

# 4. Customize the system prompt (optional)
cp system_prompt.txt.example system_prompt.txt
# Edit system_prompt.txt to define your bot's personality

# 5. Run
python bot.py

# 6. Start your QQ client with NapCat
# NapCat will connect to NoneBot2 automatically
```

## Configuration

All settings are in `.env`. Copy `.env.example` to `.env` and edit:

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | `claude`, `openai`, or `custom` | `custom` |
| `CUSTOM_API_BASE` | Base URL for OpenAI-compatible API | `https://api.deepseek.com/v1` |
| `CUSTOM_API_KEY` | Your API key | *(required)* |
| `CUSTOM_MODEL` | Model name | `deepseek-chat` |
| `CUSTOM_BACKUP_MODELS` | Comma-separated fallback models | *(optional)* |
| `PORT` | NoneBot2 listen port | `8080` |
| `TRIGGER_MODE` | `at_only` or `prefix` | `at_only` |
| `MAX_HISTORY_TURNS` | Conversation turns to remember | `20` |
| `MAX_RESPONSE_TOKENS` | Max tokens per LLM response | `1024` |
| `TEMPERATURE` | LLM creativity (0–1) | `0.7` |
| `RATE_LIMIT_PER_USER` | Max requests/user per window | `20` |
| `RATE_LIMIT_PER_GROUP` | Max requests/group per window | `60` |
| `BOT_OWNER_QQ` | QQ number for admin commands | *(required)* |

### System Prompt

The bot's personality is defined by the system prompt. You have two options:

1. **File-based** (recommended): Create `system_prompt.txt` — takes priority over `.env`
2. **Env-based**: Set `SYSTEM_PROMPT` in `.env` — used as fallback

## Chat Modes

### Private Chat
Send any message to the bot's QQ account. All messages receive a response.

### Group Chat
**At-only mode** (default): The bot only responds when @mentioned.

**Prefix mode**: Set `TRIGGER_MODE=prefix` and `CHAT_PREFIX=/chat` in `.env`. The bot responds to messages starting with the prefix (without needing @mention).

## Commands

| Command | Description | Scope |
|---------|-------------|-------|
| `/reset` or `/clear` | Clear conversation history | Private + Group |
| `/status` | Show bot status (provider, model, sessions) | Owner only |
| `/ping` | Check if bot is online | Owner only |

## Project Structure

```
├── .env.example              # Configuration template
├── .gitignore
├── LICENSE
├── README.md
├── bot.py                    # Entry point
├── requirements.txt          # Python dependencies
├── system_prompt.txt.example # Example system prompt
└── src/
    ├── config.py             # Pydantic settings model
    └── plugins/
        ├── admin/
        │   ├── __init__.py
        │   └── commands.py   # /status, /ping
        └── ai_chat/
            ├── __init__.py
            ├── chat_handler.py   # Message routing & pipeline
            ├── llm_client.py     # LLM API client
            ├── session_manager.py # Conversation history
            └── rate_limiter.py   # Rate limiter
```

## Troubleshooting

### Bot doesn't respond

1. **Check NoneBot2 is running** — The terminal should show `Uvicorn running on http://127.0.0.1:8080`
2. **Check NapCat is connected** — The terminal should show `OneBot V11 | Bot <qq> connected`
3. **Check token config** — Both `.env` (`ONEBOT_ACCESS_TOKEN`) and NapCat's `access_token` must be empty
4. **Check WebSocket URL** — NapCat's URL must end with `/` and use the correct port
5. **Check trigger mode** — In groups with `at_only` mode, you must @mention the bot

### API errors

| Error | Cause |
|-------|-------|
| `AI 服务繁忙` (HTTP 429) | Rate limited — wait a moment |
| `API 鉴权失败` (HTTP 401) | Invalid API key |
| `API 访问被拒绝` (HTTP 403) | Account/permission issue |
| `AI 服务端错误` (HTTP 5xx) | Provider server error — wait and retry |

### Port already in use

```bash
# Windows
netstat -an | findstr 8080

# Linux/macOS
lsof -i :8080
```

Change `PORT` in `.env` and update NapCat's WebSocket URL to match.

## License

MIT — see [LICENSE](LICENSE) for details.
