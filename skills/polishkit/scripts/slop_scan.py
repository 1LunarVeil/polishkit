"""Scan UI source for generic-default ("AI slop") tells and craft defects.

Usage:
  python slop_scan.py PATH [PATH ...] [--json] [--include-tests] [--limit N]
  python slop_scan.py PATH [PATH ...] --changed

Read-only. Findings are prompts for a decision, not verdicts: a default is
fine when it was chosen for the brief. Rule IDs map to references/anti-slop.md.
Only accessibility-floor violations are blocking; taste tells are review.

A code line ending in "slop-ignore: RULE-ID" (comma-separated list allowed)
hides that rule for that line. A ".sloprc" JSON file in a scanned root accepts
{"ignore_rules": ["RULE-ID"], "ignore_file_rules": {"glob": ["RULE-ID"]}};
suppressed findings are counted in the summary line. --changed scans only the
files git reports as changed or untracked under the given paths.

Exit status is 1 when any blocking finding exists, 2 when --changed was given
but git is unavailable or this is not a git repository, otherwise 0.
"""

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

MAX_FILE_BYTES = 1_000_000
SEVERITY_ORDER = {"blocking": 0, "important": 1, "review": 2, "polish": 3}
SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", "target", "out", ".next", "vendor",
    "__pycache__", ".venv", "venv", "coverage", "release", "_internal",
    "webview2-data", "logs",
}
TEST_DIRS = {"tests", "test", "__tests__", "spec", "fixtures", "mocks"}
FOCUS_REMOVED = re.compile(r"outline\s*:\s*(?:none|0)\b", re.IGNORECASE)
FOCUS_REPLACEMENT = re.compile(r"focus-visible|:focus\b|focus-within|\bfocus:", re.IGNORECASE)
MOTION_USE = re.compile(r"transition\s*:|animation\s*:|@keyframes|transition-|animate-", re.IGNORECASE)
REDUCED_MOTION = re.compile(r"prefers-reduced-motion", re.IGNORECASE)
SUPPRESS_INLINE = re.compile(r"slop-ignore\s*:\s*([A-Z0-9-]+(?:\s*,\s*[A-Z0-9-]+)*)", re.IGNORECASE)
DURATION = re.compile(r"(\d*\.?\d+)(ms|s)\b", re.IGNORECASE)
HOVER_SELECTOR = re.compile(r":hover\b[^{}]*\{")
HOVER_LIFT_BODY = re.compile(r"(?:transform|box-shadow)\s*:")
EMOJI = r"[\U0001F300-\U0001FAFF\U0001F900-\U0001F9FF\U00002600-\U000027BF\U00002B00-\U00002BFF]"

