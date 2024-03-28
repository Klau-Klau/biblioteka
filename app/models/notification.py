from database_setup import Base
from sqlalchemy import ForeignKey
from sqlalchemy import Column, Integer, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .user import User


class Notification(Base):
    __tablename__ = 'notifications'

    id = Column('notification_id', Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    content = Column(Text, nullable=False)  # Typ TEXT do przechowywania dłuższych treści
    date_of_sending = Column(DateTime, default=func.current_timestamp(), nullable=False)

    # Relacja z użytkownikiem
    user = relationship("User", back_populates="notifications")


User.notifications = relationship("Notification", order_by=Notification.id, back_populates="user")
