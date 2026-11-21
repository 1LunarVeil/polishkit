"""Browser-free tests for POLISHKIT_CHROME_EXTRA_ARGS and the load fallback.

Two runner facts shaped these. Ubuntu 24.04's AppArmor restriction on
unprivileged user namespaces aborts a stock Chrome (exit -6) before the debug
port opens, and Chrome for Testing ships no AppArmor profile to escape it —
so CI passes --no-sandbox explicitly through the env var, and a stale or
malformed value must fail loudly rather than quietly launching without it.
And runner VMs occasionally never deliver Page.loadEventFired for a page that
has finished loading (a Windows CI run timed out on one invocation and passed
the next with nothing changed), so a complete document counts as loaded.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "polishkit" / "scripts"))

import cdp  # noqa: E402


class ExtraChromeArgsTests(unittest.TestCase):
    def test_parsed_with_shlex_and_empty_when_unset(self):
        with mock.patch.dict(os.environ,
                             {"POLISHKIT_CHROME_EXTRA_ARGS": '--no-sandbox --lang="zh-CN"'}):
            self.assertEqual(cdp.extra_chrome_args(), ["--no-sandbox", "--lang=zh-CN"])
        with mock.patch.dict(os.environ, {}):
            os.environ.pop("POLISHKIT_CHROME_EXTRA_ARGS", None)
            self.assertEqual(cdp.extra_chrome_args(), [])

    def test_launch_command_places_extra_args_before_the_startup_url(self):
        with mock.patch.dict(os.environ, {"POLISHKIT_CHROME_EXTRA_ARGS": "--no-sandbox"}):
            command = cdp.chrome_launch_command("chrome", Path("profile"))
        self.assertEqual(command[-1], "about:blank")
        self.assertIn("--no-sandbox", command)
        self.assertLess(command.index("--no-sandbox"),
                        command.index("about:blank"),
                        "an extra argument must not become the startup URL")
        self.assertIn("--remote-debugging-port=0", command)

    def test_malformed_value_fails_loudly(self):
        with mock.patch.dict(os.environ, {"POLISHKIT_CHROME_EXTRA_ARGS": '--unbalanced "quote'}):
            with self.assertRaises(ValueError):
                cdp.extra_chrome_args()


class WaitForLoadTests(unittest.TestCase):
    def _page(self, ready_state):
        page = cdp.PageSession("http://127.0.0.1:9/")
        page.session = mock.Mock()
        page.session.send.return_value = {"result": {"value": ready_state}}
        page.session_id = "sid"
        page.load_timeout = 0.05
        return page

    def test_event_received_means_loaded_without_asking_the_page(self):
        page = self._page("interactive")
        with mock.patch.object(cdp, "wait_for_event", return_value={"method": "Page.loadEventFired"}):
            page._wait_for_load()
        page.session.send.assert_not_called()

    def test_lost_event_with_a_complete_page_is_loaded(self):
        page = self._page("complete")
        with mock.patch.object(cdp, "wait_for_event", return_value=None):
            page._wait_for_load()

    def test_lost_event_with_an_incomplete_page_names_the_state(self):
        page = self._page("loading")
        with mock.patch.object(cdp, "wait_for_event", return_value=None):
            with self.assertRaises(cdp.BrowserError) as caught:
                page._wait_for_load()
        self.assertIn("loading", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
