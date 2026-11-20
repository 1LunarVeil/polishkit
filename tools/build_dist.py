"""Build the install staging tree for PolishKit.

Why this exists: ZCode's directory-type marketplace copies the whole plugin
folder on install. The dev tree carries process artefacts (notes/, .mimosa/,
tests/, benchmark/ with ~37 MB of screenshots), and every one of them reached
a user's installed cache (40 MB). The manifest has no exclude mechanism, so
the only clean fix is to install from a generated tree that contains runtime
components only.

Usage:
  python tools/build_dist.py                  # build/refresh ../polishkit-dist
  python tools/build_dist.py --check          # verify staging, no writes
  python tools/build_dist.py --mirror-check   # verify the publish mirror too

Two gates, because two different trees can be wrong:

  --check         staging vs dev. A manifest-only check cannot see that a
                  reference or a script was edited after the last build, so this
                  compares every staged file byte for byte.
  --mirror-check  the git mirror vs dev. The mirror also publishes tests/ and
                  benchmark/, which never enter the install payload and so are
                  invisible to --check. A test file edited in one tree only is
                  exactly how the mirror once ran 244 tests while dev ran 251.

The build also stamps the two derived manifests (.claude-plugin/plugin.json and
the Claude marketplace entry in .claude-plugin/marketplace.json) with the name,
version and description of the source manifest (.zcode-plugin/plugin.json). The
marketplace entry kept its own 0.1.2 through seven releases — every gate compared
the manifests that were already consistent, and the one the public reads was not.

The target is generated: never edit it by hand. This script refuses to clear a
target that lacks the marker. The marker lives beside the target, not inside it:
a directory-type marketplace copies the whole tree, so anything inside reaches
a user's cache — and `.generated-by-build_dist` did, in every release up to
2.2.0.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT.parent / "polishkit-dist"
# Beside the target, never inside it. See the module docstring.
MARKER = ROOT.parent / ".polishkit-dist.generated"
# The old in-tree marker. Still honoured so an existing target can be rebuilt,
# and checked for so a rebuild that leaves it behind is caught.
LEGACY_MARKER = ".generated-by-build_dist"

# The source manifest is .zcode-plugin/plugin.json; two derived manifests
# repeat its name/version/description and are stamped from it on every build.
SOURCE_MANIFEST = ROOT / ".zcode-plugin" / "plugin.json"
CLAUDE_MANIFEST = ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"

# Only what a plugin needs at runtime, plus the documents a user reads.
INCLUDE_DIRS = (".zcode-plugin", ".claude-plugin", "skills", "commands")
INCLUDE_FILES = (
    "README.md",
    "README.zh-CN.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "SECURITY.md",
    "THIRD_PARTY_NOTICES.md",
)
# Process artefacts that must never reach an install.
FORBIDDEN = ("notes", ".mimosa", "tests", "benchmark", "__pycache__")

# Publish-side tooling. Not installed (the marketplace never copies it), but the
# mirror needs the same copy: CONTRIBUTING tells contributors to run it there,
# and it had been stuck at whatever version was first copied by hand.
PUBLISH_TOOLING = ("tools",)

# The publish mirror's own directories that this staging build does not manage.
# `.github/` is mirror-only by design; benchmark/ and tests/ are published but
# not installed. The mirror sits beside the marketplace root, not under it:
#   D:\agent_try\plugins\polishkit  (dev)   ->  ROOT
#   D:\agent_try\plugins\polishkit-dist (staging)
#   D:\agent_try\GitHub\polishkit     (mirror)
MIRROR = ROOT.parent.parent / "GitHub" / "polishkit"
MIRROR_SHARED_DIRS = ("tests", "benchmark") + PUBLISH_TOOLING
# Local-only benchmark history. The mirror publishes `runs/treatment/` (the
# v3 pages, renamed on the way out); the v1/v2 archives, the v3 working copy and
# the weakness analysis stay here on purpose — see notes/SESSION-START.md.
MIRROR_EXCLUDED = (
    "benchmark/WEAKNESS-ANALYSIS.md",
    "benchmark/runs/treatment-v1-archive",
    "benchmark/runs/treatment-v2-archive",
    "benchmark/runs/treatment-v3",
)
# Paths that are renamed on the way to the mirror: the dev tree keeps the
# iteration in its name, the published tree drops it. Left unmapped these look
# like a mirror-only directory on every check.
MIRROR_RENAMED = {
    "benchmark/runs/treatment/": "benchmark/runs/treatment-v3/",
}


def _fail(message):
    print(f"build_dist: {message}", file=sys.stderr)
    return 1


def _manifest():
    return json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))


def _write_json(path, payload):
    # newline="\n" because json.dumps + a default text write produces CRLF on
    # Windows, and the mirror's .gitattributes then flags every rewrite.
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _stamp_manifests():
    """Stamp name/version/description from the source manifest into the derived ones.

    The marketplace entry is the one that bit: it kept its own version from
    0.1.2 while the plugin moved to 2.2.x, so the Claude Code plugin
    marketplace showed every reader a version several minor lines behind the
    artifact — found by an external review, not by any gate. The gates only
    knew about the catalog and the two plugin manifests.

    Stamping runs on every build, before anything is copied. Both files stay
    hand-editable for the fields the manifest does not carry (display names,
    category, i18n descriptions); the three stamped fields are no longer
    hand-editable in practice, which is the point.
    """
    manifest = _manifest()
    claude = json.loads(CLAUDE_MANIFEST.read_text(encoding="utf-8"))
    changed = [field for field in ("name", "version", "description")
               if claude.get(field) != manifest.get(field)]
    if changed:
        for field in changed:
            claude[field] = manifest[field]
        _write_json(CLAUDE_MANIFEST, claude)
        print(f"  stamped .claude-plugin/plugin.json <- {manifest['version']}")

    if not MARKETPLACE.is_file():
        return _fail(f"missing marketplace manifest: {MARKETPLACE}")
    marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    entries = marketplace.get("plugins", [])
    named = [entry for entry in entries if entry.get("name") == manifest["name"]]
    if len(named) > 1:
        return _fail(f"marketplace manifest lists {manifest['name']!r} {len(named)} times")
    if named:
        entry = named[0]
    elif len(entries) == 1:
        # A rename: the entry keeps its old name until this stamp updates it.
        entry = entries[0]
    else:
        return _fail("marketplace manifest has no plugin entry to stamp")
    changed = [field for field in ("name", "version", "description")
               if entry.get(field) != manifest.get(field)]
    if changed:
        for field in changed:
            entry[field] = manifest[field]
        _write_json(MARKETPLACE, marketplace)
        print(f"  stamped .claude-plugin/marketplace.json <- {manifest['version']}")
    return 0


def _strip_hook_ledger(target):
    """Remove .mimosa/ from a tree about to be installed or verified.

    Mimosa, the security hook, writes its ledger into any workspace a session
    touches — and `polishkit-dist` is such a workspace. It reappears whenever a
    command runs in or near the tree, so a check that only *reports* it fails on
    the tool's own bookkeeping rather than on anything an author did.

    Removing it is safe and lossless: the ledger belongs to the hook, never to
    the plugin, and nothing under .mimosa/ is ever copied from the dev tree.
    """
    shutil.rmtree(target / ".mimosa", ignore_errors=True)


def _verify(target):
    """Return a list of problems found in the staged tree."""
    problems = []
    manifest = _manifest()
    staged_manifest_path = target / ".zcode-plugin" / "plugin.json"
    if not staged_manifest_path.is_file():
        return [f"missing staged manifest: {staged_manifest_path}"]
    staged = json.loads(staged_manifest_path.read_text(encoding="utf-8"))
    if staged.get("name") != manifest.get("name"):
        problems.append(f"manifest name drift: {staged.get('name')!r} vs {manifest.get('name')!r}")
    if staged.get("version") != manifest.get("version"):
        problems.append(f"manifest version drift: {staged.get('version')!r} vs {manifest.get('version')!r}")

    # The marketplace entry is what the Claude Code plugin marketplace shows
    # the user; it carried 0.1.2 through seven releases before the stamp and
    # this check existed. Verify it every time, not only after a stamp.
    marketplace_path = target / ".claude-plugin" / "marketplace.json"
    if marketplace_path.is_file():
        entries = [entry for entry in json.loads(marketplace_path.read_text(encoding="utf-8")).get("plugins", [])
                   if entry.get("name") == manifest["name"]]
        if len(entries) != 1:
            problems.append(f"marketplace.json has {len(entries)} entries named {manifest['name']!r}")
        else:
            if entries[0].get("version") != manifest["version"]:
                problems.append(f"marketplace version drift: {entries[0].get('version')!r} "
                                f"vs {manifest['version']!r}")
            if entries[0].get("description") != manifest.get("description"):
                problems.append("marketplace description differs from the manifest")

    skill = target / "skills" / manifest["name"] / "SKILL.md"
    if not skill.is_file():
        problems.append(f"missing skill entry point: {skill}")
    else:
        head = skill.read_text(encoding="utf-8").splitlines()[:6]
        if not any(line.strip() == f"name: {manifest['name']}" for line in head):
            problems.append(f"SKILL.md frontmatter name does not match {manifest['name']!r}")

    # At any depth, not just at the root: the hook writes into subdirectories,
    # and a root-only check passed a tree carrying .mimosa/ under scripts/.
    for name in FORBIDDEN:
        if (target / name).exists():
            problems.append(f"forbidden path present: {name}/")
        for found in target.rglob(name):
            if found != target / name:
                problems.append(f"forbidden path present: {found.relative_to(target).as_posix()}/")

    if not (target / "commands").is_dir():
        problems.append("missing commands/")
    scripts = list((target / "skills" / manifest["name"] / "scripts").glob("*.py"))
    if not scripts:
        problems.append("missing skill scripts")
    data = list((target / "skills" / manifest["name"] / "data").glob("*.csv"))
    if not data:
        problems.append("missing skill data CSVs")
    return problems


def _shipped_files(root):
    """Relative paths of exactly the files this script copies into a target.

    `.mimosa/` is excluded at any depth. The hook writes its ledger wherever a
    session has touched, which includes `skills/polishkit/scripts/` — a sync run
    staged `.mimosa/hook-state/*` into the publish tree under that directory and
    nothing caught it, because the top-level check looked only at the tree root.
    """
    files = set()
    for name in INCLUDE_DIRS:
        for path in (root / name).rglob("*"):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts or ".mimosa" in path.parts:
                continue
            if path.suffix == ".pyc":
                continue
            files.add(path.relative_to(root).as_posix())
    for name in INCLUDE_FILES:
        if (root / name).is_file():
            files.add(name)
    return files


def _content_drift(target):
    """Compare the staged tree against the dev tree, file by file.

    A manifest-only check cannot see that SKILL.md, a reference or a script was
    edited after the last build — the failure that made installs serve stale
    content. Byte comparison is the honest test; anything else lets a stale
    staged tree pass as clean.
    """
    problems = []
    expected = _shipped_files(ROOT)
    actual = {p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()}
    # The marker belongs beside the tree now. Seeing one inside means the build
    # predates that change, and it would ship to every install.
    if LEGACY_MARKER in actual:
        problems.append(f"{LEGACY_MARKER} is inside the tree; it reaches user caches "
                        f"— rebuild with the current tools/build_dist.py")
        actual.discard(LEGACY_MARKER)
    for missing in sorted(expected - actual):
        problems.append(f"missing from staging: {missing}")
    for extra in sorted(actual - expected):
        problems.append(f"unexpected file in staging: {extra}")
    for relative in sorted(expected & actual):
        if (ROOT / relative).read_bytes() != (target / relative).read_bytes():
            problems.append(f"content drift: {relative}")
    return problems


def _size(path):
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def build():
    # The derived manifests are stamped before anything is copied, so the
    # staged tree and the mirror both carry the source manifest's version.
    stamped = _stamp_manifests()
    if stamped:
        return stamped

    # An existing target may carry either the new sidecar marker or the old
    # in-tree one; both say this script made the directory.
    owned = MARKER.is_file() or (TARGET / LEGACY_MARKER).is_file()
    if TARGET.exists() and not owned:
        return _fail(f"{TARGET} exists but carries no marker; refusing to clear a "
                     f"tree this script did not create")
    if TARGET.exists():
        shutil.rmtree(TARGET)
    TARGET.mkdir(parents=True)

    for name in INCLUDE_DIRS:
        source = ROOT / name
        if not source.is_dir():
            return _fail(f"expected component directory missing: {source}")
        # .mimosa/ can sit at any depth in the dev tree — the hook writes into
        # whatever directory a command ran in, including scripts/. Excluding it
        # here is the only way it never reaches a staging tree at all.
        shutil.copytree(
            source, TARGET / name,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".mimosa"),
        )
    for name in INCLUDE_FILES:
        source = ROOT / name
        if not source.is_file():
            return _fail(f"expected document missing: {source}")
        shutil.copy2(source, TARGET / name)

    MARKER.write_text(
        "Generated by tools/build_dist.py from the dev tree. Do not edit.\n"
        "This file sits beside polishkit-dist, not inside it: the marketplace\n"
        "copies the tree whole, so a marker inside would reach every install.\n",
        encoding="utf-8",
    )

    # Mimosa (a security hook) writes .mimosa/ into any workspace this session
    # touches — including the staging tree. Strip it after staging so an
    # install never inherits hook ledgers.
    _strip_hook_ledger(TARGET)

    problems = _verify(TARGET)
    if problems:
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return _fail("staged tree failed verification")

    manifest = _manifest()
    print(f"built {TARGET} <- {ROOT}")
    print(f"  plugin: {manifest['name']} {manifest['version']}")
    print(f"  files:  {sum(1 for p in TARGET.rglob('*') if p.is_file())}")
    print(f"  size:   {_size(TARGET) / 1024:.0f} KiB")
    print("  verified: manifest identity, skill entry point, no process artefacts")
    return 0


def dev_path_for(posix):
    """Map a mirror-relative path to where the same file lives in the dev tree.

    The published benchmark drops the iteration suffix (`treatment-v3/` becomes
    `treatment/`). Every other path is identical in both trees.
    """
    for mirror_prefix, dev_prefix in MIRROR_RENAMED.items():
        if posix.startswith(mirror_prefix):
            return dev_prefix + posix[len(mirror_prefix):]
    return posix


def mirror_drift():
    """Compare the publish mirror against the dev tree for non-install files.

    The install payload is checked by build(); this covers what it deliberately
    leaves out and what the mirror alone carries:

    - the shipped files, byte for byte (the same set build() stages);
    - tests/ and benchmark/, which are published but not installed — a test
      file edited in only one tree is how the mirror ran 244 tests while dev
      ran 251;
    - .github/, which exists only in the mirror, so it is reported as a count
      and never compared (there is nothing to compare it against).

    Files ignored on purpose: notes/, .mimosa/, generated fixtures, archives.
    """
    problems = []
    if not MIRROR.is_dir():
        return [f"mirror not found at {MIRROR}"]

    shipped = _shipped_files(ROOT)
    for relative in sorted(shipped):
        mine = ROOT / relative
        theirs = MIRROR / relative
        if not theirs.is_file():
            problems.append(f"mirror missing {relative}")
        elif mine.read_bytes() != theirs.read_bytes():
            problems.append(f"mirror differs: {relative}")

    skip_parts = {".mimosa", "__pycache__", ".git", "png"}
    seen = set(shipped)
    for name in MIRROR_SHARED_DIRS:
        source = ROOT / name
        for path in source.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT)
            if any(part in skip_parts for part in relative.parts):
                continue
            if path.suffix in (".pyc", ".png"):
                continue
            posix = relative.as_posix()
            if posix in seen:
                continue  # already compared above; report each file once
            seen.add(posix)
            if any(posix == excluded or posix.startswith(excluded + "/")
                   for excluded in MIRROR_EXCLUDED):
                continue
            theirs = MIRROR / relative
            if not theirs.is_file():
                problems.append(f"mirror missing {posix}")
            elif path.read_bytes() != theirs.read_bytes():
                problems.append(f"mirror differs: {posix}")

    # Files that exist only in the mirror are the other half of the comparison.
    # Without this, adding a helper straight to the publish tree passed every
    # gate — the dev tree had nothing to compare it against and said "clean".
    #
    # `.mimosa/` is the exception to the skip list here: it is a hook ledger,
    # never published, so finding one in the mirror is a leak to report rather
    # than a file to ignore. A sync bug wrote one into benchmark/runs/treatment
    # and every gate called the tree clean.
    for name in MIRROR_SHARED_DIRS:
        source = MIRROR / name
        for path in source.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(MIRROR)
            posix = relative.as_posix()
            if ".mimosa" in relative.parts:
                problems.append(f"hook ledger leaked into the mirror: {posix}")
                continue
            if any(part in skip_parts for part in relative.parts):
                continue
            if path.suffix in (".pyc", ".png"):
                continue
            if any(posix == excluded or posix.startswith(excluded + "/")
                   for excluded in MIRROR_EXCLUDED):
                continue
            counterpart = dev_path_for(posix)
            # The dev→mirror pass above already compared every file present in
            # both trees, shared directories included. Reporting those again
            # here printed each drift twice. This pass exists for files that
            # have no dev counterpart at all.
            if (ROOT / counterpart).is_file():
                continue
            problems.append(f"mirror-only file (not in the dev tree): {posix}")
    return problems


def check():
    if not TARGET.is_dir():
        return _fail(f"{TARGET} does not exist; run the build first")
    # The hook rewrites its ledger on its own schedule; clear it before asking
    # whether the tree is publishable, or the answer is about the hook.
    _strip_hook_ledger(TARGET)
    problems = _verify(TARGET)
    if not problems:
        # The manifest is one file; report it separately so a version bump alone
        # does not masquerade as a content check.
        if (TARGET / ".zcode-plugin" / "plugin.json").read_bytes() != (ROOT / ".zcode-plugin" / "plugin.json").read_bytes():
            problems.append("manifest bytes differ; rebuild the staged tree")
        problems.extend(_content_drift(TARGET))
    if problems:
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return _fail(f"staged tree drifted from the dev tree ({len(problems)} item(s)); rebuild it")
    print(f"{TARGET} is clean and matches the dev tree, byte for byte")
    return 0


def sync_mirror():
    """Copy the shipped files and published test/benchmark sources to the mirror.

    The mirror is the publish source of truth and is a separate git repository,
    so it cannot be updated by rebuilding staging. Keeping the copy here means
    one implementation decides what "in sync" means, and --mirror-check proves
    the result. Files this script does not own (notes/, .mimosa/, the benchmark
    archives) are never touched.
    """
    if not MIRROR.is_dir():
        return _fail(f"mirror not found at {MIRROR}")

    wanted = set(_shipped_files(ROOT))
    skip_parts = {".mimosa", "__pycache__", ".git", "png"}
    for name in MIRROR_SHARED_DIRS:
        for path in (ROOT / name).rglob("*"):
            if not path.is_file() or path.suffix in (".pyc", ".png"):
                continue
            relative = path.relative_to(ROOT)
            if any(part in skip_parts for part in relative.parts):
                continue
            posix = relative.as_posix()
            if any(posix == excluded or posix.startswith(excluded + "/")
                   for excluded in MIRROR_EXCLUDED):
                continue
            wanted.add(posix)

    # Pairs where the mirror uses a different directory name. The same skip
    # list applies: a renamed source is still source, and `.mimosa/` was copied
    # into the published benchmark tree because this branch did not filter it.
    pairs = []
    for mirror_prefix, dev_prefix in MIRROR_RENAMED.items():
        for path in (ROOT / dev_prefix.rstrip("/")).rglob("*"):
            if not path.is_file() or path.suffix in (".pyc", ".png"):
                continue
            relative = path.relative_to(ROOT / dev_prefix.rstrip("/"))
            if any(part in skip_parts for part in relative.parts):
                continue
            pairs.append((path, MIRROR / mirror_prefix / relative))

    copied = 0
    for posix in sorted(wanted):
        source = ROOT / posix
        target = MIRROR / posix
        data = source.read_bytes()
        if target.is_file() and target.read_bytes() == data:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        copied += 1
        print(f"  synced {posix}")
    for source, target in pairs:
        data = source.read_bytes()
        if target.is_file() and target.read_bytes() == data:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        copied += 1
        print(f"  synced {target.relative_to(MIRROR).as_posix()}")
    print(f"{copied} file(s) written to {MIRROR}")
    return 0 if not mirror_drift() else _fail(
        "the mirror still differs after syncing; check MIRROR_EXCLUDED")


def check_mirror():
    problems = mirror_drift()
    if problems:
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return _fail(f"publish mirror drifted ({len(problems)} item(s)); sync it before pushing")
    print(f"{MIRROR} matches the dev tree for shipped files, tests/ and benchmark/")
    return 0


def check_catalog():
    """Verify the marketplace catalog names this plugin's real version.

    The plugin-creator spec requires the catalog entry and both manifests to
    agree. Nothing checked it, so 2.2.0 shipped with a catalog still saying
    2.1.0 — a user reading the marketplace saw the wrong version, and an
    installer comparing versions would have skipped the update.
    """
    catalog_path = ROOT.parent / "marketplace.json"
    if not catalog_path.is_file():
        return _fail(f"no catalog at {catalog_path}")
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return _fail(f"catalog is not valid JSON: {exc}")

    manifest = _manifest()
    entries = [entry for entry in catalog.get("plugins", [])
               if entry.get("name") == manifest["name"]]
    if not entries:
        return _fail(f"catalog has no entry named {manifest['name']!r}")
    if len(entries) > 1:
        return _fail(f"catalog lists {manifest['name']!r} {len(entries)} times")

    entry = entries[0]
    problems = []
    if entry.get("version") != manifest["version"]:
        problems.append(f"catalog version {entry.get('version')!r} != manifest "
                        f"{manifest['version']!r}")
    if entry.get("description") != manifest.get("description"):
        problems.append("catalog description differs from the manifest")
    expected_source = f"./{TARGET.name}"
    if entry.get("source") != expected_source:
        problems.append(f"catalog source {entry.get('source')!r} != {expected_source!r}")
    if problems:
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return _fail("catalog is out of step with the manifest")
    print(f"catalog entry for {manifest['name']} matches the manifest "
          f"({manifest['version']}, {expected_source})")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build or verify the install staging tree.")
    parser.add_argument("--check", action="store_true", help="verify the staging tree; do not write")
    parser.add_argument("--mirror-check", action="store_true",
                        help="verify the publish mirror also matches this tree "
                             "(shipped files, tests/, benchmark/)")
    parser.add_argument("--sync-mirror", action="store_true",
                        help="copy shipped files, tests/ and benchmark/ into the "
                             "publish mirror, then verify")
    parser.add_argument("--catalog-check", action="store_true",
                        help="verify the marketplace catalog names this version")
    args = parser.parse_args(argv)
    if args.catalog_check:
        return check_catalog()
    if args.sync_mirror:
        return sync_mirror()
    if args.mirror_check:
        return check_mirror()
    return check() if args.check else build()


if __name__ == "__main__":
    sys.exit(main())
