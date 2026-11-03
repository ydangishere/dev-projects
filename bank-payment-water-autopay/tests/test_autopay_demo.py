import copy
import unittest
from autopay_demo import DEFAULT_STATE, run_bill

class TestAutoPay(unittest.TestCase):
    def setUp(self):
        self.s = copy.deepcopy(DEFAULT_STATE)

    def test_success_debits_once(self):
        first = run_bill(self.s, "2026-11", 189000)
        self.assertEqual(first["status"], "SUCCESS")
        second = run_bill(self.s, "2026-11", 189000)
        self.assertEqual(second["status"], "ALREADY_PAID")
        self.assertEqual(self.s["balance_vnd"], 1311000)
        self.assertEqual(len(self.s["payments"]), 1)

    def test_exceeds_mandate(self):
        result = run_bill(self.s, "2026-12", 700000)
        self.assertEqual(result["status"], "LIMIT_EXCEEDED")
        self.assertEqual(self.s["balance_vnd"], 1500000)

    def test_no_funds(self):
        self.s["balance_vnd"] = 50000
        result = run_bill(self.s, "2026-12", 189000)
        self.assertEqual(result["status"], "INSUFFICIENT_FUNDS")
        self.assertFalse(self.s["payments"])

    def test_disabled_mandate(self):
        self.s["mandate"]["active"] = False
        self.assertEqual(run_bill(self.s, "2026-12", 189000)["status"], "MANDATE_INACTIVE")

if __name__ == "__main__":
    unittest.main()
