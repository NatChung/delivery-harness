import os
import subprocess
import tempfile
import unittest
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
CLI = os.path.join(HERE, "cli.py")

TEMPLATE = '''---
id: "{{id}}"
slug: {{slug}}
track: {{track}}
phase: 0-intake
created: {{created}}
---

# Feature {{id}} — {{slug}}

## History
- {{created}} created (track={{track}})
'''

BUG_TEMPLATE = '''---
id: "{{id}}"
slug: {{slug}}
track: bug
phase: 0-intake
severity: {{severity}}
created: {{created}}
---

# Bug {{id}} — {{slug}}

## Gates
- [ ] repro-red
- [ ] tests-green
- [ ] bug-verified

## History
- {{created}} created (track=bug, severity={{severity}})
'''

INDEX = '''# Feature 索引

| id | slug | track | phase | created |
|----|------|-------|-------|---------|
'''


def run(root, *args):
    return subprocess.run(
        ["python3", CLI, "--root", root, *args],
        capture_output=True, text=True,
    )


class CliTestBase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        feats = os.path.join(self.root, "docs", "features")
        os.makedirs(feats)
        with open(os.path.join(feats, "_template.md"), "w") as f:
            f.write(TEMPLATE)
        with open(os.path.join(feats, "_template_bug.md"), "w") as f:
            f.write(BUG_TEMPLATE)
        with open(os.path.join(feats, "INDEX.md"), "w") as f:
            f.write(INDEX)

    def tearDown(self):
        shutil.rmtree(self.root)


class TestNew(CliTestBase):
    def test_new_creates_ticket_and_updates_index(self):
        r = run(self.root, "new", "search-filter", "--track", "full",
                "--date", "2026-06-22")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("001", r.stdout)
        ticket = os.path.join(self.root, "docs", "features",
                              "001-search-filter", "ticket.md")
        self.assertTrue(os.path.exists(ticket))
        with open(ticket) as f:
            body = f.read()
        self.assertIn('id: "001"', body)
        self.assertIn("track: full", body)
        self.assertIn("phase: 0-intake", body)
        with open(os.path.join(self.root, "docs", "features", "INDEX.md")) as f:
            self.assertIn("| 001 | search-filter | full | 0-intake |", f.read())

    def test_new_second_feature_gets_002(self):
        run(self.root, "new", "a", "--track", "full", "--date", "2026-06-22")
        r = run(self.root, "new", "b", "--track", "lite", "--date", "2026-06-22")
        self.assertIn("002", r.stdout)

    def test_new_rejects_bad_track(self):
        r = run(self.root, "new", "x", "--track", "bogus", "--date", "2026-06-22")
        self.assertNotEqual(r.returncode, 0)


