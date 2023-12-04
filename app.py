from flask import Flask, redirect, url_for, render_template, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
import os
from database_setup import User, engine, Book, Reservation, Loan
from sqlalchemy.orm import scoped_session, sessionmaker
from app.forms import LoginForm, RegistrationForm


template_dir = os.path.abspath('./app/templates')
app = Flask(__name__, template_folder=template_dir)

app.secret_key = 'tajny_klucz'  # Ustaw tajny klucz

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

db_session = scoped_session(sessionmaker(bind=engine))

@login_manager.user_loader
def load_user(user_id):
    return db_session.query(User).get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = db_session.query(User).filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Nieprawidłowy email lub hasło.', 'danger')  # Dodany komunikat
    return render_template('login.html', form=form)



db_session = scoped_session(sessionmaker(bind=engine))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))  # Przekieruj zalogowanych użytkowników

    form = RegistrationForm()
    if form.validate_on_submit():
        # Sprawdzanie, czy użytkownik z takim emailem już istnieje
        existing_user = db_session.query(User).filter_by(email=form.email.data).first()
        if existing_user is None:
            hashed_password = generate_password_hash(form.password.data, method='sha256')
            new_user = User(
                name=form.name.data,
                surname=form.surname.data,
                email=form.email.data,
                password=hashed_password,
                role='czytelnik'  # Zakładając, że każdy nowy użytkownik ma rolę 'czytelnik'
            )
            db_session.add(new_user)
            db_session.commit()
            flash('Konto zostało pomyślnie utworzone.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Email już istnieje.', 'danger')

    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Zostałeś wylogowany.', 'success')
    return redirect(url_for('login'))


@app.route('/search_books', methods=['GET'])
def search_books():
    # Pobranie parametrów zapytania
    title = request.args.get('title')
    author = request.args.get('author')
    isbn = request.args.get('isbn')

    # Stworzenie zapytania do bazy danych na podstawie dostarczonych parametrów
    query = db_session.query(Book)
    if title:
        query = query.filter(Book.title.like(f"%{title}%"))
    if author:
        query = query.filter(Book.author.like(f"%{author}%"))
    if isbn:
        query = query.filter(Book.ISBN == isbn)

    books = query.all()  # Pobranie wyników zapytania

    # Przygotowanie odpowiedzi JSON z listą książek
    books_data = [{"title": book.title, "author": book.author, "isbn": book.ISBN} for book in books]
    return jsonify(books_data)

@app.route('/reserve_book', methods=['POST'])
@login_required
def reserve_book():
    book_id = request.form.get('book_id')

    # Pobranie książki z bazy danych
    book = db_session.query(Book).filter_by(id=book_id).first()

    if not book:
        return jsonify({'message': 'Książka nie znaleziona'}), 404

    if book.status not in ['dostępna']:
        return jsonify({'message': 'Ksiazka jest juz zarezerwowana lub wypozyczona'}), 400

    # Zmiana statusu książki
    book.status = 'zarezerwowana'

    # Utworzenie rezerwacji
    reservation = Reservation(
        user_id=current_user.id,
        book_id=book_id,
        status='aktywna'
    )
    db_session.add(reservation)

    # Zapisanie zmian
    db_session.commit()

    return jsonify({'message': 'Rezerwacja zostala pomyslnie utworzona'}), 200


@app.route('/reserve', methods=['GET'])
@login_required
def show_reserve_form():
    if current_user.role == 'czytelnik':
        return render_template('reserve_book.html')
    else:
        flash('Tylko czytelnicy mogą rezerwować książki.', 'warning')
        return redirect(url_for('index'))

@app.route('/mark_as_loan', methods=['GET', 'POST'])
@login_required
def loan_book():
    if current_user.role != 'pracownik':
        flash('Tylko pracownicy mogą wypożyczać książki.', 'warning')
        return redirect(url_for('index'))

    if request.method == 'POST':
        book_id = request.form.get('book_id')
        book = db_session.query(Book).filter_by(id=book_id).first()
        reservation = db_session.query(Reservation).filter_by(book_id=book_id, status='aktywna').first()

        if not book or book.status != 'zarezerwowana':
            flash('Nie można wypożyczyć tej książki.', 'danger')
            return redirect(url_for('loan_book'))

        # Aktualizacja statusu książki i rezerwacji
        book.status = 'wypożyczona'
        if reservation:
            reservation.status = 'zakończona'

        # Dodanie wpisu do tabeli loans
        new_loan = Loan(user_id=reservation.user_id if reservation else None, book_id=book_id, status='w trakcie')
        db_session.add(new_loan)

        db_session.commit()
        flash('Książka została wypożyczona.', 'success')
        return redirect(url_for('index'))

    return render_template('mark_as_loan.html')


@app.route('/my_books')
@login_required
def my_books():

    if current_user.role != 'czytelnik':
        return redirect(url_for('index'))

    user_id = current_user.id
    reserved_books = db_session.query(Book).join(Reservation).filter(Reservation.user_id == user_id, Reservation.status == 'aktywna').all()
    loaned_books = db_session.query(Book).join(Loan).filter(Loan.user_id == user_id, Loan.status == 'w trakcie').all()

    return render_template('my_books.html', reserved_books=reserved_books, loaned_books=loaned_books)


# To powinno być na samym końcu pliku
if __name__ == '__main__':
    app.run(debug=True)
