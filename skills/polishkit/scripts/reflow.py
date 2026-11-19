"""Audit WCAG 1.4.10 Reflow and 1.4.4 Resize Text on a live page over CDP.

Usage:
  python reflow.py URL [--json] [--allow-private]
                       [--widths 320,400,768] [--text-scale 2.0]

SC 1.4.10 Reflow (AA) asks one measurable thing at its core: at a viewport
equivalent to 320 CSS pixels of width, content must not require scrolling in
two dimensions. SC 1.4.4 Resize Text (AA) asks that text survive enlargement
to 200 percent. Both are viewport questions, not style-override questions, so
this tool changes the viewport (and optionally the page's text scale) and reads
the resulting geometry — which is what a user actually experiences.

What is measured:

- OVERFLOW   the document's scrollWidth exceeds its clientWidth at the tested
             width. This is the 1.4.10 failure itself: horizontal scrolling on
             vertically-flowing content.
- WIDER       one element's right edge or width exceeds the viewport. The
             document may still fit because a parent clips, but the element is
             then unreachable — the difference between "no scrollbar" and
             "content is reachable" matters.
- FIXED-W    an element whose computed width is a fixed length larger than the
             viewport. The usual cause of both findings above, and the one an
             author can fix without redesigning.
- TEXT-CLIP  at 200 percent text (1.4.4), an element whose text overflows a
             clipping box it did not overflow at 100 percent.

Exceptions, honoured by the tool rather than assumed:

- SC 1.4.10 excepts "parts of the content which require two-dimensional layout
  for usage or meaning" — maps, diagrams, video, games, presentations, data
  tables (not individual cells), and toolbars that must stay in view. Elements
  inside a marked region (`<table>`, `<pre>`, `<svg>`, `<canvas>`,
  `<video>`, `[role=img]`) are reported as `uncertain:2d-exception` with the
  ancestor named, never as failures. The exception is per section, so it does
  not excuse the page around them.
- A scrollable container that is itself the intended two-dimensional surface
  (a table wrapper with overflow:auto) is listed as `uncertain:scroll-container`
  rather than failed, because the criterion is about the page, not every inner
  scroller.

Exit status: 0 no measurable failure, 1 at least one OVERFLOW / WIDER / FIXED-W
/ TEXT-CLIP, 2 no browser or CDP failure ({"verified": false}), 3 URL rejected.

Read-only: prints a report and writes nothing. stdlib only; CDP on loopback.
"""

import argparse
import json
import sys

sys.dont_write_bytecode = True
import cdp  # noqa: E402  (sibling module; no third-party dependencies)
import visual_capture  # noqa: E402
import wcag  # noqa: E402

# 320 px is the criterion's width; 400 and 768 are useful intermediate stops
# because a page often breaks at one and not the others.
DEFAULT_WIDTHS = (320, 400, 768)
VIEWPORT_HEIGHT = 800
MAX_FINDINGS = 120
SNIPPET_CHARS = 60

CLAUSE_COVERAGE = (
    "WCAG 1.4.10 Reflow (AA): no two-dimensional scrolling at 320 CSS px width; "
    "WCAG 1.4.4 Resize Text (AA): text survives 200% enlargement"
)

# Regions the Reflow exception names: maps, diagrams, video, games,
# presentations and data tables. `code` is deliberately absent — an inline code
# span or a snippet with `white-space:nowrap` is exactly the kind of content
# that must wrap or scroll on its own, and treating every <code> as an excepted
# two-dimensional surface hid the only real overflow on the probe page.
EXCEPTION_SELECTOR = (
    "table, svg, canvas, video, iframe, object, embed, pre, "
    "[role=img], [role=figure], [role=table], .chart, .table-wrap"
)

