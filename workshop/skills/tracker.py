"""Skills: mock tracker (markdown fixtures)."""

from pathlib import Path
import re

from skills._fixtures import read_document

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
TRACKER_DIR = FIXTURES / "tracker"


def tracker_get(bug_id: str) -> str:
    """Read a bug/incident report by id, e.g. BUG-1024."""
    if not isinstance(bug_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", bug_id):
        return "TOOL ERROR: report id must contain only letters, digits, underscores or hyphens"
    return read_document(TRACKER_DIR, f"{bug_id}.md")


def tracker_list() -> str:
    files = sorted(TRACKER_DIR.glob("*.md"))
    if not files:
        return "No tracker reports found"
    return "\n".join(f.stem for f in files)


TRACKER_TOOLS_IMPL = {
    "tracker_get": tracker_get,
    "tracker_list": tracker_list,
}

TRACKER_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "tracker_get",
            "description": "Read a bug or incident report from the tracker by id (e.g. BUG-1024).",
            "parameters": {
                "type": "object",
                "properties": {
                    "bug_id": {
                        "type": "string",
                        "description": "Report id without path, e.g. BUG-1024",
                    }
                },
                "required": ["bug_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tracker_list",
            "description": "List available tracker report ids.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]
