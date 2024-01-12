from flask import Flask, redirect, url_for, render_template, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
import os
from database_setup import User, engine, Book, Reservation, Loan, BookCopy, Notification, Reminder, Review, CartItem, \
    Recommendation
from sqlalchemy.orm import scoped_session, sessionmaker, joinedload
from app.forms import LoginForm, RegistrationForm, EditUserForm, EditUserEmployee, EditUserFormByStaff, \
    SendNotificationForm
from datetime import datetime, timedelta
from sqlalchemy import func, or_


template_dir = os.path.abspath('./app/templates')
app = Flask(__name__, template_folder=template_dir)
app.secret_key = 'tajny_klucz'

# Ustawienia Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Ustawienia bazy danych
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
    search_query = request.args.get('search')
    genre = request.args.get('genre')
    year_range = request.args.get('year')
    availability = request.args.get('availability')
    rating = request.args.get('rating')
    sort = request.args.get('sort', 'newest')

    # Zbudowanie zapytania SQL z uwzględnieniem filtrów
    query = db_session.query(Book)

    search_query = request.args.get('search', '')  # Ustaw domyślną wartość jako pusty string

    # Zastosowanie filtrowania na podstawie zapytania wyszukiwania
    if search_query:
        query = query.filter(or_(
            Book.title.ilike(f'%{search_query}%'),
            Book.author.ilike(f'%{search_query}%'),
            Book.ISBN.ilike(f'%{search_query}%')
        ))

    # Zastosowanie filtrów niezależnie od wyszukiwania
    if genre and genre != 'Wszystkie gatunki':
        query = query.filter(Book.genre.ilike(f"%{genre}%"))

    if year_range and year_range != 'Wszystkie lata':
        start_year, end_year = map(int, year_range.split('-'))
        query = query.filter(Book.publication_year.between(start_year, end_year))

    if availability:
        subquery = db_session.query(BookCopy.book_id).filter(BookCopy.status == 'dostępna').subquery()
        if availability == 'Dostępne':
            query = query.filter(Book.id.in_(subquery))
        elif availability == 'Niedostępne':
            query = query.filter(~Book.id.in_(subquery))

    if rating and rating != 'Wszystkie':
        min_rating = int(rating)
        review_subquery = db_session.query(
            Review.book_id,
            func.avg(Review.rating).label('average_rating')
        ).group_by(Review.book_id).subquery()
        query = query.join(review_subquery, Book.id == review_subquery.c.book_id).filter(
            review_subquery.c.average_rating >= min_rating
        )

    if sort == 'newest':
        query = query.order_by(Book.publication_year.desc())
    elif sort == 'oldest':
        query = query.order_by(Book.publication_year)
    elif sort == 'highest_rating':
        review_subquery = db_session.query(
            Review.book_id,
            func.avg(Review.rating).label('average_rating')
        ).group_by(Review.book_id).subquery()
        query = query.outerjoin(review_subquery, Book.id == review_subquery.c.book_id) \
            .order_by(review_subquery.c.average_rating.desc())
    elif sort == 'lowest_rating':
        review_subquery = db_session.query(
            Review.book_id,
            func.avg(Review.rating).label('average_rating')
        ).group_by(Review.book_id).subquery()
        query = query.outerjoin(review_subquery, Book.id == review_subquery.c.book_id) \
            .order_by(review_subquery.c.average_rating)
    elif sort == 'most_popular':
        loan_count_subq = db_session.query(
            BookCopy.book_id,
            func.count('*').label('loan_count')
        ).join(BookCopy.loans).group_by(BookCopy.book_id).subquery()
        query = query.outerjoin(loan_count_subq, Book.id == loan_count_subq.c.book_id) \
            .order_by(loan_count_subq.c.loan_count.desc())
    elif sort == 'least_popular':
        loan_count_subq = db_session.query(
            BookCopy.book_id,
            func.count('*').label('loan_count')
        ).join(BookCopy.loans).group_by(BookCopy.book_id).subquery()
        query = query.outerjoin(loan_count_subq, Book.id == loan_count_subq.c.book_id) \
            .order_by(loan_count_subq.c.loan_count)
    elif sort == 'alphabetical_a_z':
        query = query.order_by(Book.title)
    elif sort == 'alphabetical_z_a':
        query = query.order_by(Book.title.desc())

    # Pobranie wyników
    books = query.all()

    if current_user.is_authenticated:
        user_cart_items = db_session.query(CartItem).filter_by(user_id=current_user.id).all()
        cart_copy_ids = {item.book_copy_id for item in user_cart_items}  # Zmiana tutaj

        for book in books:
            book_copies = db_session.query(BookCopy).filter_by(book_id=book.id, status='dostępna').all()
            book.available_not_in_cart = any(copy.id not in cart_copy_ids for copy in book_copies)  # Zmiana tutaj

    return render_template('search_results.html', books=books,
                           search_query=search_query, genre=genre,
                           year_range=year_range, availability=availability,
                           rating=rating, sort=sort)


