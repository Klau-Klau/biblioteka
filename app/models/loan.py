from database_setup import Base
from sqlalchemy import ForeignKey
from sqlalchemy import Column, Integer, DateTime, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .user import User
from .bookcopy import BookCopy

class Loan(Base):
    __tablename__ = 'loans'

    id = Column('loan_id', Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    book_id = Column(Integer, ForeignKey('book_copies.id'), nullable=False)
    date_of_loan = Column(DateTime, default=func.current_timestamp(), nullable=False)
    due_date = Column(DateTime, nullable=False)
    return_date = Column(DateTime, nullable=True)  # Może być NULL, oznacza to, że książka nie została jeszcze zwrócona
    status = Column(Enum('w trakcie', 'zakończone', 'książka przetrzymana'), nullable=False)

    # Relacje
    user = relationship("User", back_populates="loans")
    book_copy = relationship("BookCopy", back_populates="loans")  # Zaktualizowana relacja

User.loans = relationship("Loan", order_by=Loan.id, back_populates="user")
BookCopy.loans = relationship("Loan", order_by=Loan.id, back_populates="book_copy")