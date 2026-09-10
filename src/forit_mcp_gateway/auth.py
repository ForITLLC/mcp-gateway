"""Bearer credentials for service clients, Entra OAuth for interactive login."""

import hashlib
import hmac

from fastmcp.server.auth import AccessToken, TokenVerifier

from .config import Auth, secret


class BearerVerifier(TokenVerifier):
    def __init__(self, token: str):
        super().__init__(required_scopes=["tools.read"])
        if len(token) < 32:
            raise ValueError("Gateway bearer token must contain at least 32 characters")
        self.digest = hashlib.sha256(token.encode()).digest()

    async def verify_token(self, token: str):
        if not hmac.compare_digest(self.digest, hashlib.sha256(token.encode()).digest()):
            return None
        return AccessToken(token=token, client_id="gateway-service", scopes=["tools.read"])


def create_auth(config: Auth):
    if config.mode == "bearer":
        return BearerVerifier(secret(config.tokenEnv))
    from fastmcp.server.auth.providers.azure import AzureProvider

    key = secret("MCP_OAUTH_SIGNING_KEY")
    if len(key) < 32:
        raise ValueError("MCP_OAUTH_SIGNING_KEY must contain at least 32 characters")
    return AzureProvider(
        client_id=secret("ENTRA_CLIENT_ID"),
        client_secret=secret("ENTRA_CLIENT_SECRET"),
        tenant_id=secret("ENTRA_TENANT_ID"),
        base_url=config.publicUrl,
        required_scopes=["tools.read"],
        jwt_signing_key=key,
        allowed_client_redirect_uris=config.allowedRedirectUris,
    )
