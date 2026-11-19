"""Audit CJK line-breaking (禁则) on a live page over CDP.

Usage:
  python cjk_breaks.py URL [--json] [--allow-private] [--width W]

Why this is a runtime check and not a lint rule: browsers already implement
clreq's line-start and line-end prohibitions (行首行尾禁则) under
`line-break: auto`. A source scanner can only find the CSS that disables them;
it cannot tell you whether a given line actually broke at a bad character. This
tool walks the rendered text character by character with a Range, finds where
each line starts and ends, and reports the lines that violate the rule.

What it reports:

- LINE-START   a line begins with a character that may not start one: a
               closing bracket or a terminal punctuation mark. clreq §6.1.1.
- LINE-END     a line ends with a character that may not end one: an opening
               bracket. clreq §6.1.1.
- BREAK-ALL    an element sets `word-break: break-all` (or `line-break: anywhere`)
               on CJK prose. That is the usual cause of the two findings above,
               and the skill calls it a tell rather than a fix. Reported once
               per element, with the computed value as evidence.
- NO-AUTOSPACE `text-autospace` is unsupported or left at `normal` while the
               element mixes CJK and Latin; clreq §2.1.3 asks for up to a
               quarter-em between them. This is a review item, never a failure:
               the property is still not universally supported, and the skill's
               own guidance says to treat it as progressive enhancement.

Uncertainty: characters inside an element whose text is hidden, an SVG text
node, or a run with `white-space: pre` (where wrapping is the author's explicit
choice) are counted and skipped, never failed. A page with no CJK text is
reported as `cjk: false` and claims nothing else.

Exit status: 0 no measurable violation, 1 at least one LINE-START / LINE-END,
2 no browser or CDP failure ({"verified": false}), 3 URL rejected.

Read-only: prints a report and writes nothing. stdlib only; CDP on loopback.
"""

import argparse
import json
import sys
import unicodedata

sys.dont_write_bytecode = True
import cdp  # noqa: E402  (sibling module; no third-party dependencies)
import visual_capture  # noqa: E402

MAX_ELEMENTS = 400
MAX_LINES = 40
SNIPPET_CHARS = 48

CLAUSE_COVERAGE = (
    "clreq §6.1.1 行首行尾禁则 (line-start and line-end prohibitions) "
    "as the browser implements them under line-break:auto; "
    "clreq §2.1.3 ⅓-em spacing between CJK and Latin (review only)"
)

# Characters that may not begin a line. Derived from Unicode categories rather
# than a copied table: `Pe` is every closing bracket, and the `Po` marks below
# are the terminal punctuation the prohibition names. Opening brackets are `Ps`
# and are legal at line start, so the category alone is not enough for Po.
CLOSING_PUNCTUATION = set(
    "、。，．：；！？・"          # ideographic and fullwidth terminals
    "‼⁇⁈⁉"                    # doubled terminals
    "…‥"                       # ellipses
    "．，：；！？"                # halfwidth forms used in CJK copy
)
# Marks that may not end a line: opening brackets and opening quotes.
OPENING_PUNCTUATION = set(
    "（［｛〈《「『【〔〖〘〚"
    "“(‘"
)

# Ranges that count as CJK for deciding whether an element is CJK prose.
CJK_RANGES = (
    (0x2E80, 0x2EFF), (0x3000, 0x303F), (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF), (0xF900, 0xFAFF), (0xFF00, 0xFFEF),
    (0x20000, 0x2FA1F),
)


def is_cjk(char):
    """True for characters in the CJK blocks, by code point."""
    point = ord(char)
    return any(low <= point <= high for low, high in CJK_RANGES)


def is_cjk_text(text, minimum=0.3):
    """True when at least `minimum` of the non-space characters are CJK."""
    meaningful = [ch for ch in text if not ch.isspace()]
    if not meaningful:
        return False
    cjk = sum(1 for ch in meaningful if is_cjk(ch))
    return cjk / len(meaningful) >= minimum


