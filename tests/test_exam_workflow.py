import json
import unittest
from app import app
from models.user import db, User
from models.proctor import ExamSession, SuspiciousReport


class ExamWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:"
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            db.drop_all()
            db.create_all()
            # Register test user
            user = User(
                name="Proctor Student",
                email="student@exam.com",
                password="hashed_pw"
            )
            db.session.add(user)
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_full_exam_monitoring_and_submission_workflow(self):
        # 1. Login
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['email'] = 'student@exam.com'
            sess['name'] = 'Proctor Student'

        # 2. Access exam page
        response = self.client.get('/exam/take/math101')
        self.assertEqual(response.status_code, 200)

        # Verify active exam session created
        with self.app.app_context():
            session_obj = ExamSession.query.filter_by(email='student@exam.com', course_id='math101').first()
            self.assertIsNotNone(session_obj)
            session_id = session_obj.id

        # 3. Send face-check API request
        face_resp = self.client.post(
            '/exam/monitor/face-check',
            json={
                'email': 'student@exam.com',
                'course': 'math101',
                'session_id': session_id,
                'image_data': 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2Q=='
            }
        )
        self.assertEqual(face_resp.status_code, 200)

        # 4. Send browser events log API request
        event_resp = self.client.post(
            '/exam/monitor/log-events',
            json={
                'email': 'student@exam.com',
                'course': 'math101',
                'session_id': session_id,
                'events': [
                    {'type': 'tab_switch', 'details': 'Switch #1'},
                    {'type': 'window_blur', 'details': 'Blur #1'}
                ],
                'summary': {
                    'focusLossCount': 1,
                    'tabSwitchCount': 1,
                    'faceAbsentTotalSeconds': 0.0
                }
            }
        )
        self.assertEqual(event_resp.status_code, 200)

        # 5. Submit Exam
        submit_resp = self.client.post(
            '/exam/submit',
            json={
                'email': 'student@exam.com',
                'course': 'math101',
                'session_id': session_id,
                'name': 'Proctor Student',
                'answers': ['4', '4'],  # Correct answers for math101
                'monitorSummary': {
                    'focusLossCount': 1,
                    'tabSwitchCount': 1,
                    'faceAbsentTotalSeconds': 0.0,
                    'multiFaceCount': 0,
                    'unauthorizedActionsCount': 0
                }
            }
        )
        self.assertEqual(submit_resp.status_code, 200)
        data = submit_resp.get_json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['score'], 100.0)

        # 6. Verify SuspiciousReport persisted
        with self.app.app_context():
            report = SuspiciousReport.query.filter_by(session_id=session_id).first()
            self.assertIsNotNone(report)
            self.assertEqual(report.email, 'student@exam.com')

        # 7. Access Proctor Integrity Report page
        report_page = self.client.get(f'/exam/report/{session_id}')
        self.assertEqual(report_page.status_code, 200)
        self.assertIn(b'Integrity Report', report_page.data)


if __name__ == "__main__":
    unittest.main()
