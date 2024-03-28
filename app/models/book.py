from database_setup import Base
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship
from .bookcopy import BookCopy


class Book(Base):
    __tablename__ = 'books'

    id = Column('book_id', Integer, primary_key=True, autoincrement=True)
    ISBN = Column(String(20), nullable=False)
    title = Column(String(200), nullable=False)
    author = Column(String(100), nullable=False)
    genre = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)  # TEXT może być NULL, jeśli opis książki nie jest wymagany
    publication_year = Column(Integer, nullable=False)
    quantity = Column(Integer, default=1)
    cover_image_url = Column(String(500), nullable=True)

    book_copies = relationship("BookCopy", order_by=BookCopy.id, back_populates="book")