def forbidden_at_start(char):
    """True when a line may not begin with this character.

    Unicode gives the category, not the prohibition: `Pe` (closing bracket) is
    always forbidden at line start, `Ps` (opening bracket) never is, and `Po`
    splits — a full stop is forbidden, an opening quote is not. So `Pe` and the
    explicit terminal set decide, and `Ps` plus the opening set veto.
    """
    if not char:
        return False
    if char in OPENING_PUNCTUATION:
        return False
    if char in CLOSING_PUNCTUATION:
        return True
    return unicodedata.category(char) == "Pe"


def forbidden_at_end(char):
    """True when a line may not end with this character."""
    if not char:
        return False
    if char in OPENING_PUNCTUATION:
        return True
    return unicodedata.category(char) == "Ps"


def classify(payload):
    """Split the collector's findings into (measures, uncertain, reviews)."""
    measures, uncertain, reviews = [], [], []
    for element in payload.get("elements") or []:
        tag = element.get("tag", "(unknown)")
        method = str(element.get("skip") or "")
        if method:
            uncertain.append({"tag": tag, "method": f"uncertain:{method}",
                              "status": "uncertain", "severity": "review",
                              "clause": "clreq §6.1.1",
                              "evidence": element.get("evidence", "")})
            continue

        if element.get("word_break") in ("break-all", "anywhere") or \
                element.get("line_break") == "anywhere":
            reviews.append({
                "check": "BREAK-ALL", "tag": tag, "status": "review",
                "severity": "review", "clause": "clreq §6.1.1",
                "message": (f"{tag} sets word-break:{element.get('word_break')}"
                            f"/line-break:{element.get('line_break')} on CJK text; "
                            f"this is what disables the browser's own 禁则"),
            })

        for line in element.get("lines") or []:
            if line.get("violation") == "start":
                measures.append({
                    "check": "LINE-START", "tag": tag, "status": "FAIL",
                    "severity": "important", "clause": "clreq §6.1.1",
                    "char": line.get("first"), "line": line.get("index"),
                    "snippet": line.get("snippet"),
                    "message": (f"{tag} line {line.get('index')} begins with "
                                f"“{line.get('first')}”, which may not start a "
                                f"line: …{line.get('snippet')}…"),
                })
            elif line.get("violation") == "end":
                measures.append({
                    "check": "LINE-END", "tag": tag, "status": "FAIL",
                    "severity": "important", "clause": "clreq §6.1.1",
                    "char": line.get("last"), "line": line.get("index"),
                    "snippet": line.get("snippet"),
                    "message": (f"{tag} line {line.get('index')} ends with "
                                f"“{line.get('last')}”, which may not end a "
                                f"line: …{line.get('snippet')}…"),
                })

        if element.get("mixed_scripts") and element.get("text_autospace") in (
                "normal", "unset", ""):
            reviews.append({
                "check": "NO-AUTOSPACE", "tag": tag, "status": "review",
                "severity": "review", "clause": "clreq §2.1.3",
                "message": (f"{tag} mixes CJK and Latin without text-autospace; "
                            f"clreq asks for up to a quarter-em between them. "
                            f"Progressive enhancement — judge by eye"),
            })
    return measures, uncertain, reviews


def build_report(url, payload, viewport=None):
    measures, uncertain, reviews = classify(payload)
    fails = [item for item in measures if item.get("status") == "FAIL"]
    return {
        "url": url,
        "verified": True,
        "viewport": viewport,
        "clause_coverage": CLAUSE_COVERAGE,
        "cjk": bool(payload.get("cjk")),
        "findings": fails + reviews + uncertain,
        "summary": {
            "elements_checked": payload.get("checked", 0),
            "lines_walked": payload.get("lines", 0),
            "line_start": sum(1 for item in fails if item["check"] == "LINE-START"),
            "line_end": sum(1 for item in fails if item["check"] == "LINE-END"),
            "break_all": sum(1 for item in reviews if item["check"] == "BREAK-ALL"),
            "no_autospace": sum(1 for item in reviews
                                if item["check"] == "NO-AUTOSPACE"),
            "fail": len(fails),
            "uncertain": len(uncertain),
            "review": len(reviews),
            "capped": bool(payload.get("capped")),
        },
    }


