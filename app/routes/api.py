from flask import flash, request, jsonify, send_file
from flask_login import login_user, logout_user, login_required, current_user
import os
from database_setup import *
from sqlalchemy.orm import scoped_session, sessionmaker, joinedload, aliased
from datetime import datetime, timedelta
from sqlalchemy import func, or_
import re
from mimetypes import guess_type
from werkzeug.utils import secure_filename
from flask import Blueprint, current_app
from app.models import *


api_blueprint = Blueprint('api', __name__)
db_session = scoped_session(sessionmaker(bind=engine))


@api_blueprint.route('/user-data', methods=['GET'])
@login_required
def get_userdata():
    user_data = {
        'id': current_user.id,
        'name': current_user.name,
        'surname': current_user.surname,
        'email': current_user.email,
        'role': current_user.role,
        'wants_notifications': current_user.wants_notifications
    }
    return jsonify(user_data)


@api_blueprint.route('/books')
def get_books():
    # Pobieranie danych o książkach z bazy danych
    books_query = db_session.query(Book).all()
    books = [
        {
            "title": book.title,
            "author": book.author,
            "genre": book.genre,
            "description": book.description,
            "publication_year": book.publication_year,
            "quantity": book.quantity
        }
        for book in books_query
    ]
    return jsonify(books=books)


@api_blueprint.route('/login', methods=['POST', 'GET'])
def login_api():
    # Sprawdzenie, czy użytkownik jest już zalogowany
    if current_user.is_authenticated:
        # Jeśli użytkownik jest już zalogowany, zwróć błąd
        return jsonify({'success': False, 'error': 'User already logged in'}), 400

    # Pobranie danych z żądania
    data = request.json
    email = data.get('email')
    password = data.get('password')

    # Wyszukiwanie użytkownika w bazie danych
    user = db_session.query(User).filter_by(email=email).first()

    # Sprawdzenie hasła i logowanie użytkownika
    if user and check_password_hash(user.password, password):
        login_user(user)
        return jsonify({
            'success': True,
            'user_info': {
                'id': user.id,
                'name': user.name,
                'surname': user.surname,
                'email': user.email,
                'role': user.role
            }
        }), 200
    else:
        # Jeśli dane logowania są nieprawidłowe
        return jsonify({'success': False, 'error': 'Nieprawidłowe dane logowania'}), 401


@api_blueprint.route('/register', methods=['POST'])
def register_api():
    if current_user.is_authenticated:
        # Przekierowanie zalogowanych użytkowników
        return jsonify({'success': False, 'error': 'User already logged in'}), 400

    # Pobranie danych z żądania JSON
    data = request.json
    name = data.get('name')
    surname = data.get('surname')
    email = data.get('email')
    password = data.get('password')

    # Walidacja imienia i nazwiska
    if not re.match(r'^[A-Z][a-z]{1,}$', name) or not re.match(r'^[A-Z][a-z]{1,}$', surname):
        return jsonify({'success': False,
                        'error': 'Imię i nazwisko muszą zaczynać się z wielkiej litery i zawierać przynajmniej 2 litery.'}), 400

    # Walidacja hasła
    password_pattern = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$')
    if not password_pattern.match(password):
        return jsonify({'success': False, 'error': 'Hasło nie spełnia wymagań.'}), 400

    # Sprawdzenie, czy użytkownik już istnieje
    existing_user = db_session.query(User).filter_by(email=email).first()
    if existing_user is not None:
        # Użytkownik już istnieje
        return jsonify({'success': False, 'error': 'Użytkownik z podanym adresem e-mail już istnieje'}), 409


    # Tworzenie nowego czytelnika
    hashed_password = generate_password_hash(password, method='sha256')
    new_user = User(
        name=name,
        surname=surname,
        email=email,
        password=hashed_password,
        role='czytelnik'
    )
    db_session.add(new_user)
    db_session.commit()

    # Odpowiedź po pomyślnej rejestracji
    return jsonify({'success': True, 'message': 'Account successfully created'}), 201


@api_blueprint.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'success': True, 'message': 'Zostałeś wylogowany.'}), 200


@api_blueprint.route('/search_books', methods=['GET'])
def search_books():
    # Pobranie parametrów zapytania
    search_query = request.args.get('search')
    genre = request.args.get('genre')
    year_range = request.args.get('year')
    availability = request.args.get('availability')
    rating = request.args.get('rating')
    sort = request.args.get('sort', 'newest')

    # Zapytanie SQL z uwzględnieniem filtrów
    query = db_session.query(Book)

    search_query = request.args.get('search', '')  # Ustawienie domyślnej wartości jako pusty string

    # Zastosowanie filtrowania na podstawie zapytania wyszukiwania
    if search_query:
        query = query.filter(or_(
            Book.title.ilike(f'%{search_query}%'),
            Book.author.ilike(f'%{search_query}%'),
            Book.ISBN.ilike(f'%{search_query}%')
        ))

    # Zastosowanie filtrów niezależnie od wyszukiwania
    if genre:
        genre_list = genre.split(',')
        genre_filters = [Book.genre.ilike(f"%{g}%") for g in genre_list]
        query = query.filter(or_(*genre_filters))

    if year_range:
        year_ranges = year_range.split(',')
        year_range_filters = [Book.publication_year.between(*map(int, y.split('-'))) for y in year_ranges if
                              y != 'Wszystkie lata']
        if year_range_filters:
            query = query.filter(or_(*year_range_filters))

    if availability:
        subquery = db_session.query(BookCopy.book_id).filter(BookCopy.status == 'dostępna').subquery()
        if availability == 'Dostępne':
            query = query.filter(Book.id.in_(subquery))
        elif availability == 'Niedostępne':
            query = query.filter(~Book.id.in_(subquery))

    if rating:
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
        cart_copy_ids = {item.book_copy_id for item in user_cart_items}

        for book in books:
            book_copies = db_session.query(BookCopy).filter_by(book_id=book.id, status='dostępna').all()
            book.available_not_in_cart = any(copy.id not in cart_copy_ids for copy in book_copies)

    results = [
        {
            "book_id": book.id,
            "title": book.title,
            "author": book.author,
            "genre": book.genre,
            "year": book.publication_year,
            "available": any(copy.status == 'dostępna' for copy in book.book_copies)

        } for book in books
    ]

    return jsonify({
        "books": results,
        "searchQuery": search_query,
        "selectedGenre": genre,
        "selectedYearRange": year_range,
        "selectedAvailability": availability,
        "selectedRating": rating,
        "selectedSort": sort
    })


