"""Audit rendered-page accessibility on a live page over CDP.

Usage:
  python page_audit.py URL [--json] [--allow-private] [--limit N]

One persistent headless browser (sibling cdp.py; the launch sequence is shared
with visual_capture.py) navigates the URL, then a single Runtime.evaluate
collects two datasets. Text pairs (v1) are reported per the uncertainty
taxonomy in notes/roadmap-0.1.3-2.0.md (修订 2):

- resolved        an ancestor background-color with alpha > 0 was found;
                  translucent layers are composited over the canvas first,
                  then Python computes the WCAG ratio (pass/FAIL verdict)
- assumed-canvas  nothing opaque up to the root; measured against the canvas
                  color implied by prefers-color-scheme — the assumption is
                  stated in the report header and counted in the summary
- uncertain:*     a gradient/image behind the text, opacity/blend/filter in
                  the ancestor chain, a fixed/sticky overlay covering the
                  text, or a color wcag.parse_color rejects — listed with
                  their evidence and NEVER verdicted; the visual capture loop
                  is the only way to settle these
- skipped         invisible text (display:none, visibility hidden, zero-size
                  rect, font-size 0) — counted, not listed

v2 adds three WCAG 2.2 non-contrast checks through the same taxonomy
(covered clauses are named in the report header):

- TARGET-SIZE (2.5.8, AA)  pointer target boxes of button / a[href] /
                  input[type=button|submit|reset] / select / [role=button]
                  measured from the border box; below 24x24 CSS px is a
                  measurable FAIL (important). Inline text links inside a
                  paragraph get "uncertain:inline-link" — the 2.5.8 Inline
                  exception (size constrained by the line-height of
                  non-target text) needs the rendered line, so they are
                  listed and never verdicted.
- ARIA-NAME (4.1.2 / 1.1.1 subset, A)  buttons, links, images and form
                  fields need a name from aria-label, aria-labelledby,
                  title, alt, value, a label element or text content;
                  placeholder is not a name; alt="" (decorative) counts as a
                  valid alternative. Unnamed = measurable FAIL (important);
                  the message says what was absent. Named elements only
                  raise the pass count.
- HEADING-ORDER (APG/WAI structure guidance, NOT a WCAG failure)  heading
                  rank jumps that open a subsection (h1 -> h3) and a missing
                  h1 are review-severity findings; skipping ranks when
                  closing subsections is allowed.

Every finding lands in exactly one bucket (measurable pass/FAIL, uncertain,
review). Uncertain findings describe what was seen; they never masquerade as
pass/fail. page_audit supplements, never replaces, the capture loop.

Exit status: 0 no measurable failures (contrast pairs, undersized targets or
unnamed controls), 1 at least one FAIL, 2 no browser or browser/CDP failure
({"verified": false, "reason": ...} — the tool claims nothing about the
page), 3 URL rejected (visual_capture.validate_url).

Read-only: prints a report and writes nothing. stdlib only; CDP on loopback.
"""

import argparse
import json
import shutil
import sys

sys.dont_write_bytecode = True
import cdp  # noqa: E402  (sibling module; no third-party dependencies)
import visual_capture  # noqa: E402  (validate_url / find_browser / launch)
import wcag  # noqa: E402

MAX_ROWS = 400
MAX_COVERS = 20
MAX_FINDINGS = 200
SNIPPET_CHARS = 60
LOAD_TIMEOUT = 10.0
LARGE_SIZE = 24.0
LARGE_BOLD_SIZE = 18.66
BOLD_WEIGHT = 700
TARGET_FLOOR = 24.0  # WCAG 2.5.8: 24x24 CSS px minimum pointer target

CANVAS_ASSUMPTION = (
    "text with no opaque ancestor background was measured against the "
    "{scheme} canvas color {canvas} (prefers-color-scheme: {scheme})"
)
CLAUSE_COVERAGE = (
    "WCAG 1.4.3 text contrast; 2.5.8 target size (24x24 CSS px minimum, "
    "Inline exception uncertain); 4.1.2 / 1.1.1 accessible names (subset)"
)

