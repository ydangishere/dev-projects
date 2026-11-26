"""Protect source attribution and existing knowledge during resource updates."""
import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent / "scripts"))
import update_youtube_knowledge as job


class SourceChecks(unittest.TestCase):
    def setUp(self):
        self.text = "[10] kiểm tra kim phao không nhún được nên bình xăng chảy xăng\n"
        self.record = {"video_id": "VDaR6Uv2EFI", "duration_seconds": 60}
        self.case = {"t": 10, "system": "nhiên liệu", "symptom": "Bình xăng chảy xăng",
                     "cause": "Kim phao không nhún", "fix": "Kiểm tra kim phao",
                     "parts": [], "tools": [], "vehicles": [], "specs": [], "warnings": [],
                     "evidence": [{"t": 10, "quote": "kiểm tra kim phao không nhún được"}]}

    def test_timestamped_caption_text_is_not_lost(self):
        segments = [{"start": 0.1, "duration": 1, "text": "kiểm tra kim"},
                    {"start": 0.8, "duration": 1, "text": "phao không nhún"},
                    {"start": 40, "duration": 1, "text": "tháo ra vệ sinh"}]
        chunks = job.transcript_chunks(segments)
        self.assertEqual(" ".join(text for _, text in chunks), "kiểm tra kim phao không nhún tháo ra vệ sinh")
        self.assertEqual([start for start, _ in chunks], [0, 40])

    def test_evidence_cannot_be_attributed_to_another_time(self):
        self.case["evidence"][0]["t"] = 400
        accepted, rejected = job.verify_cases({"cases": [self.case]}, self.record, self.text)
        self.assertFalse(accepted)
        self.assertIn("quote_not_in_source_at_timestamp", rejected[0]["reasons"])

    def test_unsupported_numeric_specification_is_not_importable(self):
        self.case["specs"] = [{"name": "khe hở", "value": "0.15", "unit": "mm"}]
        accepted, rejected = job.verify_cases({"cases": [self.case]}, self.record, self.text)
        self.assertFalse(accepted)
        self.assertIn("spec_number_not_in_transcript", rejected[0]["reasons"])

    def test_machine_extraction_does_not_become_expert_approval(self):
        self.case["reviewed"] = True
        accepted, rejected = job.verify_cases({"cases": [self.case]}, self.record, self.text)
        self.assertFalse(rejected)
        self.assertIs(accepted[0]["reviewed"], False)

    def test_existing_case_collision_stops_before_touching_store(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data, stage = root / "data", root / "staging"
            data.mkdir()
            stage.mkdir()
            (data / "videos.tsv").write_text("video_id\ttitle\tduration\ttopic\tstatus\n", encoding="utf-8")
            old = {"cases": [{"id": "C01", "fix": "original knowledge"}]}
            original = data / "knowledge.json"
            original.write_text(json.dumps(old), encoding="utf-8")
            before = original.read_bytes()
            manifest = stage / "manifest.json"
            job.save_json(manifest, {})
            case = dict(self.case, id="C01", video_id=self.record["video_id"], reviewed=False)
            job.save_json(stage / "knowledge_prepared.json", {"videos": {}, "cases": [case]})
            job.save_json(stage / "preview_check.json", {
                "validation_exit": 0,
                "prepared_sha256": hashlib.sha256((stage / "knowledge_prepared.json").read_bytes()).hexdigest(),
            })
            with patch.multiple(job, DATA=data, STAGE=stage, MANIFEST=manifest):
                with self.assertRaisesRegex(ValueError, "collides"):
                    job.apply(SimpleNamespace())
            self.assertEqual(original.read_bytes(), before)
            self.assertFalse((data / "knowledge_youtube_update.json").exists())

    def test_windows_line_endings_do_not_discard_valid_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data, stage, reports = root / "data", root / "staging", root / "reports"
            for path in [data, stage / "clean", stage / "extracted", reports]:
                path.mkdir(parents=True, exist_ok=True)
            vid = "VDaR6Uv2EFI"
            clean = stage / "clean" / (vid + ".txt")
            clean.write_bytes(b"[0] source words kept with timestamps\r\n")
            digest = hashlib.sha256(clean.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
            job.save_json(stage / "extracted" / (vid + ".json"), {
                "transcript_sha256": digest, "result": {"disposition": "technical"},
                "accepted_cases": [], "rejected_cases": [],
            })
            job.save_json(stage / "manifest.json", {vid: {"title": "Source", "url": "https://example.test"}})
            (reports / "youtube_unused_videos.csv").write_text("video_id\n" + vid + "\n", encoding="utf-8")
            with patch.multiple(job, DATA=data, STAGE=stage, REPORTS=reports,
                                MANIFEST=stage / "manifest.json"):
                with contextlib.redirect_stdout(io.StringIO()):
                    job.prepare(SimpleNamespace())
            prepared = json.loads((stage / "knowledge_prepared.json").read_text(encoding="utf-8"))
            self.assertIn(vid, prepared["videos"])

    @unittest.skipUnless((Path(__file__).parent / "index" / "state.pkl").exists(), "Build the local index first")
    def test_larger_corpus_keeps_specific_carburetor_diagnosis(self):
        import gemini_client
        import rag
        with patch.object(gemini_client, "available", return_value=False):
            rag.reset()
            state = rag.state()
            result = rag.retrieve("binh xang con buong ga ma ga khong ve")
            self.assertEqual(state["cases"][result["cases"][0]]["id"], "C28")
            rag.reset()


if __name__ == "__main__":
    unittest.main()
