#!/usr/bin/env python3
"""docgraph: 驗證 docs/MAP.md 文件圖譜完整性(獨立、純 stdlib)。
無發現 exit 0,有發現 exit 1。從 pohai doc-rot check.py 抽 map-graph 半邊。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    category: str
    message: str


def repo_root() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], stderr=subprocess.DEVNULL
        )
        return out.decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return os.getcwd()


def collect_md_files(root: str) -> list:
    """收 root 下所有 .md 的 repo-relative 路徑。優先 git ls-files,失敗 fallback os.walk。"""
    try:
        out = subprocess.check_output(
            ["git", "ls-files", "*.md"], cwd=root, stderr=subprocess.DEVNULL
        )
        files = [ln for ln in out.decode().splitlines() if ln]
        if files:
            return files
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    files = []
    for dirpath, dirnames, names in os.walk(root):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for n in names:
            if n.endswith(".md"):
                files.append(os.path.relpath(os.path.join(dirpath, n), root))
    return files


@dataclass(frozen=True)
class MapEntry:
    id: str
    path: str
    anchor: str
    type: str
    status: str
    sensitive: bool
    domain: str
    line: int


MAP_REL = "docs/MAP.md"
_PIPE_SPLIT = re.compile(r"(?<!\\)\|")
DOMAIN_HDR_RE = re.compile(r"^##\s+(\S+)\s*$")
WIKILINK_RE = re.compile(r"\[\[([a-z0-9-]+)\]\]")


def parse_map(map_full: str) -> "list[MapEntry]":
    entries = []
    domain = ""
    with open(map_full, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    for idx, line in enumerate(lines):
        hm = DOMAIN_HDR_RE.match(line)
        if hm:
            domain = hm.group(1)
            continue
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in _PIPE_SPLIT.split(line.strip().strip("|"))]
        if not cells or cells[0] == "id" or set(cells[0]) <= set("-: "):
            continue  # header 列 / 分隔列
        if len(cells) < 6:
            continue
        path, _, anchor = cells[1].partition("#")
        entries.append(MapEntry(
            id=cells[0], path=path, anchor=anchor,
            type=cells[2], status=cells[3],
            sensitive=cells[4].lower() == "true",
            domain=domain, line=idx + 1,
        ))
    return entries


def _read_lines(full: str) -> list:
    with open(full, encoding="utf-8") as fh:
        return fh.read().splitlines()


def _frontmatter_id(lines: list):
    # 只把「納管節點」當節點 = front-matter 同時有 id 與 domain。
    # bug ticket 有 id 但只有 track/system、無 domain → 回 None,不誤判。
    if not (lines and lines[0].strip() == "---"):
        return None
    fid = None
    has_domain = False
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            break
        m = re.match(r"^id:\s*([a-z0-9-]+)\s*$", lines[i])
        if m:
            fid = m.group(1)
        if re.match(r"^domain:\s*\S+", lines[i]):
            has_domain = True
    return fid if has_domain else None


def _related_ids(lines: list) -> list:
    out = []
    if not (lines and lines[0].strip() == "---"):
        return out
    in_related = False
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            break
        if re.match(r"^related:\s*$", lines[i]):
            in_related = True
            continue
        if in_related:
            m = re.match(r"^\s*-\s*([a-z0-9-]+)\s*$", lines[i])
            if m:
                out.append((i + 1, m.group(1)))
            elif lines[i].strip():
                in_related = False
    return out


def _inline_ids(lines: list) -> list:
    out = []
    in_fence = False
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        # 跳 inline-code span,讓散文裡 `[[id]]` 範例不被當真連結
        clean = re.sub(r"`[^`]*`", "", line)
        for m in WIKILINK_RE.finditer(clean):
            out.append((i + 1, m.group(1)))
    return out


def check_map_graph(files: list, root: str) -> list:
    findings = []
    map_full = os.path.join(root, MAP_REL)
    if not os.path.exists(map_full):
        return findings
    entries = parse_map(map_full)
    seen = {}
    dup_ids = set()
    for e in entries:
        if e.id in seen:
            dup_ids.add(e.id)
            findings.append(Finding(MAP_REL, e.line, "duplicate-id",
                                    f"id 重複: {e.id}(也在第 {seen[e.id]} 行)"))
        else:
            seen[e.id] = e.line
    id_to_path = {}
    for e in entries:
        id_to_path.setdefault(e.id, e.path)  # first-wins,duplicate-id 已單獨報
    valid_ids = set(id_to_path)
    for e in entries:
        full = os.path.join(root, e.path)
        if not os.path.exists(full):
            findings.append(Finding(MAP_REL, e.line, "dead-map-entry",
                                    f"path 不存在: {e.path}"))
            continue
        if e.anchor:
            try:
                content = "\n".join(_read_lines(full))
            except (OSError, UnicodeDecodeError):
                content = ""
            if ("{#%s}" % e.anchor) not in content:
                findings.append(Finding(MAP_REL, e.line, "dead-map-entry",
                                        f"anchor {{#{e.anchor}}} 不在 {e.path}"))
    for path in files:
        if not path.endswith(".md"):
            continue
        full = os.path.join(root, path)
        try:
            lines = _read_lines(full)
        except (OSError, UnicodeDecodeError):
            continue
        fid = _frontmatter_id(lines)
        link_ids = list(_inline_ids(lines))  # inline [[id]] 是明確圖譜邊,全檔都查
        if fid is not None:
            if fid not in valid_ids:
                findings.append(Finding(path, 1, "id-path-mismatch",
                                        f"front-matter id {fid} 不在 MAP"))
            elif fid in dup_ids:
                pass  # 已報 duplicate-id,不再加 id-path-mismatch 噪音
            elif id_to_path[fid] != path:
                findings.append(Finding(path, 1, "id-path-mismatch",
                                        f"MAP 說 {fid}→{id_to_path[fid]},實為 {path}"))
            # related: 只在納管節點(有 id+domain)算圖譜邊;bug 票用 related:
            # 做 bug↔bug 交叉引用,非圖譜邊,不該誤報 dangling-link。
            link_ids += _related_ids(lines)
        for ln, rid in link_ids:
            if rid not in valid_ids:
                findings.append(Finding(path, ln, "dangling-link",
                                        f"連結 id 不在 MAP: {rid}"))
    return findings


def format_report(findings: list) -> str:
    if not findings:
        return "—— 乾淨,0 筆。"
    out = [f"{f.path}:{f.line} | {f.category} | {f.message}" for f in findings]
    counts = {}
    for f in findings:
        counts[f.category] = counts.get(f.category, 0) + 1
    summary = "、".join(f"{c} {n} 筆" for c, n in sorted(counts.items()))
    out.append(f"—— {summary},共 {len(findings)} 筆。退出碼 1 ——")
    return "\n".join(out)


def main(argv=None) -> int:
    root = repo_root()
    files = collect_md_files(root)
    findings = check_map_graph(files, root)
    print(format_report(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
