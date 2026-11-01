import os
from urllib.parse import urlparse

import uvicorn
from django.conf import settings
from django.core.asgi import get_asgi_application
from django.core.exceptions import ImproperlyConfigured
from mcp.server import MCPServer
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
django_app = get_asgi_application()

if not settings.MCP_OWNER_USERNAME:
    raise ImproperlyConfigured(
        "Set MCP_OWNER_USERNAME to the diary owner's Django login."
    )
public_url = urlparse(settings.APP_BASE_URL)
if (
    public_url.path
    or public_url.query
    or public_url.fragment
    or public_url.username is not None
    or not public_url.hostname
    or (
        public_url.scheme != "https"
        and not (
            public_url.scheme == "http"
            and public_url.hostname in {"localhost", "127.0.0.1", "::1"}
        )
    )
):
    raise ImproperlyConfigured(
        "APP_BASE_URL must be an HTTPS origin or local HTTP origin."
    )


def create_server():
    from foodlog.mcp_auth import DiaryTokenVerifier

    return MCPServer(
        "lifelog",
        title="LifeLog diary",
        description=(
            "Private personal diary integration. Currently provides only a fixed "
            "demo day for testing the authenticated MCP connection."
        ),
        instructions=(
            "get_days currently returns synthetic demo data marked is_stub=true. "
            "Use it to test the connection. It cannot read real diary entries or "
            "create, update, or delete records. Do not treat its sample notes, "
            "medications, meals, or dates as facts about the user."
        ),
        version="0.2.0",
        token_verifier=DiaryTokenVerifier(),
        auth=AuthSettings(
            issuer_url=settings.APP_BASE_URL,
            resource_server_url=settings.MCP_RESOURCE_URL,
            required_scopes=["diary:read"],
            validate_token_resource=True,
        ),
    )


mcp = create_server()


@mcp.tool(
    title="Get diary days (demo)",
    meta={"securitySchemes": [{"type": "oauth2", "scopes": ["diary:read"]}]},
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, openWorldHint=False
    ),
)
def get_days() -> dict[str, object]:
    """Test the authenticated diary connection by returning a fixed sample day.

    The result contains synthetic notes and empty medication and meal lists.
    It is marked is_stub=true and does not read the user's actual diary.
    Takes no arguments and never creates, changes, or deletes records.
    """
    return {
        "is_stub": True,
        "days": [
            {
                "date": "2026-01-01",
                "daily_intake": None,
                "notes": [{"time": "12:00:00", "text": "MCP test note."}],
                "taking_pills": [],
                "meals": [],
            }
        ],
    }


host = os.getenv("MCP_HOST", "127.0.0.1")
app = mcp.streamable_http_app(
    host=host,
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            urlparse(settings.APP_BASE_URL).netloc,
            "localhost:8010",
            "127.0.0.1:8010",
        ],
        allowed_origins=[
            settings.APP_BASE_URL,
            "http://localhost:6274",
            "http://127.0.0.1:6274",
        ],
    ),
)
app.routes.append(Mount("/", app=django_app))
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:6274", "http://127.0.0.1:6274"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id", "MCP-Protocol-Version", "WWW-Authenticate"],
)


if __name__ == "__main__":
    uvicorn.run(app, host=host, port=8010)
