from flask import Flask, redirect, url_for, render_template, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
import os
from database_setup import User, engine, Book, Reservation, Loan
from sqlalchemy.orm import scoped_session, sessionmaker
from app.forms import LoginForm, RegistrationForm, EditUserForm, EditPasswordForm, EditUserEmployee, EditUserFormByStaff
from datetime import datetime, timedelta
from sqlalchemy import or_


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

        # Ustawienie terminu zwrotu na 3 miesiące do przodu
        due_date = datetime.now() + timedelta(days=90)

        # Dodanie wpisu do tabeli loans
        new_loan = Loan(
            user_id=reservation.user_id if reservation else None,
            book_id=book_id,
            status='w trakcie',
            due_date=due_date
        )
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


@app.route('/add_book', methods=['GET', 'POST'])
@login_required
def add_book():
    if current_user.role != 'pracownik':
        flash('Tylko pracownicy mogą dodać książki.', 'warning')
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Pobierz dane z formularza
        isbn = request.form.get('isbn')
        title = request.form.get('title')
        author = request.form.get('author')
        genre = request.form.get('genre')
        description = request.form.get('description')
        publication_year = request.form.get('publication_year')

        # Stwórz nowy obiekt Book
        new_book = Book(
            ISBN=isbn,
            title=title,
            author=author,
            genre=genre,
            description=description,
            publication_year=publication_year,
            status='dostępna'  # Domyślny status dla nowo dodanej książki
        )

        # Dodaj książkę do sesji i zapisz zmiany w bazie danych
        db_session.add(new_book)
        db_session.commit()
        flash('Książka została pomyślnie dodana.', 'success')
        return redirect(url_for('index'))

    # GET - wyświetl formularz dodawania książki
    return render_template('add_book.html')


@app.route('/edit_book/<int:book_id>', methods=['GET', 'POST'])
@login_required
def edit_book(book_id):
    # Ograniczenie dostępu tylko dla pracowników
    if current_user.role != 'pracownik':
        flash('Tylko pracownicy mogą edytować książki.', 'warning')
        return redirect(url_for('index'))

    book = db_session.query(Book).get(book_id)
    if book is None:
        flash('Książka nie została znaleziona.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Aktualizacja danych książki z formularza
        book.ISBN = request.form.get('isbn')
        book.title = request.form.get('title')
        book.author = request.form.get('author')
        book.genre = request.form.get('genre')
        book.description = request.form.get('description')
        book.publication_year = request.form.get('publication_year')

        db_session.commit()
        flash('Książka została zaktualizowana.', 'success')
        return redirect(url_for('my_books'))

    # GET - wyświetlenie danych książki w formularzu
    return render_template('edit_book.html', book=book)


@app.route('/delete_book/<int:book_id>', methods=['POST'])
@login_required
def delete_book(book_id):
    if current_user.role != 'pracownik':
        flash('Tylko pracownicy mogą usuwać książki.', 'warning')
        return redirect(url_for('index'))

    book = db_session.query(Book).get(book_id)
    if book is None:
        flash('Książka nie została znaleziona.', 'danger')
        return redirect(url_for('index'))

    if book.status != 'dostępna':
        flash('Tylko książki o statusie "dostępna" mogą być usunięte.', 'danger')
        return redirect(url_for('index'))

    db_session.delete(book)
    db_session.commit()
    flash('Książka została usunięta.', 'success')
    return redirect(url_for('index'))


@app.route('/manage_book')
@login_required
def manage_books():
    if current_user.role != 'pracownik':
        flash('Brak dostępu.', 'warning')
        return redirect(url_for('index'))

    books = db_session.query(Book).all()
    return render_template('manage_book.html', books=books)


@app.route('/return_book/<int:book_id>', methods=['POST'])
@login_required
def return_book(book_id):
    if current_user.role != 'pracownik':
        flash('Tylko pracownicy mogą zarządzać zwrotami książek.', 'warning')
        return redirect(url_for('manage_books'))

    book = db_session.query(Book).get(book_id)
    if not book:
        flash('Książka nie została znaleziona.', 'danger')
        return redirect(url_for('manage_books'))

    loan = db_session.query(Loan).filter(
        Loan.book_id == book.id,
        or_(Loan.status == 'w trakcie', Loan.status == 'książka przetrzymana')
    ).first()
    if loan:
        loan.status = 'zakończone'
        loan.return_date = datetime.utcnow()
        book.status = 'dostępna'
        db_session.commit()
        flash(f'Książka "{book.title}" została zwrócona i jest teraz dostępna.', 'success')
    else:
        flash(f'Brak aktywnego wypożyczenia dla książki "{book.title}".', 'warning')

    return redirect(url_for('manage_books'))


@app.route('/user_profile/<int:user_id>', methods=['GET'])
@login_required
def user_profile(user_id):
    # Jeśli zalogowany użytkownik jest czytelnikiem i próbuje zobaczyć profil innego użytkownika
    if current_user.role == 'czytelnik' and current_user.id != user_id:
        flash('Nie masz uprawnień do wyświetlenia tego profilu.', 'danger')
        return redirect(url_for('index'))

    # Pobranie danych użytkownika z bazy danych
    user = db_session.query(User).get(user_id)

    if user is None:
        flash('Użytkownik nie został znaleziony.', 'danger')
        return redirect(url_for('index'))

    # Przekazujemy tylko bezpieczne dane, bez hasła
    user_data = {
        'name': user.name,
        'surname': user.surname,
        'email': user.email,
        'role': user.role
    }

    return render_template('user_profile.html', user=user_data)


@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    user = db_session.query(User).get(user_id)
    if user is None:
        flash('Użytkownik nie został znaleziony.', 'danger')
        return redirect(url_for('index'))

    is_editing_self = current_user.id == user_id
    is_staff = current_user.role == 'pracownik'
    is_target_user_staff = user.role == 'pracownik'

    # Pracownik edytuje siebie
    if is_staff and is_editing_self:
        form = EditUserEmployee(obj=user)  # Formularz bez pola e-mail
    # Pracownik edytuje innego pracownika
    elif is_staff and is_target_user_staff:
        flash('Nie masz uprawnień do edycji tego użytkownika.', 'danger')
        return redirect(url_for('index'))
    # Pracownik edytuje innego użytkownika
    elif is_staff and not is_editing_self:
        form = EditUserFormByStaff(obj=user)
    # Czytelnik edytuje siebie
    elif not is_staff and is_editing_self:
        form = EditUserForm(obj=user)
    else:
        flash('Nie masz uprawnień do edycji tego użytkownika.', 'danger')
        return redirect(url_for('index'))

    if form.validate_on_submit():
        user.name = form.name.data
        user.surname = form.surname.data

        # Zmiana e-maila tylko dla czytelnika edytującego swoje dane
        if not is_staff:
            user.email = form.email.data

        if is_editing_self and form.change_password.data:
            user.password = generate_password_hash(form.password.data)

        db_session.commit()
        flash('Dane użytkownika zostały zaktualizowane.', 'success')
        return redirect(url_for('edit_user', user_id=user_id))

    # Przekazanie dodatkowej zmiennej do szablonu, aby kontrolować wyświetlanie pola e-mail
    return render_template('edit_user.html', form=form, user_id=user_id, is_editing_self=is_editing_self, is_staff=is_staff, is_target_user_staff=is_target_user_staff)




# To powinno być na samym końcu pliku
if __name__ == '__main__':
    app.run(debug=True)