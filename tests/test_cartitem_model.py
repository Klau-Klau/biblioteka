import unittest
from datetime import datetime
from app.models import User, BookCopy, CartItem, Book
from database_setup import Base, engine, check_connection
from sqlalchemy.orm import Session

class TestCartItemModel(unittest.TestCase):
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

    def test_create_cart_item(self):
        # Tworzenie użytkownika
        new_user = User(name="Test", surname="User", email="testuser@example.com", password="testpassword",
                        role='czytelnik', wants_notifications=True)
        self.session.add(new_user)
        self.session.flush()

        # Utworzenie książki
        new_book = Book(ISBN="1234567890", title="Test Book", author="Author", genre="Fiction", publication_year=2021,
                        quantity=1)
        self.session.add(new_book)
        self.session.flush()

        # Tworzenie kopii książki
        new_book_copy = BookCopy(book_id=new_book.id, status='dostępna')
        self.session.add(new_book_copy)
        self.session.flush()

        # Tworzenie instancji CartItem
        new_cart_item = CartItem(user_id=new_user.id, book_copy_id=new_book_copy.id)
        self.session.add(new_cart_item)
        self.session.flush()

        # Pobieranie CartItem z bazy danych
        cart_item = self.session.query(CartItem).filter_by(user_id=new_user.id).first()
        self.assertIsNotNone(cart_item)
        self.assertEqual(cart_item.book_copy_id, new_book_copy.id)
        self.assertTrue(isinstance(cart_item.added_at, datetime))


if __name__ == '__main__':
    unittest.main()

#python -m unittest tests/test_cartitem_model.py
#python -m unittest discover -s tests
