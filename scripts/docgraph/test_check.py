import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import check  # noqa: E402

MAP_SAMPLE = """\
# MAP

## cicd
| id | path#anchor | type | status | sensitive | hook |
|----|-------------|------|--------|-----------|------|
| stg-deploy-runbook | docs/STG_DEPLOY_RUNBOOK.md | runbook | current | false | 全平台 STG 部署 |
| deploy-cms-stg | docs/STG_DEPLOY_RUNBOOK.md#deploy-cms-stg | procedure | current | false | 部署 cms 到 STG |

## architecture
| id | path#anchor | type | status | sensitive | hook |
|----|-------------|------|--------|-----------|------|
| adr-gcs-public-url | docs/architecture/adr-gcs-public-url.md | adr | current | false | 圖用公開 URL 的決策 |
"""

GOOD_MAP = """\
## cicd
| id | path#anchor | type | status | sensitive | hook |
|----|-------------|------|--------|-----------|------|
| runbook | docs/run.md | runbook | current | false | 部署 |
| deploy-cms | docs/run.md#deploy-cms | procedure | current | false | 部署 cms |
"""

EMPTY_MAP = """\
# MAP

## cicd
| id | path#anchor | type | status | sensitive | hook |
|----|-------------|------|--------|-----------|------|

## architecture
| id | path#anchor | type | status | sensitive | hook |
|----|-------------|------|--------|-----------|------|
"""

RUN_MD = """\
---
id: runbook
title: Run
type: runbook
status: current
domain: cicd
sensitive: false
related:
  - deploy-cms
---
# Run
## 部署 cms {#deploy-cms}
步驟……內文連到 [[deploy-cms]]。
"""


class DocGraphCheck(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, rel, text):
        p = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return p

    def _run(self):
        files = []
        for dirpath, _, names in os.walk(self.root):
            for n in names:
                if n.endswith(".md"):
                    full = os.path.join(dirpath, n)
                    files.append(os.path.relpath(full, self.root))
        return check.check_map_graph(files, self.root)

    def _cats(self):
        return {f.category for f in self._run()}

    def test_parse_map_basic(self):
        self._write("docs/MAP.md", MAP_SAMPLE)
        entries = check.parse_map(os.path.join(self.root, "docs/MAP.md"))
        by_id = {e.id: e for e in entries}
        self.assertEqual(
            set(by_id),
            {"stg-deploy-runbook", "deploy-cms-stg", "adr-gcs-public-url"},
        )
        self.assertEqual(by_id["deploy-cms-stg"].path, "docs/STG_DEPLOY_RUNBOOK.md")
        self.assertEqual(by_id["deploy-cms-stg"].anchor, "deploy-cms-stg")
        self.assertEqual(by_id["deploy-cms-stg"].type, "procedure")
        self.assertEqual(by_id["deploy-cms-stg"].domain, "cicd")
        self.assertEqual(by_id["stg-deploy-runbook"].anchor, "")
        self.assertEqual(by_id["adr-gcs-public-url"].domain, "architecture")
        self.assertIs(by_id["adr-gcs-public-url"].sensitive, False)

    def test_clean_graph_no_findings(self):
        self._write("docs/MAP.md", GOOD_MAP)
        self._write("docs/run.md", RUN_MD)
        self.assertEqual(self._run(), [])

    def test_dead_map_entry_missing_anchor(self):
        self._write("docs/MAP.md", GOOD_MAP.replace("docs/run.md#deploy-cms", "docs/run.md#nope"))
        self._write("docs/run.md", RUN_MD)
        self.assertIn("dead-map-entry", self._cats())

    def test_dead_map_entry_missing_file(self):
        self._write("docs/MAP.md", GOOD_MAP.replace("docs/run.md", "docs/gone.md"))
        self.assertIn("dead-map-entry", self._cats())

    def test_missing_map_is_clean(self):
        self.assertEqual(check.check_map_graph([], self.root), [])

    def test_empty_map_is_clean(self):
        self._write("docs/MAP.md", EMPTY_MAP)
        self.assertEqual(self._run(), [])

    def test_dangling_link(self):
        self._write("docs/MAP.md", GOOD_MAP)
        self._write("docs/run.md", RUN_MD.replace("[[deploy-cms]]", "[[ghost]]"))
        self.assertIn("dangling-link", self._cats())

    def test_duplicate_id(self):
        self._write("docs/MAP.md", GOOD_MAP + "| runbook | docs/run.md | runbook | current | false | dup |\n")
        self._write("docs/run.md", RUN_MD)
        self.assertIn("duplicate-id", self._cats())

    def test_id_path_mismatch(self):
        self._write("docs/MAP.md", GOOD_MAP)
        self._write("docs/other.md", RUN_MD)
        self._write("docs/run.md", "# Run\n## 部署 cms {#deploy-cms}\n")
        self.assertIn("id-path-mismatch", self._cats())

    def test_bug_ticket_not_a_node(self):
        self._write("docs/MAP.md", GOOD_MAP)
        self._write("docs/run.md", RUN_MD)
        self._write("docs/bugs/x.md", "---\nid: bug-x\ntrack: bug\nsystem: app\n---\n# Bug x\n")
        self.assertEqual(self._run(), [])

    def test_inline_code_wikilink_ignored(self):
        self._write("docs/MAP.md", GOOD_MAP)
        self._write("docs/run.md", RUN_MD)
        self._write("docs/meta.md", "# Meta\n說明:連結寫成 `[[id]]`,例如 `[[ghost]]`。\n")
        self.assertEqual(self._run(), [])

    def test_non_node_related_not_dangling(self):
        self._write("docs/MAP.md", GOOD_MAP)
        self._write("docs/run.md", RUN_MD)
        self._write("docs/bugs/y.md", "---\nid: bug-y\ntrack: bug\nsystem: app\nrelated:\n  - bug-zzz\n---\n# Bug y\n")
        self.assertEqual(self._run(), [])

    def test_managed_node_related_dangling(self):
        self._write("docs/MAP.md", GOOD_MAP)
        self._write("docs/run.md", RUN_MD.replace("  - deploy-cms\n", "  - deploy-cms\n  - ghostnode\n"))
        self.assertIn("dangling-link", self._cats())

    def test_duplicate_id_no_spurious_mismatch(self):
        self._write("docs/MAP.md", GOOD_MAP + "| runbook | docs/other.md | runbook | current | false | dup |\n")
        self._write("docs/run.md", RUN_MD)
        cats = self._cats()
        self.assertIn("duplicate-id", cats)
        self.assertNotIn("id-path-mismatch", cats)


if __name__ == "__main__":
    unittest.main()
