import unittest
from app.models import User, Book, BookCopy, Reminder
from database_setup import Base, engine, check_connection
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

class TestReminderModel(unittest.TestCase):
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

    def test_create_reminder(self):
        # Utworzenie użytkownika
        new_user = User(name="TestUser", surname="TestSurname", email="user@example.com", password="testpassword")
        self.session.add(new_user)
        self.session.flush()

        # Utworzenie książki
        new_book = Book(ISBN="1234567890", title="Example Book", author="Author", genre="Fiction", publication_year=2021)
        self.session.add(new_book)
        self.session.flush()

        # Utworzenie kopii książki
        new_book_copy = BookCopy(book_id=new_book.id, status='dostępna')
        self.session.add(new_book_copy)
        self.session.flush()

        # Utworzenie przypomnienia
        reminder_date = datetime.now() + timedelta(days=1)  # Ustawienie daty przypomnienia na jutro
        new_reminder = Reminder(user_id=new_user.id, book_id=new_book_copy.id, date_of_sending=reminder_date, type='odbiór')
        self.session.add(new_reminder)
        self.session.flush()

        # Pobieranie przypomnienia z bazy danych
        reminder = self.session.query(Reminder).filter_by(user_id=new_user.id, book_id=new_book_copy.id).first()
        self.assertIsNotNone(reminder)
        self.assertEqual(reminder.type, 'odbiór')
        self.assertEqual(reminder.user, new_user)
        self.assertEqual(reminder.book_copy, new_book_copy)
        self.assertTrue(reminder.date_of_sending > datetime.now())

if __name__ == '__main__':
    unittest.main()


#python -m unittest tests/test_reminder_model.py
#python -m unittest discover -s tests