import unittest
from app.models import User, Book, Recommendation
from database_setup import Base, engine, check_connection
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash
from datetime import datetime

class TestRecommendationModel(unittest.TestCase):
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

    def test_create_recommendation(self):
        # Utworzenie użytkownika
        new_user = User(name="TestUser", surname="TestSurname", email="user@example.com",
                        password=generate_password_hash("password"), role="czytelnik", wants_notifications=True)
        self.session.add(new_user)
        self.session.flush()

        # Utworzenie książki
        new_book = Book(ISBN="1234567890", title="Example Book", author="Author", genre="Fiction", publication_year=2021)
        self.session.add(new_book)
        self.session.flush()

        # Utworzenie rekomendacji
        new_recommendation = Recommendation(user_id=new_user.id, book_id=new_book.id,
                                            date_of_recommendation=datetime.now(), reason="Great read")
        self.session.add(new_recommendation)
        self.session.flush()

        # Pobieranie rekomendacji z bazy danych
        recommendation = self.session.query(Recommendation).filter_by(user_id=new_user.id, book_id=new_book.id).first()
        self.assertIsNotNone(recommendation)
        self.assertEqual(recommendation.reason, "Great read")
        self.assertEqual(recommendation.user, new_user)
        self.assertEqual(recommendation.book, new_book)

if __name__ == '__main__':
    unittest.main()


#python -m unittest tests/test_recommendation_model.py
#python -m unittest discover -s tests