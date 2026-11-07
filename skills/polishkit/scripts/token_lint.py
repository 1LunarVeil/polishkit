"""Audit design tokens: definitions, contrast pairs, leaks and scale.

Usage:
  python token_lint.py PATH [PATH ...] [--json] [--limit N]

Read-only. This script is the single owner of design-token auditing;
slop_scan reports pattern tells and never interprets token semantics
(Decision 1 in notes/roadmap-0.1.3-2.0.md). Checks:

  RAW-LEAK      polish    raw hex colors outside token definitions; names the
                          token to use when the value matches one
  DEF-CONTRAST  important token color pairs below the 4.5:1 WCAG text floor;
                          border-vs-bg pairs below 3:1 are review
  MISSING-ROLES review    the token set lacks a semantic role; important when
                          the scanned files define no tokens at all
  UNUSED-TOKEN  polish    a defined token with no var() reference anywhere
  OFF-SCALE     review    radius, shadow blur or duration off the scale in
                          references/layout-and-motion.md
  SEMANTIC-LEAK review    component CSS using a primitive token where a
                          semantic token with the same value exists (v2)

v2 token layers (SEMANTIC-LEAK): defined tokens are classified into a
primitive and a semantic layer by naming convention, modelled on USWDS design
tokens (designsystem.digital.gov/design-tokens/ — system tokens are
family+grade names like blue-60, green-cool-10, indigo-warm-60v, spacing is
numeric units like '05'; theme tokens are role-based like primary/danger) and
on Carbon's color tokens (carbondesignsystem.com/elements/color/tokens/ —
role-based core/contextual tokens like $text-primary, $layer-01,
$border-subtle-00, whose primitives are IBM color grades). The convention:

- a name containing a role word (bg, background, canvas, surface, text, fg,
  muted, border, accent, action, link, icon, focus, primary, secondary,
  layer, field, success, warning, danger, ...) is SEMANTIC — role words win,
  so Carbon-style numeric context suffixes ($layer-01) stay semantic;
- otherwise, when the last name segment is a numeric grade (blue-6, gray-70,
  space-2, '05'), a numeric grade with USWDS's vivid suffix (60v), or a
  t-shirt size (xs, sm, md, lg, xl, 2xl ...), it is PRIMITIVE;
- anything else is unclassified and never reported.

SEMANTIC-LEAK then flags component CSS — var() uses outside token
definitions — that references a primitive token while a semantic token
resolving to the same value exists, and names the semantic token. Aliasing
inside token definitions (--color-action: var(--color-blue-6)) is the
intended mapping layer and is exempt.

v1 heuristics, stated so the limits are visible: raw-value lines are skipped
when they contain "--" or "var(" (definitions and token uses), as in the old
COLOR-RAW-HEX rule; contrast pairs are recognized by name segments —
text/fg/foreground tokens are checked against bg/background/canvas/surface,
and against muted and accent when those names carry no text segment (the
shadcn convention, where --muted is a surface and --muted-foreground is text);
a pair needs a shared qualifier segment, or both names bare. Radius and
duration checks read token definitions only; the shadow check aggregates
box-shadow declarations across the whole scanned set. A brand-color accent
paired against body text can false-positive; findings are prompts for a
decision, not verdicts.

Token sources: CSS custom properties in .css/.scss/.sass/.less files, and
JSON files whose name matches token|theme|variable|design with string values
that look like colors or px sizes.

No rule here is blocking; the command always exits 0 or 2 (2 on usage errors
such as an invalid JSON token file). Unreadable files are skipped with a note
on stderr.
"""

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.dont_write_bytecode = True  # keep the plugin tree free of __pycache__
import wcag  # noqa: E402  (sibling module in this scripts/ directory)

MAX_FILE_BYTES = 1_000_000
SEVERITY_ORDER = {"blocking": 0, "important": 1, "review": 2, "polish": 3}

