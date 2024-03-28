from database_setup import Base
from sqlalchemy import ForeignKey
from sqlalchemy import Column, Integer, DateTime, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship


class Reminder(Base):
    __tablename__ = 'reminders'

    id = Column('reminder_id', Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    book_id = Column(Integer, ForeignKey('book_copies.id'), nullable=False)
    date_of_sending = Column(DateTime, default=func.current_timestamp(), nullable=False)
    type = Column(Enum('odbiór', 'zapłata', 'zwrot'), nullable=False)


    user = relationship("User", backref="user_reminders")
    book_copy = relationship("BookCopy", backref="copy_reminders")