# Life Journal with Plan and Notes

A personal diary managed through Django Admin.

## Installation

```bash
pip install --upgrade poetry
poetry install
```

## Running the application locally

`poetry run python manage.py runserver`

## MCP

Configure `APP_BASE_URL` (the application address) and `MCP_OWNER_USERNAME` in
`project/settings.py`. The MCP endpoint is `APP_BASE_URL/mcp`.

Run with Docker Compose:

```bash
docker compose build mcp
docker compose up -d mcp
```

Or run directly:

```bash
poetry run python -m foodlog.mcp_server
```

Start MCP Inspector:

```bash
npx @modelcontextprotocol/inspector@latest
```

In Django Admin, register an OAuth application owned by your user: grant type
**Authorization code**, client type **Public** for Inspector or **Confidential**
for ChatGPT. Use the client's exact callback URL and keep **Skip authorization** off.

In Inspector, select **Streamable HTTP**, URL `http://localhost:8010/mcp`, and OAuth.
Enter the client ID and scope `diary:read`, sign in, then call `get_days` in **Tools**:

```json
{}
```

The tool reads existing days with classification, notes, medication records, meals,
and dishes, in the diary timezone. Up to 31 existing days per page, newest first:

- No dates: latest days through today.
- Only `start_date`: first days from that date through today.
- Only `end_date`: latest days through that date.
- Both dates: days in the inclusive range; use the same date for a single day.

Dates use `YYYY-MM-DD`. Calendar gaps do not count toward the limit. While
`has_more` is true, use `next_offset` as `offset` with the original date parameters
and `limit`. Start-only pages advance forward; other pages go backward.
For production, use the `mcp-prod` service.

## Ruff

Check code and formatting:

```bash
poetry run ruff check .
poetry run ruff format --check .
```

Apply fixes and formatting:

```bash
poetry run ruff check . --fix
poetry run ruff format .
```

Django entry points (`manage.py`, `asgi.py`, `wsgi.py`), `apps.py`, and migrations
are excluded from linting and formatting.

## Docker compose

```bash
docker compose build prod
docker compose up -d prod
```