@api_blueprint.route('/add_to_cart', methods=['POST'])
@login_required
def api_add_to_cart():
    data = request.json
    book_id = data.get('book_id')
    print("Otrzymano żądanie dodania do koszyka dla książki z ID:", book_id)

    available_copies = db_session.query(BookCopy).filter(
        BookCopy.book_id == book_id,
        BookCopy.status == 'dostępna',
        ~BookCopy.id.in_(db_session.query(CartItem.book_copy_id).filter_by(user_id=current_user.id))
    ).all()

    if available_copies:
        new_cart_item = CartItem(user_id=current_user.id, book_copy_id=available_copies[0].id)
        db_session.add(new_cart_item)
        db_session.commit()
        return jsonify({'success': True, 'message': 'Książka została dodana do koszyka.'})

    return jsonify({'success': False, 'message': 'Brak dostępnych egzemplarzy tej książki.'})



@api_blueprint.route('/update_cart_quantity/<int:book_copy_id>', methods=['POST'])
@login_required
def update_cart_quantity(book_copy_id):
    data = request.json
    new_quantity = data.get('quantity')

    if not str(new_quantity).isdigit() or int(new_quantity) < 1:
        flash('Nieprawidłowa ilość.', 'danger')
        return jsonify({'error': 'Nieprawidłowa ilość.'}), 400

    new_quantity = int(new_quantity)

    # Pobieranie book_id z book_copy_id
    book_copy = db_session.query(BookCopy).get(book_copy_id)
    if not book_copy:
        flash('Nie znaleziono egzemplarza książki.', 'danger')
        return jsonify({'error': 'Nie znaleziono egzemplarza książki.'}), 404
    book_id = book_copy.book_id

    available_copies = db_session.query(BookCopy).filter(
        BookCopy.book_id == book_id,
        BookCopy.status == 'dostępna',
        ~BookCopy.id.in_(db_session.query(CartItem.book_copy_id).filter_by(user_id=current_user.id))
    ).all()

    cart_items_same_book = db_session.query(CartItem).filter(
        CartItem.user_id == current_user.id,
        CartItem.book_copy.has(book_id=book_id)
    ).all()

    current_quantity = len(cart_items_same_book)

    response_message = ''
    status_code = 200

    if new_quantity > current_quantity:
        difference = new_quantity - current_quantity
        if difference <= len(available_copies):
            for i in range(difference):
                new_cart_item = CartItem(user_id=current_user.id, book_copy_id=available_copies[i].id)
                db_session.add(new_cart_item)
            db_session.commit()
            response_message = 'Dodano książki do koszyka.'
        else:
            response_message = 'Niewystarczająca ilość dostępnych książek.'
            status_code = 400
    elif new_quantity < current_quantity:
        difference = current_quantity - new_quantity
        for i in range(difference):
            db_session.delete(cart_items_same_book[i])
        db_session.commit()
        response_message = 'Usunięto książki z koszyka.'

    return jsonify({'message': response_message}), status_code


@api_blueprint.route('/reservation_cart', methods=['GET'])
@login_required
def get_reservation_cart():
    # Zwracanie listy book_copy_id dla każdej książki
    cart_items = db_session.query(
        Book.id.label('book_id'), Book.title, Book.author,
        func.count(CartItem.book_copy_id).label('quantity'),
        func.group_concat(CartItem.book_copy_id).label('book_copy_ids')
    ).join(BookCopy, CartItem.book_copy_id == BookCopy.id
          ).join(Book, BookCopy.book_id == Book.id
                ).filter(CartItem.user_id == current_user.id
                        ).group_by(Book.id
                                   ).all()

    # Przygotowanie danych do odpowiedzi JSON
    cart_items_json = [
        {
            'book_id': item.book_id,
            'title': item.title,
            'author': item.author,
            'quantity': item.quantity,
            'book_copy_ids': item.book_copy_ids.split(',')
        } for item in cart_items
    ]

    return jsonify(cart_items_json)

@api_blueprint.route('/reservation_cart', methods=['POST'])
@login_required
def post_reservation_cart():
    data = request.json
    selected_book_ids = data.get('selected_books')

    if not selected_book_ids:
        return jsonify({'error': 'Brak wybranych książek'}), 400

    response_messages = []

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

        # Zwrócenie komunikatów o wyniku operacji w formacie JSON
        return jsonify({'messages': response_messages})


@api_blueprint.after_request
def add_header(response):
    response.cache_control.no_store = True
    return response


@api_blueprint.route('/remove_from_cart/<int:book_id>', methods=['POST'])
@login_required
def remove_from_cart(book_id):
    # Usuwanie wszystkich egzemplarzy książki z koszyka
    CartItemsToDelete = db_session.query(CartItem).filter(
        CartItem.user_id == current_user.id,
        CartItem.book_copy.has(book_id=book_id)
    ).all()

    if not CartItemsToDelete:
        return jsonify({'message': 'Brak książek w koszyku do usunięcia.'}), 404

    for item in CartItemsToDelete:
        db_session.delete(item)
    db_session.commit()

    return jsonify({'message': 'Wszystkie egzemplarze książki zostały usunięte z koszyka.'}), 200



