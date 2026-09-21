import unittest
from services.suspicion_engine import SuspicionEngine


class SuspicionEngineTests(unittest.TestCase):
    def setUp(self):
        self.rules = {
            "focus_loss_max": 3,
            "tab_switch_max": 2,
            "face_absence_max_seconds": 10,
            "face_absence_single_max_seconds": 5,
            "multi_face_max": 1,
            "unauthorized_actions_max": 2,
        }
        self.engine = SuspicionEngine(rules=self.rules)

    def test_clean_session_evaluation(self):
        res = self.engine.evaluate(
            focus_loss_count=0,
            tab_switch_count=0,
            face_absence_total_seconds=0.0,
            multi_face_count=0,
            unauthorized_actions_count=0
        )
        self.assertEqual(res['suspicion_score'], 0.0)
        self.assertEqual(res['suspicion_level'], 'LOW')
        self.assertFalse(res['is_suspicious'])
        self.assertEqual(len(res['flags_triggered']), 0)

    def test_single_threshold_breach(self):
        # Exceed tab switch threshold (max = 2)
        res = self.engine.evaluate(
            focus_loss_count=1,
            tab_switch_count=3,
            face_absence_total_seconds=2.0
        )
        self.assertIn('EXCESSIVE_TAB_SWITCH', res['flags_triggered'])
        self.assertGreaterEqual(res['suspicion_score'], 25.0)
        self.assertIn(res['suspicion_level'], ['MEDIUM', 'HIGH', 'CRITICAL'])

    def test_cumulative_and_single_face_absence_breach(self):
        face_intervals = [
            {'start_timestamp': 100, 'end_timestamp': 108, 'duration_seconds': 8.0},
            {'start_timestamp': 200, 'end_timestamp': 204, 'duration_seconds': 4.0},
        ]
        res = self.engine.evaluate(
            focus_loss_count=0,
            tab_switch_count=0,
            face_absence_total_seconds=12.0,  # > 10s max
            face_intervals=face_intervals
        )
        self.assertIn('CUMULATIVE_FACE_ABSENCE_EXCEEDED', res['flags_triggered'])
        self.assertIn('LONG_SINGLE_FACE_ABSENCE', res['flags_triggered'])
        self.assertTrue(res['is_suspicious'])

    def test_multiple_faces_detected_flag(self):
        res = self.engine.evaluate(
            multi_face_count=2
        )
        self.assertIn('MULTIPLE_FACES_DETECTED', res['flags_triggered'])
        self.assertGreaterEqual(res['suspicion_score'], 35.0)

    def test_critical_composite_violations(self):
        res = self.engine.evaluate(
            focus_loss_count=5,
            tab_switch_count=4,
            face_absence_total_seconds=25.0,
            multi_face_count=2,
            unauthorized_actions_count=4
        )
        self.assertEqual(res['suspicion_level'], 'CRITICAL')
        self.assertTrue(res['is_suspicious'])
        self.assertGreaterEqual(len(res['flags_triggered']), 4)


if __name__ == "__main__":
    unittest.main()
