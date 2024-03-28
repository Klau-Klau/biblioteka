import unittest
from app.models import User, Book, BookCopy, Loan
from database_setup import Base, engine, Session, check_connection
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

class TestLoanModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not check_connection(engine):
            raise Exception("Failed to connect to the database.")

    def setUp(self):
        Base.metadata.create_all(engine)
        self.session = Session(bind=engine)
        self.transaction = self.session.begin_nested()

    def tearDown(self):
        self.transaction.rollback()
        self.session.close()

    def test_create_loan(self):
        # Create a user instance
        new_user = User(name="Test", surname="User", email="testuser@example.com",
                        password=generate_password_hash("testpassword"), role='czytelnik',
                        wants_notifications=True)
        self.session.add(new_user)
        self.session.flush()

        new_book = Book(ISBN="1234567890", title="Test Book", author="Author",
                        genre="Fiction", publication_year=2021)
        self.session.add(new_book)
        self.session.flush()


        new_book_copy = BookCopy(book_id=new_book.id, status='dostępna')
        self.session.add(new_book_copy)
        self.session.flush()


        loan_date = datetime.now().replace(microsecond=0)
        due_date = loan_date + timedelta(days=14)
        new_loan = Loan(user_id=new_user.id, book_id=new_book_copy.id, date_of_loan=loan_date,
                        due_date=due_date, status='w trakcie')
        self.session.add(new_loan)
        self.session.flush()

        loan = self.session.query(Loan).filter_by(user_id=new_user.id).first()
        self.assertIsNotNone(loan)
        self.assertEqual(loan.book_id, new_book_copy.id)
        self.assertEqual(loan.status, 'w trakcie')
        self.assertEqual(loan.due_date.replace(microsecond=0), due_date)

if __name__ == '__main__':
    unittest.main()

#python -m unittest tests/test_loan_model.py
#python -m unittest discover -s tests