@api_blueprint.route('/reserve_book', methods=['POST'])
@login_required
def reserve_book():
    data = request.json
    book_copy_ids = data.get('bookCopyIds')  # Pobieranie listy ID egzemplarzy książek

    if not book_copy_ids:
        return jsonify({'message': 'Nie podano id egzemplarzy książek'}), 400

    for book_copy_id in book_copy_ids:
        # Przygotowanie zapytania dla każdego ID
        book_copy = db_session.query(BookCopy).filter_by(id=book_copy_id, status='dostępna').first()

        if not book_copy:
            return jsonify({'message': f'Egzemplarz książki o ID {book_copy_id} nie znaleziony lub nie jest dostępny'}), 404

        # Zmiana statusu egzemplarza książki
        book_copy.status = 'zarezerwowana'

        # Utworzenie rezerwacji
        reservation = Reservation(
            user_id=current_user.id,
            book_id=book_copy.id,
            status='aktywna'
        )
        db_session.add(reservation)

    db_session.commit()
    return jsonify({'message': 'Rezerwacje zostały pomyślnie utworzone'}), 200


@api_blueprint.route('/mark_as_loan', methods=['GET'])
@login_required
def search_user_and_books():
    if current_user.role != 'pracownik':
        return jsonify({'status': 'error', 'message': 'Tylko pracownicy mogą przeglądać informacje.'}), 403

    email = request.args.get('email')
    if not email:
        return jsonify({'status': 'error', 'message': 'Email jest wymagany.'}), 400

    user = db_session.query(User).filter_by(email=email).first()
    if not user:
        return jsonify({'status': 'error', 'message': 'Użytkownik nie znaleziony.'}), 404

    # Pobieranie książek gotowych do odbioru dla tego użytkownika
    books_ready_for_pickup = db_session.query(BookCopy).join(Book).join(Reservation).filter(
        Reservation.user_id == user.id,
        Reservation.status == 'aktywna',
        BookCopy.status == 'do odbioru'
    ).all()

    # Pobieranie książek wypożyczonych przez tego użytkownika
    loaned_books = db_session.query(BookCopy).join(Book).join(Loan).filter(
        Loan.user_id == user.id,
        or_(Loan.status == 'w trakcie', Loan.status == 'książka przetrzymana')
    ).all()

    books_data = [{
        'id': book_copy.id,
        'title': book_copy.book.title,
        'author': book_copy.book.author,
        'status': book_copy.status
    } for book_copy in books_ready_for_pickup]

    for book_copy in loaned_books:
        books_data.append({
            'id': book_copy.id,
            'title': book_copy.book.title,
            'author': book_copy.book.author,
            'status': book_copy.status,
            'loaned': True
        })

    return jsonify({
        'status': 'success',
        'user': {
            'id': user.id,
            'name': user.name,
            'surname': user.surname,
            'email': user.email,
        },
        'books': books_data
    })


@api_blueprint.route('/mark_as_loan', methods=['POST'])
@login_required
def mark_as_loan():
    if current_user.role != 'pracownik':
        return jsonify({'status': 'error', 'message': 'Tylko pracownicy mogą wypożyczać książki.'}), 403

    data = request.get_json()
    copy_id = data.get('copy_id')

    book_copy = db_session.query(BookCopy).filter_by(id=copy_id).first()
    if not book_copy or book_copy.status != 'do odbioru':
        return jsonify({'status': 'error', 'message': 'Książka nie jest dostępna do wypożyczenia.'}), 400

    # Znajdowanie aktywnej rezerwacji
    reservation = db_session.query(Reservation).filter_by(book_id=copy_id, status='aktywna').first()

    # Ustawienie daty zwrotu na 90 dni od dzisiaj
    due_date = datetime.now() + timedelta(days=90)

    # Utworzenie nowego wypożyczenia
    new_loan = Loan(
        user_id=reservation.user_id if reservation else current_user.id,
        book_id=copy_id,
        status='w trakcie',
        due_date=due_date
    )

    # Zmiana statusu egzemplarza książki i rezerwacji
    book_copy.status = 'wypożyczona'
    if reservation:
        reservation.status = 'zakończona'

    # Zapisanie zmian w bazie danych
    db_session.add(new_loan)
    db_session.commit()

    return jsonify({'status': 'success', 'message': 'Książka została wypożyczona.'})


@api_blueprint.route('/my_books')
@login_required
def my_books():
    if current_user.role != 'czytelnik':
        return jsonify({'error': 'Brak dostępu'}), 403

    user_id = current_user.id

    # Zapytanie o zarezerwowane egzemplarze książek
    reserved_copies = db_session.query(BookCopy).join(Reservation, BookCopy.id == Reservation.book_id).filter(
        Reservation.user_id == user_id,
        Reservation.status == 'aktywna'
    ).all()

    # Zapytanie o wypożyczone egzemplarze książek
    loaned_copies = db_session.query(BookCopy).join(Loan, BookCopy.id == Loan.book_id).filter(
        Loan.user_id == user_id,
        or_(Loan.status == 'w trakcie', Loan.status == 'książka przetrzymana')
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
            "due_date": loan.due_date,
            "loan_status": loan.status  # Dodanie status wypożyczenia
        }
        for copy in loaned_copies
        for loan in copy.loans if loan.status in ['w trakcie', 'książka przetrzymana']
    ]

    return jsonify({
        'reserved_books': reserved_books_data,
        'loaned_books': loaned_books_data
    })


