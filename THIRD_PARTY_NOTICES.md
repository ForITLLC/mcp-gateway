# Third-party software

This application uses FastMCP 3.2.3, distributed under Apache-2.0:

- Source: https://github.com/PrefectHQ/fastmcp
- License: https://github.com/PrefectHQ/fastmcp/blob/main/LICENSE

FastMCP is installed as a dependency; this repository does not vendor or replace its source. The gateway sets its configurable UI logo fallback to cover callback pages in the pinned version. ForIT's original gateway integration is separately maintained here.

HTTPX and other transitive dependencies retain their own licenses and notices, included in their distributions. Installations and container images contain these dependencies; review their metadata when redistributing a packaged deployment.

The bundled `src/forit_mcp_gateway/assets/forit.png` is the ForIT logo, supplied by ForIT LLC. Trademark rights are reserved; its presence does not confer ForIT endorsement of third-party deployments.
