#!/usr/bin/env python3
"""`/feature` pipeline CLI — manages feature tickets + registry state.

Usage:
  cli.py [--root DIR] new <slug> --track <full|lite|spike> [--date YYYY-MM-DD]
  cli.py [--root DIR] status <id>
  cli.py [--root DIR] advance <id> --to <phase> [--date YYYY-MM-DD]
  cli.py [--root DIR] lint <id>
"""
import argparse
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state_machine as sm
import ticket as tk

SEVERITIES = {"P0-prod-down", "P1-prod-partial", "P2-user-facing", "P3-internal"}


def _feats_dir(root):
    return os.path.join(root, "docs", "features")


def _index_path(root):
    return os.path.join(_feats_dir(root), "INDEX.md")


def _ticket_dir(root, fid, slug):
    return os.path.join(_feats_dir(root), f"{fid}-{slug}")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _find_ticket(root, fid):
    """Return (ticket_path, slug) for feature id `fid`, or (None, None).

    `fid` may be unpadded ("1") or padded ("001"); numeric ids are normalized
    to 3-digit zero-padded.
    """
    try:
        fid = f"{int(fid):03d}"
    except (TypeError, ValueError):
        pass
    base = _feats_dir(root)
    for name in os.listdir(base):
        if name.startswith(f"{fid}-") and os.path.isdir(os.path.join(base, name)):
            return os.path.join(base, name, "ticket.md"), name[len(fid) + 1:]
    return None, None


def _parse_ticket(tpath):
    """Read+parse a ticket; return (fields, None) or (None, error_message)."""
    try:
        return tk.parse_frontmatter(_read(tpath)), None
    except ValueError as e:
        return None, str(e)


def cmd_new(args):
    if args.track not in sm.TRACKS:
        print(f"error: unknown track {args.track!r} (use {sorted(sm.TRACKS)})",
              file=sys.stderr)
        return 2
    severity = args.severity or "P2-user-facing"
    if args.track == "bug" and severity not in SEVERITIES:
        print(f"error: bad severity {severity!r} (use {sorted(SEVERITIES)})",
              file=sys.stderr)
        return 2
    date = args.date or datetime.date.today().isoformat()
    index = _read(_index_path(args.root))
    fid = tk.next_id(index)

    tname = "_template_bug.md" if args.track == "bug" else "_template.md"
    template = _read(os.path.join(_feats_dir(args.root), tname))
    body = (template
            .replace("{{id}}", fid)
            .replace("{{slug}}", args.slug)
            .replace("{{track}}", args.track)
            .replace("{{severity}}", severity)
            .replace("{{created}}", date))

    tdir = _ticket_dir(args.root, fid, args.slug)
    os.makedirs(tdir, exist_ok=True)
    _write(os.path.join(tdir, "ticket.md"), body)

    row = f"| {fid} | {args.slug} | {args.track} | 0-intake | {date} |\n"
    _write(_index_path(args.root), index.rstrip() + "\n" + row)

    print(f"created {args.track} ticket {fid} ({args.slug}) "
          f"-> docs/features/{fid}-{args.slug}/ticket.md")
    return 0


def _update_index_row(index_text, fid, slug, track, phase):
    """Rewrite the INDEX row for `fid` with new track/phase (keep created col)."""
    out = []
    for line in index_text.splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) >= 6 and cells[1] == fid:
            created = cells[5]
            out.append(f"| {fid} | {slug} | {track} | {phase} | {created} |")
        else:
            out.append(line)
    return "\n".join(out) + "\n"