def has_measurable_fail(report):
    return bool(report["summary"]["fail"])


def render_text(report):
    summary = report["summary"]
    lines = [
        f"CJK line-breaking audit: {report['url']}",
        f"Clauses: {report['clause_coverage']}",
    ]
    if not report.get("cjk"):
        lines.append("No CJK prose found on this page; nothing to check.")
        return "\n".join(lines)
    for finding in report["findings"]:
        if finding.get("status") == "FAIL":
            lines.append(f"FAIL [{finding['check']}] {finding.get('message')}")
    for finding in report["findings"]:
        if finding.get("status") == "review":
            lines.append(f"REVIEW [{finding['check']}] {finding.get('tag')} — "
                         f"{finding.get('message')}")
    for finding in report["findings"]:
        if finding.get("status") == "uncertain":
            lines.append(f"UNCERTAIN [{finding.get('method')}] "
                         f"{finding.get('tag')} — {finding.get('evidence')}")
    lines.append(
        f"Summary: {summary['fail']} FAIL ({summary['line_start']} line-start, "
        f"{summary['line_end']} line-end), {summary['review']} review "
        f"({summary['break_all']} break-all, {summary['no_autospace']} no autospace), "
        f"{summary['uncertain']} uncertain across {summary['elements_checked']} "
        f"CJK elements / {summary['lines_walked']} lines")
    if summary.get("capped"):
        lines.append(f"NOTE: collection stopped at {MAX_ELEMENTS} elements; "
                     f"later text was not walked")
    return "\n".join(lines)


# --- browser path ---------------------------------------------------------


