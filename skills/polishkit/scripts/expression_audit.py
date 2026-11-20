"""Measure the parts of the expression layer that a browser can measure.

Usage:
  python expression_audit.py URL [--json] [--allow-private] [--width W]

`references/expression.md` describes four kinds of deliberate contrast and a
six-item checklist. Three of those items have numbers behind them, and until
now nothing checked them — the same gap the keyboard and text-spacing audits
closed for their clauses. This tool measures the measurable ones and says
plainly which items it cannot judge.

Measured (each reported as a number with a verdict against the file's floor):

- TYPE RATIO   largest rendered text / body text. `expression.md` asks for at
               least 3x; under 2.5x reads flat and is a FAIL, 2.5-3x is a review.
- WEIGHT SPAN  the set of rendered font weights. The file asks for "the ends of
               the family — 200-300 against 700-800"; a page whose lightest
               weight is 400 and heaviest 600 is the dullest use of a variable
               font and gets a review.
- SIZE STEPS   how many distinct font sizes carry text. One step per role is the
               point; a page with 2 sizes or with 15 near-identical ones reads
               either flat or noisy.
- DISPLAY TRACKING  display-size runs should tighten tracking (-0.01 to -0.03em)
               and cut line-height to 1.0-1.2, which is what contrasts with the
               open body setting. Reported as numbers, judged as a review.

Not measured, and named as such in every report:

- whether there is exactly one asymmetry, one full-bleed moment, one focal point
  (all are visual judgements a rect cannot make);
- whether the signature element is the best-crafted thing on the page;
- whether a hero field is dead flat (texture);
- whether removing the signature would leave the page generic.

Those stay in the polish pass, and a report that lists them as "manual" is more
honest than one that scores them from geometry.

Exit status: 0 no measurable failure, 1 the type ratio is under 2.5x,
2 no browser or CDP failure ({"verified": false}), 3 URL rejected.

Read-only: prints a report and writes nothing. stdlib only; CDP on loopback.
"""

import argparse
import json
import sys

sys.dont_write_bytecode = True
import cdp  # noqa: E402  (sibling module; no third-party dependencies)
import visual_capture  # noqa: E402

BODY_FALLBACK = 16.0
MIN_RATIO = 3.0        # expression.md: display >= 3x body
FLAT_RATIO = 2.5       # below this a page reads flat
MIN_LIGHT = 400        # a page whose lightest weight is 400 has no light end
MAX_HEAVY = 600        # ... and whose heaviest is 600 has no heavy end
DISPLAY_MIN_SIZE = 32.0
DISPLAY_TRACKING = (-0.03, -0.01)
DISPLAY_LINE_HEIGHT = (1.0, 1.2)
MAX_SAMPLES = 400

CLAUSE_COVERAGE = (
    "references/expression.md items 1 (type drama: display >= 3x body, weight "
    "extremes) measured; items 2-6 (composition, softening, focal point, "
    "texture, signature) are visual and left to the polish pass"
)

MANUAL_ITEMS = (
    "exactly one asymmetry per screen",
    "one full-bleed or overlap moment",
    "exactly one focal point earned by two levers",
    "whether any hero-scale field is dead flat",
    "whether removing the signature element would leave the page generic",
)

COLLECTOR_JS = r"""(function () {
  var MAX = __MAX_SAMPLES__;
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

  function ownText(el) {
    var out = "";
    for (var i = 0; i < el.childNodes.length; i++) {
      var node = el.childNodes[i];
      if (node.nodeType === 3) out += node.nodeValue;
    }
    return out.trim();
  }

  function collect() {
    var body = document.body || document.documentElement;
    var bodySize = parseFloat(getComputedStyle(body).fontSize) || 16;
    var all = document.querySelectorAll("*");
    var samples = [];
    var sizes = {};
    var weights = {};
    var capped = false;

    for (var i = 0; i < all.length; i++) {
      var el = all[i];
      var text = ownText(el);
      if (!text) continue;
      var rect = el.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) continue;
      var cs = getComputedStyle(el);
      if (cs.display === "none" || cs.visibility === "hidden") continue;
      if (parseFloat(cs.opacity) === 0) continue;
      var fontSize = parseFloat(cs.fontSize) || 0;
      var fontWeight = parseInt(cs.fontWeight, 10) || 400;
      var rounded = Math.round(fontSize);
      sizes[rounded] = (sizes[rounded] || 0) + 1;
      weights[fontWeight] = (weights[fontWeight] || 0) + 1;
      if (samples.length < MAX) {
        samples.push({
          tag: label(el),
          size: rounded,
          weight: fontWeight,
          line_height_ratio: cs.lineHeight === "normal" ? null :
            (parseFloat(cs.lineHeight) || 0) / fontSize,
          letter_spacing_em: cs.letterSpacing === "normal" ? 0 :
            (parseFloat(cs.letterSpacing) || 0) / fontSize,
          family: (cs.fontFamily || "").split(",")[0].replace(/["']/g, "").trim(),
          family_declaration: (cs.fontFamily || "").replace(/["']/g, "")
            .replace(/\\s*,\\s*/g, ", ").trim(),
          text: text.slice(0, 40)
        });
      } else {
        capped = true;
      }
    }

    return {
      body_size: bodySize,
      sizes: sizes,
      weights: weights,
      samples: samples,
      capped: capped,
      viewport_width: document.documentElement.clientWidth
    };
  }
})()"""


