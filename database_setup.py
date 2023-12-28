from sqlalchemy import create_engine, ForeignKey, Numeric, text
from sqlalchemy import Column, Integer, String, DateTime, Enum, Text, Boolean
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from werkzeug.security import generate_password_hash, check_password_hash

Base = declarative_base()

# Uwaga: Zastąp 'username', 'password', 'host' i 'database_name' właściwymi wartościami
DATABASE_URI = 'mysql+pymysql://root:Maria@localhost:80/library'
engine = create_engine(DATABASE_URI, echo=True)

class Reminder(Base):
    __tablename__ = 'reminders'

    id = Column('reminder_id', Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    book_id = Column(Integer, ForeignKey('book_copies.id'), nullable=False)
    date_of_sending = Column(DateTime, default=func.current_timestamp(), nullable=False)
    type = Column(Enum('odbiór', 'zapłata', 'zwrot'), nullable=False)

    # Zmienione relacje - używamy innej nazwy dla backref
    user = relationship("User", backref="user_reminders")
    book_copy = relationship("BookCopy", backref="copy_reminders")



class User(Base):
    __tablename__ = 'users'

    id = Column('user_id', Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    surname = Column(String(50), nullable=False)
    email = Column(String(100), nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(Enum('czytelnik', 'pracownik'), default='czytelnik', nullable=False)
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


class BookCopy(Base):
    __tablename__ = 'book_copies'

    id = Column(Integer, primary_key=True, autoincrement=True)
    book_id = Column(Integer, ForeignKey('books.book_id'), nullable=False)
    status = Column(Enum('dostępna', 'wypożyczona', 'zarezerwowana', 'do odbioru'), nullable=False)

    # Relacja z Book
    book = relationship("Book", back_populates="book_copies")
    reminders = relationship("Reminder", order_by=Reminder.id, back_populates="book_copy")


class Book(Base):
    __tablename__ = 'books'

    id = Column('book_id', Integer, primary_key=True, autoincrement=True)
    ISBN = Column(String(20), nullable=False)
    title = Column(String(200), nullable=False)
    author = Column(String(100), nullable=False)
    genre = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)  # TEXT może być NULL, jeśli opis książki nie jest wymagany
    publication_year = Column(Integer, nullable=False)
    quantity = Column(Integer, default=1)

    # Nowa relacja do BookCopy
    book_copies = relationship("BookCopy", order_by=BookCopy.id, back_populates="book")


class Loan(Base):
    __tablename__ = 'loans'

    id = Column('loan_id', Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    book_id = Column(Integer, ForeignKey('book_copies.id'), nullable=False)
    date_of_loan = Column(DateTime, default=func.current_timestamp(), nullable=False)
    due_date = Column(DateTime, nullable=False)
    return_date = Column(DateTime, nullable=True)  # Może być NULL, oznacza to, że książka nie została jeszcze zwrócona
    status = Column(Enum('w trakcie', 'zakończone', 'książka przetrzymana'), nullable=False)

    # Relacje (opcjonalnie, jeśli chcesz mieć dostęp do powiązanych obiektów użytkowników i książek)
    user = relationship("User", back_populates="loans")
    book_copy = relationship("BookCopy", back_populates="loans")  # Zaktualizowana relacja

# Następnie dodaj relacje do klas User i Book (jeśli potrzebujesz nawigować między nimi)
User.loans = relationship("Loan", order_by=Loan.id, back_populates="user")
BookCopy.loans = relationship("Loan", order_by=Loan.id, back_populates="book_copy")

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

# Dodaj relacje do istniejących klas User i Book
User.reservations = relationship("Reservation", order_by=Reservation.id, back_populates="user")
BookCopy.reservations = relationship("Reservation", order_by=Reservation.id, back_populates="book_copy")


class Payment(Base):
    __tablename__ = 'payments'

    id = Column('payment_id', Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)  # Typ DECIMAL reprezentowany przez Numeric
    date_of_payment = Column(DateTime, default=func.current_timestamp(), nullable=False)
    status = Column(Enum('opłacona', 'oczekująca', 'anulowana'), nullable=False)

    # Relacja z użytkownikiem
    user = relationship("User", back_populates="payments")

# Dodaj relację do klasy User
User.payments = relationship("Payment", order_by=Payment.id, back_populates="user")

class Notification(Base):
    __tablename__ = 'notifications'

    id = Column('notification_id', Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    content = Column(Text, nullable=False)  # Typ TEXT do przechowywania dłuższych treści
    date_of_sending = Column(DateTime, default=func.current_timestamp(), nullable=False)

    # Relacja z użytkownikiem
    user = relationship("User", back_populates="notifications")

# Dodaj relację do klasy User
User.notifications = relationship("Notification", order_by=Notification.id, back_populates="user")


class Review(Base):
    __tablename__ = 'reviews'

    id = Column('review_id', Integer, primary_key=True, autoincrement=True)
    book_id = Column(Integer, ForeignKey('books.book_id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    text = Column(Text, nullable=False)  # Typ TEXT do przechowywania treści recenzji
    rating = Column(Integer, nullable=False)  # Ocena jako liczba całkowita
    date = Column(DateTime, default=func.current_timestamp(), nullable=False)

    # Relacje
    user = relationship("User", back_populates="reviews")
    book = relationship("Book", back_populates="reviews")

# Dodaj relacje do istniejących klas User i Book
User.reviews = relationship("Review", order_by=Review.id, back_populates="user")
Book.reviews = relationship("Review", order_by=Review.id, back_populates="book")


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

# Dodaj relacje do istniejących klas User i Book
User.recommendations = relationship("Recommendation", order_by=Recommendation.id, back_populates="user")
Book.recommendations = relationship("Recommendation", order_by=Recommendation.id, back_populates="book")


class Report(Base):
    __tablename__ = 'reports'

    id = Column('report_id', Integer, primary_key=True, autoincrement=True)
    title = Column(String(100), nullable=False)
    date_of_generation = Column(DateTime, default=func.current_timestamp(), nullable=False)
    type = Column(Enum('wypożyczenia', 'rezerwacje', 'użytkownicy'), nullable=False)
    content = Column(Text, nullable=True)  # Typ TEXT do przechowywania treści raportu, może być NULL

# Klasa Report nie potrzebuje bezpośrednich relacji z innymi klasami

class CartItem(Base):
    __tablename__ = 'cart_items'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    book_copy_id = Column(Integer, ForeignKey('book_copies.id'), nullable=False)
    added_at = Column(DateTime, default=func.current_timestamp(), nullable=False)

    user = relationship("User", backref="cart_items")
    book_copy = relationship("BookCopy", backref="cart_items")


# Sprawdzenie połączenia wykonując zapytanie SELECT
with Session(engine) as session:
    result = session.execute(text("SELECT 1"))
    print(result.one())