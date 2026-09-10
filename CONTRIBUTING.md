# Contributing

Open an issue describing the behavior you want to change, or submit a focused pull request. Include an example configuration using fictional services and environment variable names. Never include credentials, customer records, production manifests, or internal logs.

Install `.[dev]`, run `python -m pytest -q`, and build with `python -m build`. Changes to authentication, schema filtering, refresh behavior, or upstream request confinement should include a regression test. Keep FastMCP upgrades explicit so provider and login behavior can be verified together.

Keep real client settings outside the checkout in `~/.config/forit-mcp-gateway/clients/`, or in your private deployment repository. Run `python scripts/check_public_files.py` before publishing. Adding a new public configuration example requires explicit review of the allowlist in that script; use fictional data only. Never bypass exclusions to commit client configuration.

Contributions are accepted under this project's Apache-2.0 license. Keep upstream attribution and license notices intact.