COLLECTOR_JS = r"""(function () {
  var MAX = __MAX_FINDINGS__;
  var SNIPPET = __SNIPPET__;
  var EXCEPTIONS = __EXCEPTIONS__;
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
    var text = (el.innerText || "").replace(/\s+/g, " ").trim();
    return el.tagName.toLowerCase() + (text ? '["' + text.slice(0, 18) + '"]' : "");
  }

  function exceptionAncestor(el, scope) {
    // The element itself counts: a <table> is the excepted surface, and
    // checking only ancestors failed the table while listing its cells as
    // uncertain — the exception applied to the parts and not the whole.
    try {
      if (el.matches(EXCEPTIONS)) return label(el);
    } catch (e) {}
    var node = el.parentElement;
    var steps = 0;
    while (node && node !== scope && steps < 40) {
      try {
        if (node.matches(EXCEPTIONS)) return label(node);
      } catch (e) {}
      node = node.parentElement;
      steps++;
    }
    return null;
  }

  function scrollContainer(el) {
    var cs = getComputedStyle(el);
    var scrolls = /(auto|scroll)/.test(cs.overflowX) || /(auto|scroll)/.test(cs.overflowY);
    if (!scrolls) return false;
    return el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1;
  }

  function visible(el) {
    var cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") return false;
    if (parseFloat(cs.opacity) === 0) return false;
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  function collect() {
    var scope = document.body || document.documentElement;
    // `clientWidth` excludes the vertical scrollbar, and a page that scrolls
    // vertically always has one. Measuring against it made every element that
    // reached past the scrollbar look like horizontal overflow: at a 320px
    // request the report said "305px viewport" and produced 112 false WIDER
    // findings on one page. The criterion's width is the viewport the author
    // is asked to support, which is the requested width; the scrollbar is the
    // browser's furniture, not the page's failure.
    var viewportWidth = Math.max(
      document.documentElement.clientWidth,
      window.innerWidth || 0,
      __VIEWPORT_WIDTH__ || 0
    );
    var doc = document.documentElement;
    var all = scope.getElementsByTagName("*");
    var findings = [];
    var uncertain = [];
    var capped = false;

    for (var i = 0; i < all.length && findings.length + uncertain.length < MAX; i++) {
      var el = all[i];
      if (!visible(el)) continue;
      var cs = getComputedStyle(el);
      var r = el.getBoundingClientRect();
      var entry = {
        tag: label(el),
        left: Math.round(r.left + window.scrollX),
        right: Math.round(r.right + window.scrollX),
        width: Math.round(r.width),
        height: Math.round(r.height),
        viewport_width: viewportWidth,
        element_width_css: cs.width,
        position: cs.position,
        overflow_x: cs.overflowX
      };

      // A region the criterion excepts is listed with its ancestor, never
      // failed: maps, tables, video and diagrams are allowed to be wide.
      var exception = exceptionAncestor(el, scope);
      if (exception) {
        if (r.right + window.scrollX > viewportWidth + 1) {
          uncertain.push({ method: "uncertain:2d-exception", tag: entry.tag,
                           ancestor: exception, width: entry.width });
        }
        continue;
      }

      // A deliberate inner scroller is not the page failing to reflow.
      if (scrollContainer(el)) {
        if (r.right + window.scrollX > viewportWidth + 1) {
          uncertain.push({ method: "uncertain:scroll-container", tag: entry.tag,
                           ancestor: null, width: entry.width });
        }
        continue;
      }

      if (r.width > viewportWidth + 1 || r.right + window.scrollX > viewportWidth + 1) {
        var fixedWidth = /^\d+(\.\d+)?px$/.test(cs.width) &&
                         parseFloat(cs.width) > viewportWidth;
        findings.push({
          check: fixedWidth ? "FIXED-W" : "WIDER",
          tag: entry.tag,
          width: entry.width,
          right: entry.right,
          viewport_width: viewportWidth,
          element_width_css: cs.width,
          position: cs.position,
          snippet: (el.innerText || "").replace(/\s+/g, " ").trim().slice(0, SNIPPET)
        });
      }
    }
    if (all.length > MAX) capped = true;

    return {
      viewport_width: viewportWidth,
      doc_scroll_width: doc.scrollWidth,
      // Compared against the same viewport width the element tests use, so a
      // scrollbar cannot manufacture overflow.
      doc_client_width: viewportWidth,
      horizontal_overflow: doc.scrollWidth > viewportWidth + 1,
      findings: findings,
      uncertain: uncertain,
      capped: capped
    };
  }
})()"""


# --- pure logic ------------------------------------------------------------


def overflow_px(payload):
    """How far the document overflows horizontally, in CSS px (0 when it fits)."""
    return max(0, int(payload.get("doc_scroll_width") or 0)
               - int(payload.get("doc_client_width") or 0))