@app.route('/add_to_cart', methods=['POST'])
@login_required
def add_to_cart():
    if current_user.role != 'czytelnik':
        flash('Tylko czytelnicy mogą dodawać książki do koszyka.', 'warning')
        return redirect(url_for('index'))

    book_id = request.form.get('book_id')

    # Pobierz wszystkie egzemplarze tej książki, które są dostępne i nie są już w koszyku użytkownika
    available_copies = db_session.query(BookCopy).filter(
        BookCopy.book_id == book_id,
        BookCopy.status == 'dostępna',
        ~BookCopy.id.in_(db_session.query(CartItem.book_copy_id).filter_by(user_id=current_user.id))
    ).all()

    if available_copies:
        # Dodaj pierwszy dostępny egzemplarz, który nie jest jeszcze w koszyku
        new_cart_item = CartItem(user_id=current_user.id, book_copy_id=available_copies[0].id)
        db_session.add(new_cart_item)
        db_session.commit()
        flash('Książka została dodana do koszyka.', 'success')
    else:
        flash('Brak dostępnych egzemplarzy tej książki.', 'danger')

    return redirect(url_for('search_books'))



@app.route('/update_cart_quantity/<int:book_copy_id>', methods=['POST'])
@login_required
def update_cart_quantity(book_copy_id):
    quantity_field = f'quantity_{book_copy_id}'  # Dynamiczne tworzenie nazwy pola na podstawie book_copy_id
    new_quantity = request.form.get(quantity_field)

    if not new_quantity.isdigit() or int(new_quantity) < 1:  # Sprawdzamy czy liczba jest dodatnią liczbą całkowitą
        flash('Nieprawidłowa ilość.', 'danger')
        return redirect(url_for('reservation_cart'))

    new_quantity = int(new_quantity)

    # Pobierz book_id z book_copy_id
    book_copy = db_session.query(BookCopy).get(book_copy_id)
    if not book_copy:
        flash('Nie znaleziono egzemplarza książki.', 'danger')
        return redirect(url_for('reservation_cart'))
    book_id = book_copy.book_id

    # Pobierz wszystkie egzemplarze tej książki, które są dostępne i nie są już w koszyku użytkownika
    available_copies = db_session.query(BookCopy).filter(
        BookCopy.book_id == book_id,
        BookCopy.status == 'dostępna',
        ~BookCopy.id.in_(db_session.query(CartItem.book_copy_id).filter_by(user_id=current_user.id))
    ).all()

    # Pobierz wszystkie egzemplarze książek w koszyku użytkownika tej samej książki
    cart_items_same_book = db_session.query(CartItem).filter(
        CartItem.user_id == current_user.id,
        CartItem.book_copy.has(book_id=book_id)
    ).all()

    current_quantity = len(cart_items_same_book)

    # Dodawanie nowych egzemplarzy do koszyka
    if new_quantity > current_quantity:
        difference = new_quantity - current_quantity
        if difference <= len(available_copies):
            for i in range(difference):
                new_cart_item = CartItem(user_id=current_user.id, book_copy_id=available_copies[i].id)
                db_session.add(new_cart_item)
            db_session.commit()
            flash('Dodano książki do koszyka.', 'success')
        else:
            flash('Niewystarczająca ilość dostępnych książek.', 'danger')

    # Usuwanie egzemplarzy z koszyka
    elif new_quantity < current_quantity:
        difference = current_quantity - new_quantity
        for i in range(difference):
            db_session.delete(cart_items_same_book[i])
        db_session.commit()
        flash('Usunięto książki z koszyka.', 'success')

    return redirect(url_for('reservation_cart'))


