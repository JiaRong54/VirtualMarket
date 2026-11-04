import unittest
from convert_history import movement_stats

class MovementStatsTests(unittest.TestCase):
    def test_missing_days_and_sales_window(self):
        result = movement_stats([['2026-10-01', 100, 10], ['2026-10-24', 200, 20], ['2026-10-30', 300, 30], ['2026-11-01', 400, 40]])
        self.assertEqual(result['price'], 400)
        self.assertEqual(result['prev'], {'1': 300, '7': 200, '30': 100})
        self.assertEqual(result['sold_7d'], 70)