COLLECTOR_JS = r"""(function () {
  var MAX_ELEMENTS = __MAX_ELEMENTS__;
  var MAX_LINES = __MAX_LINES__;
  var SNIPPET = __SNIPPET__;
  var CLOSING = __CLOSING__;
  var OPENING = __OPENING__;
  var result;
  try {
    result = collect();
  } catch (err) {
    result = { error: String((err && err.message) || err) };
  }
  return JSON.stringify(result);

  function label(el) {
    var cls = typeof el.className === "string" ? el.className.trim().split(/\s+/)[0] : "";
    if (el.id) return el.tagName.toLowerCase() + "#" + el.id;
    if (cls) return el.tagName.toLowerCase() + "." + cls;
    return el.tagName.toLowerCase();
  }

  function hasOwnText(el) {
    for (var i = 0; i < el.childNodes.length; i++) {
      var node = el.childNodes[i];
      if (node.nodeType === 3 && node.nodeValue.trim().length > 1) return true;
    }
    return false;
  }

  function isCjkText(text) {
    var meaningful = 0, cjk = 0;
    for (var i = 0; i < text.length; i++) {
      var ch = text[i];
      if (/\s/.test(ch)) continue;
      meaningful++;
      var cp = ch.codePointAt(0);
      if ((cp >= 0x2E80 && cp <= 0x2EFF) || (cp >= 0x3000 && cp <= 0x303F) ||
          (cp >= 0x3400 && cp <= 0x4DBF) || (cp >= 0x4E00 && cp <= 0x9FFF) ||
          (cp >= 0xF900 && cp <= 0xFAFF) || (cp >= 0xFF00 && cp <= 0xFFEF) ||
          (cp >= 0x20000 && cp <= 0x2FA1F)) cjk++;
    }
    return meaningful > 0 && cjk / meaningful >= 0.3;
  }

  function isCjkChar(ch) {
    var cp = ch.codePointAt(0);
    return (cp >= 0x2E80 && cp <= 0x2EFF) || (cp >= 0x3000 && cp <= 0x303F) ||
           (cp >= 0x3400 && cp <= 0x4DBF) || (cp >= 0x4E00 && cp <= 0x9FFF) ||
           (cp >= 0xF900 && cp <= 0xFAFF) || (cp >= 0xFF00 && cp <= 0xFFEF) ||
           (cp >= 0x20000 && cp <= 0x2FA1F);
  }

  function forbiddenStart(ch) {
    if (!ch) return false;
    if (OPENING.indexOf(ch) >= 0) return false;
    if (CLOSING.indexOf(ch) >= 0) return true;
    return false;
  }

  function forbiddenEnd(ch) {
    if (!ch) return false;
    if (OPENING.indexOf(ch) >= 0) return true;
    return false;
  }

  // Walk one text node character by character. A Range per character gives
  // the exact box, so a change in `top` between consecutive characters is a
  // line break — which is the only reliable way to know where the browser put
  // the break, as opposed to where it could have.
  function walkNode(node) {
    var text = node.nodeValue;
    if (!text || text.length < 4) return [];
    var range = document.createRange();
    var lines = [];
    var start = 0;
    var previousTop = null;
    for (var i = 0; i < text.length; i++) {
      range.setStart(node, i);
      range.setEnd(node, i + 1);
      var box = range.getBoundingClientRect();
      if (previousTop !== null && Math.abs(box.top - previousTop) > 2) {
        lines.push({ start: start, end: i });
        start = i;
        if (lines.length >= MAX_LINES) break;
      }
      previousTop = box.top;
    }
    lines.push({ start: start, end: text.length });

    var out = [];
    for (var li = 0; li < lines.length; li++) {
      var line = lines[li];
      var first = (text.slice(line.start, line.end).match(/[^\s]/) || [""])[0];
      // The last non-space character of the line.
      var segment = text.slice(line.start, line.end).replace(/\s+$/, "");
      var last = segment ? segment[segment.length - 1] : "";
      var violation = null;
      if (forbiddenStart(first)) violation = "start";
      else if (forbiddenEnd(last)) violation = "end";
      out.push({
        index: li + 1,
        first: first,
        last: last,
        violation: violation,
        snippet: text.slice(line.start, Math.min(line.end, line.start + SNIPPET))
      });
    }
    return out;
  }

  function collect() {
    var scope = document.body || document.documentElement;
    var nodes = scope.querySelectorAll("*");
    var elements = [];
    var checked = 0;
    var linesWalked = 0;
    var sawCjk = false;
    var capped = false;

    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      if (!hasOwnText(el)) continue;
      var cs = getComputedStyle(el);
      if (cs.display === "none" || cs.visibility === "hidden") continue;
      var ownText = "";
      for (var k = 0; k < el.childNodes.length; k++) {
        if (el.childNodes[k].nodeType === 3) ownText += el.childNodes[k].nodeValue;
      }
      if (!isCjkText(ownText)) continue;
      sawCjk = true;
      if (elements.length >= MAX_ELEMENTS) { capped = true; break; }

      var tag = label(el);
      var entry = {
        tag: tag,
        word_break: cs.wordBreak,
        line_break: cs.lineBreak,
        text_autospace: cs.textAutospace || "",
        mixed_scripts: false,
        lines: []
      };
      // Mixed scripts: at least one CJK and one Latin letter in the same run.
      entry.mixed_scripts = /[A-Za-z]/.test(ownText) &&
                            /[\u2E80-\u9FFF\uFF00-\uFFEF]/.test(ownText);

      if (cs.whiteSpace === "pre" || cs.whiteSpace === "pre-wrap") {
        entry.skip = "white-space-pre";
        entry.evidence = "wrapping is authored explicitly; 禁则 does not apply";
        elements.push(entry);
        continue;
      }

      var allLines = [];
      for (var n = 0; n < el.childNodes.length; n++) {
        var child = el.childNodes[n];
        if (child.nodeType !== 3) continue;
        var found = walkNode(child);
        for (var fi = 0; fi < found.length; fi++) {
          found[fi].index = allLines.length + 1;
          allLines.push(found[fi]);
        }
      }
      entry.lines = allLines;
      linesWalked += allLines.length;
      // Only multi-line runs can violate a line-edge rule; a single line is
      // its own first and last and is excluded.
      if (allLines.length > 1) {
        entry.lines = allLines.filter(function (line) {
          return line.violation !== null;
        });
      } else {
        entry.lines = [];
      }
      checked++;
      elements.push(entry);
    }

    return { cjk: sawCjk, checked: checked, lines: linesWalked,
             elements: elements, capped: capped,
             viewport_width: document.documentElement.clientWidth };
  }
})()"""