MARKUP = {".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".astro"}
STYLE = {".css", ".scss", ".sass", ".less", ".styl"}
SCRIPT = {".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".astro"}
CODE = MARKUP | STYLE | SCRIPT
ANY = CODE


@dataclass
class Rule:
    id: str
    severity: str
    extensions: set
    pattern: re.Pattern
    message: str
    below: float = None  # for numeric rules: report only values below this


def _rule(rule_id, severity, extensions, pattern, message, below=None):
    return Rule(rule_id, severity, extensions, re.compile(pattern, re.IGNORECASE), message, below)


RULES = [
    _rule("A11Y-ZOOM", "blocking", MARKUP,
          r"user-scalable\s*=\s*(?:no|0)\b|maximum-scale\s*=\s*1(?:\.0+)?(?![\d.])",
          "zoom is disabled, so users cannot enlarge text (WCAG 1.4.4)"),
    _rule("A11Y-IMG-ALT", "blocking", MARKUP | SCRIPT,
          r"<img\b(?![^>]*\balt\s*=)[^>]*>",
          'img without alt; use alt="" when the image is decorative (WCAG 1.1.1)'),
    _rule("A11Y-TABINDEX", "important", MARKUP | SCRIPT,
          r"tabindex\s*=\s*[\"']?[1-9]\d*",
          "positive tabindex overrides the natural focus order (WCAG 2.4.3)"),
    _rule("TYPE-TINY", "important", CODE,
          r"(?:font-size\s*:\s*|text-\[)(\d+(?:\.\d+)?)px",
          "text under 12px; body copy should be 14px or larger on desktop and 16px on the web",
          below=12),
    _rule("MOTION-ALL", "important", CODE,
          r"transition\s*:\s*all\b|transition-all\b",
          "transition: all animates every property; list the properties that change"),
    _rule("MOTION-LAYOUT", "review", CODE,
          r"transition\s*:[^;{}]*\b(?:width|height|top|left|right|bottom|margin|padding)\b",
          "transitions a layout property; prefer transform and opacity unless this is a deliberate reveal"),
    _rule("MOTION-GENERIC-ENTRANCE", "review", CODE,
          r"fade-?in-?up|slide-?up|fade-?up\b|rise-?in\b|animate-fade-in",
          "generic fade-and-slide entrance; motion should show what changed or be one orchestrated moment"),
    _rule("EMOJI-ICON", "review", MARKUP | SCRIPT,
          EMOJI,
          "emoji used as an icon; use one labelled icon family unless the emoji itself is the content"),
    _rule("TYPE-DEFAULT-PRIMARY", "review", CODE,
          r"font-family\s*:\s*[\"']?(?:Inter|Roboto|Arial|Open Sans)\b",
          "a common default is the primary family; keep it only if it was chosen for this brief"),
    _rule("TYPE-CAPS", "review", CODE,
          r"text-transform\s*:\s*uppercase",
          "all-caps text; keep it for short labels that have enough letter-spacing"),
    _rule("COLOR-PURPLE-GRADIENT", "review", CODE,
          r"gradient\([^;{}]*#(?:7c3aed|8b5cf6|a855f7|6366f1|9333ea|7e22ce|6d28d9|4f46e5|667eea|764ba2|c084fc)\b",
          "purple-to-blue gradient, the most common generated accent; confirm it is a deliberate choice"),
    _rule("COLOR-PURE-BLACK", "polish", CODE,
          r"(?:background|color|border)[\w-]*\s*:[^;{}]*#0{3}(?:0{3})?\b",
          "pure black; a tinted near-black usually reads better"),
    _rule("COLOR-GREY-SHADOW", "review", CODE,
          r"box-shadow\s*:[^;{}]*rgba\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0?\.\d+\s*\)",
          "generic black shadow; tint it to the palette or drop it"),
    _rule("COPY-LOREM", "important", ANY,
          r"lorem ipsum",
          "placeholder copy left in the UI"),
    _rule("COPY-GENERIC-ERROR", "review", MARKUP | SCRIPT,
          r"something went wrong|\boops\b|no results found|please try again later",
          "generic error or empty copy; say what happened and what to do next"),
    _rule("COPY-SUBMIT", "review", MARKUP | SCRIPT,
          r">\s*submit\s*<|value\s*=\s*[\"']submit[\"']",
          "'Submit' does not say what happens; name the action, such as 'Save changes'"),
    _rule("COPY-ARROW-CTA", "review", MARKUP | SCRIPT,
          r"(?:<button\b|<a\b|role\s*=\s*[\"']button).*→|→.*</(?:button|a)>",
          "arrow glyph on a control; a plain verb reads better"),
    _rule("COPY-MIDDOT-META", "review", MARKUP | SCRIPT,
          r"[A-Za-z0-9)]\s+·\s+[A-Za-z0-9(]",
          "middle-dot separated metadata, a common template tell"),
]


@dataclass
class Finding:
    rule: str
    severity: str
    file: str
    line: int
    snippet: str
    message: str


def _snippet(line):
    text = " ".join(line.split())
    return text if len(text) <= 140 else text[:137] + "..."


def _is_comment(line):
    stripped = line.strip()
    if stripped.startswith(("//", "/*", "<!--")):
        return True
    return stripped.startswith("*") and "{" not in stripped


OPEN_TAG = re.compile(r"<[a-zA-Z][^<>]*$")


def _logical_lines(lines):
    """Join tags whose markup spans lines, so per-line tag rules see whole elements.

    Bounded at 10 continuation lines. A JSX/TSX generic without a closing '>'
    on its line can be joined by mistake; that costs a little scanning
    precision, never correctness.
    """
    out = []
    i = 0
    total = len(lines)
    while i < total:
        line = lines[i]
        j = i
        while OPEN_TAG.search(line) and j + 1 < total and j - i < 10:
            j += 1
            line = line + " " + lines[j]
        out.append((i + 1, line))
        i = j + 1
    return out


def _line_pairs(path, lines):
    """Return (start line number, text) pairs; markup gets multi-line tags joined."""
    if path.suffix.lower() in MARKUP:
        return _logical_lines(lines)
    return list(enumerate(lines, start=1))


def _code_lines(pairs):
    return [(number, line) for number, line in pairs if not _is_comment(line)]


def _suppressed_ids(line):
    match = SUPPRESS_INLINE.search(line)
    if not match:
        return frozenset()
    return {token.strip().upper() for token in match.group(1).split(",")}


def _display(path):
    try:
        relative = os.path.relpath(path)
    except ValueError:
        return str(path)
    return str(path) if relative.startswith("..") else relative


def iter_files(paths, include_tests):
    for raw in paths:
        root = Path(raw)
        if root.is_file():
            yield root
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                name for name in dirnames
                if name not in SKIP_DIRS and (include_tests or name not in TEST_DIRS)
            ]
            for name in sorted(filenames):
                candidate = Path(dirpath) / name
                if candidate.suffix.lower() in CODE:
                    yield candidate


def _focus_findings(path, pairs, text, suppressed):
    if path.suffix.lower() not in CODE:
        return []
    has_replacement = FOCUS_REPLACEMENT.search(text) is not None
    severity = "important" if has_replacement else "blocking"
    suffix = "" if has_replacement else " and this file has no focus style"
    found = []
    for number, line in _code_lines(pairs):
        if FOCUS_REMOVED.search(line):
            if "A11Y-FOCUS-REMOVED" in suppressed.get(number, frozenset()):
                continue
            found.append(Finding(
                "A11Y-FOCUS-REMOVED", severity, _display(path), number, _snippet(line),
                f"focus outline removed{suffix} (WCAG 2.4.7)",
            ))
    return found


def _hover_lift_findings(path, pairs, suppressed):
    """Hover blocks that move the element or change its shadow.

    Block-aware rather than line-based: pretty-printed CSS puts the transform
    on the line after the selector.
    """
    ext = path.suffix.lower()
    if ext not in STYLE and ext not in MARKUP:
        return []
    text = "\n".join(line for _, line in pairs)
    found = []
    for match in HOVER_SELECTOR.finditer(text):
        index = text.count("\n", 0, match.start())
        if index >= len(pairs) or _is_comment(pairs[index][1]):
            continue
        body_end = text.find("}", match.end())
        body = text[match.end(): body_end if body_end != -1 else match.end() + 400][:400]
        if not HOVER_LIFT_BODY.search(body):
            continue
        number, line = pairs[index]
        if "HOVER-LIFT" in suppressed.get(number, frozenset()):
            continue
        found.append(Finding(
            "HOVER-LIFT", "review", _display(path), number, _snippet(line),
            "hover moves the element or changes its shadow; a color or border change reads better unless this is the one deliberate lift",
        ))
    return found


def scan_text(path, text):
    ext = path.suffix.lower()
    pairs = _line_pairs(path, text.splitlines())
    suppressed = {number: _suppressed_ids(line) for number, line in pairs}
    found = []
    for rule in RULES:
        if ext not in rule.extensions:
            continue
        for number, line in _code_lines(pairs):
            if rule.below is not None:
                hit = any(float(match.group(1)) < rule.below for match in rule.pattern.finditer(line))
            else:
                hit = rule.pattern.search(line) is not None
            if hit and rule.id not in suppressed.get(number, frozenset()):
                found.append(Finding(rule.id, rule.severity, _display(path), number, _snippet(line), rule.message))
    found.extend(_focus_findings(path, pairs, text, suppressed))
    found.extend(_hover_lift_findings(path, pairs, suppressed))
    return found


def _reduced_motion_findings(texts):
    if any(REDUCED_MOTION.search(text) for text in texts.values()):
        return []
    for path in sorted(texts):
        if path.suffix.lower() not in CODE:
            continue
        for number, line in _code_lines(_line_pairs(path, texts[path].splitlines())):
            if MOTION_USE.search(line):
                return [Finding(
                    "A11Y-REDUCED-MOTION", "important", _display(path), number, _snippet(line),
                    "motion is used, but no scanned file honours prefers-reduced-motion (WCAG 2.3.3)",
                )]
    return []


def _motion_uniform_findings(texts):
    """One duration across the whole scanned set means no motion tiers were chosen.

    Aggregate like the reduced-motion check, not a line rule: the tell is a
    property of the change set, not of a single line.
    """
    count = 0
    values = set()
    first = None
    for path in sorted(texts):
        if path.suffix.lower() not in CODE:
            continue
        for number, line in _code_lines(_line_pairs(path, texts[path].splitlines())):
            if not MOTION_USE.search(line):
                continue
            count += 1
            if first is None:
                first = (path, number, line)
            for match in DURATION.finditer(line):
                amount, unit = match.groups()
                values.add(float(amount) * (1000 if unit.lower() == "s" else 1))
    if count >= 5 and len(values) == 1:
        path, number, line = first
        value = int(next(iter(values)))
        return [Finding(
            "MOTION-UNIFORM", "review", _display(path), number, _snippet(line),
            f"{count} motion declarations share one duration ({value}ms); set a tier per interaction",
        )]
    return []


def _load_sloprc(paths):
    """Merge .sloprc JSON files found in the scanned roots.

    Accepted shape: {"ignore_rules": ["RULE-ID"], "ignore_file_rules":
    {"glob": ["RULE-ID"]}}. Multiple roots merge additively.
    """
    merged_rules = set()
    merged_file_rules = {}
    for raw in paths:
        root = Path(raw)
        directory = root if root.is_dir() else root.parent
        candidate = directory / ".sloprc"
        if not candidate.is_file():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"{candidate}: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"{candidate}: expected a JSON object")
        rules = data.get("ignore_rules", [])
        if isinstance(rules, list):
            merged_rules.update(str(rule).upper() for rule in rules)
        for pattern, rule_list in (data.get("ignore_file_rules") or {}).items():
            if not isinstance(rule_list, list):
                rule_list = [rule_list]
            merged_file_rules.setdefault(str(pattern), set()).update(
                str(rule).upper() for rule in rule_list
            )
    return {"ignore_rules": merged_rules, "ignore_file_rules": merged_file_rules}


def _apply_config(findings, config):
    """Drop configured findings; return (kept, suppressed count)."""
    ignored = config["ignore_rules"]
    file_rules = [(pattern, rules) for pattern, rules in config["ignore_file_rules"].items()]
    kept = []
    suppressed = 0
    for finding in findings:
        if finding.rule in ignored or any(
            finding.rule in rules and fnmatch.fnmatch(finding.file, pattern)
            for pattern, rules in file_rules
        ):
            suppressed += 1
        else:
            kept.append(finding)
    return kept, suppressed


def _filter_changed(names, roots, include_tests=False, exists=None):
    """Filter git-reported file names to scannable code files under the roots."""
    if exists is None:
        exists = Path.is_file
    files = []
    seen = set()
    for name in names:
        candidate = Path(name)
        if candidate.suffix.lower() not in CODE or not exists(candidate):
            continue
        if not include_tests and any(part in TEST_DIRS for part in candidate.parts):
            continue
        if roots and not any(candidate.is_relative_to(root) for root in roots):
            continue
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            files.append(candidate)
    return files


def _git_changed_files(paths, include_tests=False):
    """Changed and untracked files from git, filtered to scannable code files.

    Git runs anchored at the first given path (its directory), so one call
    scans one repository regardless of the process working directory.
    Returns None when git is unavailable or that directory is not inside a
    repository.
    """
    if not paths:
        return []
    anchor = Path(paths[0])
    if not anchor.is_dir():
        anchor = anchor.parent
    prefix = ("git", "-C", str(anchor))
    commands = (
        prefix + ("diff", "--name-only", "HEAD"),
        prefix + ("ls-files", "--others", "--exclude-standard"),
    )
    names = []
    try:
        for command in commands:
            result = subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=30, check=False,
            )
            if result.returncode != 0:
                return None
            names.extend(result.stdout.splitlines())
    except OSError:
        return None
    joined = [str(anchor / name) for name in names]
    return _filter_changed(joined, [Path(p) for p in paths], include_tests=include_tests)


