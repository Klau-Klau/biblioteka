from database_setup import Base
from sqlalchemy import ForeignKey
from sqlalchemy import Column, Integer, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .user import User
from .book import Book


class Recommendation(Base):
    __tablename__ = 'recommendations'

    id = Column('recommendation_id', Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    book_id = Column(Integer, ForeignKey('books.book_id'), nullable=False)
    date_of_recommendation = Column(DateTime, default=func.current_timestamp(), nullable=False)
    reason = Column(Text, nullable=True)  # Typ TEXT do przechowywania powodu rekomendacji, może być NULL

    # Relacje
    user = relationship("User", back_populates="recommendations")
    book = relationship("Book", back_populates="recommendations")


User.recommendations = relationship("Recommendation", order_by=Recommendation.id, back_populates="user")
Book.recommendations = relationship("Recommendation", order_by=Recommendation.id, back_populates="book")

