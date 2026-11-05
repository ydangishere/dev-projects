import json
import tempfile
import unittest
from pathlib import Path
from triage_agent.connectors import WorkItem, mock_items
from triage_agent.engine import triage, redact
from triage_agent.knowledge import SCENARIOS
from triage_agent.report import report

class TriageTests(unittest.TestCase):
    def test_all_15_scenarios_and_unknown(self):
        items = mock_items(Path("fixtures/issues.json"))
        results = triage(items)
        mapping = {r["source_id"]: r["scenario_id"] for r in results}
        for number in range(101,116):
            key = f"DEMO-{number}" if number not in (103,106,108,110,114) else f"demo-mail-{number}"
            self.assertEqual(mapping[key],number-100)
        self.assertIsNone(mapping["demo-mail-116"])

    def test_deduplication(self):
        item = WorkItem("jira","SAME","Double booking same slot","")
        self.assertEqual(len(triage([item,item])),1)

    def test_redaction(self):
        r = redact("User a.person@example.org phoned +84901234567")
        self.assertNotIn("example.org",r)
        self.assertNotIn("901234567",r)

    def test_reports_have_all_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            md,js = report(triage([WorkItem("jira","X","Double booking same slot","")]),Path(tmp),"mock")
            body = md.read_text(encoding="utf-8")
            self.assertIn("Tình huống | Vấn đề | Cách sửa | Dùng gì để sửa",body)
            self.assertEqual(body.count("| ☐ |"),16)  # one event + 15 reference rows
            self.assertEqual(len(json.loads(js.read_text(encoding="utf-8"))["items"]),1)

if __name__ == "__main__":
    unittest.main()