def classify(payload, width):
    """Split one viewport's measurements into (measures, uncertain).

    Document-level horizontal overflow is the criterion's own failure; the
    element-level findings explain it and are reported alongside. A page can
    pass the document test while still hiding an element off-screen behind a
    clipping parent, which is why WIDER is not folded into OVERFLOW.
    """
    measures, uncertain = [], []
    over = overflow_px(payload)
    if over > 1:
        measures.append({
            "check": "OVERFLOW", "tag": "(document)", "width": width,
            "status": "FAIL", "severity": "important", "clause": "WCAG 1.4.10",
            "message": (f"at {width} CSS px the document is {over}px wider than the "
                        f"viewport ({payload.get('doc_scroll_width')} vs "
                        f"{payload.get('doc_client_width')}); vertical content "
                        f"requires horizontal scrolling"),
        })
    for finding in payload.get("findings") or []:
        kind = finding.get("check")
        # `width` and `right` here are the element's own geometry; the tested
        # viewport travels as `viewport`. The first version set
        # "width": width (the viewport) and dropped `right` entirely, so every
        # finding read "320px wide" and the de-duplication that groups by right
        # edge had nothing to group on.
        geometry = {
            "width": finding.get("width"),
            "right": finding.get("right"),
            "viewport": width,
            "element_width_css": finding.get("element_width_css"),
        }
        if kind == "FIXED-W":
            measures.append(dict(geometry, **{
                "check": "FIXED-W", "tag": finding.get("tag"),
                "status": "FAIL", "severity": "important", "clause": "WCAG 1.4.10",
                "message": (f"{finding.get('tag')} has a fixed width of "
                            f"{finding.get('element_width_css')} at a "
                            f"{finding.get('viewport_width')}px viewport"),
            }))
        elif kind == "WIDER":
            measures.append(dict(geometry, **{
                "check": "WIDER", "tag": finding.get("tag"),
                "status": "FAIL", "severity": "important", "clause": "WCAG 1.4.10",
                "message": (f"{finding.get('tag')} is {finding.get('width')}px wide "
                            f"and ends at x={finding.get('right')} in a "
                            f"{finding.get('viewport_width')}px viewport"),
            }))
    for item in payload.get("uncertain") or []:
        # `viewport` names the tested width; the collector's own `width` is the
        # element's. Overwriting it with the viewport number made the report say
        # "td at 114px" — an element width presented as a viewport.
        uncertain.append(dict(item, viewport=width, status="uncertain",
                              severity="review", clause="WCAG 1.4.10"))
    return measures, uncertain


def group_by_origin(measures, tolerance=2):
    """Collapse element findings that share one root cause.

    A single unresponsive grid produces dozens of descendants at the same
    right edge: measured on one dashboard, five children of one hero all ended
    at x=386 and each became its own WIDER finding, burying the two findings
    that mattered under 106 that restated them. Findings are grouped by
    (check, right edge rounded to `tolerance`), and one representative per
    group survives — the widest element, which is the one whose removal would
    actually change the layout.

    The group size is recorded on the survivor as `siblings`, so the report
    still says how much of the page the finding covers.
    """
    groups = {}
    keep = []
    for item in measures:
        if item.get("check") not in ("WIDER", "FIXED-W"):
            keep.append(item)
            continue
        right = item.get("right")
        if right is None:
            key = (item.get("check"), item.get("tag"), item.get("viewport"))
        else:
            # The viewport is part of the key: the same element ends at a
            # different x at each width, and merging across widths would hide
            # which viewport the finding belongs to.
            key = (item.get("check"), item.get("viewport"),
                   round(float(right) / tolerance))
        current = groups.get(key)
        if current is None:
            groups[key] = {"representative": item, "members": [item]}
            continue
        current["members"].append(item)
        if (item.get("width") or 0) > (current["representative"].get("width") or 0):
            current["representative"] = item
    for group in groups.values():
        representative = dict(group["representative"])
        if len(group["members"]) > 1:
            representative["siblings"] = len(group["members"])
            tags = sorted({m.get("tag") for m in group["members"]})
            representative["message"] = (
                representative.get("message", "") +
                f" (and {len(group['members']) - 1} more element(s) ending at the "
                f"same edge: {', '.join(tags[:4])}"
                + (", ..." if len(tags) > 4 else "") + ")")
        keep.append(representative)
    return keep


