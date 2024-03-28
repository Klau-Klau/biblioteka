from database_setup import Base
from sqlalchemy import ForeignKey
from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship


class CartItem(Base):
    __tablename__ = 'cart_items'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    book_copy_id = Column(Integer, ForeignKey('book_copies.id'), nullable=False)
    added_at = Column(DateTime, default=func.current_timestamp(), nullable=False)

    user = relationship("User", backref="cart_items")
    book_copy = relationship("BookCopy", backref="cart_items")