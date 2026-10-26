import os
import sqlite3
from datetime import datetime, timezone
import tempfile
import unittest
from unittest.mock import patch

from agent.monitor import (
    extract_comments,
    heuristic_question,
    resolve_channel_id,
    message_text,
    connect_db,
    first_run_cutoff,
)


class CommentMonitorTests(unittest.TestCase):
    def test_parse_channel_url(self):
        channel_id = "UC1234567890123456789012"
        self.assertEqual(resolve_channel_id("https://www.youtube.com/channel/" + channel_id, "key"), channel_id)

    def test_handle_resolver(self):
        with patch("agent.monitor.request_json", return_value={"items": [{"id": "UCxx"}]}) as request:
            self.assertEqual(resolve_channel_id("https://www.youtube.com/@mycreator", "key"), "UCxx")
            self.assertEqual(request.call_args.kwargs["params"]["forHandle"], "@mycreator")

    def test_reject_fake_url(self):
        with self.assertRaises(ValueError):
            resolve_channel_id("https://youtube.com.evil.com/@x", "key")

    def test_extract_top_comment_and_reply(self):
        thread = {"snippet": {"videoId": "vid", "topLevelComment": {"id": "one", "snippet": {"textDisplay": "hi", "publishedAt": "2026-10-25T12:00:00Z"}}},
                  "replies": {"comments": [{"id": "two", "snippet": {"textDisplay": "hello", "publishedAt": "2026-10-25T12:01:00Z"}}]}}
        items = extract_comments(thread)
        self.assertEqual([x["kind"] for x in items], ["top-level", "reply"])
        self.assertEqual(items[1]["video_id"], "vid")

    def test_heuristic_question(self):
        self.assertTrue(heuristic_question("Hàn nhôm bao nhiêu A?"))
        self.assertFalse(heuristic_question("Cảm ơn bạn nhé"))

    def test_telegram_message(self):
        msg = message_text({"kind": "top-level", "video_id": "abc123", "comment_id": "comment1", "author": "Minh", "text": "Cho hỏi?"},
                           {"is_question": True, "reply": "Bạn thử nhé"})
        self.assertIn("lc=comment1", msg)
        self.assertIn("Bạn thử nhé", msg)

    def test_monitor_sends_only_once(self):
        from agent.monitor import monitor
        item = {
            "comment_id": "id-1", "video_id": "video-1", "text": "Có hướng dẫn không?",
            "author": "Viewers", "author_channel_id": "other-channel",
            "published_at": datetime.now(timezone.utc).isoformat(), "kind": "top-level"
        }
        with tempfile.TemporaryDirectory() as d:
            env = {
                "YOUTUBE_CHANNEL_URL": "https://www.youtube.com/@test",
                "YOUTUBE_API_KEY": "mock", "TELEGRAM_BOT_TOKEN": "mock",
                "TELEGRAM_CHAT_ID": "1", "COMMENT_DB_PATH": os.path.join(d, "comments.sqlite3"),
                "OPENAI_API_KEY": "", "INITIAL_LOOKBACK_MINUTES": "15"
            }
            with patch.dict(os.environ, env), \
                 patch("agent.monitor.resolve_channel_id", return_value="channel"), \
                 patch("agent.monitor.fetch_recent_comments", return_value=[item]), \
                 patch("agent.monitor.notify_telegram") as notify:
                self.assertEqual(monitor()["notified"], 1)
                self.assertEqual(monitor()["notified"], 0)
                notify.assert_called_once()

    def test_airflow_schedule_twice_per_day_vietnam_time(self):
        from pathlib import Path
        dag_file = Path(__file__).resolve().parents[1] / "dags" / "youtube_comments.py"
        content = dag_file.read_text(encoding="utf-8")
        self.assertIn('schedule="0 */12 * * *"', content)
        self.assertIn('tz="Asia/Ho_Chi_Minh"', content)

    def test_default_first_run_looks_back_12_hours(self):
        from datetime import timedelta
        with tempfile.TemporaryDirectory() as d:
            conn = connect_db(os.path.join(d, "comments.sqlite3"))
            with patch.dict(os.environ, {}, clear=True):
                before = datetime.now(timezone.utc)
                start = first_run_cutoff(conn)
                after = datetime.now(timezone.utc)
            self.assertTrue(before - timedelta(hours=12) <= start <= after - timedelta(hours=12))
            conn.close()

    def test_bootstrap_is_sticky(self):
        with tempfile.TemporaryDirectory() as d:
            conn = connect_db(os.path.join(d, "comments.sqlite3"))
            with patch.dict(os.environ, {"INITIAL_LOOKBACK_MINUTES": "15"}):
                start1 = first_run_cutoff(conn)
                start2 = first_run_cutoff(conn)
            self.assertEqual(start1, start2)
            conn.close()


if __name__ == "__main__":
    unittest.main()
