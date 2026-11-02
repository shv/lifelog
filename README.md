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

To add notes, authorize scopes `diary:read notes:write` and call `add_note`:

```json
{"text": "My note, saved exactly as written."}
```

Without dates or times it uses the current diary date and time. `note_time` alone
uses today; `note_date` requires `note_time`. Future timestamps are rejected. A
missing day is created with the default classification. The first letter is
capitalized; the rest of the text is saved unchanged.
After deployment, refresh the ChatGPT connection's tools and authorize the new
`notes:write` permission; existing read-only tokens cannot add notes.

`get_pills` returns the active pill catalogue; `include_inactive=true` also shows
archived entries. Manage pills and their **Active for external APIs** checkbox in
Django Admin. This flag does not restrict viewing or selecting pills in Admin.
Existing pills are active by default after applying the migration.

`add_pill_intake` requires `diary:read pills:write`, a `pill_id` from that catalogue,
and `is_taken`: `true` for a completed intake, `false` for a plan. `note` holds the
optional comment (up to 150 characters). `intake_date` and `intake_time` follow
the note date/time rules, except that future timestamps are allowed for plans.
Missing or ambiguous pill names must be clarified before recording.

For this update, run `python manage.py migrate` before starting the updated Django
and MCP processes, refresh the connection's tools and authorize `pills:write`.

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
