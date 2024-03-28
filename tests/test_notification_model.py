import unittest
from app.models import User, Notification
from database_setup import Base, engine, check_connection
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

class TestNotificationModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not check_connection(engine):
            raise Exception("Nie udało się połączyć z bazą danych.")

    def setUp(self):
        Base.metadata.create_all(engine)
        self.session = Session(bind=engine)
        self.transaction = self.session.begin_nested()

    def tearDown(self):
        self.transaction.rollback()
        self.session.close()

    def test_create_notification(self):
        new_user = User(name="TestUser", surname="TestSurname", email="user@example.com",
                        password=generate_password_hash("password"), role="czytelnik", wants_notifications=True)
        self.session.add(new_user)
        self.session.flush()

        new_notification = Notification(user_id=new_user.id, content="Test notification content")
        self.session.add(new_notification)
        self.session.flush()

        notification = self.session.query(Notification).filter_by(user_id=new_user.id).first()
        self.assertIsNotNone(notification)
        self.assertEqual(notification.content, "Test notification content")

if __name__ == '__main__':
    unittest.main()


#python -m unittest tests/test_notification_model.py
#python -m unittest discover -s tests