# Contributing

## What this repository accepts

- A rule that is checkable, and an explanation of why breaking it hurts.
- A number with a source, or a number explicitly marked as a heuristic.
- A scanner rule that catches a pattern a reviewer would otherwise miss, with a fixture that shows it firing and a clean fixture that shows it staying quiet.
- A direction, palette or font pairing whose contrast values were computed with `wcag.py`, not estimated.

## What it does not accept

- Prefixes of "best practice" with no reason and no check.
- New defaults dressed as rules. If a direction copies a popular look, say why it suits a kind of product.
- Rule text copied from another skill or article without a source and without a rewrite, unless the license allows it and the notice is added.
- Machine-specific paths, personal names or private URLs in any file, including fixtures and tests. Tests must not depend on a path only you have.

## Versioning

The maintainer's rule, which this project follows:

- **A leap or a milestone is worth a +0.1.0 bump** — rarely. A new capability that fundamentally changes what the tool can do, or a structural change to how the project is built. Adding another audit of the same shape as the existing ones does not qualify: 2.1 added keyboard auditing and 2.2 added text-spacing auditing, and the maintainer judged both below this bar.
- **An incremental improvement is worth +0.0.1** — the default for new capability. A new script, a new check, a new reference: useful, additive, not a reinvention.
- **Fixing a known defect is not an improvement.** It does not justify a bump on its own; it corrects the project. Ship it, record it under `### Fixed`, and let the version follow the last real step. A release whose only content is repairs should not read as progress.

This matters because the version number is a claim about capability. Reserve the tenths for the releases somebody would point at.

## Workflow

1. Create a branch. Do not commit to the default branch.
2. Make the change.
3. Run the checks:

   ```
   python -B -m unittest discover -s tests -v
   python tools/build_dist.py --check
   python tools/build_dist.py --mirror-check
   python skills/polishkit/scripts/slop_scan.py tests/fixtures/tells/index.html
   ```

   `--check` proves the install staging tree matches this one byte for byte. `--mirror-check` proves the publish mirror does, including `tests/` and `benchmark/`, which are published but never installed and therefore invisible to the first check.

4. For a scanner rule, prove both directions: the fixture with the defect must trigger the rule, and a near-miss fixture without it must not. Add both to `tests/`.
5. For a new contrast value, add the pair to the test or show the `wcag.py` output in the pull request.
6. For a new rendered check, prove it against a page that has the defect and a page that does not. A check that never fires and a check that fires on healthy pages are both defects, and neither shows up in a unit test.
7. Update `CHANGELOG.md` under an Unreleased heading, and bump the version in both manifests when releasing.

## Style

- Write in complete sentences. Say what the rule is, then why it matters.
- Prefer a concrete example to an adjective.
- Mark anything that is a judgement call as one. The skill is more useful when it admits where it is unsure.
- Keep `SKILL.md` short: it is loaded on every activation. Put detail in `references/` and open it only when a step needs it.

## Compatibility

`SKILL.md` must keep working in every agent that reads Agent Skills: plain Markdown, no tool-specific syntax beyond the frontmatter fields `name` and `description`. Put agent-specific affordances in the manifests or in `commands/`.

## License

Contributions are accepted under the MIT License. By submitting a pull request you agree to license your contribution on those terms.