# One evaluate per page. Walks body-scoped elements that directly contain
# non-whitespace text; classification happens in the browser because that is
# where the ancestor chains live; Python only does color math and verdicts.
# __MAX_ROWS__ and __MAX_FINDINGS__ are replaced by Python (str.replace, not
# str.format: the JS is full of braces). Rects are viewport coordinates at
# evaluation time, the same space the fixed/sticky cover rects use.
COLLECTOR_JS = r"""(function () {
  var MAX_ROWS = __MAX_ROWS__;
  var MAX_FINDINGS = __MAX_FINDINGS__;
  var SNIPPET = 60;
  var result;
  try {
    result = collect();
  } catch (err) {
    result = { error: String((err && err.message) || err) };
  }
  return JSON.stringify(result);

  function collect() {
    var dark = false;
    try { dark = window.matchMedia("(prefers-color-scheme: dark)").matches; } catch (e) {}
    var canvas = dark ? "#000000" : "#ffffff";

    var scope = document.body || document.documentElement;
    var universe = [scope];
    var descendants = scope.getElementsByTagName("*");
    for (var di = 0; di < descendants.length; di++) universe.push(descendants[di]);

    // Overlays that can sit on top of text regardless of scroll (v1 heuristic).
    var covers = [];
    for (var ui = 0; ui < universe.length && covers.length < 20; ui++) {
      var ucs = styleOf(universe[ui]);
      if (ucs.position === "fixed" || ucs.position === "sticky") {
        var ucr = universe[ui].getBoundingClientRect();
        if (ucr.width > 0 && ucr.height > 0) {
          covers.push({ el: universe[ui], x: ucr.left, y: ucr.top,
                        w: ucr.width, h: ucr.height });
        }
      }
    }

    var rows = [], skipped = 0, capped = false;
    for (var ri = 0; ri < universe.length; ri++) {
      var el = universe[ri];
      var text = "";
      for (var node = el.firstChild; node; node = node.nextSibling) {
        if (node.nodeType === 3) text += node.nodeValue;
      }
      text = text.replace(/\s+/g, " ").trim();
      if (!text) continue;                 // no direct text: not a text pair
      if (rows.length >= MAX_ROWS) { capped = true; break; }

      var cs = styleOf(el);
      var rect = el.getBoundingClientRect();
      if (cs.display === "none" || cs.visibility === "hidden" || cs.visibility === "collapse"
          || rect.width <= 0 || rect.height <= 0 || parseFloat(cs.fontSize) === 0) {
        skipped += 1;                      // invisible: counted, not listed
        continue;
      }

      // Ancestor chain, innermost first, always to the root: every element in
      // it is an ancestor of the text, so each can affect how it is painted.
      var chain = [];
      for (var walker = el; walker && walker.nodeType === 1; walker = walker.parentElement) {
        chain.push(walker);
      }

      // First background with alpha > 0. An unparsed color format (oklch etc.)
      // counts as opaque; the raw string goes to Python, which parses it.
      var bgIndex = -1;
      for (var bi = 0; bi < chain.length; bi++) {
        var c = channelsOf(styleOf(chain[bi]).backgroundColor);
        if ((c ? c.a : 1) > 0) { bgIndex = bi; break; }
      }

      // A gradient/image is only visible over the resolved color while it sits
      // at or in front of it; behind an opaque background it cannot matter.
      var method = null, evidence = null;
      var gradientLimit = bgIndex < 0 ? chain.length : bgIndex + 1;
      for (var gi = 0; gi < gradientLimit; gi++) {
        var image = styleOf(chain[gi]).backgroundImage;
        if (image && image !== "none") {
          method = "uncertain:gradient-or-image";
          evidence = image;
          break;
        }
      }

      // Opacity < 1 composites the whole subtree; blend/filter change what is
      // really painted anywhere in the chain — full-chain scan on purpose.
      if (!method) {
        for (var fi = 0; fi < chain.length; fi++) {
          var fs = styleOf(chain[fi]);
          var why = null;
          if (parseFloat(fs.opacity) < 1) why = "opacity=" + fs.opacity;
          else if (fs.mixBlendMode && fs.mixBlendMode !== "normal") why = "mix-blend-mode=" + fs.mixBlendMode;
          else if (fs.filter && fs.filter !== "none") why = "filter=" + fs.filter;
          if (why) {
            method = "uncertain:blend-or-filter";
            evidence = tagOf(chain[fi]) + " " + why;
            break;
          }
        }
      }

      if (!method) {
        for (var ci = 0; ci < covers.length; ci++) {
          var cover = covers[ci];
          if (cover.el.contains(el)) continue;  // own container is not a cover
          if (rect.left < cover.x + cover.w && rect.right > cover.x
              && rect.top < cover.y + cover.h && rect.bottom > cover.y) {
            method = "uncertain:occluded";
            evidence = tagOf(cover.el);
            break;
          }
        }
      }

      var bg = null;
      if (!method) {
        if (bgIndex < 0) {
          method = "assumed-canvas";
          bg = canvas;
        } else {
          method = "resolved";
          var raw = styleOf(chain[bgIndex]).backgroundColor;
          var top = channelsOf(raw);
          if (!top || top.a >= 1) {
            bg = raw;                     // opaque, or an exotic format for Python
          } else {
            // Semi-transparent first, then compute: composite the translucent
            // layers over what is behind them, canvas last.
            var acc = channelsOf(canvas);
            for (var li = chain.length - 1; li >= bgIndex; li--) {
              var layer = channelsOf(styleOf(chain[li]).backgroundColor);
              if (layer && layer.a > 0) acc = over(layer, acc);
            }
            bg = rgbString(acc);
          }
        }
      }

      var fg = cs.color;
      var fgC = channelsOf(fg);
      if (fgC && fgC.a < 1) {
        var bgC = channelsOf(bg);
        if (bgC) fg = rgbString(over(fgC, bgC));  // translucent text: composite first
      }

      rows.push({
        method: method,
        fg: fg,
        bg: bg,
        font_size: parseFloat(cs.fontSize),
        font_weight: parseFloat(cs.fontWeight) || 0,
        rect: roundedRect(rect),
        text: text.slice(0, SNIPPET),
        tag: tagOf(el),
        evidence: evidence
      });
    }

    var a11y = collectFindings(scope);
    return {
      color_scheme: dark ? "dark" : "light",
      canvas: canvas,
      rows: rows,
      skipped: skipped,
      capped: capped,
      limit: MAX_ROWS,
      findings: a11y.findings,
      findings_capped: a11y.findings_capped
    };
  }

  // --- v2: WCAG 2.2 non-contrast findings (same uncertain taxonomy) -------

  function collectFindings(scope) {
    var findings = [], findings_capped = false;
    function addFinding(f) {
      if (findings.length >= MAX_FINDINGS) { findings_capped = true; return; }
      findings.push(f);
    }

    // TARGET-SIZE (2.5.8) and ARIA-NAME (4.1.2 / 1.1.1 subset). Invisible
    // elements are not rendered targets, so they are out of scope entirely.
    var named = scope.querySelectorAll(
      "button, a[href], select, textarea, [role=button], img, input");
    for (var ti = 0; ti < named.length; ti++) {
      var el = named[ti];
      var cs = styleOf(el);
      if (cs.display === "none" || cs.visibility === "hidden" || cs.visibility === "collapse") continue;
      var tag = el.tagName.toLowerCase();
      var type = (el.getAttribute("type") || "").toLowerCase();
      var roleButton = el.getAttribute("role") === "button";
      var rect = el.getBoundingClientRect();

      var sizeTarget = tag === "button" || tag === "select"
        || (tag === "a" && el.hasAttribute("href"))
        || roleButton
        || (tag === "input" && (type === "button" || type === "submit" || type === "reset"));
      if (sizeTarget) {
        // Inline exception: a text link in a paragraph, sized by the
        // line-height of non-target text — listed, never verdicted.
        if (tag === "a" && cs.display === "inline" && el.closest("p")) {
          addFinding({ check: "TARGET-SIZE", method: "uncertain:inline-link",
                       tag: tagOf(el), text: textSnippet(el), rect: roundedRect(rect) });
        } else {
          addFinding({ check: "TARGET-SIZE", kind: "measure",
                       tag: tagOf(el), rect: roundedRect(rect) });
        }
      }

      var nameable = tag === "img" || tag === "select" || tag === "textarea" || tag === "button"
        || (tag === "a" && el.hasAttribute("href")) || roleButton
        || (tag === "input" && type !== "hidden");
      if (nameable) {
        var name = nameSources(el);
        addFinding({ check: "ARIA-NAME", kind: "measure", tag: tagOf(el),
                     name: name.first, absent: name.absent, note: name.note,
                     rect: roundedRect(rect) });
      }
    }

    // HEADING-ORDER: rank jumps that open a subsection, and a missing h1.
    var heads = scope.querySelectorAll("h1,h2,h3,h4,h5,h6,[role=heading]");
    var prev = null, seenH1 = false;
    for (var hi = 0; hi < heads.length; hi++) {
      var head = heads[hi];
      var hcs = styleOf(head);
      if (hcs.display === "none" || hcs.visibility === "hidden" || hcs.visibility === "collapse") continue;
      var htag = head.tagName.toLowerCase();
      var level = /^h[1-6]$/.test(htag)
        ? parseInt(htag.charAt(1), 10)
        : (parseInt(head.getAttribute("aria-level"), 10) || 2);
      if (level === 1) seenH1 = true;
      if (prev && level > prev.level + 1) {
        addFinding({ check: "HEADING-ORDER", kind: "review", tag: tagOf(head),
                     prev_tag: prev.tag, from: prev.level, to: level,
                     rect: roundedRect(head.getBoundingClientRect()) });
      }
      prev = { tag: tagOf(head), level: level };
    }
    if (!seenH1) {
      addFinding({ check: "HEADING-ORDER", kind: "review", tag: null, missing: "h1" });
    }
    return { findings: findings, findings_capped: findings_capped };
  }

  // First accessible-name source wins (APG Button pattern order: content,
  // aria-labelledby / aria-label, plus title / alt / value / label element).
  function nameSources(el) {
    var tag = el.tagName.toLowerCase();
    var type = (el.getAttribute("type") || "").toLowerCase();
    var first = null, absent = [], note = null;
    function take(source, value) {
      if (!first) first = source + ": " + value.slice(0, 40);
    }
    var ariaLabel = (el.getAttribute("aria-label") || "").trim();
    if (ariaLabel) take("aria-label", ariaLabel); else absent.push("aria-label");
    var labelledby = el.getAttribute("aria-labelledby");
    if (labelledby) {
      var refText = labelledby.trim().split(/\s+/).map(function (id) {
        var ref = document.getElementById(id); return ref ? ref.textContent : "";
      }).join(" ").replace(/\s+/g, " ").trim();
      if (refText) take("aria-labelledby", refText);
      else absent.push("aria-labelledby (resolves to empty)");
    } else absent.push("aria-labelledby");
    var title = (el.getAttribute("title") || "").trim();
    if (title) take("title", title); else absent.push("title");
    if (tag === "img" || type === "image") {
      if (el.hasAttribute("alt")) {
        var alt = (el.getAttribute("alt") || "").trim();
        if (alt) take("alt", alt);
        else if (!first) first = "alt='' (decorative)";  // 1.1.1: null alt is a valid alternative
      } else absent.push("alt");
    }
    if (tag === "input" && (type === "button" || type === "submit" || type === "reset")) {
      var value = (el.getAttribute("value") || "").trim();
      if (value) take("value", value);
      else if (type === "button") absent.push("value");
      else if (!first) first = "UA default (" + (type === "submit" ? "Submit" : "Reset") + ")";
    }
    if (tag === "button" || tag === "a" || roleOf(el) === "button") {
      var imgs = el.querySelectorAll("img"), altText = "";
      for (var ii = 0; ii < imgs.length; ii++) altText += " " + (imgs[ii].getAttribute("alt") || "");
      var text = ((el.textContent || "") + " " + altText).replace(/\s+/g, " ").trim();
      if (text) take("text", text); else absent.push("text content");
    }
    if (el.labels && el.labels.length) {
      var labelText = el.labels[0].textContent.replace(/\s+/g, " ").trim();
      if (labelText) take("label", labelText);
    }
    if (!first && tag === "input" && el.getAttribute("placeholder")) {
      note = "placeholder is not a name";
    }
    return { first: first, absent: absent, note: note };
  }

  function roleOf(el) {
    return el.getAttribute("role");
  }

  function textSnippet(el) {
    return String(el.textContent || "").replace(/\s+/g, " ").trim().slice(0, SNIPPET);
  }

  function roundedRect(rect) {
    return { x: Math.round(rect.left * 10) / 10, y: Math.round(rect.top * 10) / 10,
             width: Math.round(rect.width * 10) / 10,
             height: Math.round(rect.height * 10) / 10 };
  }

  function styleOf(el) {
    return getComputedStyle(el);
  }

  function channelsOf(value) {
    // rgb()/rgba() (comma or space syntax) and #hex, so the canvas constant
    // composes; anything else returns null and the raw string travels on.
    var m = /^#([0-9a-f]{6})$/i.exec(value);
    if (m) {
      var h = m[1];
      return { r: parseInt(h.slice(0, 2), 16), g: parseInt(h.slice(2, 4), 16),
               b: parseInt(h.slice(4, 6), 16), a: 1 };
    }
    m = /^rgba?\(([^)]*)\)$/i.exec(value);
    if (m) {
      var parts = m[1].split(/[,\s\/]+/).filter(function (p) { return p.length > 0; });
      if (parts.length < 3) return null;
      var nums = [];
      for (var i = 0; i < 3; i++) {
        var v = parseFloat(parts[i]);
        if (isNaN(v)) return null;
        nums.push(v);
      }
      var a = 1;
      if (parts.length > 3) {
        a = parseFloat(parts[3]);
        if (isNaN(a)) a = 1;
      }
      return { r: nums[0], g: nums[1], b: nums[2], a: a };
    }
    return null;
  }

  function over(top, bottom) {
    // top painted over an opaque bottom (canvas-resolved chains only).
    return {
      r: top.r * top.a + bottom.r * (1 - top.a),
      g: top.g * top.a + bottom.g * (1 - top.a),
      b: top.b * top.a + bottom.b * (1 - top.a),
      a: 1
    };
  }

  function rgbString(c) {
    return "rgb(" + Math.round(c.r) + ", " + Math.round(c.g) + ", " + Math.round(c.b) + ")";
  }

  function tagOf(el) {
    var cls = typeof el.className === "string" ? el.className.trim().split(/\s+/)[0] : "";
    return cls ? el.tagName.toLowerCase() + "." + cls : el.tagName.toLowerCase();
  }
})()"""


