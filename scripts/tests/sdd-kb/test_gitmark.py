# /// script
# requires-python = ">=3.10"
# dependencies = ["PyYAML==6.0.3", "Markdown>=3.7,<4"]
# ///
"""Ontoship regression suite plus sdd-kb portability checks; run with uv --script."""
import importlib.util
import subprocess
import sys
sys.dont_write_bytecode = True
import tempfile
import textwrap
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "skills/sdd-kb/scripts/gitmark.py"
spec = importlib.util.spec_from_file_location("gitmark", SCRIPT)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

OKF_DOC = textwrap.dedent("""\
    ---
    node_type: service          # REQUIRED — comment must not leak into the value
    title: "Billing: overview"
    service: [billing, api]
    links:
      documents: [../../src/billing]
      depends_on:
        - ../reference/arch.md
    generated: { by: claude-code/opus-5-5, at: 2026-09-27T22:53:05Z }
    verified:
      - { by: process:validate-format, at: 2026-09-28T09:01:00Z }
      - by: human:alice
        at: 2026-09-28T09:00:00Z
    stale_after: 2026-09-23T00:00:00Z
    notes: |
      line one
      line two
    ---
    # Billing
    """)


def write(root: Path, rel: str, text: str):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(text), encoding="utf-8")


class Frontmatter(unittest.TestCase):
    def test_yaml_and_mini_parser_agree(self):
        full = g.parse_frontmatter(OKF_DOC)
        mini = g._mini_yaml(g.split_frontmatter(OKF_DOC)[0])
        self.assertEqual(full, mini)

    def test_fields(self):
        fm = g._mini_yaml(g.split_frontmatter(OKF_DOC)[0])
        self.assertEqual(fm["node_type"], "service")
        self.assertEqual(fm["title"], "Billing: overview")
        self.assertEqual(g.fm_links(fm), [("documents", "../../src/billing"),
                                          ("depends_on", "../reference/arch.md")])
        self.assertEqual(g.trust_tier(fm), "human")
        self.assertTrue(g.is_stale(fm))
        self.assertEqual(fm["notes"], "line one\nline two")

    def test_okf_type_alias_and_trust_tiers(self):
        self.assertEqual(g.node_type_of({"type": "Playbook"}), "Playbook")
        self.assertEqual(g.trust_tier({}), "unverified")
        self.assertEqual(g.trust_tier({"verified": {"by": "process:ci", "at": "x"}}), "machine")

    def test_not_quite_yaml_falls_back(self):
        self.assertEqual(g.parse_frontmatter("---\ntitle: a: b\nnode_type: plan\n---\n"),
                         {"title": "a: b", "node_type": "plan"})


class Search(unittest.TestCase):
    def test_stem_and_stopwords(self):
        self.assertEqual(g.stem("деплоймента"), "деплоймент")
        self.assertEqual(g.query_terms("Как задеплоить cache-router на стенд?"),
                         ["задеплоить", "cache-router", "стенд"])