def scan(paths, include_tests=False):
    texts = {}
    findings = []
    for path in iter_files(paths, include_tests):
        if path.stat().st_size > MAX_FILE_BYTES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        texts[path] = text
        findings.extend(scan_text(path, text))
    findings.extend(_reduced_motion_findings(texts))
    findings.extend(_motion_uniform_findings(texts))
    findings, suppressed = _apply_config(findings, _load_sloprc(paths))
    findings.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.file, f.line))
    return findings, len(texts), suppressed


def main(argv=None):
    parser = argparse.ArgumentParser(description="Scan UI source for generic-default tells and craft defects.")
    parser.add_argument("paths", nargs="+", help="files or directories to scan")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    parser.add_argument("--include-tests", action="store_true", help="also scan test and fixture directories")
    parser.add_argument("--limit", type=int, default=200, help="maximum findings to print in text mode")
    parser.add_argument("--changed", action="store_true",
                        help="scan only files git reports as changed or untracked under the given paths")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if args.changed:
        changed = _git_changed_files(args.paths, include_tests=args.include_tests)
        if changed is None:
            print("git is unavailable or this is not a git repository; --changed needs both")
            return 2
        if not changed:
            print("no changed files to scan")
            return 0
        scan_paths = changed
    else:
        scan_paths = args.paths

    try:
        findings, scanned, suppressed = scan(scan_paths, include_tests=args.include_tests)
    except ValueError as exc:
        parser.error(f"invalid .sloprc: {exc}")
    blocking = sum(f.severity == "blocking" for f in findings)

    if args.json:
        print(json.dumps([asdict(f) for f in findings], ensure_ascii=False, indent=2))
    else:
        for finding in findings[: args.limit]:
            print(f"{finding.severity:<9} {finding.rule:<24} {finding.file}:{finding.line}  {finding.snippet}")
            print(f"{'':<9} {'':<24} {finding.message}")
        if len(findings) > args.limit:
            print(f"... {len(findings) - args.limit} more; use --json or a higher --limit")
        counts = {level: sum(f.severity == level for f in findings) for level in SEVERITY_ORDER}
        suffix = f"; {suppressed} suppressed by .sloprc" if suppressed else ""
        print(
            f"scanned {scanned} file{'s' if scanned != 1 else ''}: "
            f"{counts['blocking']} blocking, {counts['important']} important, "
            f"{counts['review']} review, {counts['polish']} polish{suffix}"
        )
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