class TestStatus(CliTestBase):
    def test_status_reports_phase_and_next(self):
        run(self.root, "new", "appt", "--track", "full", "--date", "2026-06-22")
        r = run(self.root, "status", "001")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("phase: 0-intake", r.stdout)
        self.assertIn("1-requirements", r.stdout)
        self.assertIn("track: full", r.stdout)

    def test_status_unknown_id_errors(self):
        r = run(self.root, "status", "999")
        self.assertNotEqual(r.returncode, 0)

    def test_status_accepts_unpadded_id(self):
        run(self.root, "new", "appt", "--track", "full", "--date", "2026-06-22")
        r = run(self.root, "status", "1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("phase: 0-intake", r.stdout)


def _ticket_body(root, slug_dir):
    p = os.path.join(root, "docs", "features", slug_dir, "ticket.md")
    with open(p) as f:
        return f.read()


class TestAdvance(CliTestBase):
    def test_advance_legal_transition_updates_everything(self):
        run(self.root, "new", "appt", "--track", "full", "--date", "2026-06-22")
        r = run(self.root, "advance", "001", "--to", "1-requirements",
                "--date", "2026-06-23")
        self.assertEqual(r.returncode, 0, r.stderr)
        body = _ticket_body(self.root, "001-appt")
        self.assertIn("phase: 1-requirements", body)
        self.assertIn("- 2026-06-23 advanced to 1-requirements", body)
        with open(os.path.join(self.root, "docs", "features", "INDEX.md")) as f:
            self.assertIn("| 001 | appt | full | 1-requirements |", f.read())

    def test_advance_illegal_transition_rejected(self):
        run(self.root, "new", "appt", "--track", "full", "--date", "2026-06-22")
        r = run(self.root, "advance", "001", "--to", "6-uat", "--date", "2026-06-23")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("illegal", r.stderr.lower())
        self.assertIn("phase: 0-intake", _ticket_body(self.root, "001-appt"))

    def test_spike_to_ui_prototype_converts_track_to_full(self):
        run(self.root, "new", "ai", "--track", "spike", "--date", "2026-06-22")
        run(self.root, "advance", "001", "--to", "1-requirements", "--date", "2026-06-22")
        run(self.root, "advance", "001", "--to", "1b-spike", "--date", "2026-06-22")
        r = run(self.root, "advance", "001", "--to", "2-ui-prototype", "--date", "2026-06-22")
        self.assertEqual(r.returncode, 0, r.stderr)
        body = _ticket_body(self.root, "001-ai")
        self.assertIn("phase: 2-ui-prototype", body)
        self.assertIn("track: full", body)

    def test_lite_reopen_to_ui_prototype_converts_track_to_full(self):
        # reopen: went lite, then discovered a UI prototype is needed after all
        run(self.root, "new", "ai", "--track", "spike", "--date", "2026-06-22")
        run(self.root, "advance", "001", "--to", "1-requirements", "--date", "2026-06-22")
        run(self.root, "advance", "001", "--to", "1b-spike", "--date", "2026-06-22")
        run(self.root, "advance", "001", "--to", "3-spec", "--date", "2026-06-22")
        body = _ticket_body(self.root, "001-ai")
        self.assertIn("track: lite", body)  # spike -> lite first
        r = run(self.root, "advance", "001", "--to", "2-ui-prototype", "--date", "2026-06-23")
        self.assertEqual(r.returncode, 0, r.stderr)
        body = _ticket_body(self.root, "001-ai")
        self.assertIn("phase: 2-ui-prototype", body)
        self.assertIn("track: full", body)  # reopen converts lite -> full


class TestLint(CliTestBase):
    def test_lint_passes_for_valid_ticket(self):
        run(self.root, "new", "appt", "--track", "full", "--date", "2026-06-22")
        r = run(self.root, "lint", "001")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ok", r.stdout.lower())

    def test_lint_fails_for_bad_phase(self):
        run(self.root, "new", "appt", "--track", "full", "--date", "2026-06-22")
        p = os.path.join(self.root, "docs", "features", "001-appt", "ticket.md")
        with open(p) as f:
            body = f.read()
        with open(p, "w") as f:
            f.write(body.replace("phase: 0-intake", 'phase: "99-bogus"'))
        r = run(self.root, "lint", "001")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("phase", r.stderr.lower())

    def test_lint_fails_clean_on_no_frontmatter(self):
        run(self.root, "new", "appt", "--track", "full", "--date", "2026-06-22")
        p = os.path.join(self.root, "docs", "features", "001-appt", "ticket.md")
        with open(p, "w") as f:
            f.write("# no frontmatter here\n")
        r = run(self.root, "lint", "001")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)


class TestNewBug(CliTestBase):
    def test_new_bug_uses_bug_template_with_severity(self):
        r = run(self.root, "new", "login-crash", "--track", "bug",
                "--severity", "P1-prod-partial", "--date", "2026-06-22")
        self.assertEqual(r.returncode, 0, r.stderr)
        body = _ticket_body(self.root, "001-login-crash")
        self.assertIn("track: bug", body)
        self.assertIn("severity: P1-prod-partial", body)
        self.assertIn("repro-red", body)
        with open(os.path.join(self.root, "docs", "features", "INDEX.md")) as f:
            self.assertIn("| 001 | login-crash | bug | 0-intake |", f.read())

    def test_new_bug_defaults_severity_to_p2(self):
        r = run(self.root, "new", "x", "--track", "bug", "--date", "2026-06-22")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("severity: P2-user-facing", _ticket_body(self.root, "001-x"))

    def test_new_bug_rejects_bad_severity(self):
        r = run(self.root, "new", "x", "--track", "bug", "--severity", "nope",
                "--date", "2026-06-22")
        self.assertNotEqual(r.returncode, 0)


class TestLintBug(CliTestBase):
    def test_lint_bug_passes_with_valid_severity(self):
        run(self.root, "new", "b", "--track", "bug", "--severity", "P0-prod-down",
            "--date", "2026-06-22")
        r = run(self.root, "lint", "001")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ok", r.stdout.lower())

    def test_lint_bug_fails_on_bad_severity(self):
        run(self.root, "new", "b", "--track", "bug", "--severity", "P0-prod-down",
            "--date", "2026-06-22")
        p = os.path.join(self.root, "docs", "features", "001-b", "ticket.md")
        with open(p) as f:
            body = f.read()
        with open(p, "w") as f:
            f.write(body.replace("severity: P0-prod-down", "severity: bogus"))
        r = run(self.root, "lint", "001")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("severity", r.stderr.lower())


class TestOutputUsesTrackWord(CliTestBase):
    def test_bug_status_and_advance_say_bug_not_feature(self):
        run(self.root, "new", "b", "--track", "bug", "--severity", "P2-user-facing",
            "--date", "2026-06-23")
        s = run(self.root, "status", "001")
        self.assertIn("bug 001", s.stdout)
        self.assertNotIn("feature 001", s.stdout)
        a = run(self.root, "advance", "001", "--to", "bug-debug", "--date", "2026-06-23")
        self.assertIn("bug 001:", a.stdout)
        self.assertNotIn("feature 001:", a.stdout)


if __name__ == "__main__":
    unittest.main()
