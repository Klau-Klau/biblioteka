import unittest
from datetime import datetime
from app.models import User, BookCopy, Reservation
from database_setup import Base, engine, check_connection
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

class TestReservationModel(unittest.TestCase):
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

    def test_create_reservation(self):
        new_user = User(name="Test", surname="User", email="test@example.com",
                        password=generate_password_hash("testpassword"), role='czytelnik',
                        wants_notifications=True)
        self.session.add(new_user)
        self.session.flush()
        new_book_copy = BookCopy(status='dostępna')
        self.session.add(new_book_copy)
        self.session.flush()

        new_reservation = Reservation(user_id=new_user.id, book_id=new_book_copy.id,
                                      status='aktywna')
        self.session.add(new_reservation)
        self.session.flush()

        reservation = self.session.query(Reservation).filter_by(user_id=new_user.id).first()
        self.assertIsNotNone(reservation)
        self.assertEqual(reservation.status, 'aktywna')
        self.assertTrue(isinstance(reservation.date_of_reservation, datetime))

if __name__ == '__main__':
    unittest.main()

#python -m unittest tests/test_reservation_model.py
#python -m unittest discover -s tests