@api_blueprint.route('/add_book', methods=['POST'])
@login_required
def add_book():
    if current_user.role != 'pracownik':
        return jsonify({'status': 'error', 'message': 'Tylko pracownicy mogą dodać książki.'}), 403

    if 'cover_image' not in request.files:
        return jsonify({'status': 'error', 'message': 'Brak pliku obrazu okładki.'}), 400

    cover_image = request.files['cover_image']
    if cover_image.filename == '':
        return jsonify({'status': 'error', 'message': 'Nie wybrano pliku obrazu okładki.'}), 400

    # Zapisanie obrazu okładki w Azure Blob Storage
    filename = secure_filename(cover_image.filename)
    blob_service_client = current_app.blob_service_client
    blob_client = blob_service_client.get_blob_client(container="ksiazki", blob=filename)
    blob_client.upload_blob(cover_image)

    data = request.form
    isbn = data.get('isbn')

    # Sprawdzenie czy książka już istnieje
    existing_book = db_session.query(Book).filter_by(ISBN=isbn).first()
    if existing_book:
        return jsonify({'status': 'error', 'message': 'Książka o podanym ISBN już istnieje i nie może zostać dodana ponownie.'}), 409

    # Odbieranie pozostałych danych książki i tworzenie nowego rekordu
    title = data.get('title')
    author = data.get('author')
    genre = data.get('genre')
    description = data.get('description')
    publication_year = data.get('publication_year')
    quantity = int(data.get('quantity', 1))

    new_book = Book(
        ISBN=isbn,
        title=title,
        author=author,
        genre=genre,
        description=description,
        publication_year=publication_year,
        cover_image_url=blob_client.url  # URL obrazu okładki
    )
    db_session.add(new_book)
    db_session.flush()

    # Dodawanie kopii książki
    for _ in range(quantity):
        new_copy = BookCopy(book_id=new_book.id, status='dostępna')
        db_session.add(new_copy)

    db_session.commit()
    return jsonify({'status': 'success', 'message': f'Książka {title} została pomyślnie dodana.', 'cover_image_url': blob_client.url})


@api_blueprint.route('/edit_book', methods=['GET'])
@login_required
def search_book():
    isbn = request.args.get('isbn')
    if not isbn:
        return jsonify({'status': 'error', 'message': 'Nie podano numeru ISBN.'}), 400

    book = db_session.query(Book).filter(Book.ISBN == isbn).first()
    if book is None:
        return jsonify({'status': 'error', 'message': 'Książka nie została znaleziona.'}), 404

    return jsonify({
        'book_id': book.id,
        'isbn': book.ISBN,
        'title': book.title,
        'author': book.author,
        'genre': book.genre,
        'description': book.description,
        'publication_year': book.publication_year,
        'copies': [{'id': copy.id, 'status': copy.status} for copy in book.book_copies]
    })


@api_blueprint.route('/edit_book', methods=['POST', 'DELETE'])
@login_required
def edit_book():
    if current_user.role != 'pracownik':
        return jsonify({'status': 'error', 'message': 'Tylko pracownicy mogą zarządzać książkami.'}), 403

    if request.method == 'POST':
        data = request.get_json()
        book_id = data.get('book_id')
        if not book_id:
            return jsonify({'status': 'error', 'message': 'Nie podano ID książki.'}), 400

        book = db_session.query(Book).get(book_id)
        if book is None:
            return jsonify({'status': 'error', 'message': 'Książka nie została znaleziona.'}), 404

        book.ISBN = data.get('isbn')
        book.title = data.get('title')
        book.author = data.get('author')
        book.genre = data.get('genre')
        book.description = data.get('description')
        book.publication_year = data.get('publication_year')

        db_session.commit()
        return jsonify({'status': 'success', 'message': 'Książka została zaktualizowana.'})

    elif request.method == 'DELETE':
        data = request.get_json()
        copy_id = data.get('copy_id')
        if not copy_id:
            return jsonify({'error': 'Nie podano ID egzemplarza.'}), 400

        return delete_book(copy_id)


@api_blueprint.route('/manage_books')
@login_required
def manage_books():
    if current_user.role != 'pracownik':
        return jsonify({'error': 'Brak dostępu.'}), 403

    # Łączenie książek z ich kopiami i wypożyczeniami
    books_with_details = db_session.query(Book).options(
        joinedload(Book.book_copies)
        .joinedload(BookCopy.loans)
        .joinedload(Loan.user),
        joinedload(Book.book_copies)
        .joinedload(BookCopy.reservations)
        .joinedload(Reservation.user)
    ).all()

    # Przekształcenie danych na format JSON
    books_json = []
    for book in books_with_details:
        book_data = {
            'id': book.id,
            'title': book.title,
            'author': book.author,
            'copies': [{
                'id': copy.id,
                'status': copy.status,
            } for copy in book.book_copies]
        }
        books_json.append(book_data)

    return jsonify(books_json)


@api_blueprint.route('/return_book/<int:copy_id>', methods=['POST'])
@login_required
def return_book(copy_id):
    if current_user.role != 'pracownik':
        return jsonify({'error': 'Tylko pracownicy mogą zarządzać zwrotami książek.'}), 403

    # Znajdowanie egzemplarza książki na podstawie ID
    book_copy = db_session.query(BookCopy).get(copy_id)
    if not book_copy:
        return jsonify({'error': 'Egzemplarz książki nie został znaleziony.'}), 404

    loan = db_session.query(Loan).filter(
        Loan.book_id == copy_id,
        or_(Loan.status == 'w trakcie', Loan.status == 'książka przetrzymana')
    ).first()

    if loan:
        loan.status = 'zakończone'
        loan.return_date = datetime.utcnow()
        book_copy.status = 'dostępna'
        db_session.commit()
        return jsonify({'message': f'Egzemplarz książki "{book_copy.book.title}" został zwrócony i jest teraz dostępny.'})
    else:
        return jsonify({'warning': 'Brak aktywnego wypożyczenia dla tego egzemplarza książki.'})


