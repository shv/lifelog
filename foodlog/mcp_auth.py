"""Django OAuth integration for the private diary MCP server."""

import hashlib
import re

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import close_old_connections
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.utils import timezone
from mcp.server.auth.provider import AccessToken
from oauth2_provider.models import get_access_token_model
from oauth2_provider.oauth2_validators import OAuth2Validator
from oauth2_provider.views import AuthorizationView
from oauthlib.oauth2 import InvalidGrantError
from oauthlib.oauth2.rfc6749.errors import CustomOAuth2Error


def is_mcp_owner(user):
    return bool(
        settings.MCP_OWNER_USERNAME
        and user
        and user.is_active
        and user.get_username() == settings.MCP_OWNER_USERNAME
    )


class OwnerAuthorizationView(AuthorizationView):
    login_url = "admin:login"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if not is_mcp_owner(request.user):
                return HttpResponseForbidden(
                    "MCP access is restricted to the diary owner."
                )
            resources = (
                request.POST.get("resource", "").split()
                if request.method == "POST"
                else request.GET.getlist("resource")
            )
            if resources != [settings.MCP_RESOURCE_URL]:
                return HttpResponseBadRequest("The diary MCP resource is required.")
            params = request.POST if request.method == "POST" else request.GET
            if params.get("code_challenge_method") != "S256" or not re.fullmatch(
                r"[A-Za-z0-9_-]{43}", params.get("code_challenge", "")
            ):
                return HttpResponseBadRequest(
                    "PKCE with an S256 challenge is required."
                )
        return super().dispatch(request, *args, **kwargs)


class DiaryOAuthValidator(OAuth2Validator):
    def validate_scopes(self, client_id, scopes, client, request, *args, **kwargs):
        return is_mcp_owner(client.user) and super().validate_scopes(
            client_id, scopes, client, request, *args, **kwargs
        )

    def _check_and_set_request_resource(self, request):
        super()._check_and_set_request_resource(request)
        if request.resource != [settings.MCP_RESOURCE_URL]:
            raise CustomOAuth2Error(
                error="invalid_target",
                description="Invalid diary resource.",
                request=request,
            )
        if not is_mcp_owner(request.user):
            raise InvalidGrantError(request=request)

    def validate_refresh_token(self, refresh_token, client, request, *args, **kwargs):
        return super().validate_refresh_token(
            refresh_token, client, request, *args, **kwargs
        ) and is_mcp_owner(request.user)


class DiaryTokenVerifier:
    @sync_to_async
    def verify_token(self, token: str) -> AccessToken | None:
        close_old_connections()
        try:
            checksum = hashlib.sha256(token.encode()).hexdigest()
            saved = (
                get_access_token_model()
                .objects.select_related("user", "application")
                .filter(token_checksum=checksum, expires__gt=timezone.now())
                .first()
            )
            if (
                saved is None
                or not is_mcp_owner(saved.user)
                or saved.resource != [settings.MCP_RESOURCE_URL]
                or saved.application is None
                or saved.application.user_id != saved.user_id
                or saved.application.authorization_grant_type != "authorization-code"
            ):
                return None
            return AccessToken(
                token=token,
                client_id=saved.application.client_id,
                scopes=saved.scope.split(),
                expires_at=int(saved.expires.timestamp()),
                resource=settings.MCP_RESOURCE_URL,
                subject=str(saved.user_id),
            )
        finally:
            close_old_connections()
