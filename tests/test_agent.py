"""Offline tests: nothing here talks to a real platform or posts anything.

Run:  ~/.venvs/social-agent/bin/python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import requests  # noqa: E402

import common  # noqa: E402
import publish  # noqa: E402
import voice  # noqa: E402
from platforms import linkedin  # noqa: E402


def response(status: int, headers: dict | None = None) -> requests.Response:
    r = requests.Response()
    r.status_code, r._content = status, b"{}"
    r.headers.update(headers or {})
    return r


class HttpRetryTest(unittest.TestCase):
    def setUp(self):
        self.sleep = mock.patch("time.sleep").start()
        self.addCleanup(mock.patch.stopall)

    def test_retries_server_errors_then_succeeds(self):
        with mock.patch("requests.request", side_effect=[response(503), response(502), response(200)]) as req:
            self.assertEqual(common.http("GET", "https://x").status_code, 200)
        self.assertEqual(req.call_count, 3)

    def test_honours_retry_after(self):
        with mock.patch("requests.request", side_effect=[response(429, {"Retry-After": "7"}), response(200)]):
            common.http("GET", "https://x")
        self.sleep.assert_called_once_with(7)

    def test_gives_up_with_last_response(self):
        with mock.patch("requests.request", return_value=response(500)):
            self.assertEqual(common.http("GET", "https://x", attempts=2).status_code, 500)

    def test_final_call_never_retried_after_lost_answer(self):
        with mock.patch("requests.request", side_effect=requests.exceptions.ReadTimeout()) as req:
            with self.assertRaises(common.OutcomeUnknown):
                common.http("POST", "https://x", final=True)
        self.assertEqual(req.call_count, 1)

    def test_final_call_5xx_is_unknown(self):
        with mock.patch("requests.request", return_value=response(504)) as req:
            with self.assertRaises(common.OutcomeUnknown):
                common.http("POST", "https://x", final=True)
        self.assertEqual(req.call_count, 1)

    def test_final_call_retries_when_request_never_arrived(self):
        side = [requests.exceptions.ConnectTimeout(), response(429), response(201)]
        with mock.patch("requests.request", side_effect=side) as req:
            self.assertEqual(common.http("POST", "https://x", final=True).status_code, 201)
        self.assertEqual(req.call_count, 3)

    def test_file_body_rewound_between_tries(self):
        seen = []
        with tempfile.TemporaryFile() as f:
            f.write(b"hello")
            f.seek(0)

            def fake(method, url, data=None, **kw):
                seen.append(data.read())
                return response(503) if len(seen) == 1 else response(200)
            with mock.patch("requests.request", side_effect=fake):
                common.http("PUT", "https://x", data=f)
        self.assertEqual(seen, [b"hello", b"hello"])


class LinkedInTextTest(unittest.TestCase):
    def test_escape_keeps_hashtags_and_mentions(self):
        out = linkedin.escape("Hi (all) #AIAgents @[Replit](urn:li:organization:42) a_b")
        self.assertIn("\\(all\\)", out)
        self.assertIn("{hashtag|\\#|AIAgents}", out)
        self.assertIn("@[Replit](urn:li:organization:42)", out)
        self.assertIn("a\\_b", out)

    def test_expand_mentions(self):
        with mock.patch.object(linkedin, "load_mentions",
                               return_value={"Replit": "urn:li:organization:1", "n8n": "urn:li:organization:2"}):
            out = linkedin.expand_mentions("@Replit and @n8n, mail x@Replit.com, @Replit's", "main")
        self.assertEqual(out, "@[Replit](urn:li:organization:1) and @[n8n](urn:li:organization:2), "
                              "mail x@Replit.com, @[Replit](urn:li:organization:1)'s")

    def test_caption_limit(self):
        self.assertTrue(linkedin.check({"caption": "x" * 3001}, None, {"kind": "image"}))
        self.assertFalse(linkedin.check({"caption": "fine"}, None, {"kind": "image"}))


class VoiceTest(unittest.TestCase):
    def test_flags_template_caption(self):
        text = "Notice the pattern:\n→ one\n→ two\n#a #b #c #d"
        found = " ".join(voice.ai_tells(text))
        self.assertIn("notice the pattern", found)
        self.assertIn("arrow", found)
        self.assertIn("4 hashtags", found)

    def test_plain_caption_passes(self):
        self.assertEqual(voice.ai_tells("Spent the week testing agent launches. Most of the work was "
                                        "approvals, honestly. #AIAgents #AIAutomation"), [])

    def test_instagram_allows_more_hashtags(self):
        self.assertEqual(voice.ai_tells("Nice day " + " ".join(f"#t{i}" for i in range(6)), "instagram"), [])


def fake_platform(behaviour):
    return types.SimpleNamespace(LABEL="Fake", MODE="api", MEDIA={"text"},
                                 check=lambda t, m, i: [], publish=behaviour)


class PublishFlowTest(unittest.TestCase):
    """run_targets with fake platforms, in a temp project folder."""

    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(publish, "POSTED", tmp / "posted").start()
        mock.patch.object(common, "POSTED", tmp / "posted").start()
        mock.patch.object(common, "HISTORY", tmp / "posted" / "log.jsonl").start()
        mock.patch.object(publish, "get_account", return_value=("me", {})).start()
        self.d = tmp / "drafts" / "20261121-0900-test"
        self.d.mkdir(parents=True)
        self.draft = {"id": self.d.name, "title": "t", "kind": "text", "media": None, "status": "pending",
                      "targets": [{"platform": "a", "caption": "x"}, {"platform": "b", "caption": "y"}],
                      "results": {}}
        common.save_draft(self.d, self.draft)

    def use(self, mods: dict):
        mock.patch.object(publish.platforms, "load", side_effect=lambda p: mods[p]).start()

    def test_crash_in_one_platform_does_not_stop_others(self):
        def boom(*a):
            raise KeyError("value")
        self.use({"a": fake_platform(boom), "b": fake_platform(lambda *a: {"id": "2", "url": "u"})})
        with mock.patch("traceback.print_exc"):
            publish.run_targets(self.d, self.draft, None)
        r = common.load_draft(self.d)["results"]
        self.assertEqual(r["a:default"]["status"], "failed")
        self.assertIn("KeyError", r["a:default"]["error"])
        self.assertEqual(r["b:default"]["status"], "posted")
        self.assertEqual(common.load_draft(self.d)["status"], "partial")

    def test_unknown_outcome_is_never_retried(self):
        calls = []

        def unsure(*a):
            calls.append(1)
            raise common.OutcomeUnknown("lost answer")
        ok = fake_platform(lambda *a: {"id": "2", "url": "u"})
        self.use({"a": fake_platform(unsure), "b": ok})
        publish.run_targets(self.d, self.draft, None)
        draft = common.load_draft(self.d)
        self.assertEqual(draft["status"], "needs_check")
        publish.run_targets(self.d, draft, None)  # a second publish must not touch "a" again
        self.assertEqual(len(calls), 1)

    def test_all_posted_moves_to_posted_and_logs(self):
        ok = fake_platform(lambda *a: {"id": "1", "url": "u"})
        self.use({"a": ok, "b": ok})
        final = publish.run_targets(self.d, self.draft, None)
        self.assertEqual(final.parent, publish.POSTED)
        self.assertEqual(common.load_draft(final)["status"], "posted")
        self.assertEqual(json.loads(common.HISTORY.read_text().splitlines()[0])["id"], self.d.name)

    def test_fingerprint_changes_with_caption(self):
        before = common.fingerprint(self.d, self.draft)
        self.draft["targets"][0]["caption"] = "edited"
        self.assertNotEqual(before, common.fingerprint(self.d, self.draft))


class DraftLockTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        p = mock.patch.object(common, "ROOT", self.root)
        p.start()
        self.addCleanup(p.stop)

    def test_second_run_is_refused_while_locked(self):
        d = Path("drafts/x")
        with common.DraftLock(d):
            with self.assertRaises(SystemExit):
                common.DraftLock(d).__enter__()
        self.assertFalse(common.DraftLock(d).path.exists())

    def test_stale_lock_from_crashed_run_is_cleared(self):
        lock = common.DraftLock(Path("drafts/x"))
        lock.path.parent.mkdir(parents=True)
        lock.path.write_text("999999999 old\n")  # no such process
        with lock:
            self.assertTrue(lock.path.exists())


if __name__ == "__main__":
    unittest.main()
