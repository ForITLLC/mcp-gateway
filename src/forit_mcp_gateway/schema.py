"""Reduce an OpenAPI document before FastMCP sees its operations."""

from copy import deepcopy

from .config import Source

METHODS = {"get", "head", "post", "put", "patch", "delete", "options", "trace"}


def prepare_schema(document: dict, source: Source) -> dict:
    if not isinstance(document, dict) or not str(document.get("openapi", "")).startswith("3."):
        raise ValueError("An OpenAPI 3 document is required")
    result = deepcopy(document)

    def sanitize(value):
        if isinstance(value, dict):
            ref = value.get("$ref")
            if ref is not None and (not isinstance(ref, str) or not ref.startswith("#/components/")):
                raise ValueError("Only local component references are supported")
            value.pop("servers", None)
            for child in value.values():
                sanitize(child)
        elif isinstance(value, list):
            for child in value:
                sanitize(child)

    sanitize(result)
    paths = result.get("paths")
    if not isinstance(paths, dict):
        raise ValueError("OpenAPI paths must be an object")
    filtered = {}
    seen = set()
    for path, item in paths.items():
        if not path.startswith("/") or path.startswith("//") or "$ref" in item:
            raise ValueError("Unsupported OpenAPI path")
        kept = {}
        for method, operation in item.items():
            if method not in METHODS:
                continue
            if source.readOnly and method not in {"get", "head"}:
                continue
            operation_id = operation.get("operationId")
            if not operation_id or operation_id in seen:
                raise ValueError("Exposed operations require unique operationId values")
            seen.add(operation_id)
            if source.allowedOperations is not None and operation_id not in source.allowedOperations:
                continue
            kept[method] = operation
        if kept:
            if "parameters" in item:
                kept["parameters"] = item["parameters"]
            filtered[path] = kept
    result["paths"] = filtered
    result.pop("webhooks", None)
    return result
