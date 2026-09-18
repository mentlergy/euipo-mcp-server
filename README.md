# EUIPO MCP Server

This repo is a fork of the https://github.com/enxebre/euipo-mcp-server.
Thanks for his work.

MCP server for the [EUIPO](https://euipo.europa.eu/) (European Union Intellectual Property Office) APIs — trademark search and goods & services classification.

## Setup

1. Register (free) at [dev.euipo.europa.eu](https://dev.euipo.europa.eu/)
2. Create an App to get your Client ID and Secret
3. Subscribe to the **Trademark Search** and/or **Goods and Services** API plans

Sandbox access is approved in ~1 day. Production takes up to 1 week.

## Installation

```bash
git clone https://github.com/mentlergy/euipo-mcp-server.git
cd euipo-mcp-server
cp .env.example .env.sandbox
# Edit .env.sandbox with your credentials
```
## Installing uv

### Windows
```Powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
#### Linux
With curl:
```Bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
or wget
```Bash
wget -qO- https://astral.sh/uv/install.sh | sh
```


## Usage with Claude Code

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "euipo": {
      "command": "/absolute_path_to_the_uv_executable/uv",
      "args": ["--directory", "/path/to/euipo-mcp-server", "run", "euipo-mcp-server"],
      "env": {
        "EUIPO_CLIENT_ID": "your-client-id",
        "EUIPO_CLIENT_SECRET": "your-client-secret",
        "EUIPO_USE_SANDBOX": "true"
      }
    }
  }
}
```

## Tools

### Trademark Search

| Tool | Description |
|------|-------------|
| `search_trademarks` | Search by name, Nice class, status, applicant, date range |
| `get_trademark` | Get full details by application number |
| `get_trademark_image` | Get image URL for figurative marks |

### Goods & Services (TMClass)

| Tool | Description |
|------|-------------|
| `search_goods_and_services` | Search harmonised terms by text and/or class number |
| `get_nice_class_headings` | List all 45 Nice Classification class headings |
| `get_nice_taxonomy` | Browse the Nice Classification taxonomy tree |
| `suggest_goods_and_services` | Get term suggestions for free-text descriptions |
| `validate_classification` | Validate terms against the harmonised database |
| `translate_classification` | Translate terms between EU languages |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `EUIPO_CLIENT_ID` | Yes | — | From EUIPO developer portal |
| `EUIPO_CLIENT_SECRET` | Yes | — | From EUIPO developer portal |
| `EUIPO_USE_SANDBOX` | No | `true` | Set `false` for production data |

## License

MIT
