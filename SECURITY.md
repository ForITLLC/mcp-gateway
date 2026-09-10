# Security

The 0.1.x release line receives security fixes. Report vulnerabilities through this repository's **Security → Report a vulnerability** page. Do not post exploitable details or secrets in public issues. Include the affected version, a fictional reproduction, and the impact you observed.

Deploy one gateway per trust boundary with scoped upstream credentials and HTTPS. Administrator configuration and upstream schemas are trusted inputs. All authenticated clients share the deployment's selected operations and upstream identity. See the README for the authorization and single-replica limits of this release.