@app.route('/reservation_cart', methods=['GET', 'POST'])
@login_required
def reservation_cart():
    if request.method == 'POST':
        selected_book_ids = request.form.getlist('selected_books')
        for book_id in selected_book_ids:
            # Sprawdzanie dostępności egzemplarzy przed rezerwacją
            available_copies = db_session.query(BookCopy).filter(
                BookCopy.book_id == book_id,
                BookCopy.status == 'dostępna',
                BookCopy.id.in_(db_session.query(CartItem.book_copy_id).filter_by(user_id=current_user.id))
            ).all()

            # Pobieranie tytułu książki
            book_title = db_session.query(Book.title).filter_by(id=book_id).scalar()

            if not available_copies:
                flash(f'Wszystkie egzemplarze książki "{book_title}" zostały już wypożyczone.', 'danger')
                continue

            for book_copy in available_copies:
                book_copy.status = 'zarezerwowana'
                new_reservation = Reservation(user_id=current_user.id, book_id=book_copy.id, status='aktywna')
                db_session.add(new_reservation)
                cart_item = db_session.query(CartItem).filter_by(book_copy_id=book_copy.id, user_id=current_user.id).first()
                if cart_item:
                    db_session.delete(cart_item)
            db_session.commit()
            flash(f'Egzemplarze książki "{book_title}" zostały zarezerwowane.', 'success')
        return redirect(url_for('reservation_cart'))


    # Zmodyfikowane zapytanie, aby zwracać listę book_copy_id dla każdej książki
    cart_items = db_session.query(
        Book.id.label('book_id'), Book.title, Book.author,
        func.count(CartItem.book_copy_id).label('quantity'),
        func.group_concat(CartItem.book_copy_id).label('book_copy_ids')
    ).join(BookCopy, CartItem.book_copy_id == BookCopy.id
            ).join(Book, BookCopy.book_id == Book.id
                    ).filter(CartItem.user_id == current_user.id
                            ).group_by(Book.id
                                        ).all()

    # Zwrócenie odpowiedzi dla GET lub POST, jeśli nie było przekierowania
    return render_template('reservation_cart.html', cart_items=cart_items)



@app.after_request
def add_header(response):
    response.cache_control.no_store = True
    return response

@app.route('/remove_from_cart/<int:book_id>', methods=['POST'])
@login_required
def remove_from_cart(book_id):
    # Usuń wszystkie egzemplarze książki z koszyka
    CartItemsToDelete = db_session.query(CartItem).filter(
        CartItem.user_id == current_user.id,
        CartItem.book_copy.has(book_id=book_id)
    ).all()
    for item in CartItemsToDelete:
        db_session.delete(item)
    db_session.commit()
    flash('Wszystkie egzemplarze książki zostały usunięte z koszyka.', 'success')
    return redirect(url_for('reservation_cart'))


