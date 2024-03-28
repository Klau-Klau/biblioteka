import unittest
from decimal import Decimal
from app.models import User, BookCopy, Payment
from database_setup import Base, engine, check_connection
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

class TestPaymentModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not check_connection(engine):
            raise Exception("Nie udało się połączyć z bazą danych.")

    def setUp(self):
        Base.metadata.create_all(engine)
        self.session = Session(bind=engine)
        self.transaction = self.session.begin_nested()

    def tearDown(self):
        self.transaction.rollback()  # Wycofanie transakcji
        self.session.close()

    def test_create_payment(self):
        new_user = User(name="TestUser", surname="TestSurname", email="user@example.com",
                        password=generate_password_hash("password"), role="czytelnik", wants_notifications=True)
        self.session.add(new_user)
        self.session.flush()  # Zapisanie zmian bez zatwierdzania

        new_book_copy = BookCopy(book_id=4, status='dostępna')
        self.session.add(new_book_copy)
        self.session.flush()  # Zapisanie zmian bez zatwierdzania

        new_payment = Payment(user_id=new_user.id, book_copy_id=new_book_copy.id,
                              amount=Decimal("9.99"), status='opłacona')
        self.session.add(new_payment)
        self.session.flush()  # Zapisanie zmian bez zatwierdzania

        payment = self.session.query(Payment).filter_by(user_id=new_user.id).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.amount, Decimal("9.99"))
        self.assertEqual(payment.status, "opłacona")

if __name__ == '__main__':
    unittest.main()


#python -m unittest tests/test_payment_model.py
#python -m unittest discover -s tests