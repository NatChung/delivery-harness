import unittest
from state_machine import (
    PHASES, TRACKS, TERMINAL, valid_next, is_valid_transition,
)


class TestForwardTransitions(unittest.TestCase):
    def test_full_track_linear_forward(self):
        self.assertIn("1-requirements", valid_next("full", "0-intake"))
        self.assertIn("2-ui-prototype", valid_next("full", "1-requirements"))
        self.assertIn("3-spec", valid_next("full", "2-ui-prototype"))
        self.assertIn("done", valid_next("full", "6-uat"))

    def test_lite_track_skips_ui_prototype(self):
        self.assertIn("3-spec", valid_next("lite", "1-requirements"))
        self.assertNotIn("2-ui-prototype", valid_next("lite", "1-requirements"))

    def test_lite_can_reopen_to_ui_prototype(self):
        # reopen edge: went lite, then a UI prototype turns out to be needed
        nxt = valid_next("lite", "3-spec")
        self.assertIn("2-ui-prototype", nxt)  # reopen target
        self.assertIn("4-plan", nxt)          # normal forward still allowed
        self.assertTrue(is_valid_transition("lite", "3-spec", "2-ui-prototype"))

    def test_terminal_phases_have_no_transitions(self):
        self.assertEqual(valid_next("full", "done"), set())
        self.assertEqual(valid_next("full", "rejected"), set())

    def test_unknown_track_or_phase_raises(self):
        with self.assertRaises(ValueError):
            valid_next("nope", "0-intake")
        with self.assertRaises(ValueError):
            valid_next("full", "99-bogus")

    def test_enums_are_exact(self):
        self.assertEqual(TRACKS, {"full", "lite", "spike", "bug"})
        self.assertEqual(TERMINAL, {"done", "rejected"})
        self.assertIn("1b-spike", PHASES)
        for p in ("bug-debug", "bug-repro", "bug-fix", "bug-verify"):
            self.assertIn(p, PHASES)


class TestSpecialEdges(unittest.TestCase):
    def test_spike_resolves_to_full_or_lite(self):
        nxt = valid_next("spike", "1b-spike")
        self.assertIn("2-ui-prototype", nxt)
        self.assertIn("3-spec", nxt)

    def test_uat_failure_can_rework_backwards(self):
        nxt = valid_next("full", "6-uat")
        self.assertIn("2-ui-prototype", nxt)
        self.assertIn("3-spec", nxt)
        self.assertIn("5-implement", nxt)

    def test_any_active_phase_can_go_on_hold(self):
        self.assertIn("on-hold", valid_next("full", "2-ui-prototype"))
        self.assertIn("on-hold", valid_next("lite", "1-requirements"))
        self.assertNotIn("on-hold", valid_next("full", "done"))

    def test_prototype_can_be_rejected(self):
        self.assertIn("rejected", valid_next("full", "2-ui-prototype"))

    def test_on_hold_resumes_or_abandons(self):
        nxt = valid_next("full", "on-hold")
        self.assertIn("rejected", nxt)
        self.assertIn("1-requirements", nxt)
        self.assertNotIn("done", nxt)

    def test_is_valid_transition_helper(self):
        self.assertTrue(is_valid_transition("full", "0-intake", "1-requirements"))
        self.assertFalse(is_valid_transition("full", "0-intake", "6-uat"))

    def test_lite_uat_rework_stays_in_track(self):
        nxt = valid_next("lite", "6-uat")
        self.assertIn("3-spec", nxt)
        self.assertIn("5-implement", nxt)
        self.assertNotIn("2-ui-prototype", nxt)  # lite has no 2-ui-prototype


class TestBugTrack(unittest.TestCase):
    def test_bug_forward_sequence(self):
        self.assertIn("bug-debug", valid_next("bug", "0-intake"))
        self.assertIn("bug-repro", valid_next("bug", "bug-debug"))
        self.assertIn("bug-fix", valid_next("bug", "bug-repro"))
        self.assertIn("bug-verify", valid_next("bug", "bug-fix"))
        self.assertIn("done", valid_next("bug", "bug-verify"))

    def test_bug_rework_loops_back_to_debug(self):
        self.assertIn("bug-debug", valid_next("bug", "bug-repro"))
        self.assertIn("bug-debug", valid_next("bug", "bug-verify"))

    def test_bug_debug_can_reject_directly(self):
        self.assertIn("rejected", valid_next("bug", "bug-debug"))

    def test_feature_tracks_never_route_to_bug_phases(self):
        for t in ("full", "lite", "spike"):
            reachable = set()
            for ph in ("0-intake", "1-requirements", "6-uat"):
                reachable |= valid_next(t, ph)
            self.assertFalse(any(p.startswith("bug-") for p in reachable))


if __name__ == "__main__":
    unittest.main()