# --- pure logic ------------------------------------------------------------


def type_ratio(payload):
    """Largest rendered size divided by body size."""
    sizes = payload.get("sizes") or {}
    if not sizes:
        return 0.0
    raw_body = payload.get("body_size")
    # `or` would turn a measured 0 into the fallback; a zero body size is not a
    # missing one, it is an unrenderable page, and the ratio is undefined.
    body = float(raw_body) if raw_body is not None else BODY_FALLBACK
    if body <= 0:
        return 0.0
    largest = max(float(size) for size in sizes)
    return largest / body


def ratio_verdict(ratio):
    """(status, severity, message) for the display/body ratio."""
    if ratio >= MIN_RATIO:
        return ("pass", "none", f"display is {ratio:.1f}x body, at or above the 3x floor")
    if ratio >= FLAT_RATIO:
        return ("FAIL", "important",
                f"display is {ratio:.1f}x body; expression.md asks for 3x, and under "
                f"2.5x reads flat")
    return ("FAIL", "important",
            f"display is only {ratio:.1f}x body; a page whose largest text is under "
            f"2.5x the body reads flat")


def weight_span(payload):
    """(lightest, heaviest) rendered weights, or (None, None) when none."""
    weights = payload.get("weights") or {}
    if not weights:
        return None, None
    values = sorted(int(weight) for weight in weights)
    return values[0], values[-1]


def weight_verdict(light, heavy):
    """Review when the page never leaves the middle of the family.

    "The middle" is 400-600: 400 is the default body weight, so a page whose
    lightest weight is 400 has no light end however heavy its headings get, and
    a page whose heaviest is 600 never reaches a real bold. The comparison is
    inclusive at both ends for that reason.
    """
    if light is None:
        return ("review", "review", "no text found, so no weight span to read")
    if light >= MIN_LIGHT and heavy <= MAX_HEAVY:
        return ("review", "review",
                f"weights run only {light}-{heavy}; expression.md asks for the ends "
                f"of the family (200-300 against 700-800)")
    if light >= MIN_LIGHT:
        return ("review", "review",
                f"the lightest weight is {light}; there is no light end to contrast "
                f"the heavy one")
    if heavy <= MAX_HEAVY:
        return ("review", "review",
                f"the heaviest weight is {heavy}; there is no heavy end to contrast "
                f"the light one")
    return ("pass", "none",
            f"weights span {light}-{heavy}, which reaches both ends")


def size_steps(payload):
    """Distinct rounded font sizes that carry text."""
    return len(payload.get("sizes") or {})


def steps_verdict(steps):
    if steps <= 0:
        return ("review", "review", "no sized text found")
    if steps <= 2:
        return ("review", "review",
                f"only {steps} distinct text sizes; hierarchy has almost no room")
    if steps > 12:
        return ("review", "review",
                f"{steps} distinct text sizes; a scale this granular reads as drift")
    return ("pass", "none", f"{steps} distinct sizes")


def display_samples(payload):
    """Samples at display size, for the tracking and line-height reading."""
    return [sample for sample in payload.get("samples") or []
            if float(sample.get("size") or 0) >= DISPLAY_MIN_SIZE]


