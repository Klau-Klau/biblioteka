from database_setup import Base
from sqlalchemy import Column, Integer, String, DateTime, Enum, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from .reminder import Reminder

class User(Base):
    __tablename__ = 'users'

    id = Column('user_id', Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    surname = Column(String(50), nullable=False)
    email = Column(String(100), nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(Enum('czytelnik', 'pracownik', 'administrator'), default='czytelnik', nullable=False)
    registration_date = Column(DateTime, default=func.current_timestamp(), nullable=False)
    wants_notifications = Column(Boolean, default=True, nullable=False)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    # Metody Flask-Login
    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    reminders = relationship("Reminder", order_by=Reminder.id, back_populates="user")