# --- pure logic (no browser; the collector payload is plain dicts) ----------


def threshold_for(row):
    """AA large text (3.0) at >= 24px or >= 18.66px bold; else 4.5."""
    size = float(row.get("font_size") or 0)
    weight = float(row.get("font_weight") or 0)
    if size >= LARGE_SIZE or (size >= LARGE_BOLD_SIZE and weight >= BOLD_WEIGHT):
        return wcag.AA_LARGE_OR_UI
    return wcag.AA_TEXT


def verdict(row):
    """Verdict dict for one measurable row; None for uncertain methods.

    Raises ValueError (from wcag.parse_color / contrast_ratio) when a color
    cannot be parsed; classify_rows turns that into "uncertain:unparseable".
    """
    if str(row.get("method", "")).startswith("uncertain:"):
        return None
    ratio = wcag.contrast_ratio(row["fg"], row["bg"])
    threshold = threshold_for(row)
    return {
        "ratio": round(ratio, 2),
        "threshold": threshold,
        "verdict": "pass" if ratio >= threshold else "FAIL",
    }


def classify_rows(rows, skipped_count=0):
    """Split collector rows into (verdicts, uncertain, skipped_count).

    "resolved" and "assumed-canvas" rows get verdicts; anything starting
    "uncertain:" is listed verbatim and never verdicted; unparseable colors
    become "uncertain:unparseable" instead of crashing; rows marked "skipped"
    (and the browser-side skipped count) only raise the count.
    """
    verdicts, uncertain = [], []
    for row in rows:
        method = str(row.get("method", ""))
        if method == "skipped":
            skipped_count += 1
            continue
        if method in ("resolved", "assumed-canvas"):
            try:
                result = verdict(row)
            except (ValueError, KeyError) as exc:  # unknown color or missing field
                bad = dict(row, method="uncertain:unparseable", evidence=str(exc))
                uncertain.append(bad)
                continue
            verdicts.append(dict(row, **result))
        else:
            uncertain.append(row)
    return verdicts, uncertain, skipped_count


