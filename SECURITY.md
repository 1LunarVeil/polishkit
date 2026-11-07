# Security Policy

## What this project runs

This plugin executes Python on your machine when an agent calls its scripts. Being precise about what they can do is the point of this file.

| Script | Reads | Writes | Network | Spawns |
|---|---|---|---|---|
| `wcag.py` | nothing | stdout | none | nothing |
| `design_lookup.py` | `data/*.csv` beside the skill | stdout | none | nothing |
| `slop_scan.py` | the source paths you pass | stdout | none | nothing |
| `image_diff.py` | the PNG files you pass | stdout | none | nothing |
| `visual_capture.py` | the URL you pass | PNG files in `--out` | the URL you pass, only | a Chromium-family browser |

`visual_capture.py` is the only script that starts a process, and it takes three precautions:

- The browser is resolved by absolute path only, from a fixed list under Program Files (Windows) or `/usr/bin` and `/Applications` (macOS and Linux). It never resolves a bare name, because on Windows the executable search order favours the current directory and the application folder.
- The URL is validated before use: only `http` and `https`, a leading `-` is refused so it cannot be parsed as a browser switch, and non-public addresses are refused unless you pass `--allow-private` explicitly.
- The subprocess is invoked with an argument list and `shell=False`.

No script reads environment secrets, writes outside the capture directory, or edits source files.

## Resource limits in the PNG decoder

`image_diff.py` reads PNG files that may come from anywhere, so decoding is bounded:

- The declared dimensions are checked against a 40-million-pixel limit before any inflation.
- The expected scanline size is checked against a 160 MB limit before any inflation.
- Inflation uses `zlib.decompressobj().decompress(data, max_length)` with the declared size as the bound, so excess output is never produced. Exceeding it is reported as a decompression bomb.

This was a real defect, not a hypothetical one. Before 0.1.2, a 65 KB PNG declaring a 1x1 image inflated to 64 MB and was accepted, because the length check ran only after decompression. It was found by a manual review that reproduced it; the fix is pinned by `test_decompression_bomb_is_rejected_before_inflating` and `test_declared_dimensions_above_the_pixel_limit_are_rejected`, both of which fail against the old implementation.

## Reporting a vulnerability

Open a private security advisory through the repository's **Security** tab, or email LunarVeil666@outlook.com. Do not open a public issue for a vulnerability.

Please include: the script involved, the exact command, the input that triggers it, and what you expected instead. A reproduction matters more than a severity label.

Expect an acknowledgement within about a week. This is a small, single-maintainer project without a formal SLA.

## Scope

In scope: anything under `skills/polishkit/scripts/`, the manifests, and the CI workflow, since those are what run on a user's machine.

Out of scope: the content of the vendored CSV data (report data quality as a normal issue), and findings that require an already-compromised machine.

## Supported versions

Only the latest released version receives fixes.
