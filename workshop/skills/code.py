"""Read-only source tools bounded to Boutique and order-worker roots."""

from __future__ import annotations

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BOUTIQUE_ROOT = Path(
    os.getenv("BOUTIQUE_ROOT") or REPO_ROOT / "microservices-demo"
).expanduser().resolve()
ORDER_WORKER_ROOT = Path(
    os.getenv("ORDER_WORKER_ROOT") or REPO_ROOT / "workshop/services/order-worker"
).expanduser().resolve()
WORKER_PREFIX = Path("workshop/services/order-worker")

MAX_FILE_CHARS = 12000
MAX_HITS = 40


def _source_roots(root: str | None = None) -> dict[str, Path]:
    roots = {"boutique": BOUTIQUE_ROOT.resolve(), "order-worker": ORDER_WORKER_ROOT.resolve()}
    if root is not None:
        if root not in roots:
            raise ValueError(f"Unknown source root: {root!r}; use boutique or order-worker")
        return {root: roots[root]}
    return roots


def _contained_path(source_root: Path, path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(source_root):
        raise ValueError(f"Path escapes source root: {path}")
    return resolved


def _locate_code_path(path: str, root: str | None) -> tuple[str, Path]:
    roots = _source_roots(root)
    relative = Path(path)
    if relative.is_absolute():
        raise ValueError(f"Source path must be relative: {path}")
    parts = relative.parts
    for prefix in (WORKER_PREFIX.parts, ("..",) + WORKER_PREFIX.parts):
        if parts[:len(prefix)] == prefix:
            if root is not None and root != "order-worker":
                raise ValueError(f"Path does not belong to source root {root}: {path}")
            root = "order-worker"
            relative = Path(*parts[len(prefix):])
            break
    else:
        if parts and parts[0] == "workshop":
            raise ValueError(f"Only the order-worker source subtree is allowed under workshop: {path}")
    name = root or "boutique"
    source_root = roots[name]
    return name, _contained_path(source_root, source_root / relative)


def resolve_code_path(path: str, root: str | None = None) -> Path:
    """Resolve a source path within either allowed root, or raise ValueError.

    Boutique paths remain relative to BOUTIQUE_ROOT. Worker paths use the
    canonical workshop/services/order-worker prefix, its legacy ../ prefix,
    or an unprefixed filename with root="order-worker".
    """
    return _locate_code_path(path, root)[1]


def _canonical_location(name: str, path: Path) -> str:
    relative = path.relative_to(_source_roots(name)[name])
    return (WORKER_PREFIX / relative).as_posix() if name == "order-worker" else relative.as_posix()


def code_search(pattern: str, glob: str = "*.go", root: str | None = None) -> str:
    """Regex search in both source roots, or one selected root (default *.go)."""
    try:
        roots = _source_roots(root)
    except ValueError as exc:
        return str(exc)
    if not glob or Path(glob).is_absolute() or ".." in Path(glob).parts:
        return f"Invalid glob: {glob!r}; use a relative pattern without parent traversal"
    try:
        rx = re.compile(pattern)
    except re.error as exc:
        return f"Invalid regex: {exc}"

    hits: list[str] = []
    available = False
    for name, source_root in roots.items():
        if not source_root.is_dir():
            continue
        available = True
        search_root = source_root / "src" if name == "boutique" else source_root
        if not search_root.exists():
            search_root = source_root
        try:
            search_root = _contained_path(source_root, search_root)
        except ValueError:
            continue
        try:
            candidates = search_root.rglob(glob)
            for candidate in candidates:
                if any(part in {".git", "vendor", "node_modules"} for part in candidate.relative_to(source_root).parts):
                    continue
                try:
                    path = _contained_path(source_root, candidate)
                    if not path.is_file():
                        continue
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except (OSError, ValueError):
                    continue
                for i, line in enumerate(text.splitlines(), 1):
                    if rx.search(line):
                        hits.append(f"{_canonical_location(name, path)}:{i}: {line.strip()}")
                        if len(hits) >= MAX_HITS:
                            return "\n".join(hits) + f"\n... truncated at {MAX_HITS} hits"
        except (OSError, ValueError, NotImplementedError) as exc:
            return f"Invalid glob: {glob!r}: {exc}"
    if not available:
        return "Source roots not found: " + ", ".join(f"{name}={path}" for name, path in roots.items())
    return "\n".join(hits) if hits else f"No matches for {pattern!r} in {glob}"


def read_file(path: str, start_line: int = 1, max_lines: int = 120, root: str | None = None) -> str:
    """Read a file within one allowed source root and emit its canonical location."""
    try:
        name, file_path = _locate_code_path(path, root)
    except ValueError as exc:
        return str(exc)
    if not file_path.is_file():
        return f"File not found: {path} (root={name})"
    lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    start = max(1, int(start_line))
    end = min(len(lines), start + max(1, int(max_lines)) - 1)
    chunk = [f"{i}: {lines[i - 1]}" for i in range(start, end + 1)]
    text = "\n".join(chunk)
    if len(text) > MAX_FILE_CHARS:
        text = text[:MAX_FILE_CHARS] + "\n... truncated"
    return f"File: {_canonical_location(name, file_path)}\n" + (text or "(empty)")


CODE_TOOLS_IMPL = {
    "code_search": code_search,
    "read_file": read_file,
}

CODE_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "code_search",
            "description": (
                "Search Boutique and order-worker source code by regex. "
                "Useful queries: priceCache, cache hit, UpdateProductPrice, GetProduct, PRICE_CACHE."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "glob": {
                        "type": "string",
                        "description": "Filename glob, default *.go (use *.py for Python services)",
                    },
                    "root": {
                        "type": "string",
                        "enum": ["boutique", "order-worker"],
                        "description": "Optional source root; omitted searches both roots",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file within Boutique or order-worker source roots (relative path).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "e.g. src/productcatalogservice/product_catalog.go or workshop/services/order-worker/workflows.py",
                    },
                    "start_line": {"type": "integer"},
                    "max_lines": {"type": "integer"},
                    "root": {
                        "type": "string",
                        "enum": ["boutique", "order-worker"],
                        "description": "Optional source root; use order-worker for unprefixed Python filenames",
                    },
                },
                "required": ["path"],
            },
        },
    },
]