# --- v2 a11y findings (same taxonomy: measurable / uncertain / review) ------


def target_size_verdict(rect):
    """WCAG 2.5.8: the pointer target box must admit a 24x24 CSS px square."""
    width = float((rect or {}).get("width") or 0)
    height = float((rect or {}).get("height") or 0)
    ok = width >= TARGET_FLOOR and height >= TARGET_FLOOR
    return {"status": "pass" if ok else "FAIL"}


def classify_findings(findings):
    """Split collector a11y findings into (measures, uncertain, reviews).

    TARGET-SIZE and ARIA-NAME are measurable: each gets a pass/FAIL status
    with severity important (2.5.8 is AA; 4.1.2/1.1.1 are A). Entries with
    method "uncertain:inline-link" (the 2.5.8 Inline exception) are listed
    and never verdicted; HEADING-ORDER entries are review severity —
    APG/WAI structure guidance, not a WCAG failure.
    """
    measures, uncertain, reviews = [], [], []
    for finding in findings:
        check = finding.get("check")
        if check == "TARGET-SIZE":
            if finding.get("method") == "uncertain:inline-link":
                uncertain.append(dict(finding, status="uncertain", severity="review"))
            else:
                measures.append(dict(
                    finding, severity="important", clause="WCAG 2.5.8",
                    **target_size_verdict(finding.get("rect", {}))))
        elif check == "ARIA-NAME":
            measures.append(dict(
                finding, severity="important", clause="WCAG 4.1.2 / 1.1.1",
                status="pass" if finding.get("name") else "FAIL"))
        elif check == "HEADING-ORDER":
            reviews.append(dict(
                finding, status="review", severity="review",
                clause="APG/WAI structure guidance (not a WCAG failure)"))
    return measures, uncertain, reviews


