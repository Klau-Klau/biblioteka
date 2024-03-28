import unittest
from app.models import Media
from database_setup import Base, engine, check_connection
from sqlalchemy.orm import Session

class TestMediaModel(unittest.TestCase):
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

    def test_create_media(self):
        new_media = Media(media_type="ebook", file_url="http://example.com/ebook.pdf",
                          title="Test Media", author="Author", publish_year=2021,
                          genre="Fiction", description="Test Description", cover_image_url=None)
        self.session.add(new_media)
        self.session.flush()

        media = self.session.query(Media).filter_by(title="Test Media").first()
        self.assertIsNotNone(media)
        self.assertEqual(media.author, "Author")
        self.assertEqual(media.media_type, "ebook")

if __name__ == '__main__':
    unittest.main()


#python -m unittest tests/test_media_model.py
#python -m unittest discover -s tests