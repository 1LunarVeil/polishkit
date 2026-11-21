"""Fail-positive tests for tools/build_dist.py's four publish gates.

CONTRIBUTING's rule: every check needs a test that can make it fail. These
tests apply it to the gates that were written before the rule was — each one
scaffolds a minimal-but-valid four-tree layout (dev, staging, mirror,
catalog), injects one specific violation, and demands exit 1:

- the staging gate must catch manifest drift, edited files, forbidden
  directories at any depth, and a marketplace entry that disagrees with the
  manifest (the 0.1.2 incident);
- the mirror gate must catch missing and diverging files, mirror-only files,
  and a hook ledger leaking into the publish tree;
- the catalog gate must catch version, description and source mismatches,
  missing and duplicated entries (the 2.1.0-vs-2.2.0 incident);
- the stamp must pull both derived manifests to the source manifest;
- and build() must refuse to clear a tree it did not create.

Everything runs in a TemporaryDirectory; nothing outside it is touched.
"""

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_dist  # noqa: E402

MANIFEST = {
    "name": "polishkit",
    "version": "9.9.9",
    "description": "test manifest description",
    "author": {"name": "t"},
    "license": "MIT",
    "skills": "./skills",
    "commands": "./commands",
}
DOCS = ("README.md", "README.zh-CN.md", "CHANGELOG.md", "CONTRIBUTING.md",
        "LICENSE", "SECURITY.md", "THIRD_PARTY_NOTICES.md")


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _json(path, payload):
    _write(path, json.dumps(payload, indent=2) + "\n")


def _scaffold(tmp):
    """Return (dev, dist, mirror): a valid dev tree, a matching staging tree,
    a matching mirror, and a matching catalog at tmp/marketplace.json."""
    dev, dist, mirror = tmp / "dev", tmp / "polishkit-dist", tmp / "mirror"

    _json(dev / ".zcode-plugin" / "plugin.json", MANIFEST)
    _json(dev / ".claude-plugin" / "plugin.json", MANIFEST)
    _json(dev / ".claude-plugin" / "marketplace.json", {
        "name": "polishkit",
        "owner": {"name": "t"},
        "plugins": [{"name": "polishkit", "source": "./", "version": "9.9.9",
                     "description": "test manifest description",
                     "displayName": "T"}],
    })
    _write(dev / "skills" / "polishkit" / "SKILL.md",
           "---\nname: polishkit\ndescription: test\n---\n\n# t\n")
    _write(dev / "skills" / "polishkit" / "scripts" / "tool.py", "print('x')\n")
    _write(dev / "skills" / "polishkit" / "data" / "look.csv", "a,b\n1,2\n")
    _write(dev / "commands" / "hello.md", "# hello\n")
    for doc in DOCS:
        _write(dev / doc, f"# {doc}\n")
    _write(dev / "tests" / "test_x.py", "x = 1\n")
    _write(dev / "tools" / "helper.py", "x = 1\n")

    _json(tmp / "marketplace.json", {
        "name": "test-market",
        "plugins": [{"name": "polishkit", "source": "./polishkit-dist",
                     "version": "9.9.9",
                     "description": "test manifest description"}],
    })

    # The staging tree carries exactly the shipped set, byte for byte.
    for name in (".zcode-plugin", ".claude-plugin", "skills", "commands"):
        shutil.copytree(dev / name, dist / name)
    for doc in DOCS:
        shutil.copy2(dev / doc, dist / doc)
    # The mirror shares the shipped set plus tests/ and tools/.
    shutil.copytree(dev, mirror)
    return dev, dist, mirror


@contextlib.contextmanager
def _gates(dev, dist, mirror):
    """Point every module-level path the gates read at the scaffold."""
    with contextlib.ExitStack() as stack:
        for name, value in (
            ("ROOT", dev),
            ("SOURCE_MANIFEST", dev / ".zcode-plugin" / "plugin.json"),
            ("CLAUDE_MANIFEST", dev / ".claude-plugin" / "plugin.json"),
            ("MARKETPLACE", dev / ".claude-plugin" / "marketplace.json"),
            ("TARGET", dist),
            ("MARKER", dist.parent / ".polishkit-dist.generated"),
            ("MIRROR", mirror),
        ):
            stack.enter_context(mock.patch.object(build_dist, name, value))
        yield


@contextlib.contextmanager
def _quiet():
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield out, err


from unittest import mock  # noqa: E402  (kept late so the scaffold reads first)