def a11y_message(entry):
    """Human message for one classified a11y finding, evidence included."""
    check = entry.get("check")
    tag = entry.get("tag") or "(page)"
    rect = entry.get("rect") or {}
    dims = f"{rect.get('width', 0):g}x{rect.get('height', 0):g} at ({rect.get('x', 0):g}, {rect.get('y', 0):g})"
    if check == "TARGET-SIZE":
        if entry.get("status") == "uncertain":
            return (f"inline text link {tag} {dims} — 2.5.8 Inline exception: "
                    f"size constrained by the line-height of non-target text; visual check decides")
        if entry.get("status") == "FAIL":
            return (f"{tag} pointer target {dims} is below the {TARGET_FLOOR:g}x{TARGET_FLOOR:g} "
                    f"CSS px floor (WCAG 2.5.8 AA); spacing/equivalent/essential "
                    f"exceptions need judgement")
        return f"{tag} pointer target {dims} meets the {TARGET_FLOOR:g}x{TARGET_FLOOR:g} CSS px floor (WCAG 2.5.8)"
    if check == "ARIA-NAME":
        if entry.get("name"):
            return f"{tag} named via \"{entry['name']}\""
        absent = entry.get("absent") or []
        missing = ", ".join(f"no {part}" for part in absent)
        note = f"; {entry['note']}" if entry.get("note") else ""
        return f"{tag} has no accessible name ({missing}){note} (WCAG 4.1.2 / 1.1.1)"
    if check == "HEADING-ORDER":
        if entry.get("missing") == "h1":
            return (f"no h1 on the page; WAI structure guidance: the most important "
                    f"heading is rank 1 (not a WCAG failure)")
        return (f"heading level jumps {entry.get('prev_tag')} (h{entry.get('from')}) "
                f"to {tag} (h{entry.get('to')}); skipping ranks confuses structure "
                f"(WAI/APG guidance, not a WCAG failure)")
    return str(entry)