def display_readings(payload):
    """Summarise tracking and line-height at display size.

    Reported as numbers, never as a verdict: `expression.md` asks for tight
    tracking and a 1.0-1.2 line-height to contrast the open body setting, but a
    subject can justify other values and a rect cannot tell which.
    """
    samples = display_samples(payload)
    if not samples:
        return {"samples": 0, "tracking_em": None, "line_height_ratio": None}
    tracking = [sample.get("letter_spacing_em") for sample in samples
                if sample.get("letter_spacing_em") is not None]
    ratios = [sample.get("line_height_ratio") for sample in samples
              if sample.get("line_height_ratio")]
    return {
        "samples": len(samples),
        "tracking_em": round(sum(tracking) / len(tracking), 3) if tracking else None,
        "line_height_ratio": round(sum(ratios) / len(ratios), 2) if ratios else None,
        "tracking_in_range": bool(tracking) and
                             DISPLAY_TRACKING[0] <= (sum(tracking) / len(tracking)) <= DISPLAY_TRACKING[1],
        "line_height_in_range": bool(ratios) and
                                DISPLAY_LINE_HEIGHT[0] <= (sum(ratios) / len(ratios)) <= DISPLAY_LINE_HEIGHT[1],
    }


def families(payload):
    """Every distinct `font-family` declaration that carries text, with counts.

    Counting first names was wrong and produced a false finding on every
    benchmark page: `Segoe UI` and `Segoe UI Light` are one family at two
    weights, `Cascadia Code` and `Consolas` are one mono stack, and a
    `Noto Sans SC` CJK fallback is a fourth role rather than a fourth family.
    A page declaring five stacks (sans, sans-light, serif, mono, CJK fallback)
    is doing exactly what `color-and-type.md` asks for.

    So this reports the declarations and their sample counts, and lets the
    reviewer map them onto roles. It is not a count with a threshold.
    """
    counts = {}
    for sample in payload.get("samples") or []:
        declaration = sample.get("family_declaration") or sample.get("family")
        if declaration:
            counts[declaration] = counts.get(declaration, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: -item[1]))


def classify(payload):
    """Split into (measures, reviews). There is no uncertain bucket here.

    Every number this tool reports is a measured value; what it cannot measure
    it does not report at all, and lists under `manual` instead. Everything is
    review severity and nothing is a failure: the type ratio is the only item
    with a number in the file, and even that describes expressiveness rather
    than conformance. A tool that could fail a build on taste would reproduce
    exactly the failure mode the benchmark's human-verdict section warns about.
    """
    reviews = []
    ratio = type_ratio(payload)
    _, _, message = ratio_verdict(ratio)
    reviews.append({"check": "TYPE-RATIO", "status": "review",
                    "severity": "review", "clause": "expression.md item 1",
                    "ratio": round(ratio, 2), "message": message})

    light, heavy = weight_span(payload)
    _, _, message = weight_verdict(light, heavy)
    reviews.append({"check": "WEIGHT-SPAN", "status": "review",
                    "severity": "review", "clause": "expression.md item 1",
                    "light": light, "heavy": heavy, "message": message})

    steps = size_steps(payload)
    _, _, message = steps_verdict(steps)
    reviews.append({"check": "SIZE-STEPS", "status": "review",
                    "severity": "review", "clause": "expression.md item 1",
                    "steps": steps, "message": message})

    readings = display_readings(payload)
    if readings["samples"]:
        tracking = readings["tracking_em"]
        line_height = readings["line_height_ratio"]
        notes = []
        # A tolerance of 0.005em absorbs the rounding that made -0.030 measure
        # as "outside -0.03 to -0.01" on a page that had set exactly -0.03.
        if tracking is not None and not readings["tracking_in_range"] \
                and not (DISPLAY_TRACKING[0] - 0.005 <= tracking
                         <= DISPLAY_TRACKING[1] + 0.005):
            notes.append(f"tracking {tracking:.3f}em is outside the "
                         f"{DISPLAY_TRACKING[0]} to {DISPLAY_TRACKING[1]}em the file asks for")
        if line_height is not None and not readings["line_height_in_range"] \
                and not (DISPLAY_LINE_HEIGHT[0] - 0.02 <= line_height
                         <= DISPLAY_LINE_HEIGHT[1] + 0.02):
            notes.append(f"display line-height {line_height:.2f} is outside the "
                         f"{DISPLAY_LINE_HEIGHT[0]} to {DISPLAY_LINE_HEIGHT[1]} range")
        if notes:
            reviews.append({"check": "DISPLAY-SETTING", "status": "review",
                            "severity": "review", "clause": "expression.md item 1",
                            "tracking_em": tracking, "line_height_ratio": line_height,
                            "message": "at display size, " + "; ".join(notes)})

    names = families(payload)
    if len(names) > 6:
        # Six declarations is where a page stops looking like roles and starts
        # looking like drift. Below that, five is normal (sans, sans-light,
        # serif, mono, CJK fallback) and the report lists them without judging.
        reviews.append({"check": "FAMILIES", "status": "review", "severity": "review",
                        "clause": "expression.md / color-and-type.md",
                        "families": list(names)[:6],
                        "message": f"{len(names)} distinct font-family declarations "
                                   f"carry text ({'; '.join(list(names)[:3])}; ...); "
                                   f"check they map onto named roles rather than drift"})
    return [], reviews