@api_blueprint.route('/delete_book/<int:copy_id>', methods=['DELETE'])
@login_required
def delete_book(copy_id):
    if current_user.role != 'pracownik':
        return jsonify({'error': 'Tylko pracownicy mogą usuwać książki.'}), 403

    book_copy = db_session.query(BookCopy).get(copy_id)
    if book_copy is None:
        return jsonify({'error': 'Egzemplarz książki nie został znaleziony.'}), 404

    if book_copy.status != 'dostępna':
        return jsonify({'error': 'Tylko egzemplarze książek o statusie "dostępna" mogą być usunięte.'}), 400

    book_id = book_copy.book_id
    db_session.delete(book_copy)
    db_session.commit()

    # Sprawdzenie czy są inne egzemplarze tej książki
    if not db_session.query(BookCopy).filter_by(book_id=book_id).count():
        book = db_session.query(Book).get(book_id)
        recommendations = db_session.query(Recommendation).filter_by(book_id=book_id).all()
        reviews = db_session.query(Review).filter_by(book_id=book_id).all()

        for recommendation in recommendations:
            db_session.delete(recommendation)
        for review in reviews:
            db_session.delete(review)

        db_session.delete(book)
        db_session.commit()
        return jsonify({'message': 'Książka oraz wszystkie związane z nią rekomendacje i recenzje zostały usunięte.'})
    else:
        return jsonify({'message': 'Egzemplarz książki został usunięty.'})


@api_blueprint.route('/reserved_books', methods=['GET'])
@login_required
def get_reserved_books():
    if current_user.role != 'pracownik':
        return jsonify({'error': 'Brak uprawnień.'}), 403

    reserved_books = db_session.query(BookCopy).filter(BookCopy.status == 'zarezerwowana').all()
    books_data = [{
        'id': book.id,
        'title': book.book.title,
        'author': book.book.author,
        'status': book.status
    } for book in reserved_books]

    return jsonify(books_data)


@api_blueprint.route('/book_ready_for_pickup/<int:copy_id>', methods=['POST'])
@login_required
def book_ready_for_pickup(copy_id):
    if current_user.role != 'pracownik':
        return jsonify({'error': 'Brak uprawnień.'}), 403

    book_copy = db_session.query(BookCopy).get(copy_id)
    if not book_copy:
        return jsonify({'error': 'Egzemplarz książki nie został znaleziony.'}), 404

    if book_copy.status != 'zarezerwowana':
        return jsonify({'error': 'Egzemplarz nie jest w statusie zarezerwowanej.'}), 400

    book_copy.status = 'do odbioru'
    db_session.commit()

    user_id = book_copy.reservations[-1].user_id
    user = db_session.query(User).get(user_id)
    if user and user.wants_notifications:
        # Wysyłanie powiadomień tylko użytkownikom, którzy chcą je otrzymywać
        new_reminder = Reminder(
            user_id=user_id,
            book_id=copy_id,
            date_of_sending=datetime.now(),
            type='odbiór'
        )
        db_session.add(new_reminder)
        db_session.commit()

    return jsonify({'message': 'Status książki został zmieniony na gotową do odbioru.'})


@api_blueprint.route('/edit_user/<int:user_id>', methods=['POST'])
@login_required
def api_edit_user(user_id):
    user = db_session.query(User).get(user_id)
    if user is None:
        return jsonify({'error': 'Użytkownik nie został znaleziony.'}), 404

    # Uprawnienia do edycji
    if current_user.id != user_id and current_user.role != 'administrator':
        return jsonify({'error': 'Nie masz uprawnień do edycji tego użytkownika.'}), 403

    data = request.get_json()

    # Pracownik edytujący sam siebie może zmienić tylko hasło
    if current_user.id == user_id and current_user.role == 'pracownik':
        if 'password' in data and data['password']:
            user.password = generate_password_hash(data['password'])
    else:
        # Edycja innych pól dla administratora lub samych siebie
        user.name = data.get('name', user.name)
        user.surname = data.get('surname', user.surname)
        user.email = data.get('email', user.email)

        # Edycja powiadomień tylko dla czytelników
        if user.role == 'czytelnik':
            user.wants_notifications = data.get('wants_notifications', user.wants_notifications)

    db_session.commit()
    return jsonify({'message': 'Dane użytkownika zostały zaktualizowane.'})



@api_blueprint.route('/edit_user/<int:user_id>', methods=['GET'])
@login_required
def get_user_data(user_id):
    user = db_session.query(User).get(user_id)
    if user is None:
        return jsonify({'error': 'Użytkownik nie został znaleziony.'}), 404

    is_editing_self = current_user.id == user_id
    is_admin = current_user.role == 'administrator'
    is_target_user_staff = user.role in ['pracownik', 'administrator']

    user_data = {
        'id': user.id,
        'name': user.name,
        'surname': user.surname,
        'email': user.email,
        'role': user.role,
        'wants_notifications': user.wants_notifications if user.role == 'czytelnik' else None,
        'is_editing_self': is_editing_self,
        'is_admin': is_admin,
        'is_target_user_staff': is_target_user_staff
    }

    return jsonify(user_data)


@api_blueprint.route('/notifications')
@login_required
def api_notifications():
    if current_user.role != 'czytelnik':
        return jsonify({'error': 'Tylko czytelnicy mogą przeglądać powiadomienia.'}), 403

    user_notifications = db_session.query(Notification).filter_by(user_id=current_user.id).all()
    user_reminders = db_session.query(Reminder).filter_by(user_id=current_user.id).all()

    notifications_data = [{'content': n.content, 'date_of_sending': n.date_of_sending.strftime('%Y-%m-%d %H:%M:%S')} for n in user_notifications]
    reminders_data = [
        {
            'type': r.type,
            'title': r.book_copy.book.title if r.book_copy and r.book_copy.book else "Brak tytułu",
            'date_of_sending': r.date_of_sending.strftime('%Y-%m-%d %H:%M:%S')
        }
        for r in user_reminders
    ]

    print(f"wants_notifications for user {current_user.id}: {current_user.wants_notifications}")
    return jsonify({
        'notifications': notifications_data,
        'reminders': reminders_data,
        'wants_notifications': current_user.wants_notifications
    })


@api_blueprint.route('/send_notification', methods=['POST'])
@login_required
def api_send_notification():
    if current_user.role != 'pracownik':
        return jsonify({'error': 'Tylko pracownicy mogą wysyłać powiadomienia.'}), 403

    data = request.json
    user_id = data.get('user_id')
    content = data.get('content')


    new_notification = Notification(user_id=user_id, content=content)
    db_session.add(new_notification)
    db_session.commit()

    return jsonify({'message': 'Powiadomienie zostało wysłane.'})