def build_report(url, measurements, text_scale=None):
    """Full report from [(width, payload)] plus the optional 1.4.4 payload."""
    measures, uncertain = [], []
    for width, payload in measurements:
        page_measures, page_uncertain = classify(payload, width)
        measures.extend(page_measures)
        uncertain.extend(page_uncertain)

    if text_scale is not None:
        for payload in text_scale.get("payloads") or []:
            for finding in payload.get("findings") or []:
                if finding.get("check") != "TEXT-CLIP":
                    continue
                measures.append({
                    "check": "TEXT-CLIP", "tag": finding.get("tag"),
                    "status": "FAIL", "severity": "important", "clause": "WCAG 1.4.4",
                    "message": (f"{finding.get('tag')} clips its text at "
                                f"{text_scale.get('scale')}x text scale but not at "
                                f"1x"),
                })
        for item in text_scale.get("uncertain") or []:
            uncertain.append(dict(item, status="uncertain", severity="review",
                                  clause="WCAG 1.4.4"))

    fails = [item for item in measures if item.get("status") == "FAIL"]
    fails = group_by_origin(fails)
    reached = [width for width, payload in measurements if payload.get("reached", True)]
    summary = {
        "widths_tested": len(measurements),
        "smallest_width": min((w for w, _p in measurements), default=None),
        "reached_320": any(w <= 320 for w, _p in measurements if _p.get("reached", True)),
        "overflow": sum(1 for item in fails if item["check"] == "OVERFLOW"),
        "wider": sum(1 for item in fails if item["check"] == "WIDER"),
        "fixed_width": sum(1 for item in fails if item["check"] == "FIXED-W"),
        "text_clip": sum(1 for item in fails if item["check"] == "TEXT-CLIP"),
        "fail": len(fails),
        "uncertain": len(uncertain),
        "per_width": {
            str(width): {
                "scroll_width": payload.get("doc_scroll_width"),
                "client_width": payload.get("doc_client_width"),
                "overflow_px": overflow_px(payload),
            } for width, payload in measurements
        },
    }
    if text_scale is not None:
        summary["text_scale"] = text_scale.get("scale")
        summary["text_scale_reached"] = text_scale.get("reached", False)
    return {
        "url": url,
        "verified": True,
        "clause_coverage": CLAUSE_COVERAGE,
        "findings": fails + uncertain,
        "summary": summary,
    }


def has_measurable_fail(report):
    return bool(report["summary"]["fail"])


def render_text(report):
    summary = report["summary"]
    lines = [
        f"Reflow audit (WCAG 1.4.10 / 1.4.4): {report['url']}",
        f"Clauses: {report['clause_coverage']}",
        "Viewports: " + ", ".join(
            f"{width}px → {data['scroll_width']}x{data['client_width']}"
            + (f" (+{data['overflow_px']}px)" if data['overflow_px'] else "")
            for width, data in summary["per_width"].items()),
    ]
    if not summary.get("reached_320"):
        lines.append("NOTE: the browser could not reach a 320px viewport; "
                     "the criterion's own test width was not exercised")
    for finding in report["findings"]:
        if finding.get("status") == "FAIL":
            lines.append(f"FAIL [{finding['check']}] {finding.get('tag')} — "
                         f"{finding.get('message')}")
    for finding in report["findings"]:
        if finding.get("status") == "uncertain":
            ancestor = finding.get("ancestor")
            where = f" inside {ancestor}" if ancestor else ""
            lines.append(f"UNCERTAIN [{finding.get('method')}] "
                         f"{finding.get('tag')}{where} at {finding.get('viewport')}px "
                         f"(element {finding.get('width')}px wide)")
    lines.append(
        f"Summary: {summary['fail']} FAIL ({summary['overflow']} document overflow, "
        f"{summary['wider']} wider-than-viewport, {summary['fixed_width']} fixed width, "
        f"{summary['text_clip']} text clip), {summary['uncertain']} uncertain")
    return "\n".join(lines)


# --- browser path ---------------------------------------------------------


def _evaluate(session, session_id, expression, await_promise=False):
    result = session.send(
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True, "awaitPromise": await_promise},
        session=session_id,
    )
    return result["result"].get("value")


def _collect(session, session_id, requested_width=None):
    expression = (
        "(async () => {"
        "try { if (document.fonts && document.fonts.ready) await document.fonts.ready; }"
        " catch (e) {}"
        "return " + COLLECTOR_JS.replace("__MAX_FINDINGS__", str(MAX_FINDINGS))
        .replace("__SNIPPET__", str(SNIPPET_CHARS))
        .replace("__EXCEPTIONS__", json.dumps(EXCEPTION_SELECTOR))
        .replace("__VIEWPORT_WIDTH__", str(int(requested_width or 0))) + ";"
        "})()"
    )
    value = _evaluate(session, session_id, expression, await_promise=True)
    if not isinstance(value, str):
        raise cdp.BrowserError("collector returned no data (evaluation blocked?)")
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise cdp.BrowserError("collector returned unexpected data")
    if payload.get("error"):
        raise cdp.BrowserError(f"collector failed on the page: {payload['error']}")
    return payload