def build_report(url, payload):
    """Full report dict from one collector payload (real or synthetic)."""
    verdicts, uncertain, skipped = classify_rows(
        payload.get("rows", []), payload.get("skipped", 0))
    fails = [row for row in verdicts if row["verdict"] == "FAIL"]
    passes = [row for row in verdicts if row["verdict"] != "FAIL"]
    measures, uncertain_findings, reviews = classify_findings(payload.get("findings", []))
    a11y_fails = [m for m in measures if m["status"] == "FAIL"]
    scheme = payload.get("color_scheme", "light")
    canvas = payload.get("canvas", "#ffffff")
    summary = {
        "checked": len(verdicts) + len(uncertain),
        "pass": len(passes),
        "fail": len(fails),
        "uncertain": len(uncertain),
        "skipped": skipped,
        "assumed_canvas": sum(1 for row in verdicts if row["method"] == "assumed-canvas"),
        "capped": bool(payload.get("capped")),
        # a11y measures: fails listed, passes counted (a healthy page has too
        # many named buttons to list); reviews are listed, never exit-driving.
        "target_size": sum(1 for f in a11y_fails if f["check"] == "TARGET-SIZE"),
        "target_pass": sum(1 for m in measures if m["check"] == "TARGET-SIZE" and m["status"] == "pass"),
        "aria_name": sum(1 for f in a11y_fails if f["check"] == "ARIA-NAME"),
        "name_pass": sum(1 for m in measures if m["check"] == "ARIA-NAME" and m["status"] == "pass"),
        "heading_order": len(reviews),
        "findings_capped": bool(payload.get("findings_capped")),
    }
    if summary["capped"]:
        summary["limit"] = payload.get("limit", MAX_ROWS)
    a11y = [dict(entry, message=a11y_message(entry))
            for entry in a11y_fails + reviews + uncertain_findings]
    return {
        "url": url,
        "verified": True,
        "color_scheme": scheme,
        "canvas_assumption": CANVAS_ASSUMPTION.format(scheme=scheme, canvas=canvas),
        "clause_coverage": CLAUSE_COVERAGE,
        # FAIL pairs first, then passes, then the uncertain list.
        "results": fails + passes + uncertain,
        # a11y: FAILs first, then review entries, then inline-link uncertains.
        "a11y": a11y,
        "summary": summary,
    }


