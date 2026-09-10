# ForIT MCP Gateway

An authenticated, branded gateway that turns selected OpenAPI operations into MCP tools. Maintained by **ForIT LLC**, built on [FastMCP](https://github.com/PrefectHQ/fastmcp).

This is the public gateway application, released with a fresh history and a fictional local demo. It does not include ForIT's private connectors, customer configurations, or deployment infrastructure. It is independently maintained; it is not an official FastMCP distribution.

## What it does

- Combines OpenAPI 3 services under separate tool namespaces.
- Defaults to GET/HEAD operations; writes require an explicit operation allowlist.
- Authenticates service clients with a bearer token, or interactive clients through Microsoft Entra OAuth.
- Uses the ForIT mark throughout OAuth login, including callback error pages; supports your own name and HTTPS logo.
- Refreshes schemas without restarting, using ETags and content hashes. Failed refreshes retain the last working tools and mark readiness degraded.
- Keeps configured upstream credential headers fixed, disables redirects, and confines requests to the configured origin and API base path.

The value is a small, reviewable gateway layer around FastMCP: consistent authentication, branding, API selection, and schema maintenance. FastMCP supplies the MCP protocol, OpenAPI conversion, and OAuth machinery.

## Run the demo

Requires Python 3.11 or newer. From a checkout:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python examples/catalog_api.py
```

In a second terminal, activate the same environment and start the gateway:

```sh
. .venv/bin/activate
export MCP_GATEWAY_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
forit-mcp-gateway --config examples/gateway.json
```

The endpoint is `http://127.0.0.1:8000/mcp`. Configure an MCP client for Streamable HTTP with an `Authorization: Bearer <your MCP_GATEWAY_TOKEN>` header. The token stays in the gateway terminal's environment; provide it to your client through its secret settings.

To check the demo from that environment:

```sh
curl http://127.0.0.1:8000/health
python examples/check_client.py
```

You should see `catalog_list_items` and `catalog_get_item`. The catalog's POST operation is excluded. This demo binds to loopback and explicitly permits local HTTP. Use HTTPS for a network deployment.

## Configure your APIs

Use an administrator-owned JSON file:

```json
{
  "name": "Your MCP Gateway",
  "logoUrl": "https://www.example.com/logo.png",
  "auth": {"mode": "bearer", "tokenEnv": "MCP_GATEWAY_TOKEN"},
  "refreshSeconds": 120,
  "sources": [{
    "namespace": "catalog",
    "baseUrl": "https://api.example.com/v1",
    "specUrl": "https://api.example.com/openapi.json",
    "auth": {"envVar": "CATALOG_API_KEY", "header": "Authorization", "prefix": "Bearer "},
    "readOnly": true,
    "allowedOperations": ["listItems", "getItem"]
  }]
}
```

Set `CATALOG_API_KEY` and `MCP_GATEWAY_TOKEN` through your secret manager or environment. Missing secrets fail startup. Bearer tokens must have at least 32 characters; generate them randomly. Bearer mode represents one service identity and has no user login, expiration, or individual revocation. Rotate the environment token and restart to revoke it.

### Keep client configuration local

Keep all real client configuration in one directory **outside the public repository**:

```sh
install -d -m 700 "$HOME/.config/forit-mcp-gateway/clients"
# Save your administrator configuration as clients/<client-name>.json there.
forit-mcp-gateway --config "$HOME/.config/forit-mcp-gateway/clients/<client-name>.json"
```

Use one JSON file per client and environment, containing environment-variable references rather than secret values. Protect each file with mode `600`. Keep credentials in your secret manager or process environment. The CLI does not automatically load `.env` files. For containers, mount the selected JSON file read-only at `/config/gateway.json`; supply secrets at runtime.

Existing production configurations may instead remain in a dedicated private deployment repository as their single source of truth. Do not copy those files or that repository's history into this public repository. The only public API configuration is `examples/gateway.json`, which uses the fictional local catalog.

Local configuration folders and credential files are excluded from Git, Docker contexts, and package builds. CI rejects tracked deployment folders and unreviewed configuration files, including files added with `git add -f`. These controls support review; they do not replace checking file contents for customer data or secrets before publishing.

`allowedOperations` matches OpenAPI `operationId` values. Omitting it exposes all GET/HEAD operations; an empty list exposes none. Set `readOnly: false` **and** supply a nonempty allowlist to expose writes. An operation changing from GET to POST will disappear under read-only configuration. HTTP method filtering cannot guarantee an upstream GET has no side effects.

Specifications must be JSON OpenAPI 3 documents with unique operation IDs. Embedded `servers` entries are removed; the configured `baseUrl` controls routing. Only references into local `#/components/` are accepted; external references and path-item references are rejected. Spec and API URLs must share an origin. Redirects are not followed. Schemas and configuration must come from trusted administrators; this is not a sandbox for arbitrary API definitions.

## Microsoft Entra login

Set `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET`, and a random, persistent `MCP_OAUTH_SIGNING_KEY` of at least 32 characters. Configure authentication as:

```json
{
  "mode": "entra",
  "publicUrl": "https://gateway.example.com",
  "allowedRedirectUris": ["https://client.example.com/oauth/callback"]
}
```

In your tenant, register a single-tenant application, expose the delegated `tools.read` scope under its default `api://<client-id>` identifier, and register `https://gateway.example.com/auth/callback` as the application's web redirect URI. Use each MCP client's actual callback address in `allowedRedirectUris`; wildcards are rejected. Configure enterprise application assignment and consent according to the audience you intend to admit. See [FastMCP's Azure provider documentation](https://gofastmcp.com/servers/auth/providers/azure) for the underlying provider's setup.

Serve the gateway behind HTTPS and persist the signing key across restarts. FastMCP uses an encrypted local file store for OAuth state; set `FASTMCP_HOME` to a private, writable persistent directory and preserve it across container replacements. Use a single replica for this initial release. Multi-replica OAuth and live Entra tenant configuration are not covered by the automated demo tests. One gateway per process is required because the pinned FastMCP version uses a process-wide fallback logo on some error pages.

## Authorization and tenancy

Run a separate deployment and narrowly scoped upstream credentials for each trust boundary. Every authenticated client of a deployment receives the same selected tool surface and acts with that deployment's upstream credentials. This release does **not** implement per-user upstream impersonation, row-level access controls, or isolated tenants inside one process. Namespace names and the OAuth `tools.read` scope are not data-access boundaries; the scope grants access to the configured surface, including explicitly allowed writes.

Tool results can contain sensitive upstream data. Apply access restrictions at the source and configure your hosting logs accordingly. The public `/health` endpoint exposes only aggregate readiness counts. It returns 503 if any source's most recent refresh failed, even when its last working tools remain usable; this is readiness, not a liveness/restart signal. Initial source failures are retried on the refresh interval. Clients may need to refresh their tool list after a schema update.

## Build and test

```sh
python -m pytest -q
python -m build
docker build -t forit-mcp-gateway .
```

The Docker image runs as a non-root user. Mount your configuration at `/config/gateway.json`, provide its referenced secrets through your deployment environment, and expose port 8000 behind TLS. No container registry or PyPI package is published as part of the initial source release.

## License and branding

Code is licensed under [Apache-2.0](LICENSE). See [NOTICE](NOTICE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for attribution. The bundled ForIT logo is a ForIT trademark; the code license does not grant trademark rights or endorsement. Configure your own logo when presenting a modified deployment as your own product.

Contributions: [CONTRIBUTING.md](CONTRIBUTING.md). Vulnerability reporting: [SECURITY.md](SECURITY.md).
