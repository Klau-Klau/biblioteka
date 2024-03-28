import unittest
from app.models import Book, BookCopy
from database_setup import Base, engine, check_connection
from sqlalchemy.orm import Session

class TestBookCopyModel(unittest.TestCase):
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

    def test_create_book_copy(self):
        book = Book(ISBN="1234567890", title="Test Book", author="Author", genre="Fiction", publication_year=2021)
        self.session.add(book)
        self.session.flush()

        # Tworzenie egzemplarza książki
        new_book_copy = BookCopy(book_id=book.id, status='dostępna')
        self.session.add(new_book_copy)
        self.session.flush()

        book_copy = self.session.query(BookCopy).filter_by(book_id=book.id).first()
        self.assertIsNotNone(book_copy)
        self.assertEqual(book_copy.status, 'dostępna')

if __name__ == '__main__':
    unittest.main()

#python -m unittest tests/test_bookcopy_model.py
#python -m unittest discover -s tests