# File-scope helpers mirror slop_scan (SKIP_DIRS, TEST_DIRS, CODE, _display,
# _snippet, _is_comment): slop_scan does not export them for import, so these
# ~20 lines are duplicated on purpose. Keep the two copies in sync.
SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", "target", "out", ".next", "vendor",
    "__pycache__", ".venv", "venv", "coverage", "release", "_internal",
    "webview2-data", "logs",
}
TEST_DIRS = {"tests", "test", "__tests__", "spec", "fixtures", "mocks"}
MARKUP = {".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".astro"}
STYLE = {".css", ".scss", ".sass", ".less", ".styl"}
SCRIPT = {".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".astro"}
CODE = MARKUP | STYLE | SCRIPT

TOKEN_STYLE = {".css", ".scss", ".sass", ".less"}  # files that can define custom properties
TOKEN_FILE = re.compile(r"token|theme|variable|design", re.IGNORECASE)
HEX = re.compile(r"(?<![\w&-])#[0-9a-fA-F]{3,8}(?![\w-])")
CUSTOM_PROP = re.compile(r"(--[a-zA-Z0-9-]+)\s*:\s*([^;{}]+)")
VAR_REF = re.compile(r"var\(\s*(--[\w-]+)\s*(?:,\s*([^()]*))?\)")
VAR_USE = re.compile(r"var\(\s*(--[\w-]+)")
BOX_SHADOW = re.compile(r"box-shadow\s*:\s*([^;{}]+)", re.IGNORECASE)
COLOR_CALL = re.compile(r"(?:rgba?|hsla?)\([^)]*\)")
COLOR_VALUE = re.compile(r"^(?:#[0-9a-fA-F]{3,8}|rgba?\(|oklch\()")
PX_VALUE = re.compile(r"(\d*\.?\d+)px")
NUMBER = re.compile(r"-?\d*\.?\d+")
DURATION_VALUE = re.compile(r"(\d*\.?\d+)(ms|s)", re.IGNORECASE)

RADIUS_SCALE = {0, 2, 4, 6, 8, 12, 16, 24}
DURATION_FLOOR, DURATION_CEILING = 100, 500  # duration tiers, references/layout-and-motion.md


@dataclass
class Check:
    id: str
    severity: str
    description: str


CHECKS = [
    Check("RAW-LEAK", "polish", "raw hex colors outside token definitions"),
    Check("DEF-CONTRAST", "important", "token color pair below the WCAG text floor"),
    Check("MISSING-ROLES", "review", "token set lacks a semantic role"),
    Check("UNUSED-TOKEN", "polish", "defined token with no var() reference"),
    Check("OFF-SCALE", "review", "radius, shadow blur or duration off the documented scale"),
    Check("SEMANTIC-LEAK", "review",
          "primitive token used where a semantic token has the same value"),
]
SEVERITY = {check.id: check.severity for check in CHECKS}

# Roles are matched as whole name segments (word-boundary aware), so
# --context is not a text role. surface aliases satisfy the background role.
ROLES = [
    ("background", ("bg", "background", "canvas", "surface")),
    ("text", ("text", "fg", "foreground")),
    ("muted", ("muted",)),
    ("border", ("border",)),
    ("accent", ("accent",)),
    ("success", ("success",)),
    ("warning", ("warning",)),
    ("danger", ("danger",)),
]
_ROLE_RES = [
    (label, [re.compile(rf"(?<![a-zA-Z0-9]){alias}(?![a-zA-Z0-9])", re.IGNORECASE) for alias in aliases])
    for label, aliases in ROLES
]
_ALIAS_SEGMENTS = {alias for _, aliases in ROLES for alias in aliases}


@dataclass
class Token:
    name: str  # "--x" for CSS custom properties, dotted path for JSON
    value: str
    file: str
    line: int
    snippet: str


@dataclass
class Finding:
    rule: str
    severity: str
    file: str
    line: int
    snippet: str
    message: str


def _roles(name):
    return {label for label, patterns in _ROLE_RES if any(p.search(name) for p in patterns)}


def _qualifiers(name):
    """Name segments minus role words; the context a role is qualified by."""
    return {
        segment.lower()
        for segment in re.split(r"[^a-zA-Z0-9]+", name)
        if segment and segment.lower() not in _ALIAS_SEGMENTS
    }


# --- v2 token layers (primitive vs semantic; see module docstring) ----------

# Role words beyond the contrast _ALIAS_SEGMENTS: Carbon core/contextual
# naming ($text-primary, $layer-01, $background-hover, $field-02, $interactive),
# the common action/link/icon/focus set, and layout roles (gap/gutter/inset/stack).
SEMANTIC_WORDS = _ALIAS_SEGMENTS | {
    "action", "link", "icon", "focus", "primary", "secondary", "info", "brand",
    "layer", "field", "hover", "active", "selected", "disabled", "inverse",
    "subtle", "strong", "support", "interactive", "on",
    "gap", "gutter", "inset", "stack",
}
# USWDS system-token grades: numeric last segment, optionally USWDS's vivid
# suffix (indigo-warm-60v), or a t-shirt size (xs..xl, 2xl..5xl).
VIVID_GRADE = re.compile(r"^\d+v$", re.IGNORECASE)
SIZE_WORD = re.compile(r"^(?:\d)?(?:xs|sm|md|lg|xl)$", re.IGNORECASE)


def token_layer(name):
    """'primitive', 'semantic' or None for one token name (dotted or --)."""
    segments = [segment.lower() for segment in re.split(r"[^a-zA-Z0-9]+", name) if segment]
    if not segments:
        return None
    if any(segment in SEMANTIC_WORDS for segment in segments):
        return "semantic"
    last = segments[-1]
    if last.isdigit() or VIVID_GRADE.fullmatch(last) or SIZE_WORD.fullmatch(last):
        return "primitive"
    return None


def _value_key(value, by_name):
    """Normalized comparable form of a (possibly aliased) token value."""
    resolved = _resolve(value, by_name).strip()
    return _norm_hex(resolved) if HEX.fullmatch(resolved) else resolved


def _display(path):
    try:
        relative = os.path.relpath(path)
    except ValueError:
        return str(path)
    return str(path) if relative.startswith("..") else relative


def _snippet(line):
    text = " ".join(line.split())
    return text if len(text) <= 140 else text[:137] + "..."


def _is_comment(line):
    stripped = line.strip()
    if stripped.startswith(("//", "/*", "<!--")):
        return True
    return stripped.startswith("*") and "{" not in stripped


def _lines(text):
    return list(enumerate(text.splitlines(), start=1))


def iter_files(paths, include_tests=False):
    # Mirrors slop_scan.iter_files, plus JSON token files: slop_scan's CODE set
    # has no .json, and token_lint needs those.
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
                extension = candidate.suffix.lower()
                if extension in CODE or (extension == ".json" and TOKEN_FILE.search(name)):
                    yield candidate


def _norm_hex(value):
    """Lowercase and expand #abc to #aabbcc (and #abcd to #aabbccdd)."""
    digits = value[1:]
    if len(digits) in (3, 4):
        digits = "".join(char * 2 for char in digits)
    return "#" + digits.lower()


def _token_by_value(tokens):
    """Normalized hex value -> defining token name, for RAW-LEAK suggestions."""
    by_value = {}
    for token in tokens:
        value = token.value.strip()
        if HEX.fullmatch(value):
            by_value.setdefault(_norm_hex(value), token.name)
    return by_value


def _css_tokens(path, text):
    """Custom-property definitions in one style file, in source order."""
    return [
        Token(match.group(1), match.group(2).strip(), _display(path), number, _snippet(line))
        for number, line in _lines(text)
        if not _is_comment(line)
        for match in CUSTOM_PROP.finditer(line)
    ]


def _json_line(text, key):
    found = text.find(f'"{key}"')
    return text.count("\n", 0, found) + 1 if found != -1 else 1


def _json_tokens(path, text):
    """(name, value) pairs from a JSON token file: dotted names, string values
    that look like colors or px sizes. Raises ValueError on invalid JSON."""
    data = json.loads(text)
    out = []

    def walk(node, prefix):
        if isinstance(node, dict):
            for key, value in node.items():
                child = f"{prefix}.{key}" if prefix else str(key)
                if isinstance(value, str):
                    stripped = value.strip()
                    if COLOR_VALUE.match(stripped) or PX_VALUE.fullmatch(stripped):
                        out.append(Token(
                            child, stripped, _display(path), _json_line(text, str(key)),
                            _snippet(f'"{key}": {stripped}'),
                        ))
                elif isinstance(value, (dict, list)):
                    walk(value, child)
        elif isinstance(node, list):
            for item in node:
                walk(item, prefix)

    walk(data, "")
    return out


def _raw_leak_findings(path, text, token_by_value):
    """One finding per file for raw hex colors outside token definitions."""
    if path.suffix.lower() not in CODE:
        return []
    hits = []
    for number, line in _lines(text):
        if _is_comment(line) or "--" in line or "var(" in line:
            continue  # v1 heuristic, as in the old COLOR-RAW-HEX: skip definitions and token uses
        hits.extend((number, line, match.group(0)) for match in HEX.finditer(line))
    if not hits:
        return []
    examples = []
    for _, _, raw in hits[:3]:
        name = token_by_value.get(_norm_hex(raw))
        examples.append(f"{raw} (use var({name}))" if name else f"{raw} (no token)")
    number, line, _ = hits[0]
    return [Finding(
        "RAW-LEAK", SEVERITY["RAW-LEAK"], _display(path), number, _snippet(line),
        f"{len(hits)} raw hex colors outside token definitions, e.g. {', '.join(examples)}"
        " — replace matching values with var(--token) or move them into the token file",
    )]


def _resolve(value, by_name, depth=0):
    """Follow var() aliases (fallback included) up to 5 hops; unknown stays."""
    if depth > 5:
        return value
    match = VAR_REF.fullmatch(value.strip())
    if not match:
        return value.strip()
    target = by_name.get(match.group(1))
    if target is not None:
        return _resolve(target.value, by_name, depth + 1)
    fallback = (match.group(2) or "").strip()
    return _resolve(fallback, by_name, depth + 1) if fallback else value.strip()


def _color_of(token, by_name):
    """Resolved token value if it parses as a color, else None."""
    value = _resolve(token.value, by_name)
    try:
        wcag.parse_color(value)
    except ValueError:
        return None
    return value


def _pairs_together(fg_quals, surface_quals):
    return bool(fg_quals & surface_quals) or (not fg_quals and not surface_quals)


def _contrast_findings(tokens):
    """Definition-site contrast for recognized role pairs.

    Foreground side: names with a text/fg/foreground segment. Background side:
    bg/background/canvas/surface always, muted and accent only when the name
    carries no text segment. Pairs need a shared qualifier, or both names bare.
    Pairs span the whole token set: the token contract is global.
    """
    by_name = {}
    for token in tokens:
        if token.name.startswith("--"):
            by_name.setdefault(token.name, token)
    fgs, surfaces, borders = [], [], []
    for token in tokens:
        roles = _roles(token.name)
        quals = _qualifiers(token.name)
        if "text" in roles:
            fgs.append((token, quals))
            continue
        kinds = set()
        if "background" in roles:
            kinds.add("bg")
        if "muted" in roles:
            kinds.add("muted")
        if "accent" in roles:
            kinds.add("accent")
        if kinds:
            surfaces.append((token, quals, kinds))
        if "border" in roles:
            borders.append((token, quals))

    findings = []
    seen = set()

    def check(side, side_value, surface, surface_value, floor, floor_name, clause):
        ratio = wcag.contrast_ratio(side_value, surface_value)
        if ratio >= floor:
            return
        findings.append(Finding(
            "DEF-CONTRAST", SEVERITY["DEF-CONTRAST"] if floor == wcag.AA_TEXT else "review",
            side.file, side.line, side.snippet,
            f"{side.name} on {surface.name} is {ratio:.2f}:1, below the "
            f"{floor:g}:1 WCAG {floor_name} floor (WCAG {clause})",
        ))

    for fg, fg_quals in fgs:
        fg_value = _color_of(fg, by_name)
        if fg_value is None:
            continue
        for surface, quals, _ in surfaces:
            if not _pairs_together(fg_quals, quals) or (fg.name, surface.name) in seen:
                continue
            seen.add((fg.name, surface.name))
            surface_value = _color_of(surface, by_name)
            if surface_value is not None:
                check(fg, fg_value, surface, surface_value, wcag.AA_TEXT, "AA text", "1.4.3")
    for border, border_quals in borders:
        border_value = _color_of(border, by_name)
        if border_value is None:
            continue
        for surface, quals, kinds in surfaces:
            if "bg" not in kinds or not _pairs_together(border_quals, quals):
                continue
            if (border.name, surface.name) in seen:
                continue
            seen.add((border.name, surface.name))
            surface_value = _color_of(surface, by_name)
            if surface_value is not None:
                check(border, border_value, surface, surface_value, wcag.AA_LARGE_OR_UI, "UI", "1.4.11")
    return findings


def _missing_roles_findings(tokens, first_scanned):
    present = set()
    for token in tokens:
        present |= _roles(token.name)
    missing = [label for label, _ in ROLES if label not in present]
    if not missing:
        return []
    if tokens:
        first = tokens[0]
        return [Finding(
            "MISSING-ROLES", SEVERITY["MISSING-ROLES"], first.file, first.line, first.snippet,
            f"token set is missing roles: {', '.join(missing)}; define a token for each so components stay on the system",
        )]
    if first_scanned is None:
        return []
    # Decision 1: a project with no token contract still gets coverage.
    return [Finding(
        "MISSING-ROLES", "important", _display(first_scanned), 1, "",
        "no design tokens found; define background, text, muted, border, accent, "
        "success, warning and danger tokens so components have a system to use",
    )]


def _unused_findings(css_tokens, texts):
    """Tokens with no var(--name) reference anywhere in the scanned set."""
    if not css_tokens:
        return []
    used = set()
    for text in texts.values():
        used.update(VAR_USE.findall(text))
    unused = sorted({token.name for token in css_tokens} - used)
    if not unused:
        return []
    first = css_tokens[0]
    examples = ", ".join(unused[:5])
    more = f" and {len(unused) - 5} more" if len(unused) > 5 else ""
    return [Finding(
        "UNUSED-TOKEN", SEVERITY["UNUSED-TOKEN"], first.file, first.line, first.snippet,
        f"{len(unused)} token{'s' if len(unused) != 1 else ''} "
        f"{'has' if len(unused) == 1 else 'have'} no var() reference, e.g. {examples}{more}; use them or drop them",
    )]


def _offscale_findings(tokens):
    """Radius and duration tokens off the documented scales."""
    findings = []
    for token in tokens:
        low = token.name.lower()
        if "radius" in low or "rounded" in low:
            off = sorted({float(v) for v in PX_VALUE.findall(token.value) if float(v) not in RADIUS_SCALE})
            if off:
                values = ", ".join(f"{v:g}px" for v in off)
                findings.append(Finding(
                    "OFF-SCALE", SEVERITY["OFF-SCALE"], token.file, token.line, token.snippet,
                    f"{token.name} is {values}, off the radius scale (0, 2, 4, 6, 8, 12, 16, 24)",
                ))
            continue
        match = DURATION_VALUE.fullmatch(token.value.strip())
        if match:
            ms = float(match.group(1)) * (1000 if match.group(2).lower() == "s" else 1)
            if 0 < ms < DURATION_FLOOR or ms > DURATION_CEILING:
                # 0 is honoured: it is the reduced-motion instant value.
                shown = token.value if match.group(2).lower() == "ms" else f"{token.value} ({ms:g}ms)"
                findings.append(Finding(
                    "OFF-SCALE", SEVERITY["OFF-SCALE"], token.file, token.line, token.snippet,
                    f"{token.name} is {shown}, outside the 100-500ms duration tiers "
                    "(references/layout-and-motion.md)",
                ))
    return findings


def _semantic_leak_findings(tokens, texts):
    """Component CSS using a primitive token where a semantic token matches.

    The token contract is layered (USWDS system/theme; Carbon
    primitive/core/component): components consume role tokens, not system
    grades. Aliasing inside token definitions is the mapping layer itself
    and is exempt, so only var() uses on non-definition lines are flagged.
    """
    by_name = {}
    for token in tokens:
        if token.name.startswith("--"):
            by_name.setdefault(token.name, token)
    primitives = {name: token for name, token in by_name.items()
                  if token_layer(name) == "primitive"}
    if not primitives or not any(token_layer(name) == "semantic" for name in by_name):
        return []
    semantic_by_value = {}
    for name, token in by_name.items():
        if token_layer(name) == "semantic":
            semantic_by_value.setdefault(_value_key(token.value, by_name), name)
    findings = []
    for path, text in texts.items():
        if path.suffix.lower() not in CODE:
            continue
        for number, line in _lines(text):
            if _is_comment(line) or CUSTOM_PROP.search(line):
                continue  # definition lines are where mapping is supposed to happen
            for match in VAR_USE.finditer(line):
                name = match.group(1)
                primitive = primitives.get(name)
                if primitive is None:
                    continue
                semantic = semantic_by_value.get(_value_key(primitive.value, by_name))
                if not semantic or semantic == name:
                    continue
                findings.append(Finding(
                    "SEMANTIC-LEAK", SEVERITY["SEMANTIC-LEAK"], _display(path), number,
                    _snippet(line),
                    f"primitive token {name} used in component CSS while semantic "
                    f"{semantic} resolves to the same value — use var({semantic}) "
                    "(components consume role tokens, not system grades; "
                    "USWDS/Carbon token layers)",
                ))
    return findings


def _shadow_blurs(value):
    """Blur length of each shadow in a box-shadow value (offset-x, offset-y, blur)."""
    cleaned = COLOR_CALL.sub(" ", value)
    cleaned = HEX.sub(" ", cleaned)
    blurs = []
    for part in cleaned.split(","):
        lengths = NUMBER.findall(part)
        if len(lengths) >= 3:
            blurs.append(abs(float(lengths[2])))
    return blurs


def _shadow_declarations(path, text):
    return [
        (_display(path), number, _snippet(line), match.group(1))
        for number, line in _lines(text)
        if not _is_comment(line)
        for match in BOX_SHADOW.finditer(line)
    ]


def _shadow_scale_findings(decls):
    """More than 3 distinct blur values across the set means no elevation tiers."""
    blurs = set()
    for _, _, _, value in decls:
        blurs.update(round(blur, 2) for blur in _shadow_blurs(value))
    if len(blurs) <= 3:
        return []
    file, line, snippet, _ = decls[0]
    values = ", ".join(f"{blur:g}px" for blur in sorted(blurs))
    return [Finding(
        "OFF-SCALE", SEVERITY["OFF-SCALE"], file, line, snippet,
        f"{len(blurs)} distinct shadow blur values across the set ({values}); keep at most 3 elevation levels",
    )]


def scan(paths, include_tests=False):
    texts = {}
    css_tokens, json_tokens, shadows = [], [], []
    for path in iter_files(paths, include_tests):
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8-sig", errors="replace")  # -sig: JSON token files may carry a BOM
        except OSError as exc:
            print(f"token_lint: skipping unreadable file {path}: {exc}", file=sys.stderr)
            continue
        texts[path] = text
        extension = path.suffix.lower()
        if extension in TOKEN_STYLE:
            css_tokens.extend(_css_tokens(path, text))
            shadows.extend(_shadow_declarations(path, text))
        elif extension == ".json" and TOKEN_FILE.search(path.name):
            tokens = _json_tokens(path, text)  # ValueError on invalid JSON; main turns it into exit 2
            json_tokens.extend(tokens)
            shadows.extend(
                (token.file, token.line, token.snippet, token.value)
                for token in tokens if "shadow" in token.name.lower()
            )
    tokens = css_tokens + json_tokens
    token_by_value = _token_by_value(tokens)
    findings = []
    for path, text in texts.items():
        findings.extend(_raw_leak_findings(path, text, token_by_value))
    findings.extend(_contrast_findings(tokens))
    findings.extend(_missing_roles_findings(tokens, next(iter(texts), None)))
    findings.extend(_unused_findings(css_tokens, texts))
    findings.extend(_offscale_findings(tokens))
    findings.extend(_shadow_scale_findings(shadows))
    findings.extend(_semantic_leak_findings(tokens, texts))
    findings.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.file, f.line))
    return findings, len(texts)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Audit design tokens: definitions, contrast pairs, leaks and scale.")
    parser.add_argument("paths", nargs="+", help="files or directories to scan")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    parser.add_argument("--limit", type=int, default=200, help="maximum findings to print in text mode")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    try:
        findings, scanned = scan(args.paths)
    except ValueError as exc:
        parser.error(f"invalid token JSON: {exc}")

    if args.json:
        print(json.dumps([asdict(f) for f in findings], ensure_ascii=False, indent=2))
    else:
        for finding in findings[: args.limit]:
            print(f"{finding.severity:<9} {finding.rule:<24} {finding.file}:{finding.line}  {finding.snippet}")
            print(f"{'':<9} {'':<24} {finding.message}")
        if len(findings) > args.limit:
            print(f"... {len(findings) - args.limit} more; use --json or a higher --limit")
        counts = {level: sum(f.severity == level for f in findings) for level in SEVERITY_ORDER}
        print(
            f"scanned {scanned} file{'s' if scanned != 1 else ''}: "
            f"{counts['blocking']} blocking, {counts['important']} important, "
            f"{counts['review']} review, {counts['polish']} polish"
        )
    blocking = sum(f.severity == "blocking" for f in findings)
    return 1 if blocking else 0  # no rule here is blocking, so this is always 0


if __name__ == "__main__":
    sys.exit(main())
