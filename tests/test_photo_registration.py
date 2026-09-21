import os
import unittest

from app import app
from models.user import db, User


class PhotoRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///:memory:")
        self.client = self.app.test_client()

        with self.app.app_context():
            db.drop_all()
            db.create_all()

    def test_register_saves_photo_and_creates_user(self):
        photo_data = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2Q=="

        response = self.client.post(
            "/register",
            data={
                "name": "Test Student",
                "email": "student@example.com",
                "password": "secret123",
                "photo_data": photo_data,
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            user = User.query.filter_by(email="student@example.com").first()
            self.assertIsNotNone(user)
            self.assertTrue(user.photo)
            self.assertTrue(os.path.exists(os.path.join("static", user.photo)))


if __name__ == "__main__":
    unittest.main()