def has_measurable_fail(report):
    """Exit rule: any contrast FAIL, undersized target or unnamed control."""
    summary = report["summary"]
    return bool(summary["fail"] or summary["target_size"] or summary["aria_name"])


def render_text(report):
    """Human report: FAILs, then the uncertain list, then reviews, summary."""
    lines = [
        f"Page audit: {report['url']}",
        f"Clauses: {report.get('clause_coverage', CLAUSE_COVERAGE)}",
        f"Canvas assumption: {report['canvas_assumption']}",
    ]
    for row in report["results"]:
        if row.get("verdict") == "FAIL":
            rect = row["rect"]
            lines.append(
                f"FAIL {row['fg']} on {row['bg']} {row['ratio']:.2f}:1 "
                f"(needs {row['threshold']:.2f} for {row['font_size']:g}px"
                f"/{row['font_weight']:g}) \"{row['text']}\" {row['tag']} "
                f"rect ({rect['x']:g}, {rect['y']:g}) {rect['width']:g}x{rect['height']:g}"
            )
    for entry in report.get("a11y", []):
        if entry.get("status") == "FAIL":
            lines.append(f"FAIL {entry['check']} {entry['tag']} — {entry['message']}")
    for row in report["results"]:
        method = str(row.get("method", ""))
        if method.startswith("uncertain:"):
            line = f"UNCERTAIN {method} \"{row['text']}\" {row['tag']}"
            if row.get("evidence"):
                line += f" [{row['evidence']}]"
            lines.append(line)
    for entry in report.get("a11y", []):
        if entry.get("status") == "uncertain":
            lines.append(f"UNCERTAIN {entry['method']} \"{entry.get('text', '')}\" {entry['tag']} [{entry['message']}]")
    for entry in report.get("a11y", []):
        if entry.get("status") == "review":
            lines.append(f"REVIEW {entry['check']} {entry.get('tag') or '(page)'} — {entry['message']}")
    summary = report["summary"]
    tail = (f"checked {summary['checked']} text pairs: {summary['pass']} pass, "
            f"{summary['fail']} fail, {summary['uncertain']} uncertain, "
            f"{summary['skipped']} skipped ({summary['assumed_canvas']} assumed canvas)")
    if summary.get("capped"):
        tail += f" [capped at {summary.get('limit', MAX_ROWS)} entries]"
    lines.append(tail)
    a11y_tail = (f"a11y: {summary['target_size']} target-size fails ({summary['target_pass']} pass), "
                 f"{summary['aria_name']} unnamed ({summary['name_pass']} named), "
                 f"{summary['heading_order']} heading-order reviews")
    if summary.get("findings_capped"):
        a11y_tail += f" [findings capped at {MAX_FINDINGS}]"
    lines.append(a11y_tail)
    return "\n".join(lines)