def cmd_advance(args):
    tpath, slug = _find_ticket(args.root, args.id)
    if not tpath:
        print(f"error: no feature with id {args.id}", file=sys.stderr)
        return 2
    text = _read(tpath)
    fields, err = _parse_ticket(tpath)
    if err:
        print(f"error: bad ticket {args.id}: {err}", file=sys.stderr)
        return 2
    track, frm = fields["track"], fields["phase"]

    if not sm.is_valid_transition(track, frm, args.to):
        allowed = ", ".join(sorted(sm.valid_next(track, frm))) or "(terminal)"
        print(f"error: illegal transition {frm} -> {args.to} on track {track}. "
              f"allowed: {allowed}", file=sys.stderr)
        return 2

    new_track = track
    if frm == "1b-spike" and args.to == "2-ui-prototype":
        new_track = "full"
    elif frm == "1b-spike" and args.to == "3-spec":
        new_track = "lite"
    elif track == "lite" and args.to == "2-ui-prototype":
        new_track = "full"  # reopen: discovered a UI prototype is needed -> rejoin full flow

    date = args.date or datetime.date.today().isoformat()
    text = tk.set_frontmatter_field(text, "phase", args.to)
    if new_track != track:
        text = tk.set_frontmatter_field(text, "track", new_track)
    msg = f"advanced to {args.to}" + (
        f" (track {track}->{new_track})" if new_track != track else "")
    text = tk.append_history(text, msg, date)
    _write(tpath, text)

    index = _read(_index_path(args.root))
    _write(_index_path(args.root),
           _update_index_row(index, args.id, slug, new_track, args.to))

    print(f"{new_track} {args.id}: {frm} -> {args.to}"
          + (f" (track now {new_track})" if new_track != track else ""))
    return 0


def cmd_status(args):
    tpath, slug = _find_ticket(args.root, args.id)
    if not tpath:
        print(f"error: no feature with id {args.id}", file=sys.stderr)
        return 2
    fields, err = _parse_ticket(tpath)
    if err:
        print(f"error: bad ticket {args.id}: {err}", file=sys.stderr)
        return 2
    nxt = sorted(sm.valid_next(fields["track"], fields["phase"]))
    print(f"{fields['track']} {fields['id']} ({slug})")
    print(f"track: {fields['track']}")
    print(f"phase: {fields['phase']}")
    print(f"valid next: {', '.join(nxt) if nxt else '(terminal)'}")
    return 0


def cmd_lint(args):
    tpath, _ = _find_ticket(args.root, args.id)
    if not tpath:
        print(f"error: no feature with id {args.id}", file=sys.stderr)
        return 2
    fields, err = _parse_ticket(tpath)
    if err:
        print(f"error: bad ticket {args.id}: {err}", file=sys.stderr)
        return 2
    errors = []
    if fields.get("track") not in sm.TRACKS:
        errors.append(f"bad track: {fields.get('track')!r}")
    if fields.get("phase") not in sm.PHASES:
        errors.append(f"bad phase: {fields.get('phase')!r}")
    for required in ("id", "slug", "created"):
        if not fields.get(required):
            errors.append(f"missing field: {required}")
    if fields.get("track") == "bug" and fields.get("severity") not in SEVERITIES:
        errors.append(f"bad/missing bug severity: {fields.get('severity')!r}")
    if errors:
        print("lint failed: " + "; ".join(errors), file=sys.stderr)
        return 2
    print(f"ok: {fields['track']} {fields['id']} valid")
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="feature")
    p.add_argument("--root", default=".", help="repo root (default: cwd)")
    sub = p.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("new")
    n.add_argument("slug")
    n.add_argument("--track", required=True)
    n.add_argument("--severity", help="bug only: P0-prod-down|P1-prod-partial|P2-user-facing|P3-internal")
    n.add_argument("--date")
    n.set_defaults(func=cmd_new)

    s = sub.add_parser("status")
    s.add_argument("id")
    s.set_defaults(func=cmd_status)

    a = sub.add_parser("advance")
    a.add_argument("id")
    a.add_argument("--to", required=True)
    a.add_argument("--date")
    a.set_defaults(func=cmd_advance)

    l = sub.add_parser("lint")
    l.add_argument("id")
    l.set_defaults(func=cmd_lint)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
