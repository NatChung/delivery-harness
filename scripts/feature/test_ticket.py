import unittest
from ticket import parse_frontmatter, set_frontmatter_field, next_id, append_history

SAMPLE = '''---
id: "003"
slug: dark-mode
track: spike
phase: 1b-spike
created: 2026-06-22
---

# Feature 003 — dark-mode

## History
- 2026-06-22 created
'''


class TestFrontmatter(unittest.TestCase):
    def test_parse_reads_flat_fields(self):
        f = parse_frontmatter(SAMPLE)
        self.assertEqual(f["id"], "003")
        self.assertEqual(f["slug"], "dark-mode")
        self.assertEqual(f["track"], "spike")
        self.assertEqual(f["phase"], "1b-spike")

    def test_parse_no_frontmatter_raises(self):
        with self.assertRaises(ValueError):
            parse_frontmatter("# no frontmatter here")

    def test_set_field_updates_value_only(self):
        out = set_frontmatter_field(SAMPLE, "phase", "2-ui-prototype")
        self.assertEqual(parse_frontmatter(out)["phase"], "2-ui-prototype")
        self.assertIn("## History", out)
        self.assertEqual(parse_frontmatter(out)["slug"], "dark-mode")


INDEX = '''# Feature 索引

| id | slug | track | phase | created |
|----|------|-------|-------|---------|
| 001 | search-filter | full | 6-uat | 2026-06-20 |
| 002 | banner | full | 3-spec | 2026-06-21 |
'''


class TestIdAndHistory(unittest.TestCase):
    def test_next_id_is_max_plus_one_zero_padded(self):
        self.assertEqual(next_id(INDEX), "003")

    def test_next_id_empty_index_starts_at_001(self):
        empty = "# Feature 索引\n\n| id | slug |\n|----|------|\n"
        self.assertEqual(next_id(empty), "001")

    def test_append_history_adds_dated_line_under_section(self):
        out = append_history(SAMPLE, "advanced to 2-ui-prototype", "2026-06-23")
        self.assertIn("- 2026-06-23 advanced to 2-ui-prototype", out)
        self.assertIn("- 2026-06-22 created", out)


if __name__ == "__main__":
    unittest.main()
