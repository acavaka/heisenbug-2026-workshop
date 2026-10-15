"""The same bounded diagnostic surface for the harness and native MCP gateway."""

from copy import deepcopy

from jsonschema import Draft202012Validator

ALLOWED_TOOLS = {"analyze", "list-resources", "get-resource", "list-events", "get-logs"}
RESOURCE_TYPES = ["pod", "pods", "deployment", "deployments", "service", "services",
                  "replicaset", "replicasets", "configmap", "configmaps", "job", "jobs"]
PARAMETERS = {
    "analyze": {"namespace", "explain", "filters"},
    "list-resources": {"namespace", "resourceType", "labelSelector"},
    "get-resource": {"namespace", "resourceType", "name"},
    "list-events": {"namespace", "involvedObjectName", "involvedObjectKind", "limit"},
    "get-logs": {"namespace", "podName", "container", "previous", "tailLines", "sinceSeconds"},
}


def restrict_schema(name: str, schema: dict, namespace: str) -> dict:
    """Narrow the discovered schema; never invent access absent upstream."""
    if name not in ALLOWED_TOOLS:
        raise ValueError(f"MCP tool is not allowed: {name}")
    schema = deepcopy(schema)
    props = schema.get("properties", {})
    if schema.get("type") != "object" or "namespace" not in props:
        raise ValueError(f"Unsupported upstream schema for {name}")
    props = {key: value for key, value in props.items() if key in PARAMETERS[name]}
    props["namespace"] = {"type": "string", "enum": [namespace]}
    if "resourceType" in props:
        props["resourceType"] = {"type": "string", "enum": RESOURCE_TYPES}
    if name == "analyze":
        props["explain"] = {"type": "boolean", "const": False, "default": False}
        props["filters"] = {"type": "array", "items": {"type": "string", "enum": ["Pod", "Deployment", "Service"]}, "minItems": 1}
    for key in ("limit", "tailLines", "sinceSeconds"):
        if key in props:
            props[key] = {"type": "integer", "minimum": 1, "maximum": 3600 if key == "sinceSeconds" else 500}
    schema.update(properties=props, additionalProperties=False,
                  required=sorted(set(schema.get("required", [])) | {"namespace"}))
    Draft202012Validator.check_schema(schema)
    return schema


def validate_arguments(name: str, arguments: dict, schemas: dict[str, dict]) -> dict:
    if name not in schemas:
        raise ValueError(f"MCP tool is not allowed or not discovered: {name}")
    if not isinstance(arguments, dict):
        raise ValueError("MCP arguments must be a JSON object")
    Draft202012Validator(schemas[name]).validate(arguments)
    effective = dict(arguments)
    if name == "analyze":
        effective["explain"] = False
        effective.setdefault("filters", ["Pod", "Deployment", "Service"])
    return effective