@api_blueprint.route('/users')
@login_required
def api_users():
    query = db_session.query(User)
    if current_user.role == 'pracownik':
        query = query.filter_by(role='czytelnik')

    users_data = [
        {'id': user.id, 'name': user.name, 'surname': user.surname, 'email': user.email, 'role': user.role}
        for user in query.all()
    ]
    return jsonify(users_data)


@api_blueprint.route('/user_profile/<int:user_id>', methods=['GET'])
@login_required
def user_profile(user_id):
    if current_user.role == 'czytelnik' and current_user.id != user_id:
        return jsonify({'error': 'Nie masz uprawnień do wyświetlenia tego profilu.'}), 403

    user = db_session.query(User).get(user_id)
    if user is None:
        return jsonify({'error': 'Użytkownik nie został znaleziony.'}), 404

    user_data = {
        'id': user.id,
        'name': user.name,
        'surname': user.surname,
        'email': user.email,
        'role': user.role
    }

    return jsonify(user_data)


@api_blueprint.route('/user_debt/<int:user_id>', methods=['GET'])
@login_required
def get_user_debt(user_id):
    loan_alias = aliased(Loan)

    # Obliczenie całkowitego długu
    total_debt = db_session.query(
        func.coalesce(func.sum(Payment.amount), 0)
    ).join(
        loan_alias, Payment.book_copy_id == loan_alias.book_id
    ).join(
        BookCopy, loan_alias.book_id == BookCopy.id
    ).filter(
        Payment.user_id == user_id,
        Payment.status == 'oczekująca',
        loan_alias.status == 'zakończone',
        loan_alias.return_date.isnot(None)
    ).scalar()

    # Pobieranie wszystkich płatności użytkownika z unikalnymi tytułami książek
    all_payments_details = db_session.query(
        func.max(Payment.id),
        Payment.amount,
        func.max(Payment.status),
        Book.title,
        Book.author,
        loan_alias.status.label('loan_status')
    ).join(
        loan_alias, Payment.book_copy_id == loan_alias.book_id
    ).join(
        BookCopy, loan_alias.book_id == BookCopy.id
    ).join(
        Book, BookCopy.book_id == Book.id
    ).filter(
        Payment.user_id == user_id
    ).group_by(
        Payment.book_copy_id,  # Grupowanie po book_copy_id
        Book.title,
        Book.author
    ).all()

    payments_info = [
        {
            'payment_id': payment[0],
            'amount': payment[1],
            'status': payment[2],
            'book_title': payment[3],
            'book_author': payment[4],
            'loan_status': payment[5]
        }
        for payment in all_payments_details
    ]

    return jsonify({'total_debt': total_debt, 'all_payments_info': payments_info})


@api_blueprint.route('/update_multiple_payments', methods=['POST'])
@login_required
def update_multiple_payments_status():
    data = request.json
    print("Otrzymane dane:", data)

    payment_ids = data.get('paymentIds')
    new_status = data.get('status', 'opłacona')

    if not payment_ids or not isinstance(payment_ids, list) or not all(isinstance(id, int) for id in payment_ids):
        return jsonify({'error': 'paymentIds musi być listą identyfikatorów (liczb całkowitych).'}), 400

    try:
        # Pobieranie wszystkich płatności do aktualizacji
        payments = db_session.query(Payment).filter(Payment.id.in_(payment_ids)).all()

        if payments:
            # Aktualizacja statusów dla wszystkich znalezionych płatności
            for payment in payments:
                payment.status = new_status

            db_session.commit()
            return jsonify({'message': f'Statusy dla {len(payments)} płatności zostały zaktualizowane.'}), 200
        else:
            return jsonify({'error': 'Żadna płatność nie została znaleziona dla podanych identyfikatorów.'}), 404
    except Exception as e:
        db_session.rollback()
        return jsonify({'error': str(e)}), 500


@api_blueprint.route('/get_media', methods=['GET'])
def get_media():
    media_items = db_session.query(Media).all()
    sas_token = "sp=racwdli&st=2024-01-29T10:33:40Z&se=2024-03-16T18:33:40Z&sv=2022-11-02&sr=c&sig=P%2BAs66xZZqJDkAW1t8nhmNICIuvbo7bsDBZSWf%2F%2FMFc%3D"

    media_data = [
        {
            "id": item.id,
            "media_type": item.media_type,
            "file_url": item.file_url,
            "title": item.title,
            "author": item.author,
            "publish_year": item.publish_year,
            "genre": item.genre,
            "description": item.description,
            "image_url": f"{item.cover_image_url}?{sas_token}" if item.cover_image_url else None
        } for item in media_items
    ]

    return jsonify(media_data)


@api_blueprint.route('/upload', methods=['POST'])
@login_required
def upload_media():
    blob_service_client = current_app.blob_service_client
    if 'file' not in request.files or 'cover_image' not in request.files:
        return jsonify({'message': 'Brak pliku lub obrazu okładki w żądaniu'}), 400

    file = request.files['file']
    cover_image = request.files['cover_image']

    if file.filename == '' or cover_image.filename == '':
        return jsonify({'message': 'Nie wybrano pliku lub obrazu okładki'}), 400

    if file and cover_image:
        # Zapisanie obrazu okładki
        cover_filename = secure_filename(cover_image.filename)
        cover_blob_client = blob_service_client.get_blob_client(container="ksiazki", blob=cover_filename)
        cover_blob_client.upload_blob(cover_image)

        # Zapisanie pliku mediów
        file_blob_client = blob_service_client.get_blob_client(container="biblioteka", blob=file.filename)
        file_blob_client.upload_blob(file)

        # Odbieranie danych formularza
        media_data = request.form
        media_type = media_data.get('media_type')
        title = media_data.get('title')
        author = media_data.get('author')
        publish_year = media_data.get('publish_year')
        genre = media_data.get('genre')
        description = media_data.get('description')

        # Weryfikacja typu mediów
        if media_type not in ['ebook', 'audiobook']:
            return jsonify({"message": "Nieprawidłowy typ mediów."}), 400

        # Tworzenie nowego rekordu Media
        new_media = Media(
            media_type=media_type,
            file_url=file_blob_client.url,
            cover_image_url=cover_blob_client.url,  # Dodanie URL obrazu okładki
            title=title,
            author=author,
            publish_year=publish_year,
            genre=genre,
            description=description
        )
        db_session.add(new_media)
        db_session.commit()

        return jsonify({"message": "Media zostało przesłane.", "file_url": file_blob_client.url, "cover_image_url": cover_blob_client.url})

    return jsonify({'message': 'Wystąpił błąd podczas przesyłania mediów'}), 500



