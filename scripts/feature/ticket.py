"""Ticket + registry file I/O for the feature pipeline (stdlib only)."""
import re

_FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def parse_frontmatter(text):
    """Parse the leading --- block into a flat dict {str: str}."""
    m = _FM_RE.match(text)
    if not m:
        raise ValueError("no frontmatter block found")
    fields = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        fields[k.strip()] = v.strip().strip('"')
    return fields


def set_frontmatter_field(text, key, value):
    """Return `text` with frontmatter `key` set to `value` (added if missing)."""
    def repl(m):
        lines, found = [], False
        for line in m.group(1).splitlines():
            if re.match(rf"^\s*{re.escape(key)}\s*:", line):
                lines.append(f'{key}: {value}')
                found = True
            else:
                lines.append(line)
        if not found:
            lines.append(f'{key}: "{value}"')
        return "---\n" + "\n".join(lines) + "\n---\n"
    return _FM_RE.sub(repl, text, count=1)


_ID_ROW_RE = re.compile(r"^\|\s*(\d{1,4})\s*\|", re.MULTILINE)


def next_id(index_text):
    """Next zero-padded 3-digit id = max existing id in INDEX + 1."""
    ids = [int(x) for x in _ID_ROW_RE.findall(index_text)]
    return f"{(max(ids) + 1) if ids else 1:03d}"


def append_history(ticket_text, message, date):
    """Append `- <date> <message>` under the ticket's `## History` heading."""
    line = f"- {date} {message}"
    if "## History" not in ticket_text:
        return ticket_text.rstrip() + f"\n\n## History\n{line}\n"
    out, inserted = [], False
    for ln in ticket_text.splitlines():
        out.append(ln)
        if ln.strip() == "## History" and not inserted:
            out.append(line)
            inserted = True
    return "\n".join(out) + "\n"
