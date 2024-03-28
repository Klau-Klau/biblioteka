from database_setup import Base
from sqlalchemy import ForeignKey
from sqlalchemy import Column, Integer, DateTime, Enum, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .user import User
from .book import Book


class Review(Base):
    __tablename__ = 'reviews'

    id = Column('review_id', Integer, primary_key=True, autoincrement=True)
    book_id = Column(Integer, ForeignKey('books.book_id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    text = Column(Text, nullable=False)  # Typ TEXT do przechowywania treści recenzji
    rating = Column(Integer, nullable=False)  # Ocena jako liczba całkowita
    date = Column(DateTime, default=func.current_timestamp(), nullable=False)
    status = Column(Enum('oczekująca', 'zatwierdzona', 'odrzucona'), default='oczekująca', nullable=False)

    # Relacje
    user = relationship("User", back_populates="reviews")
    book = relationship("Book", back_populates="reviews")


User.reviews = relationship("Review", order_by=Review.id, back_populates="user")
Book.reviews = relationship("Review", order_by=Review.id, back_populates="book")