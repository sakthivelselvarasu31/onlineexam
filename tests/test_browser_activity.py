import time
import unittest
from app import app
from models.user import db
from models.proctor import ExamSession, BrowserEvent
from services.event_logger import EventLogger


class BrowserActivityTests(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:"
        )
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.drop_all()
        db.create_all()

        self.session = ExamSession(
            email="student@test.com",
            student_name="Test Student",
            course_id="math101",
            status="in_progress"
        )
        db.session.add(self.session)
        db.session.commit()

        self.logger = EventLogger()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_log_browser_events_persistence(self):
        email = "student@test.com"
        course_id = "math101"
        session_id = self.session.id

        events_data = [
            {"type": "tab_switch", "details": "Switch #1", "timestamp": time.time() * 1000},
            {"type": "window_blur", "details": "Blur #1", "timestamp": time.time() * 1000},
            {"type": "mouse_leave", "details": "Left viewport", "timestamp": time.time() * 1000},
            {"type": "context_menu", "details": "Right click blocked", "timestamp": time.time() * 1000},
            {"type": "shortcut_key", "details": "DevTools keypress", "timestamp": time.time() * 1000},
        ]

        created_events = self.logger.log_browser_events(
            email=email,
            course_id=course_id,
            events=events_data,
            session_id=session_id
        )

        self.assertEqual(len(created_events), 5)

        # Query database to verify persistence
        saved_events = BrowserEvent.query.filter_by(session_id=session_id).all()
        self.assertEqual(len(saved_events), 5)

        event_types = [e.event_type for e in saved_events]
        self.assertIn("tab_switch", event_types)
        self.assertIn("window_blur", event_types)
        self.assertIn("mouse_leave", event_types)
        self.assertIn("context_menu", event_types)
        self.assertIn("shortcut_key", event_types)

        # Check severity assignment
        critical_evt = next(e for e in saved_events if e.event_type == "shortcut_key")
        self.assertEqual(critical_evt.severity, "CRITICAL")


if __name__ == "__main__":
    unittest.main()
