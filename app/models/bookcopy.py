from database_setup import Base
from sqlalchemy import create_engine, ForeignKey
from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.orm import relationship, Session

from .reminder import Reminder


class BookCopy(Base):
    __tablename__ = 'book_copies'

    id = Column(Integer, primary_key=True, autoincrement=True)
    book_id = Column(Integer, ForeignKey('books.book_id'), nullable=False)
    status = Column(Enum('dostępna', 'wypożyczona', 'zarezerwowana', 'do odbioru'), nullable=False)

    # Relacja z Book
    book = relationship("Book", back_populates="book_copies")
    reminders = relationship("Reminder", order_by=Reminder.id, back_populates="book_copy")