"""OpenAPI sources with bounded credentials and replaceable schema providers."""

import asyncio
import base64
import hashlib
import logging
from contextlib import asynccontextmanager, suppress
from importlib.resources import files
from urllib.parse import unquote, urlsplit

import httpx
from fastmcp import FastMCP
from fastmcp.server.providers import AggregateProvider
from fastmcp.utilities import ui
from mcp.types import Icon
from starlette.responses import JSONResponse

from . import __version__
from .auth import create_auth
from .config import Config, Source, secret
from .schema import prepare_schema

log = logging.getLogger(__name__)


class SourceState:
    def __init__(self, source: Source, *, transport=None):
        self.source = source
        self.slot = AggregateProvider()
        self.etag = None
        self.digest = None
        self.ready = False
        self.credential = None
        if source.auth:
            self.credential = source.auth.prefix + secret(source.auth.envVar)
        self.client = httpx.AsyncClient(
            base_url=source.baseUrl.rstrip("/") + "/",
            timeout=30,
            follow_redirects=False,
            transport=transport,
            event_hooks={"request": [self.guard_request]},
        )

    async def guard_request(self, request: httpx.Request):
        base, target = urlsplit(self.source.baseUrl), urlsplit(str(request.url))
        if (base.scheme, base.netloc) != (target.scheme, target.netloc):
            raise ValueError("Upstream request escaped its configured origin")
        path = unquote(target.path)
        root = unquote(base.path).rstrip("/")
        if "\\" in path or any(part in {".", ".."} for part in path.split("/")):
            raise ValueError("Unsafe upstream path")
        if str(request.url) != self.source.specUrl and root and path != root and not path.startswith(root + "/"):
            raise ValueError("Upstream request escaped its configured base path")
        if self.source.auth:
            request.headers[self.source.auth.header] = self.credential

    async def refresh(self):
        try:
            response = await self.client.get(
                self.source.specUrl,
                headers={"If-None-Match": self.etag} if self.etag else {},
            )
            if response.status_code == 304 and self.digest:
                self.ready = True
                return
            response.raise_for_status()
            digest = hashlib.sha256(response.content).hexdigest()
            if digest != self.digest:
                spec = prepare_schema(response.json(), self.source)
                server = FastMCP.from_openapi(spec, client=self.client, name=self.source.namespace)
                replacement = AggregateProvider()
                replacement.add_provider(server)
                # No await during replacement: clients see one complete generation.
                self.slot.providers[:] = replacement.providers
                self.digest = digest
            self.etag = response.headers.get("etag")
            self.ready = True
        except Exception as exc:
            self.ready = False
            log.warning("Schema refresh failed for %s (%s)", self.source.namespace, type(exc).__name__)


def create_gateway(config: Config, *, transport=None):
    auth = create_auth(config.auth)
    states = [SourceState(source, transport=transport) for source in config.sources]
    logo = config.logoUrl or "data:image/png;base64," + base64.b64encode(
        files("forit_mcp_gateway").joinpath("assets/forit.png").read_bytes()
    ).decode()
    # FastMCP 3.2.3 callback error pages omit the server icon metadata.
    # One gateway per process also brands that fallback with the configured logo.
    from .login_branding import install_login_branding
    install_login_branding(
        name=config.name,
        logo_url=config.logoUrl or "https://www.forit.io/images/forit-hex-only.png",
        support_email=config.supportEmail,
    )

    async def refresh_all():
        await asyncio.gather(*(state.refresh() for state in states))

    async def poll():
        while True:
            await asyncio.sleep(config.refreshSeconds)
            await refresh_all()

    @asynccontextmanager
    async def lifespan(server):
        await refresh_all()
        task = asyncio.create_task(poll())
        try:
            yield {}
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            await asyncio.gather(*(state.client.aclose() for state in states))

    gateway = FastMCP(config.name, version=__version__, icons=[Icon(src=logo)],
                      auth=auth, lifespan=lifespan, mask_error_details=True)
    for state in states:
        gateway.add_provider(state.slot, namespace=state.source.namespace)

    @gateway.custom_route("/health", methods=["GET"])
    async def health(request):
        ready = all(state.ready for state in states)
        return JSONResponse({"status": "ok" if ready else "degraded",
                             "sources": len(states),
                             "ready": sum(state.ready for state in states)},
                            status_code=200 if ready else 503)

    return gateway
