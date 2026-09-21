import time
import unittest
from app import app
from models.user import db, User
from models.proctor import ExamSession, FaceAbsenceInterval
from services.face_detector import FaceDetector, face_detector_instance
from services.event_logger import EventLogger


class FaceMonitoringTests(unittest.TestCase):
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

        # Create test session
        self.session = ExamSession(
            email="test_student@example.com",
            student_name="Test Student",
            course_id="cs301",
            status="in_progress"
        )
        db.session.add(self.session)
        db.session.commit()

        self.logger = EventLogger()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_face_detector_initialization(self):
        detector = FaceDetector()
        self.assertIsNotNone(detector)
        # Check invalid image data URI returns None
        self.assertIsNone(detector.decode_image("invalid_data"))

    def test_face_absence_interval_logging_cycle(self):
        email = "test_student@example.com"
        course_id = "cs301"
        session_id = self.session.id

        # 1. Check face present initial state
        res1 = self.logger.process_face_check(
            email=email,
            course_id=course_id,
            face_present=True,
            face_count=1,
            session_id=session_id
        )
        self.assertTrue(res1['face_present'])
        self.assertEqual(res1['current_absence_duration'], 0.0)

        # 2. Face absent start (t0)
        t0 = time.time()
        res2 = self.logger.process_face_check(
            email=email,
            course_id=course_id,
            face_present=False,
            face_count=0,
            session_id=session_id,
            timestamp=t0
        )
        self.assertFalse(res2['face_present'])
        self.assertTrue(res2['interval_started'])

        # 3. Face absent continues after 4 seconds (t1 = t0 + 4.0)
        t1 = t0 + 4.0
        res3 = self.logger.process_face_check(
            email=email,
            course_id=course_id,
            face_present=False,
            face_count=0,
            session_id=session_id,
            timestamp=t1
        )
        self.assertAlmostEqual(res3['current_absence_duration'], 4.0, delta=0.5)

        # 4. Face returned after 6 seconds total (t2 = t0 + 6.0)
        t2 = t0 + 6.0
        res4 = self.logger.process_face_check(
            email=email,
            course_id=course_id,
            face_present=True,
            face_count=1,
            session_id=session_id,
            timestamp=t2
        )
        self.assertTrue(res4['interval_closed'])

        # Verify record in database
        interval = FaceAbsenceInterval.query.filter_by(session_id=session_id).first()
        self.assertIsNotNone(interval)
        self.assertEqual(interval.email, email)
        self.assertAlmostEqual(interval.duration_seconds, 6.0, delta=0.5)
        self.assertEqual(interval.reason, 'face_absent')

    def test_multi_face_detection_logging(self):
        email = "test_student@example.com"
        course_id = "cs301"
        session_id = self.session.id

        res = self.logger.process_face_check(
            email=email,
            course_id=course_id,
            face_present=True,
            face_count=2,  # Multiple faces
            session_id=session_id
        )
        self.assertTrue(res['interval_started'])

        interval = FaceAbsenceInterval.query.filter_by(session_id=session_id).first()
        self.assertIsNotNone(interval)
        self.assertEqual(interval.reason, 'multiple_faces')


if __name__ == "__main__":
    unittest.main()
