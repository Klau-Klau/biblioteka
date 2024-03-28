import unittest
from app.models import Book
from database_setup import Base, engine, check_connection
from sqlalchemy.orm import Session

class TestBookModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Sprawdzenie połączenia przed uruchomieniem testów
        if not check_connection(engine):
            raise Exception("Nie udało się połączyć z bazą danych.")

    def setUp(self):
        # Ustawienie połączenia z bazą danych i tworzenie tabeli
        Base.metadata.create_all(engine)
        self.session = Session(bind=engine)
        self.session.begin()  # Rozpoczyna transakcję

    def tearDown(self):
        # Cofanie transakcji po zakończeniu testu, nie usuwając tabel
        self.session.rollback()  # Wycofuje transakcję
        self.session.close()

    def test_create_book(self):
        # Tworzenie instancji książki
        new_book = Book(ISBN="1234567890", title="Test Book", author="Author", genre="Fantasy", publication_year=2021)
        self.session.add(new_book)

        # Pobieranie książki z bazy danych
        book = self.session.query(Book).filter_by(ISBN="1234567890").first()
        self.assertIsNotNone(book)
        self.assertEqual(book.title, "Test Book")

if __name__ == '__main__':
    unittest.main()


#python -m unittest tests/test_book_model.py
#python -m unittest discover -s tests