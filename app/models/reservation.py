from database_setup import Base
from sqlalchemy import ForeignKey
from sqlalchemy import Column, Integer, DateTime, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .user import User
from .bookcopy import BookCopy


class Reservation(Base):
    __tablename__ = 'reservations'

    id = Column('reservation_id', Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    book_id = Column(Integer, ForeignKey('book_copies.id'), nullable=False)
    date_of_reservation = Column(DateTime, default=func.current_timestamp(), nullable=False)
    status = Column(Enum('aktywna', 'zakończona', 'anulowana'), nullable=False)

    # Relacje
    user = relationship("User", back_populates="reservations")
    book_copy = relationship("BookCopy", back_populates="reservations")  # Zaktualizowana relacja


User.reservations = relationship("Reservation", order_by=Reservation.id, back_populates="user")
BookCopy.reservations = relationship("Reservation", order_by=Reservation.id, back_populates="book_copy")