# --- browser path (raises on any failure; main() reports "claims nothing") --


def _evaluate_collector(session, session_id, limit):
    """Run the collector once the page has settled (load + fonts.ready)."""
    expression = (
        "(async () => {"
        "try { if (document.fonts && document.fonts.ready) await document.fonts.ready; }"
        " catch (e) {}"
        "return " + COLLECTOR_JS.replace("__MAX_ROWS__", str(max(1, limit)))
        .replace("__MAX_FINDINGS__", str(MAX_FINDINGS)) + ";"
        "})()"
    )
    result = session.send(
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True, "awaitPromise": True},
        session=session_id,
    )
    value = result["result"].get("value")
    if not isinstance(value, str):
        raise cdp.BrowserError("collector returned no data (evaluation blocked?)")
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise cdp.BrowserError("collector returned unexpected data")
    if payload.get("error"):
        raise cdp.BrowserError(f"collector failed on the page: {payload['error']}")
    return payload


def audit_url(url, limit=MAX_ROWS):
    """Launch one browser, navigate, collect rows; return the payload.

    Raises on any failure (no browser, CDP trouble, collector error) so main()
    can print {"verified": false} and claim nothing about the page.
    """
    browser = visual_capture.find_browser()
    if not browser:
        raise cdp.BrowserError(
            "no Chromium-family browser found at an absolute path; page audit disabled")
    process = profile = connection = session = target_id = None
    try:
        process, profile, ws_url = visual_capture._start_cdp_browser(browser)  # noqa: SLF001 - documented sibling reuse
        connection = cdp.Connection(ws_url)
        session = cdp.Session(connection)
        target_id = session.send("Target.createTarget", {"url": "about:blank"})["targetId"]
        session_id = session.send(
            "Target.attachToTarget", {"targetId": target_id, "flatten": True}
        )["sessionId"]
        for domain in ("Page", "Runtime"):
            session.send(domain + ".enable", session=session_id)
        session.send("Page.navigate", {"url": url}, session=session_id)
        if cdp.wait_for_event(
            session, "Page.loadEventFired", LOAD_TIMEOUT,
            match=lambda message: message.get("sessionId") == session_id,
        ) is None:
            raise cdp.BrowserError(f"page did not fire load within {LOAD_TIMEOUT:g}s")
        return _evaluate_collector(session, session_id, limit)
    finally:
        if session is not None and target_id is not None:
            try:
                session.send("Target.closeTarget", {"targetId": target_id}, timeout=3)
            except Exception:
                pass
        if session is not None:
            try:
                session.send("Browser.close", timeout=3)
            except Exception:
                pass
        if connection is not None:
            connection.close()
        if process is not None:
            process.terminate()
        if profile is not None:
            shutil.rmtree(profile, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Rendered-page WCAG audit over CDP: contrast, target size, "
                    "accessible names, heading order.")
    parser.add_argument("url")
    parser.add_argument("--json", action="store_true", help="print the JSON report instead of text")
    parser.add_argument("--allow-private", action="store_true",
                        help="allow non-public, non-loopback addresses")
    parser.add_argument("--limit", type=int, default=MAX_ROWS,
                        help=f"max text rows to collect (default {MAX_ROWS})")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    try:
        url = visual_capture.validate_url(args.url, allow_private=args.allow_private)
    except visual_capture.UrlRejected as exc:
        print(json.dumps({"verified": False, "reason": f"URL rejected: {exc}"}, ensure_ascii=False))
        return 3

    try:
        payload = audit_url(url, limit=args.limit)
    except Exception as exc:  # noqa: BLE001 - the documented "claims nothing" contract
        print(json.dumps({
            "verified": False,
            "reason": f"no audit performed: {type(exc).__name__}: {exc}",
        }, ensure_ascii=False))
        return 2

    report = build_report(url, payload)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(report))
    return 1 if has_measurable_fail(report) else 0


if __name__ == "__main__":
    sys.exit(main())
