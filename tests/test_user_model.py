import unittest
from app.models import User
from database_setup import Base, engine, check_connection
from sqlalchemy.orm import Session

class TestUserModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not check_connection(engine):
            raise Exception("Failed to connect to the database.")

    def setUp(self):
        Base.metadata.create_all(engine)
        self.session = Session(bind=engine)
        self.session.begin()

    def tearDown(self):
        self.session.rollback()
        self.session.close()

    def test_create_user_and_check_password(self):
        new_user = User(name="John", surname="Doe", email="johndoe@example.com", role='czytelnik')
        new_user.set_password("securepassword")
        self.session.add(new_user)
        self.session.flush()

        user = self.session.query(User).filter_by(email="johndoe@example.com").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.name, "John")
        self.assertEqual(user.surname, "Doe")
        self.assertEqual(user.email, "johndoe@example.com")
        self.assertEqual(user.role, 'czytelnik')
        self.assertTrue(user.wants_notifications)
        self.assertTrue(user.check_password("securepassword"))
        self.assertFalse(user.check_password("wrongpassword"))

if __name__ == '__main__':
    unittest.main()

#python -m unittest tests/test_user_model.py
#python -m unittest discover -s tests