"""Read fixture documents without crossing the selected source directory."""

from pathlib import Path


def read_document(directory: Path, name: str) -> str:
    if not isinstance(name, str) or not name:
        return "TOOL ERROR: fixture name must be a nonempty relative path"
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts or "\\" in name:
        return "TOOL ERROR: fixture path must stay within its source directory"
    root = directory.resolve()
    try:
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            return "TOOL ERROR: fixture path escapes its source directory"
        if path.suffix != ".md" or not path.is_file():
            return f"TOOL ERROR: fixture document not found: {name}"
        return path.read_text(encoding="utf-8")
    except (OSError, ValueError, RuntimeError, UnicodeError) as exc:
        return f"TOOL ERROR: cannot read fixture document: {exc}"
