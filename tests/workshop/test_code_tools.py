"""Local regressions for bounded, read-only source access."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "workshop" / "skills" / "code.py"


def load_code_tools():
    spec = importlib.util.spec_from_file_location("qai_code_tools_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CodeToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name).resolve()
        self.boutique = self.repo / "microservices-demo"
        self.worker = self.repo / "workshop" / "services" / "order-worker"
        self.boutique.joinpath("src").mkdir(parents=True)
        self.worker.mkdir(parents=True)
        self.boutique.joinpath("src", "catalog.py").write_text(
            "# synthetic fixture\nshared_marker = 'catalog'\n", encoding="utf-8"
        )
        self.boutique.joinpath("src", "catalog.go").write_text(
            'package catalog\n// shared_marker\n', encoding="utf-8"
        )
        self.worker.joinpath("workflows.py").write_text(
            "# synthetic fixture\nshared_marker = 'worker'\n", encoding="utf-8"
        )
        self.worker.joinpath("synthetic.go").write_text(
            "package worker\n// shared_marker\n", encoding="utf-8"
        )
        self.secret = self.repo / "workshop" / ".env"
        self.secret.write_text("secret_marker = 'synthetic-only'\n", encoding="utf-8")
        self.code = load_code_tools()
        for name, value in (("BOUTIQUE_ROOT", self.boutique), ("ORDER_WORKER_ROOT", self.worker)):
            patcher = patch.object(self.code, name, value, create=True)
            patcher.start()
            self.addCleanup(patcher.stop)

    def resolve(self, path, root=None):
        resolver = getattr(self.code, "resolve_code_path", None)
        self.assertTrue(callable(resolver), "resolve_code_path API is missing")
        return resolver(path, root=root)

    def test_boutique_relative_paths_keep_numbered_content(self):
        result = self.code.read_file("src/catalog.py", start_line=2, max_lines=1)
        self.assertIn("2: shared_marker = 'catalog'", result)

    def test_worker_canonical_and_legacy_paths_read_same_source(self):
        canonical = self.code.read_file("workshop/services/order-worker/workflows.py")
        legacy = self.code.read_file("../workshop/services/order-worker/workflows.py")
        self.assertIn("2: shared_marker = 'worker'", canonical)
        self.assertIn("File: workshop/services/order-worker/workflows.py", canonical)
        self.assertEqual(canonical, legacy)

    def test_explicit_worker_root_reads_unprefixed_file(self):
        result = self.code.read_file("workflows.py", root="order-worker", start_line=2)
        self.assertIn("2: shared_marker = 'worker'", result)

    def test_resolver_selects_only_the_two_explicit_roots(self):
        expected_worker = self.worker / "workflows.py"
        self.assertEqual(self.resolve("src/catalog.py"), self.boutique / "src/catalog.py")
        self.assertEqual(self.resolve("workshop/services/order-worker/workflows.py"), expected_worker)
        self.assertEqual(self.resolve("../workshop/services/order-worker/workflows.py"), expected_worker)
        self.assertEqual(self.resolve("workflows.py", root="order-worker"), expected_worker)

    def test_unknown_root_is_rejected(self):
        with self.assertRaises(ValueError):
            self.resolve("src/catalog.py", root="repository")
        self.assertIn("Unknown source root", self.code.read_file("src/catalog.py", root="repository"))
        self.assertIn("Unknown source root", self.code.code_search("shared_marker", root="repository"))

    def test_explicit_root_cannot_be_overridden_by_worker_prefix(self):
        with self.assertRaises(ValueError):
            self.resolve("workshop/services/order-worker/workflows.py", root="boutique")

    def test_paths_cannot_escape_to_workshop_env_or_arbitrary_repository_files(self):
        cases = [
            ("../workshop/.env", None),
            ("workshop/.env", None),
            ("workshop/services/order-worker/../../.env", None),
            ("../../.env", "order-worker"),
            (str(self.secret), None),
        ]
        for path, root in cases:
            with self.subTest(path=path, root=root), self.assertRaises(ValueError):
                self.resolve(path, root=root)

    def test_read_symlink_cannot_escape_either_root(self):
        for source_root, root, rel in (
            (self.boutique / "src", "boutique", "src/escape.py"),
            (self.worker, "order-worker", "escape.py"),
        ):
            source_root.joinpath("escape.py").symlink_to(self.secret)
            with self.subTest(root=root), self.assertRaises(ValueError):
                self.resolve(rel, root=root)
            self.assertNotIn("synthetic-only", self.code.read_file(rel, root=root))

    def test_search_without_root_searches_both_and_emits_canonical_locations(self):
        result = self.code.code_search("shared_marker", glob="*.py")
        self.assertIn("src/catalog.py:2: shared_marker = 'catalog'", result)
        self.assertIn("workshop/services/order-worker/workflows.py:2: shared_marker = 'worker'", result)

    def test_search_root_selector_limits_matches(self):
        worker_result = self.code.code_search("shared_marker", glob="*.py", root="order-worker")
        boutique_result = self.code.code_search("shared_marker", glob="*.py", root="boutique")
        self.assertIn("workshop/services/order-worker/workflows.py:2:", worker_result)
        self.assertNotIn("catalog", worker_result)
        self.assertIn("src/catalog.py:2:", boutique_result)
        self.assertNotIn("workflows", boutique_result)

    def test_default_search_glob_remains_go(self):
        result = self.code.code_search("shared_marker")
        self.assertIn("src/catalog.go:2:", result)
        self.assertIn("workshop/services/order-worker/synthetic.go:2:", result)
        self.assertNotIn(".py:", result)

    def test_search_skips_symlink_files_outside_roots(self):
        self.boutique.joinpath("src", "escape.py").symlink_to(self.secret)
        self.worker.joinpath("escape.py").symlink_to(self.secret)
        self.assertNotIn("synthetic-only", self.code.code_search("secret_marker", glob="*.py"))

    def test_search_rejects_traversal_globs(self):
        for glob in ("../*.py", "**/../../*.py", str(self.secret)):
            with self.subTest(glob=glob):
                self.assertIn("Invalid glob", self.code.code_search("secret_marker", glob=glob))


class RepositorySourceTests(unittest.TestCase):
    def test_default_roots_are_relative_to_repository_not_home_or_current_directory(self):
        with patch.dict(os.environ, {"BOUTIQUE_ROOT": "", "ORDER_WORKER_ROOT": ""}):
            code = load_code_tools()
        self.assertEqual(code.BOUTIQUE_ROOT, REPO_ROOT / "microservices-demo")
        self.assertEqual(getattr(code, "ORDER_WORKER_ROOT", None), REPO_ROOT / "workshop/services/order-worker")

    def test_actual_worker_source_is_readable_without_importing_or_running_worker(self):
        with patch.dict(os.environ, {"BOUTIQUE_ROOT": "", "ORDER_WORKER_ROOT": ""}):
            code = load_code_tools()
        result = code.read_file("workshop/services/order-worker/workflows.py")
        self.assertIn("File: workshop/services/order-worker/workflows.py", result)
        self.assertIn(": class OrderSaga:", result)
        self.assertIn(":             maximum_attempts=0 if inp.inject_ship_fail else 3,", result)


if __name__ == "__main__":
    unittest.main()
