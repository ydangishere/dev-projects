import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from agent.auto_reply import find_rule, load_rules, normalize, process_auto_reply


class AutoReplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.comment = {
            "comment_id": "comment1", "kind": "top-level", "text": "Cảm ơn ad nhé!",
            "author_channel_id": "viewer", "published_at": datetime.now(timezone.utc).isoformat(),
        }
        self.rules = [{"id": "thanks", "triggers": ["cảm ơn ad"], "reply": "Cảm ơn bạn!"}]

    def test_normalization(self):
        self.assertEqual(normalize(" Cảm Ơn AD nhé! "), "cảm ơn ad nhé")

    def test_exact_triggers_only(self):
        self.assertEqual(find_rule(self.comment["text"], self.rules)["id"], "thanks")
        self.assertIsNone(find_rule("Xin báo giá nhôm", self.rules))

    def test_ambiguous_rules_skip(self):
        r = self.rules + [{"id": "other", "triggers": ["cảm ơn"], "reply": "Cảm ơn!"}]
        self.assertIsNone(find_rule("Cảm ơn ad nhé!", r))

    def test_empty_config_disables_all(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / "faq.json"
            file.write_text('{"rules":[]}', encoding="utf-8")
            self.assertEqual(load_rules(str(file)), [])

    def test_default_disabled_no_posts(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("agent.auto_reply.post_reply") as post:
                self.assertEqual(process_auto_reply(self.db, self.comment, "owner", self.rules, 0)["status"], "skipped")
                post.assert_not_called()

    def test_dry_run_no_posts(self):
        with patch.dict(os.environ, {"AUTO_REPLY_ENABLED": "true", "AUTO_REPLY_DRY_RUN": "true"}):
            with patch("agent.auto_reply.post_reply") as post:
                self.assertEqual(process_auto_reply(self.db, self.comment, "owner", self.rules, 0)["status"], "dry_run")
                post.assert_not_called()

    def test_no_oauth_does_not_post(self):
        with patch.dict(os.environ, {"AUTO_REPLY_ENABLED": "true", "AUTO_REPLY_DRY_RUN": "false",
                                     "YOUTUBE_OAUTH_FILE": "/does/not/exist"}):
            self.assertEqual(process_auto_reply(self.db, self.comment, "owner", self.rules, 0)["status"], "no_oauth")

    def test_only_top_level_comments(self):
        with patch.dict(os.environ, {"AUTO_REPLY_ENABLED": "true"}):
            self.comment["kind"] = "reply"
            self.assertEqual(process_auto_reply(self.db, self.comment, "owner", self.rules, 0)["status"], "skipped")

    def test_sent_once(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / "oauth.json"
            file.write_text("{}", encoding="utf-8")
            with patch.dict(os.environ, {"AUTO_REPLY_ENABLED": "true", "AUTO_REPLY_DRY_RUN": "false",
                                         "YOUTUBE_OAUTH_FILE": str(file)}):
                with patch("agent.auto_reply.post_reply", return_value="youtube-reply1") as post:
                    self.assertEqual(process_auto_reply(self.db, self.comment, "owner", self.rules, 0)["status"], "sent")
                    self.assertEqual(process_auto_reply(self.db, self.comment, "owner", self.rules, 0)["status"], "duplicate")
                    post.assert_called_once()

    def test_contact_or_question_rule_matches_only_relevant_comments(self):
        config_path = Path(__file__).resolve().parents[1] / "config" / "faq_rules.json"
        rules = load_rules(str(config_path))
        self.assertEqual(len(rules), 1)
        expected = "Bạn vui lòng add zalo 0908133919. Xin cảm ơn"
        self.assertEqual(rules[0]["reply"], expected)
        eligible = [
            "Mình muốn liên hệ với bạn", "Xin zalo của bạn nhé",
            "Cho em xin SDT để hỏi thêm", "Anh cho em hỏi được không ạ",
            "Cho minh hoi ve may han nhom", "Hàn nhôm 3mm thì chỉnh dòng bao nhiêu?",
            "Tôi muốn nhờ bạn tư vấn thêm", "How do I contact you?",
        ]
        for message in eligible:
            with self.subTest(message=message):
                self.assertEqual(find_rule(message, rules)["id"], "contact_or_question_zalo")
        ordinary = [
            "Video rất hay", "Cảm ơn bạn đã chia sẻ",
            "Chúc bạn thành công", "Like và subscribe nhé!",
            "👍", "Great video!", "Cam on ad nhe?",
        ]
        for message in ordinary:
            with self.subTest(message=message):
                self.assertIsNone(find_rule(message, rules))

    def test_contact_rule_dry_run_never_posts(self):
        config_path = Path(__file__).resolve().parents[1] / "config" / "faq_rules.json"
        rules = load_rules(str(config_path))
        self.comment["text"] = "Bạn có số điện thoại không?"
        with patch.dict(os.environ, {"AUTO_REPLY_ENABLED": "true", "AUTO_REPLY_DRY_RUN": "true"}):
            with patch("agent.auto_reply.post_reply") as post:
                outcome = process_auto_reply(self.db, self.comment, "owner", rules, 0)
                self.assertEqual(outcome["status"], "dry_run")
                post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
