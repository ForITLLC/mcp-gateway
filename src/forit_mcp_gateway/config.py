"""Validated administrator configuration; credentials stay in the environment."""

import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


def secret(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Required environment variable is missing: {name}")
    return value


class HeaderAuth(Model):
    envVar: str
    header: str = "Authorization"
    prefix: str = "Bearer "

    @model_validator(mode="after")
    def validate_header(self):
        if not re.fullmatch(r"[A-Za-z0-9-]+", self.header):
            raise ValueError("Invalid credential header")
        if self.header.lower() in {"host", "content-length", "transfer-encoding"}:
            raise ValueError("Reserved credential header")
        return self


class Source(Model):
    namespace: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    baseUrl: str
    specUrl: str
    auth: HeaderAuth | None = None
    readOnly: bool = True
    allowedOperations: list[str] | None = None
    allowInsecureHttp: bool = False

    @model_validator(mode="after")
    def validate_source(self):
        base, spec = urlsplit(self.baseUrl), urlsplit(self.specUrl)
        for url in (base, spec):
            if url.scheme not in ({"https", "http"} if self.allowInsecureHttp else {"https"}):
                raise ValueError("HTTPS is required unless allowInsecureHttp is explicit")
            if not url.hostname or url.username or url.password or url.query or url.fragment:
                raise ValueError("URLs require a host and cannot contain credentials, query or fragment")
        if (base.scheme, base.netloc) != (spec.scheme, spec.netloc):
            raise ValueError("specUrl must use the same origin as baseUrl")
        if not self.readOnly and not self.allowedOperations:
            raise ValueError("Write access requires an explicit allowedOperations list")
        return self


class Auth(Model):
    mode: str = "bearer"
    tokenEnv: str = "MCP_GATEWAY_TOKEN"
    publicUrl: str | None = None
    allowedRedirectUris: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_auth(self):
        if self.mode not in {"bearer", "entra"}:
            raise ValueError("auth.mode must be bearer or entra")
        if self.mode == "entra":
            if not self.publicUrl or not self.publicUrl.startswith("https://"):
                raise ValueError("Entra requires an HTTPS publicUrl")
            if not self.allowedRedirectUris or any(not uri.startswith("https://") or "*" in uri for uri in self.allowedRedirectUris):
                raise ValueError("Entra requires exact HTTPS client redirect URIs")
        return self


class Config(Model):
    name: str = "ForIT MCP Gateway"
    logoUrl: str | None = None
    auth: Auth = Field(default_factory=Auth)
    refreshSeconds: int = Field(default=120, ge=10, le=86400)
    sources: list[Source] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_config(self):
        names = [source.namespace for source in self.sources]
        if len(names) != len(set(names)):
            raise ValueError("Source namespaces must be unique")
        if self.logoUrl and not self.logoUrl.startswith("https://"):
            raise ValueError("Custom logoUrl must use HTTPS")
        return self

    @classmethod
    def load(cls, path: str):
        return cls.model_validate(json.loads(Path(path).read_text()))