@app.route('/reserve_book', methods=['POST'])
@login_required
def reserve_book():
    book_copy_id = request.form.get('id')  # Pobieranie id egzemplarza książki

    # Przygotowanie zapytania
    query = db_session.query(BookCopy).filter_by(id=book_copy_id, status='dostępna')
    print(query)  # Wypisanie zapytania SQL dla celów debugowania
    book_copy = query.first()

    if not book_copy:
        return jsonify({'message': 'Książka nie znaleziona lub żaden egzemplarz nie jest dostępny'}), 404

    # Zmiana statusu egzemplarza książki
    book_copy.status = 'zarezerwowana'

    # Utworzenie rezerwacji
    reservation = Reservation(
        user_id=current_user.id,
        book_id=book_copy.id,  # Używamy book_id jako klucza obcego do egzemplarza książki
        status='aktywna'
    )
    db_session.add(reservation)
    db_session.commit()

    return jsonify({'message': 'Rezerwacja została pomyślnie utworzona'}), 200


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
        copy_id = request.form.get('copy_id')
        book_copy = db_session.query(BookCopy).filter_by(id=copy_id, status='do odbioru').first()

        if not book_copy:
            flash('Nie można wypożyczyć tej książki.', 'danger')
            return redirect(url_for('loan_book'))

        # Znajdź aktywną rezerwację dla tego egzemplarza
        reservation = db_session.query(Reservation).filter_by(book_id=copy_id, status='aktywna').first()
        if reservation:
            reservation.status = 'zakończona'
            user_id = reservation.user_id
        else:
            flash('Brak aktywnej rezerwacji dla tego egzemplarza.', 'warning')
            return redirect(url_for('loan_book'))

        # Aktualizacja statusu egzemplarza książki
        book_copy.status = 'wypożyczona'

        # Ustawienie terminu zwrotu
        due_date = datetime.now() + timedelta(days=90)

        # Tworzenie wpisu wypożyczenia
        new_loan = Loan(
            user_id=user_id,
            book_id=copy_id,
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

    # Zapytanie o zarezerwowane egzemplarze książek
    reserved_copies = db_session.query(BookCopy).join(Reservation, BookCopy.id == Reservation.book_id).filter(
        Reservation.user_id == user_id,
        Reservation.status == 'aktywna'
    ).all()

    # Zapytanie o wypożyczone egzemplarze książek
    loaned_copies = db_session.query(BookCopy).join(Loan, BookCopy.id == Loan.book_id).filter(
        Loan.user_id == user_id,
        Loan.status == 'w trakcie'
    ).all()

    # Przygotowanie danych o zarezerwowanych książkach do wyświetlenia
    reserved_books_data = [
        {
            "title": copy.book.title,
            "author": copy.book.author,
            "isbn": copy.book.ISBN,
            "copy_id": copy.id,
            "reservation_id": reservation.id
        }
        for copy in reserved_copies
        for reservation in copy.reservations if reservation.status == 'aktywna'
    ]

    # Przygotowanie danych o wypożyczonych książkach do wyświetlenia
    loaned_books_data = [
        {
            "title": copy.book.title,
            "author": copy.book.author,
            "isbn": copy.book.ISBN,
            "copy_id": copy.id,
            "loan_id": loan.id,
            "due_date": loan.due_date
        }
        for copy in loaned_copies
        for loan in copy.loans if loan.status == 'w trakcie'
    ]

    return render_template('my_books.html', reserved_books=reserved_books_data, loaned_books=loaned_books_data)


@app.route('/add_book', methods=['GET', 'POST'])
@login_required
def add_book():
    if current_user.role != 'pracownik':
        flash('Tylko pracownicy mogą dodać książki.', 'warning')
        return redirect(url_for('index'))

    if request.method == 'POST':
        isbn = request.form.get('isbn')
        title = request.form.get('title')
        author = request.form.get('author')
        genre = request.form.get('genre')
        description = request.form.get('description')
        publication_year = request.form.get('publication_year')
        quantity = int(request.form.get('quantity', 1))  # domyślnie 1, jeśli nie podano

        existing_book = db_session.query(Book).filter_by(ISBN=isbn).first()

        if existing_book:
            book_id = existing_book.id
            flash('Liczba egzemplarzy książki została zaktualizowana.', 'success')
        else:
            new_book = Book(
                ISBN=isbn,
                title=title,
                author=author,
                genre=genre,
                description=description,
                publication_year=publication_year
            )
            db_session.add(new_book)
            db_session.flush()  # Zapisz obiekt new_book, aby uzyskać jego id
            book_id = new_book.id
            flash(f'Książka {title} została pomyślnie dodana.', 'success')

        for _ in range(quantity):
            new_copy = BookCopy(book_id=book_id, status='dostępna')
            db_session.add(new_copy)

        db_session.commit()
        return redirect(url_for('index'))

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


@app.route('/delete_book/<int:copy_id>', methods=['POST'])
@login_required
def delete_book(copy_id):
    if current_user.role != 'pracownik':
        flash('Tylko pracownicy mogą usuwać książki.', 'warning')
        return redirect(url_for('index'))

    book_copy = db_session.query(BookCopy).get(copy_id)
    if book_copy is None:
        flash('Egzemplarz książki nie został znaleziony.', 'danger')
        return redirect(url_for('manage_books'))

    if book_copy.status != 'dostępna':
        flash('Tylko egzemplarze książek o statusie "dostępna" mogą być usunięte.', 'danger')
        return redirect(url_for('manage_books'))

    book_id = book_copy.book_id
    db_session.delete(book_copy)
    db_session.commit()

    # Sprawdź, czy są inne egzemplarze tej książki
    if not db_session.query(BookCopy).filter_by(book_id=book_id).count():
        # Usuń książkę, powiązane rekomendacje oraz recenzje
        book = db_session.query(Book).get(book_id)
        recommendations = db_session.query(Recommendation).filter_by(book_id=book_id).all()
        reviews = db_session.query(Review).filter_by(book_id=book_id).all()

        for recommendation in recommendations:
            db_session.delete(recommendation)
        for review in reviews:
            db_session.delete(review)

        db_session.delete(book)
        db_session.commit()
        flash('Książka oraz wszystkie związane z nią rekomendacje i recenzje zostały usunięte.', 'success')
    else:
        flash('Egzemplarz książki został usunięty.', 'success')

    return redirect(url_for('manage_books'))


@app.route('/manage_book')
@login_required
def manage_books():
    if current_user.role != 'pracownik':
        flash('Brak dostępu.', 'warning')
        return redirect(url_for('index'))

    # Łączenie książek z ich kopiami i wypożyczeniami
    books_with_details = db_session.query(Book).options(
        joinedload(Book.book_copies)
        .joinedload(BookCopy.loans)
        .joinedload(Loan.user),
        joinedload(Book.book_copies)
        .joinedload(BookCopy.reservations)
        .joinedload(Reservation.user)
    ).all()

    return render_template('manage_book.html', books_with_details=books_with_details)


@app.route('/return_book/<int:copy_id>', methods=['POST'])
@login_required
def return_book(copy_id):
    if current_user.role != 'pracownik':
        flash('Tylko pracownicy mogą zarządzać zwrotami książek.', 'warning')
        return redirect(url_for('manage_books'))

    # Znajdź egzemplarz książki na podstawie ID
    book_copy = db_session.query(BookCopy).get(copy_id)
    if not book_copy:
        flash('Egzemplarz książki nie został znaleziony.', 'danger')
        return redirect(url_for('manage_books'))

    # Znajdź wypożyczenie na podstawie copy_id
    loan = db_session.query(Loan).filter(
        Loan.book_id == copy_id,
        Loan.status.in_(['w trakcie', 'książka przetrzymana'])
    ).first()

    if loan:
        # Zaktualizuj status wypożyczenia i egzemplarza książki
        loan.status = 'zakończone'
        loan.return_date = datetime.utcnow()
        book_copy.status = 'dostępna'

        db_session.commit()
        flash(f'Egzemplarz książki "{book_copy.book.title}" został zwrócony i jest teraz dostępny.', 'success')
    else:
        flash('Brak aktywnego wypożyczenia dla tego egzemplarza książki.', 'warning')

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
        form = EditUserEmployee(obj=user)
    # Pracownik próbuje edytować innego pracownika
    elif is_staff and is_target_user_staff:
        flash('Nie masz uprawnień do edycji innego pracownika.', 'danger')
        return redirect(url_for('index'))
    # Pracownik edytuje czytelnika
    elif is_staff and not is_target_user_staff:
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

        # Zmiana e-maila i opcjonalnie ustawień powiadomień
        if not is_target_user_staff:
            user.email = form.email.data
            if hasattr(form, 'wants_notifications'):
                user.wants_notifications = form.wants_notifications.data

        # Zmiana hasła
        if is_editing_self and form.change_password.data:
            user.password = generate_password_hash(form.password.data)

        db_session.commit()
        flash('Dane użytkownika zostały zaktualizowane.', 'success')
        return redirect(url_for('edit_user', user_id=user_id))

    # Ustaw wartości formularza dla żądania GET
    if request.method == 'GET':
        form.name.data = user.name
        form.surname.data = user.surname
        if not is_target_user_staff:
            form.email.data = user.email
            if hasattr(form, 'wants_notifications'):
                form.wants_notifications.data = user.wants_notifications

    return render_template(
        'edit_user.html',
        form=form,
        user_id=user_id,
        is_editing_self=is_editing_self,
        is_staff=is_staff,
        is_target_user_staff=is_target_user_staff
    )




@app.route('/notifications')
@login_required
def notifications():
    if current_user.role != 'czytelnik':
        flash('Tylko czytelnicy mogą przeglądać powiadomienia.', 'warning')
        return redirect(url_for('index'))

    # Pobranie powiadomień
    user_notifications = db_session.query(Notification).filter_by(user_id=current_user.id).all()
    # Pobranie przypomnień
    user_reminders = db_session.query(Reminder).filter_by(user_id=current_user.id).all()

    return render_template('notifications.html', notifications=user_notifications, reminders=user_reminders)



@app.route('/book_ready_for_pickup/<int:copy_id>', methods=['POST'])
@login_required
def book_ready_for_pickup(copy_id):
    if current_user.role == 'pracownik':
        book_copy = db_session.query(BookCopy).get(copy_id)
        if book_copy and book_copy.status == 'zarezerwowana':
            # Pobranie ID użytkownika, który zarezerwował książkę
            user_id = book_copy.reservations[-1].user_id  # Zakładamy, że ostatnia rezerwacja jest aktualna

            # Sprawdzenie, czy użytkownik chce otrzymywać powiadomienia
            user = db_session.query(User).get(user_id)
            if user and user.wants_notifications:
                book_copy.status = 'do odbioru'
                db_session.commit()

                # Utworzenie powiadomienia o odbiorze
                new_reminder = Reminder(
                    user_id=user_id,
                    book_id=copy_id,  # Używamy ID egzemplarza książki
                    date_of_sending=datetime.now(),
                    type='odbiór'
                )
                db_session.add(new_reminder)
                db_session.commit()
                flash('Książka jest gotowa do odbioru.', 'success')
            else:
                flash('Użytkownik zrezygnował z otrzymywania powiadomień.', 'info')
        else:
            flash('Egzemplarz książki nie został znaleziony lub nie jest zarezerwowany.', 'danger')
    else:
        flash('Brak uprawnień.', 'danger')
    return redirect(url_for('manage_books'))


@app.route('/send_notification', methods=['GET', 'POST'])
@login_required
def send_notification():
    if current_user.role != 'pracownik':
        flash('Tylko pracownicy mogą wysyłać powiadomienia.', 'warning')
        return redirect(url_for('index'))

    form = SendNotificationForm()
    form.user_id.choices = [(user.id, user.name) for user in db_session.query(User).filter_by(wants_notifications=True).all()]

    if form.validate_on_submit():
        user_id = form.user_id.data
        content = form.content.data

        new_notification = Notification(
            user_id=user_id,
            content=content
        )
        db_session.add(new_notification)
        db_session.commit()
        flash('Powiadomienie zostało wysłane.', 'success')
        return redirect(url_for('index'))

    return render_template('send_notification'
                           '.html', form=form)



# To powinno być na samym końcu pliku
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)