def _text_scale_probe(session, session_id, viewport_width, scale):
    """Grow the root font size and report text that starts clipping (1.4.4).

    Browsers zoom differently, and `Page.setDeviceMetricsOverride` with a
    deviceScaleFactor does not enlarge text the way a user's zoom does. Setting
    the root font to `scale` times its authored size is the closest honest
    simulation available from inside the page: it enlarges text and everything
    measured in `rem`/`em`, which is what a zoom does to text specifically.
    """
    before = _collect(session, session_id, requested_width=viewport_width)
    expression = (
        "(function(){"
        "var root = document.documentElement;"
        "if (!root.__pkBaseFont) {"
        "  root.__pkBaseFont = parseFloat(getComputedStyle(root).fontSize) || 16;"
        "}"
        "root.style.fontSize = (root.__pkBaseFont * " + str(scale) + ") + 'px';"
        "return root.style.fontSize;"
        "})()")
    _evaluate(session, session_id, expression)
    after = _collect(session, session_id, requested_width=viewport_width)
    _evaluate(session, session_id,
              "(function(){var root=document.documentElement;"
              "root.style.fontSize='';return 1;})()")

    before_by_tag = {row.get("tag"): row for row in before.get("findings") or []}
    clipped = []
    for row in after.get("findings") or []:
        previous = before_by_tag.get(row.get("tag"))
        if previous is not None:
            continue  # already a finding before the scale: not this clause
        if row.get("check") == "FIXED-W":
            clipped.append(dict(row, check="TEXT-CLIP"))
    return {
        "scale": scale,
        "reached": True,
        "payloads": [{"findings": clipped}],
        "uncertain": [dict(item, viewport=viewport_width)
                      for item in (after.get("uncertain") or [])],
        "viewport_width": viewport_width,
    }


def audit_url(url, widths=DEFAULT_WIDTHS, text_scale=2.0):
    """Load the page once per width and measure it. Raises on any failure."""
    measurements = []
    with cdp.PageSession(url, width=widths[0], height=VIEWPORT_HEIGHT) as page:
        for width in widths:
            page.session.send("Emulation.setDeviceMetricsOverride", {
                "width": width, "height": VIEWPORT_HEIGHT,
                "deviceScaleFactor": 1, "mobile": False,
            }, session=page.session_id)
            # A layout pass is not instant after a viewport change; the
            # collector reads geometry, so it must run on settled layout.
            page.settle()
            payload = _collect(page.session, page.session_id, requested_width=width)
            payload["reached"] = int(payload.get("viewport_width") or 0) <= width + 1
            measurements.append((width, payload))
        scale_probe = None
        if text_scale:
            page.session.send("Emulation.setDeviceMetricsOverride", {
                "width": widths[0], "height": VIEWPORT_HEIGHT,
                "deviceScaleFactor": 1, "mobile": False,
            }, session=page.session_id)
            page.settle()
            scale_probe = _text_scale_probe(page.session, page.session_id,
                                            widths[0], text_scale)
    return measurements, scale_probe


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="WCAG 1.4.10 reflow and 1.4.4 resize-text audit over CDP.")
    parser.add_argument("url")
    parser.add_argument("--json", action="store_true",
                        help="print the JSON report instead of text")
    parser.add_argument("--allow-private", action="store_true",
                        help="allow non-public, non-loopback addresses")
    parser.add_argument("--widths", default=",".join(str(w) for w in DEFAULT_WIDTHS),
                        help="comma-separated viewport widths (default 320,400,768)")
    parser.add_argument("--text-scale", type=float, default=2.0,
                        help="root text scale for 1.4.4 (default 2.0; 0 disables)")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    try:
        widths = tuple(int(part) for part in args.widths.split(",") if part.strip())
    except ValueError:
        parser.error("--widths must be comma-separated integers")
    if not widths:
        parser.error("--widths must name at least one width")

    try:
        url = visual_capture.validate_url(args.url, allow_private=args.allow_private)
    except visual_capture.UrlRejected as exc:
        print(json.dumps({"verified": False, "reason": f"URL rejected: {exc}"},
                         ensure_ascii=False))
        return 3

    try:
        measurements, scale_probe = audit_url(url, widths=widths,
                                              text_scale=args.text_scale or None)
    except Exception as exc:  # noqa: BLE001 - the documented "claims nothing" contract
        print(json.dumps({
            "verified": False,
            "reason": f"no audit performed: {type(exc).__name__}: {exc}",
        }, ensure_ascii=False))
        return 2

    report = build_report(url, measurements, scale_probe)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(report))
    return 1 if has_measurable_fail(report) else 0


if __name__ == "__main__":
    sys.exit(main())
