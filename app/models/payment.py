from database_setup import Base
from sqlalchemy import ForeignKey, Numeric
from sqlalchemy import Column, Integer, DateTime, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .user import User


class Payment(Base):
    __tablename__ = 'payments'

    id = Column('payment_id', Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    book_copy_id = Column(Integer, ForeignKey('book_copies.id'), nullable=False)  # Dodane
    amount = Column(Numeric(10, 2), nullable=False)  # Typ DECIMAL reprezentowany przez Numeric
    date_of_payment = Column(DateTime, default=func.current_timestamp(), nullable=False)
    status = Column(Enum('opłacona', 'oczekująca', 'anulowana'), nullable=False)

    # Relacja z użytkownikiem
    user = relationship("User", back_populates="payments")
    book_copy = relationship("BookCopy")  # Dodane


User.payments = relationship("Payment", order_by=Payment.id, back_populates="user")