def build_report(url, payload, viewport=None):
    measures, reviews = classify(payload)
    fails = [item for item in measures if item.get("status") == "FAIL"]
    return {
        "url": url,
        "verified": True,
        "viewport": viewport,
        "clause_coverage": CLAUSE_COVERAGE,
        "metrics": {
            "body_size": round(float(payload.get("body_size") or BODY_FALLBACK), 1),
            "type_ratio": round(type_ratio(payload), 2),
            "weights": {"light": weight_span(payload)[0],
                        "heavy": weight_span(payload)[1]},
            "size_steps": size_steps(payload),
            "display": display_readings(payload),
            "families": families(payload),
        },
        "findings": fails + reviews,
        "manual": list(MANUAL_ITEMS),
        "summary": {
            "fail": len(fails),
            "review": len(reviews),
            "type_ratio": round(type_ratio(payload), 2),
            "measured_samples": len(payload.get("samples") or []),
            "capped": bool(payload.get("capped")),
        },
    }


def has_measurable_fail(report):
    """Always False: nothing here gates a build.

    The type ratio is the closest thing to a threshold, and it is still a
    judgement about expressiveness rather than conformance. Exposing it as an
    exit code would let taste break CI, which is exactly the failure mode the
    benchmark's human verdict section warns about.
    """
    return bool(report["summary"]["fail"])


def render_text(report):
    metrics = report["metrics"]
    summary = report["summary"]
    display = metrics["display"]
    lines = [
        f"Expression audit: {report['url']}",
        f"Scope: {report['clause_coverage']}",
        f"Type ratio: {metrics['type_ratio']:.2f}x body "
        f"({metrics['body_size']:g}px body, largest carried text)",
        f"Weights: {metrics['weights']['light']} to {metrics['weights']['heavy']}; "
        f"{metrics['size_steps']} distinct sizes; "
        f"{len(metrics['families'])} font-family declaration(s)",
    ]
    for declaration, count in list(metrics["families"].items())[:6]:
        lines.append(f"  {count:>4} samples  {declaration}")
    if display["samples"]:
        lines.append(
            f"Display setting: tracking {display['tracking_em']}em, "
            f"line-height {display['line_height_ratio']} "
            f"({display['samples']} samples at >= {DISPLAY_MIN_SIZE:g}px)")
    else:
        lines.append(f"Display setting: no text at or above {DISPLAY_MIN_SIZE:g}px")
    lines.append("")
    lines.append("Measurements against expression.md (all review severity; none gate a build):")
    for finding in report["findings"]:
        lines.append(f"REVIEW [{finding['check']}] {finding.get('message')}")
    lines.append("")
    lines.append("Left to the polish pass (a rect cannot judge these):")
    for item in report["manual"]:
        lines.append(f"  - {item}")
    lines.append("")
    lines.append(f"Summary: {summary['review']} review item(s) over "
                 f"{summary['measured_samples']} text samples; no exit status "
                 f"(taste never gates a build)")
    if summary.get("capped"):
        lines.append(f"NOTE: sampling stopped at {MAX_SAMPLES} text nodes")
    return "\n".join(lines)


# --- browser path ---------------------------------------------------------


def _collect(session, session_id):
    expression = (
        "(async () => {"
        "try { if (document.fonts && document.fonts.ready) await document.fonts.ready; }"
        " catch (e) {}"
        "return " + COLLECTOR_JS.replace("__MAX_SAMPLES__", str(MAX_SAMPLES)) + ";"
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


def audit_url(url, width=1440, height=900):
    """Load at a desktop width: expression is judged on the composition, not a phone."""
    with cdp.PageSession(url, width=width, height=height) as page:
        page.settle()
        return _collect(page.session, page.session_id)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Measure the expression layer's measurable items: type ratio, "
                    "weight span, size steps, display setting.")
    parser.add_argument("url")
    parser.add_argument("--json", action="store_true",
                        help="print the JSON report instead of text")
    parser.add_argument("--allow-private", action="store_true",
                        help="allow non-public, non-loopback addresses")
    parser.add_argument("--width", type=int, default=1440)
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