@api_blueprint.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    blob_service_client = current_app.blob_service_client
    blob_client = blob_service_client.get_blob_client(container="biblioteka", blob=filename)
    download_stream = blob_client.download_blob()

    # Pobranie typu MIME na podstawie nazwy pliku
    mimetype = guess_type(filename)[0]

    # Czy typ MIME jest znany, w przeciwnym razie ustaw domyślny
    if mimetype is None:
        mimetype = 'application/octet-stream'

    # Ustawienie nazwy pliku do pobrania
    download_name = os.path.basename(filename)

    return send_file(
        download_stream,
        mimetype=mimetype,
        as_attachment=True,
        download_name=download_name
    )


@api_blueprint.route('/add_review', methods=['POST'])
@login_required
def add_review():
    # Pobieranie danych z żądania JSON
    data = request.json
    book_id = data.get('book_id')
    review_text = data.get('text')
    rating = data.get('rating')

    # Sprawdzenie czy książka istnieje
    book = db_session.query(Book).filter_by(id=book_id).first()
    if not book:
        return jsonify({'error': 'Książka nie znaleziona.'}), 404

    # Nowa recenzja
    new_review = Review(
        book_id=book_id,
        user_id=current_user.id,
        text=review_text,
        rating=rating,
        date=datetime.utcnow(),
        status='oczekująca'
    )

    # Dodanie recenzji do sesji
    db_session.add(new_review)
    db_session.commit()

    # Odpowiedz sukcesem
    return jsonify({'message': 'Recenzja została dodana.'}), 201


@api_blueprint.route('/get_reviews/<int:book_id>', methods=['GET'])
def get_reviews(book_id):
    # Pobieranie recenzji dla danej książki
    reviews = db_session.query(Review).filter_by(book_id=book_id).all()

    # Sprawdzenie, czy znaleziono recenzje
    if not reviews:
        return jsonify({'error': 'Nie znaleziono recenzji dla tej książki.'}), 404

    # Przygotowanie danych recenzji do odpowiedzi JSON
    reviews_data = [
        {
            'user_id': review.user_id,
            'text': review.text,
            'rating': review.rating,
            'date': review.date.strftime("%Y-%m-%d %H:%M:%S"),
            'status': review.status
        } for review in reviews
    ]

    # Zwrócenie danych recenzji
    return jsonify(reviews_data)


@api_blueprint.route('/pending_reviews', methods=['GET'])
@login_required
def pending_reviews():
    if current_user.role != 'pracownik':
        return jsonify({'error': 'Tylko pracownicy mogą przeglądać oczekujące recenzje.'}), 403

    pending_reviews = db_session.query(Review).filter_by(status='oczekująca').all()
    reviews_data = [
        {
            'id': review.id,
            'book_id': review.book_id,
            'user_id': review.user_id,
            'text': review.text,
            'rating': review.rating,
            'date': review.date.strftime("%Y-%m-%d %H:%M:%S")
        } for review in pending_reviews
    ]

    return jsonify(reviews_data)


@api_blueprint.route('/approve_review/<int:review_id>', methods=['POST'])
@login_required
def approve_review(review_id):
    if current_user.role != 'pracownik':
        return jsonify({'error': 'Tylko pracownicy mogą zarządzać recenzjami.'}), 403

    data = request.json
    decision = data.get('decision')  # Może być 'zatwierdzona' lub 'odrzucona'

    review = db_session.query(Review).filter_by(id=review_id).first()
    if not review:
        return jsonify({'error': 'Recenzja nie została znaleziona.'}), 404

    if decision not in ['zatwierdzona', 'odrzucona']:
        return jsonify({'error': 'Nieprawidłowa decyzja.'}), 400

    review.status = decision
    db_session.commit()

    return jsonify({'message': f'Recenzja została {decision}.'})


@api_blueprint.route('/reports/most_borrowed_books', methods=['GET'])
@login_required
def most_borrowed_books():
    if current_user.role != 'pracownik':
        return jsonify({'error': 'Brak uprawnień.'}), 403

    try:
        # Zapytanie do bazy danych
        most_borrowed_books_query = db_session.query(
            Book.title, Book.author, func.count(Loan.id).label('loan_count')
        ).join(BookCopy, Book.id == BookCopy.book_id
               ).join(Loan, BookCopy.id == Loan.book_id
                      ).group_by(Book.id
                                 ).order_by(func.count(Loan.id).desc()
                                            ).limit(5).all()

        # Przekształcenie wyników do formatu JSON
        report_data = [
            {'title': title, 'author': author, 'loan_count': loan_count}
            for title, author, loan_count in most_borrowed_books_query
        ]

        return jsonify(report_data)

    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500


@api_blueprint.route('/reports/loan_statistics', methods=['GET'])
@login_required
def loan_statistics():
    if current_user.role != 'pracownik':
        return jsonify({'error': 'Brak uprawnień.'}), 403

    try:
        # Statystyki wypożyczeń dla wszystkich książek
        loan_stats = db_session.query(
            Book.title, func.count(Loan.id).label('loan_count')
        ).join(BookCopy, Book.id == BookCopy.book_id
        ).join(Loan, BookCopy.id == Loan.book_id
        ).group_by(Book.title
        ).order_by(func.count(Loan.id).desc()
        ).all()

        # Konwersja wyników do formatu JSON
        statistics = [
            {'title': title, 'loan_count': loan_count} for title, loan_count in loan_stats
        ]

        return jsonify({'loan_statistics': statistics})

    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500


