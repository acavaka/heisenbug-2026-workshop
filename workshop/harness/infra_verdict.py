"""Structural infrastructure proof checks; do not establish causal truth."""

import json
import re

KEYS = ("kind", "namespace", "name", "uid")
RESOURCE_KINDS = {"pods": "Pod", "pod": "Pod", "deployments": "Deployment", "deployment": "Deployment",
                  "services": "Service", "service": "Service", "replicasets": "ReplicaSet", "replicaset": "ReplicaSet",
                  "configmaps": "ConfigMap", "configmap": "ConfigMap", "jobs": "Job", "job": "Job"}


def reference(value):
    return isinstance(value, dict) and all(isinstance(value.get(k), str) and value[k].strip() for k in KEYS)


def same(left, right):
    return isinstance(left, dict) and all(left.get(k) == right[k] for k in KEYS)


def quoted(quote, value):
    # Match a JSON fragment in the relevant section, never another object's metadata.
    text = json.dumps(value, ensure_ascii=False)
    if " ".join(quote.split()) in " ".join(text.split()):
        return True
    # k8sgpt emits MarshalIndent: ignore formatting outside quoted JSON strings.
    def tokens(text):
        return re.sub(r'("(?:\\.|[^"\\])*")|\s+', lambda match: match[1] or "", text)
    return tokens(quote) in tokens(text)


def validate_infrastructure(result, grounded):
    errors = []
    resources = result.get("culprit_resources")
    if not isinstance(resources, list) or not all(reference(r) for r in resources):
        return ["culprit_resources must contain kind, namespace, name and uid references"]
    supported = []
    for resource in resources:
        roles = set()
        for entry, obs in grounded:
            if not same(entry.get("resource"), resource):
                continue
            provenance = obs.get("mcp", {})
            if not isinstance(provenance, dict) or provenance.get("server") != "k8sgpt" or provenance.get("is_error"):
                continue
            tool = provenance.get("tool")
            if not isinstance(tool, str) or tool not in {"get-resource", "list-events"} or obs["tool"] != "mcp_k8sgpt_" + tool.replace("-", "_"):
                continue
            if provenance.get("mode") not in {"live", "replay"} or obs["args"].get("namespace") != resource["namespace"]:
                continue
            try:
                payload = json.loads(obs["result"])
            except (ValueError, TypeError):
                continue
            if tool == "get-resource" and entry.get("evidence_role") == "configuration" and isinstance(payload, dict):
                metadata = payload.get("metadata", {})
                resource_type = obs["args"].get("resourceType")
                kind = payload.get("kind") or (RESOURCE_KINDS.get(resource_type) if isinstance(resource_type, str) else None)
                if (isinstance(metadata, dict) and same({**metadata, "kind": kind}, resource)
                        and obs["args"].get("name") == resource["name"]
                        and isinstance(payload.get("spec"), dict) and quoted(entry["quote"], payload["spec"])):
                    roles.add("configuration")
            elif tool == "list-events" and entry.get("evidence_role") == "symptom":
                events = payload.get("items", []) if isinstance(payload, dict) else payload
                if isinstance(events, list):
                    for event in events:
                        if (isinstance(event, dict) and event.get("type") == "Warning"
                                and same(event.get("involvedObject"), resource)
                                and isinstance(event.get("message"), str) and event["message"].strip()
                                and quoted(entry["quote"], {k: event[k] for k in ("reason", "message", "type") if k in event})):
                            roles.add("symptom")
        supported.append(roles)
    if result.get("confidence") == "high" and (not resources or any(r != {"configuration", "symptom"} for r in supported)):
        errors.append("infrastructure high requires observed spec and matching Warning event for every resource UID")
    if result.get("confidence") == "medium" and not any(supported):
        errors.append("infrastructure medium requires a grounded configuration or Warning event for a resource UID")
    return errors
