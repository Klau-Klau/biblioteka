import unittest
from datetime import datetime
from app.models import User, Book, Review
from database_setup import Base, engine, check_connection
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

class TestReviewModel(unittest.TestCase):
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

    def test_create_review(self):
        new_user = User(name="ReviewUser", surname="Reviewer", email="reviewer@example.com",
                        password=generate_password_hash("password"), role='czytelnik',
                        wants_notifications=True)
        self.session.add(new_user)
        self.session.flush()

        new_book = Book(ISBN="9999999999", title="Review Book", author="Author",
                        genre="Non-fiction", publication_year=2020)
        self.session.add(new_book)
        self.session.flush()

        new_review = Review(book_id=new_book.id, user_id=new_user.id, text="Great book!",
                            rating=5, status='oczekująca')
        self.session.add(new_review)
        self.session.flush()

        review = self.session.query(Review).filter_by(user_id=new_user.id, book_id=new_book.id).first()
        self.assertIsNotNone(review)
        self.assertEqual(review.text, "Great book!")
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.status, 'oczekująca')
        self.assertTrue(isinstance(review.date, datetime))

if __name__ == '__main__':
    unittest.main()


#python -m unittest tests/test_review_model.py
#python -m unittest discover -s tests