class Repo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = self.root = Path(self.tmp.name)
        write(r, "docs/README.md", "# Docs\n- [Arch](reference/arch.md)\n")
        write(r, "docs/reference/README.md", "# Ref\n")
        write(r, "docs/reference/arch.md", """\
            ---
            node_type: reference
            title: Architecture
            description: How requests flow from the gateway to the billing service.
            status: deprecated
            ---
            # Architecture
            Gateway forwards to billing.
            """)
        write(r, "docs/reference/arch2.md", """\
            ---
            node_type: reference
            title: Architecture v2
            status: active
            links:
              supersedes: [arch.md]
              documents: [../../src/missing.py]
            ---
            # Architecture v2
            Gateway forwards to billing via the queue. See [old](arch.md) and [gone](nope.md).
            """)
        write(r, "notes/scratch.md", "# Scratch\nTODO: ask about billing.\n")
        write(r, "vendor-ish/lib.md", "# Vendored\nbilling gateway\n")
        write(r, ".gitignore", "vendor-ish/\n")
        subprocess.run(["git", "init", "-q", str(r)], check=True, shell=False)

    def tearDown(self):
        self.tmp.cleanup()

    def test_discovery_respects_gitignore_and_gitmarkignore(self):
        write(self.root, ".gitmarkignore", "notes\n")
        rels = {p.relative_to(self.root).as_posix() for p in g.iter_md(self.root)}
        self.assertNotIn("vendor-ish/lib.md", rels)
        self.assertNotIn("notes/scratch.md", rels)
        self.assertIn("docs/reference/arch2.md", rels)

    def test_search_prefers_typed_live_doc(self):
        g.cmd_index(self.root)
        res = g.cmd_search(self.root, "billing gateway", 5)
        self.assertEqual(res[0]["path"], "docs/reference/arch2.md")
        self.assertEqual(res[0]["node_type"], "reference")
        only_dep = g.cmd_search(self.root, "billing", 5, statuses=["deprecated"])
        self.assertEqual([r["path"] for r in only_dep], ["docs/reference/arch.md"])
        self.assertEqual(g.cmd_search(self.root, "billing", 5, scope="history"), [])

    def test_lint_typed_links(self):
        codes = {(i[1], i[2]) for i in g.cmd_lint(self.root)["issues"]}
        self.assertNotIn(("I6", "docs/reference/arch2.md"), codes)     # target is deprecated
        self.assertIn(("I7", "docs/reference/arch2.md"), codes)        # src/missing.py
        self.assertIn(("I4", "docs/reference/arch2.md"), codes)        # nope.md

    def test_query(self):
        r = g.cmd_query(self.root, ["type=reference", "status!=deprecated"])
        self.assertEqual([x["path"] for x in r["rows"]], ["docs/reference/arch2.md"])
        r = g.cmd_query(self.root, ["description?"])
        self.assertEqual(r["matched"], 1)
        r = g.cmd_query(self.root, ["links.supersedes~arch"], count_by="status")
        self.assertEqual(r["counts"], [("active", 1)])

    def test_agent_installations_are_not_knowledge(self):
        for directory in (".agents", ".claude", ".codex"):
            write(self.root, f"{directory}/skills/example/SKILL.md", "# Internal instructions")
        self.assertFalse(any(".agents" in p.parts or ".claude" in p.parts or ".codex" in p.parts
                             for p in g.iter_md(self.root)))

    def test_map_renders_markdown_and_uses_agent_entry_point(self):
        write(self.root, "AGENTS.md", "# Start\n[Docs](docs/README.md)\n")
        out = self.root / ".gitmark/docs-map.html"
        result = g.cmd_map(self.root, out)
        self.assertTrue(result["pretty"])
        html = out.read_text(encoding="utf-8")
        self.assertIn('"root": "AGENTS.md"', html)
        self.assertIn("<h1", html)
        self.assertIn("Architecture v2", html)

    def test_output_inside_skill_package_is_rejected(self):
        package = self.root / "installed/custom-name"
        write(package, "SKILL.md", "# Test skill")
        with self.assertRaisesRegex(SystemExit, "outside skill packages"):
            g.cmd_map(self.root, package / "map.html")
        with self.assertRaisesRegex(SystemExit, "outside skill packages"):
            g.cmd_index(package)
        self.assertFalse((package / ".gitmark").exists())
        with self.assertRaisesRegex(SystemExit, "outside skill packages"):
            g.runtime_path(self.root / ".agents/skills/new/artifact.html")

    def test_cli_default_map_and_strict_lint(self):
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--root", str(self.root), "map"],
                                capture_output=True, text=True, encoding="utf-8", shell=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / ".gitmark/docs-map.html").is_file())
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--root", str(self.root),
                                 "lint", "--strict", "--json"],
                                capture_output=True, text=True, encoding="utf-8", shell=False)
        self.assertEqual(result.returncode, 1)

    def test_unreadable_document_preserves_old_index(self):
        g.cmd_index(self.root)
        database = self.root / g.DB_REL
        before = database.read_bytes()
        original = Path.read_text

        def unreadable(path, *args, **kwargs):
            if path.name == "arch2.md":
                raise PermissionError("fixture read denied")
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", unreadable):
            with self.assertRaisesRegex(SystemExit, "Cannot read Markdown document.*arch2.md"):
                g.cmd_index(self.root)
            with self.assertRaisesRegex(SystemExit, "Cannot read Markdown document"):
                g.cmd_query(self.root, ["type=reference"])
        self.assertEqual(database.read_bytes(), before)

    def test_custom_server_prints_directory_instead_of_nonexistent_map(self):
        out = self.root / "artifacts/custom.html"
        g.cmd_map(self.root, out)
        output = StringIO()
        with patch("socketserver.TCPServer.serve_forever", side_effect=KeyboardInterrupt), redirect_stdout(output):
            g.cmd_serve(self.root, 0, out.parent)
        self.assertIn("http://127.0.0.1:", output.getvalue())
        self.assertNotIn("/docs-map.html", output.getvalue())
        self.assertNotIn(":0/", output.getvalue())


class EmptyProject(unittest.TestCase):
    def test_empty_map_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(SystemExit, "No Markdown documents"):
                g.cmd_map(root, root / ".gitmark/docs-map.html")
            self.assertFalse((root / ".gitmark").exists())

    def test_nonexistent_root_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing"
            result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--root", str(missing), "index"],
                                    capture_output=True, text=True, encoding="utf-8", shell=False)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
