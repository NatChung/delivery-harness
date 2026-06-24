"""Feature pipeline phase state machine (pure logic, no I/O)."""

PHASES = [
    "0-intake", "1-requirements", "1b-spike", "2-ui-prototype",
    "3-spec", "4-plan", "5-implement", "6-uat",
    "bug-debug", "bug-repro", "bug-fix", "bug-verify",
    "done", "rejected", "on-hold",
]
TERMINAL = {"done", "rejected"}
TRACKS = {"full", "lite", "spike", "bug"}

# Linear forward sequence per track. spike resolves into full/lite after 1b-spike.
TRACK_SEQUENCE = {
    "full":  ["0-intake", "1-requirements", "2-ui-prototype", "3-spec",
              "4-plan", "5-implement", "6-uat", "done"],
    "lite":  ["0-intake", "1-requirements", "3-spec",
              "4-plan", "5-implement", "6-uat", "done"],
    "spike": ["0-intake", "1-requirements", "1b-spike"],
    "bug":   ["0-intake", "bug-debug", "bug-repro", "bug-fix", "bug-verify", "done"],
}

# Extra (non-forward) transitions per (track, phase), beyond the generic
# forward-in-sequence / on-hold / on-hold-resume edges. Data-driven so a new
# track adds rows here instead of new `if phase == ...` branches in valid_next.
SPECIAL_EDGES = {
    "full": {
        "2-ui-prototype": {"rejected"},                        # abandon after round cap
        "6-uat": {"2-ui-prototype", "3-spec", "5-implement"},  # UAT-fail rework
    },
    "lite": {
        "3-spec": {"2-ui-prototype"},                          # reopen: UI prototype needed after all -> converts to full
        "6-uat": {"3-spec", "5-implement"},                    # lite has no 2-ui-prototype
    },
    "spike": {
        "1b-spike": {"2-ui-prototype", "3-spec"},              # spike resolves to full/lite
    },
    "bug": {
        "bug-repro": {"bug-debug"},     # repro can't be written -> back to debug
        "bug-verify": {"bug-debug"},    # UAT/verify fail -> back to debug (rework)
        "bug-debug": {"rejected"},      # not-a-bug / dup / wontfix -> reject directly
    },
}


def valid_next(track, phase):
    """Set of phases `phase` may transition to, for `track`."""
    if track not in TRACKS:
        raise ValueError(f"unknown track: {track}")
    if phase not in PHASES:
        raise ValueError(f"unknown phase: {phase}")
    if phase in TERMINAL:
        return set()

    seq = TRACK_SEQUENCE[track]

    if phase == "on-hold":
        # resume any non-terminal phase in the track, or abandon
        nxt = {p for p in seq if p not in TERMINAL}
        nxt.add("rejected")
        return nxt

    nxt = set()
    if phase in seq:                                  # forward in sequence
        i = seq.index(phase)
        if i + 1 < len(seq):
            nxt.add(seq[i + 1])
    nxt.update(SPECIAL_EDGES.get(track, {}).get(phase, set()))  # rework/reject/convert
    nxt.add("on-hold")                                # any active phase can be parked
    return nxt


def is_valid_transition(track, frm, to):
    return to in valid_next(track, frm)