class StagingGateTests(unittest.TestCase):
    """--check: the install payload must match the dev tree, byte for byte."""

    def _scaffold(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return _scaffold(Path(tmp.name))

    def test_matching_staging_passes(self):
        dev, dist, mirror = self._scaffold()
        with _gates(dev, dist, mirror), _quiet() as (_, err):
            self.assertEqual(build_dist.check(), 0)
        self.assertEqual(err.getvalue(), "")

    def test_manifest_version_drift_fails(self):
        dev, dist, mirror = self._scaffold()
        _json(dist / ".zcode-plugin" / "plugin.json", {**MANIFEST, "version": "0.0.1"})
        with _gates(dev, dist, mirror), _quiet():
            self.assertEqual(build_dist.check(), 1)

    def test_edited_staged_file_fails(self):
        dev, dist, mirror = self._scaffold()
        _write(dist / "README.md", "# edited after the build\n")
        with _gates(dev, dist, mirror), _quiet() as (_, err):
            self.assertEqual(build_dist.check(), 1)
        self.assertIn("content drift", err.getvalue())

    def test_forbidden_directory_at_the_root_fails(self):
        dev, dist, mirror = self._scaffold()
        _write(dist / "notes" / "scratch.md", "process artefact\n")
        with _gates(dev, dist, mirror), _quiet():
            self.assertEqual(build_dist.check(), 1)

    def test_forbidden_directory_at_depth_fails(self):
        # The hook writes .mimosa/ wherever a session touched — a root-only
        # check once passed a tree carrying it under scripts/.
        dev, dist, mirror = self._scaffold()
        _write(dist / "skills" / "polishkit" / "scripts" / ".mimosa" / "ledger", "x\n")
        with _gates(dev, dist, mirror), _quiet() as (_, err):
            self.assertEqual(build_dist.check(), 1)
        self.assertIn("forbidden path present", err.getvalue())

    def test_marketplace_version_drift_fails(self):
        # The exact 2.2.12 incident: the entry kept its own 0.1.2 while the
        # plugin moved on, and no gate compared them.
        dev, dist, mirror = self._scaffold()
        marketplace = json.loads((dist / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        marketplace["plugins"][0]["version"] = "0.1.2"
        _json(dist / ".claude-plugin" / "marketplace.json", marketplace)
        with _gates(dev, dist, mirror), _quiet() as (_, err):
            self.assertEqual(build_dist.check(), 1)
        self.assertIn("marketplace version drift", err.getvalue())

    def test_missing_commands_directory_fails(self):
        dev, dist, mirror = self._scaffold()
        shutil.rmtree(dist / "commands")
        with _gates(dev, dist, mirror), _quiet():
            self.assertEqual(build_dist.check(), 1)


class MirrorGateTests(unittest.TestCase):
    """--mirror-check: the publish mirror must match the dev tree for the
    shipped files and for tests/, benchmark/ and tools/, which never install
    and are therefore invisible to the staging gate."""

    def _scaffold(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return _scaffold(Path(tmp.name))

    def test_matching_mirror_passes(self):
        dev, dist, mirror = self._scaffold()
        with _gates(dev, dist, mirror), _quiet():
            self.assertEqual(build_dist.check_mirror(), 0)

    def test_mirror_missing_a_shipped_file_fails(self):
        dev, dist, mirror = self._scaffold()
        (mirror / "README.md").unlink()
        with _gates(dev, dist, mirror), _quiet() as (_, err):
            self.assertEqual(build_dist.check_mirror(), 1)
        self.assertIn("mirror missing", err.getvalue())

    def test_mirror_diverging_test_file_fails(self):
        # A test file edited in one tree only is how the mirror once ran 244
        # tests while dev ran 251.
        dev, dist, mirror = self._scaffold()
        _write(mirror / "tests" / "test_x.py", "x = 2\n")
        with _gates(dev, dist, mirror), _quiet() as (_, err):
            self.assertEqual(build_dist.check_mirror(), 1)
        self.assertIn("mirror differs", err.getvalue())

    def test_mirror_only_file_fails(self):
        # Without the mirror-to-dev pass, adding a helper straight to the
        # publish tree passed every gate.
        dev, dist, mirror = self._scaffold()
        _write(mirror / "tests" / "extra.py", "x = 1\n")
        with _gates(dev, dist, mirror), _quiet() as (_, err):
            self.assertEqual(build_dist.check_mirror(), 1)
        self.assertIn("mirror-only file", err.getvalue())

    def test_hook_ledger_in_the_mirror_is_reported_as_a_leak(self):
        dev, dist, mirror = self._scaffold()
        _write(mirror / "tests" / ".mimosa" / "ledger", "x\n")
        with _gates(dev, dist, mirror), _quiet() as (_, err):
            self.assertEqual(build_dist.check_mirror(), 1)
        self.assertIn("leaked into the mirror", err.getvalue())


class CatalogGateTests(unittest.TestCase):
    """--catalog-check: the marketplace catalog must name the real version.
    2.2.0 shipped with a catalog still saying 2.1.0 — readers saw the wrong
    version and version-comparing installers skipped the update."""

    def _scaffold(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return _scaffold(Path(tmp.name))

    def _catalog(self, dev):
        return json.loads((dev.parent / "marketplace.json").read_text(encoding="utf-8"))

    def test_matching_catalog_passes(self):
        dev, dist, mirror = self._scaffold()
        with _gates(dev, dist, mirror), _quiet():
            self.assertEqual(build_dist.main(["--catalog-check"]), 0)

    def test_version_mismatch_fails(self):
        dev, dist, mirror = self._scaffold()
        catalog = self._catalog(dev)
        catalog["plugins"][0]["version"] = "2.1.0"
        _json(dev.parent / "marketplace.json", catalog)
        with _gates(dev, dist, mirror), _quiet():
            self.assertEqual(build_dist.main(["--catalog-check"]), 1)

    def test_description_mismatch_fails(self):
        dev, dist, mirror = self._scaffold()
        catalog = self._catalog(dev)
        catalog["plugins"][0]["description"] = "stale wording"
        _json(dev.parent / "marketplace.json", catalog)
        with _gates(dev, dist, mirror), _quiet():
            self.assertEqual(build_dist.main(["--catalog-check"]), 1)

    def test_source_mismatch_fails(self):
        dev, dist, mirror = self._scaffold()
        catalog = self._catalog(dev)
        catalog["plugins"][0]["source"] = "./somewhere-else"
        _json(dev.parent / "marketplace.json", catalog)
        with _gates(dev, dist, mirror), _quiet():
            self.assertEqual(build_dist.main(["--catalog-check"]), 1)

    def test_missing_entry_fails(self):
        dev, dist, mirror = self._scaffold()
        catalog = self._catalog(dev)
        catalog["plugins"] = []
        _json(dev.parent / "marketplace.json", catalog)
        with _gates(dev, dist, mirror), _quiet():
            self.assertEqual(build_dist.main(["--catalog-check"]), 1)

    def test_duplicated_entry_fails(self):
        dev, dist, mirror = self._scaffold()
        catalog = self._catalog(dev)
        catalog["plugins"].append(dict(catalog["plugins"][0]))
        _json(dev.parent / "marketplace.json", catalog)
        with _gates(dev, dist, mirror), _quiet():
            self.assertEqual(build_dist.main(["--catalog-check"]), 1)


class StampTests(unittest.TestCase):
    """The source manifest is the only hand-set version; both derived
    manifests follow it on build. The marketplace entry kept a 0.1.2 of its
    own through seven releases before this existed."""

    def _scaffold(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return _scaffold(Path(tmp.name))

    def test_stamp_pulls_derived_manifests_to_the_source(self):
        dev, dist, mirror = self._scaffold()
        stale = {**MANIFEST, "version": "0.1.2", "description": "stale wording"}
        _json(dev / ".claude-plugin" / "plugin.json", stale)
        marketplace = json.loads(
            (dev / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        marketplace["plugins"][0]["version"] = "0.1.2"
        marketplace["plugins"][0]["description"] = "stale wording"
        _json(dev / ".claude-plugin" / "marketplace.json", marketplace)

        with _gates(dev, dist, mirror), _quiet():
            self.assertEqual(build_dist._stamp_manifests(), 0)

        claude = json.loads((dev / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(claude["version"], "9.9.9")
        self.assertEqual(claude["description"], "test manifest description")
        entry = json.loads(
            (dev / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))["plugins"][0]
        self.assertEqual(entry["version"], "9.9.9")
        self.assertEqual(entry["description"], "test manifest description")
        # Branding fields the manifest does not carry stay untouched.
        self.assertEqual(entry["displayName"], "T")

    def test_stamp_fails_loudly_without_a_marketplace_manifest(self):
        dev, dist, mirror = self._scaffold()
        absent = dev.parent / "no-such-marketplace.json"
        with _gates(dev, dist, mirror), \
             mock.patch.object(build_dist, "MARKETPLACE", absent), _quiet():
            self.assertEqual(build_dist._stamp_manifests(), 1)
        self.assertFalse(absent.exists(),
                         "a missing marketplace manifest must fail, not be invented")

    def test_stamp_fails_on_a_duplicated_entry(self):
        dev, dist, mirror = self._scaffold()
        marketplace = json.loads(
            (dev / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        marketplace["plugins"].append(dict(marketplace["plugins"][0]))
        _json(dev / ".claude-plugin" / "marketplace.json", marketplace)
        with _gates(dev, dist, mirror), _quiet():
            self.assertEqual(build_dist._stamp_manifests(), 1)


class BuildGuardTests(unittest.TestCase):
    """build() refuses to clear a tree this script did not create: the marker
    lives beside the target, because anything inside it would reach installs."""

    def _scaffold(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return _scaffold(Path(tmp.name))

    def test_build_refuses_to_clear_an_unmarked_tree(self):
        dev, dist, mirror = self._scaffold()
        _write(dist / "guard.txt", "not ours\n")
        with _gates(dev, dist, mirror), _quiet():
            self.assertEqual(build_dist.build(), 1)
        self.assertTrue((dist / "guard.txt").is_file(),
                        "build() cleared a tree it did not create")

    def test_build_with_the_marker_rebuilds_and_verifies(self):
        dev, dist, mirror = self._scaffold()
        marker = dist.parent / ".polishkit-dist.generated"
        marker.write_bytes(b"ok\n")
        with _gates(dev, dist, mirror), _quiet():
            self.assertEqual(build_dist.build(), 0)
        staged = json.loads(
            (dist / ".zcode-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(staged["version"], "9.9.9")
        self.assertTrue((dist / "skills" / "polishkit" / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