@api_blueprint.route('/reports/book_ratings', methods=['GET'])
@login_required
def book_ratings():
    if current_user.role != 'pracownik':
        return jsonify({'error': 'Brak uprawnień.'}), 403

    try:
        # Zbieranie średnich ocen dla każdej książki
        book_ratings = db_session.query(
            Book.title,
            func.avg(Review.rating).label('average_rating'),
            func.count(Review.id).label('review_count')
        ).join(Review, Book.id == Review.book_id
        ).group_by(Book.title
        ).having(func.count(Review.id) > 1).all()

        # Sortowanie wyników na podstawie średniej oceny i liczby recenzji
        top_rated_books = sorted(
            book_ratings,
            key=lambda x: (x[1], x[2]),
            reverse=True
        )[:3]

        lowest_rated_books = sorted(
            book_ratings,
            key=lambda x: (x[1], -x[2])
        )[:3]

        # Konwersja wyników do formatu JSON
        report_data = {
            'top_rated_books': [
                {'title': title, 'average_rating': round(average_rating, 2)}
                for title, average_rating, _ in top_rated_books
            ],
            'lowest_rated_books': [
                {'title': title, 'average_rating': round(average_rating, 2)}
                for title, average_rating, _ in lowest_rated_books
            ]
        }

        return jsonify(report_data)

    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500


@api_blueprint.route('/books/<int:book_id>')
def get_book_details(book_id):
    book = db_session.query(Book).get(book_id)
    if book is None:
        return jsonify({'error': 'Książka nie znaleziona.'}), 404

    # Sprawdzenie dostępności książki
    available_copies = db_session.query(BookCopy).filter_by(book_id=book_id, status='dostępna').all()
    book_available = len(available_copies) > 0

    reviews = db_session.query(Review).filter_by(book_id=book_id).all()

    # Generowanie pełnego URL obrazu okładki z tokenem SAS
    if book.cover_image_url:
        sas_token = "sp=racwdli&st=2024-01-29T10:33:40Z&se=2024-03-16T18:33:40Z&sv=2022-11-02&sr=c&sig=P%2BAs66xZZqJDkAW1t8nhmNICIuvbo7bsDBZSWf%2F%2FMFc%3D"
        cover_image_url_with_sas = f"{book.cover_image_url}?{sas_token}"
    else:
        cover_image_url_with_sas = None

    book_details = {
        'book_id': book.id,
        'ISBN': book.ISBN,
        'title': book.title,
        'author': book.author,
        'genre': book.genre,
        'description': book.description,
        'publication_year': book.publication_year,
        'quantity': book.quantity,
        'available': book_available,
        'cover_image_url': cover_image_url_with_sas,
        'reviews': [
            {'rating': review.rating, 'text': review.text, 'date': review.date.strftime("%Y-%m-%d %H:%M:%S")}
            for review in reviews
        ]
    }
    return jsonify(book_details)


@api_blueprint.route('/add_employee', methods=['POST'])
@login_required
def add_employee():
    # Sprawdzenie, czy aktualny użytkownik ma rolę administratora
    if current_user.role != 'administrator':
        return jsonify({'error': 'Brak uprawnień.'}), 403

    # Pobranie danych z żądania
    data = request.json
    name = data.get('name')
    surname = data.get('surname')
    email = data.get('email')
    password = data.get('password')


    # Sprawdzenie, czy użytkownik już istnieje
    existing_user = db_session.query(User).filter_by(email=email).first()
    if existing_user:
        return jsonify({'error': 'Użytkownik z podanym adresem e-mail już istnieje'}), 409

    # Tworzenie nowego użytkownika z rolą 'pracownik'
    hashed_password = generate_password_hash(password, method='sha256')
    new_employee = User(
        name=name,
        surname=surname,
        email=email,
        password=hashed_password,
        role='pracownik'
    )
    db_session.add(new_employee)
    db_session.commit()

    return jsonify({'success': True, 'message': 'Pracownik został pomyślnie dodany.'}), 201


@api_blueprint.route('/users-delete')
@login_required
def api_users_delete():
    query = db_session.query(User)
    if current_user.role == 'pracownik':
        query = query.filter_by(role='czytelnik')

    users_data = []
    for user in query.all():
        active_loans = db_session.query(Loan).filter(
            Loan.user_id == user.id,
            Loan.status != 'zakończone'
        ).first()
        has_active_loans = active_loans is not None
        users_data.append({
            'id': user.id,
            'name': user.name,
            'surname': user.surname,
            'email': user.email,
            'role': user.role,
            'has_active_loans': has_active_loans if user.role == 'czytelnik' else None
        })

    return jsonify(users_data)


@api_blueprint.route('/delete_user/<int:user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    # Tylko administrator może usuwać użytkowników
    if current_user.role != 'administrator':
        return jsonify({'error': 'Brak uprawnień.'}), 403

    # Pobranie użytkownika do usunięcia
    user_to_delete = db_session.query(User).get(user_id)
    if user_to_delete is None:
        return jsonify({'error': 'Użytkownik nie został znaleziony.'}), 404

    # Sprawdzenie, czy użytkownik ma aktywne wypożyczenia
    active_loans = db_session.query(Loan).filter(
        Loan.user_id == user_id,
        Loan.status != 'zakończone'
    ).first()

    if active_loans:
        return jsonify({'error': 'Nie można usunąć użytkownika z aktywnymi wypożyczeniami.'}), 400

    # Usunięcie użytkownika
    db_session.delete(user_to_delete)
    db_session.commit()
    return jsonify({'message': 'Użytkownik został usunięty.'}), 200