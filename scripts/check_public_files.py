"""Reject accidental client configuration in the tracked public source tree."""

import subprocess
import sys
from pathlib import PurePosixPath

PUBLIC_CONFIGS = {
    "examples/gateway.json",
    "pyproject.toml",
    ".github/workflows/test.yml",
}
PRIVATE_DIRECTORIES = {"clients", "config", "configs", "local", "private", "manifests", "infra"}
CONFIG_SUFFIXES = {".json", ".json5", ".jsonl", ".yaml", ".yml", ".toml", ".ini", ".cfg",
                   ".env", ".pem", ".key", ".p12", ".pfx", ".sql", ".sqlite", ".sqlite3", ".db"}


def main():
    entries = subprocess.check_output(["git", "ls-files", "--stage", "-z"]).decode().split("\0")
    rejected = []
    for entry in filter(None, entries):
        metadata, name = entry.split("\t", 1)
        path = PurePosixPath(name)
        lower_parts = {part.lower() for part in path.parts[:-1]}
        local_name = path.name.lower()
        if (metadata.startswith("120000 ")
            or lower_parts & PRIVATE_DIRECTORIES
            or local_name.startswith(".env")
            or ".local." in local_name
            or (path.suffix.lower() in CONFIG_SUFFIXES and name not in PUBLIC_CONFIGS)):
            rejected.append(name)
    if rejected:
        print("Keep client/deployment configuration outside the public repository:", file=sys.stderr)
        print("\n".join(rejected), file=sys.stderr)
        return 1
    print("Public file policy passed; only reviewed configuration examples are tracked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
