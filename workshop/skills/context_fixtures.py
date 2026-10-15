"""Skills: wiki / testops / github markdown fixtures."""

from __future__ import annotations

from pathlib import Path

from skills._fixtures import read_document

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def wiki_get(page: str = "runbook-map.md") -> str:
    """Read a wiki fixture page (filename under fixtures/wiki/)."""
    return read_document(FIXTURES / "wiki", page)


def testops_get(page: str = "runs.md") -> str:
    """Read TestOps fixture page under fixtures/testops/."""
    return read_document(FIXTURES / "testops", page)


def github_release_notes(name: str = "release-v0.10.0-workshop.md") -> str:
    """Read GitHub release notes fixture under fixtures/github/."""
    return read_document(FIXTURES / "github", name)


CONTEXT_TOOLS_IMPL = {
    "wiki_get": wiki_get,
    "testops_get": testops_get,
    "github_release_notes": github_release_notes,
}

CONTEXT_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "wiki_get",
            "description": "Read workshop wiki fixture (default runbook-map.md).",
            "parameters": {
                "type": "object",
                "properties": {"page": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "testops_get",
            "description": "Read TestOps fixture (default runs.md).",
            "parameters": {
                "type": "object",
                "properties": {"page": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_release_notes",
            "description": "Read GitHub release notes fixture.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
            },
        },
    },
]