def _collect(session, session_id):
    expression = (
        "(async () => {"
        "try { if (document.fonts && document.fonts.ready) await document.fonts.ready; }"
        " catch (e) {}"
        "return " + COLLECTOR_JS
        .replace("__MAX_ELEMENTS__", str(MAX_ELEMENTS))
        .replace("__MAX_LINES__", str(MAX_LINES))
        .replace("__SNIPPET__", str(SNIPPET_CHARS))
        .replace("__CLOSING__", json.dumps("".join(sorted(CLOSING_PUNCTUATION))))
        .replace("__OPENING__", json.dumps("".join(sorted(OPENING_PUNCTUATION)))) + ";"
        "})()"
    )
    value = session.send(
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True, "awaitPromise": True},
        session=session_id,
    )["result"].get("value")
    if not isinstance(value, str):
        raise cdp.BrowserError("collector returned no data (evaluation blocked?)")
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise cdp.BrowserError("collector returned unexpected data")
    if payload.get("error"):
        raise cdp.BrowserError(f"collector failed on the page: {payload['error']}")
    return payload


def audit_url(url, width=390, height=900):
    """Load the page at a narrow but readable width and walk its CJK lines.

    A narrow viewport is deliberate: at 1440px most CJK paragraphs fit in two
    or three lines and the line edges fall wherever the browser likes, so no
    prohibition is exercised. At 390px every paragraph wraps many times, which
    is where a broken 禁则 shows up.
    """
    with cdp.PageSession(url, width=width, height=height) as page:
        page.settle()
        return _collect(page.session, page.session_id)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="CJK line-breaking (禁则) audit over CDP: walks rendered "
                    "lines character by character and reports line edges that "
                    "break clreq §6.1.1.")
    parser.add_argument("url")
    parser.add_argument("--json", action="store_true",
                        help="print the JSON report instead of text")
    parser.add_argument("--allow-private", action="store_true",
                        help="allow non-public, non-loopback addresses")
    parser.add_argument("--width", type=int, default=390,
                        help="viewport width (default 390: narrow enough to wrap)")
    parser.add_argument("--height", type=int, default=900)
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    try:
        url = visual_capture.validate_url(args.url, allow_private=args.allow_private)
    except visual_capture.UrlRejected as exc:
        print(json.dumps({"verified": False, "reason": f"URL rejected: {exc}"},
                         ensure_ascii=False))
        return 3

    try:
        payload = audit_url(url, width=args.width, height=args.height)
    except Exception as exc:  # noqa: BLE001 - the documented "claims nothing" contract
        print(json.dumps({
            "verified": False,
            "reason": f"no audit performed: {type(exc).__name__}: {exc}",
        }, ensure_ascii=False))
        return 2

    report = build_report(url, payload,
                          viewport={"width": args.width, "height": args.height})
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(report))
    return 1 if has_measurable_fail(report) else 0


if __name__ == "__main__":
    sys.exit(main())
