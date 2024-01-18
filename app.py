from flask import Flask, flash, request, jsonify, send_file, redirect
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from database_setup import User, engine, Book, Reservation, Loan, BookCopy, Notification, Reminder, Review, CartItem, \
    Recommendation, Payment, Media
from sqlalchemy.orm import scoped_session, sessionmaker, joinedload, aliased
from datetime import datetime, timedelta
from sqlalchemy import func, or_
import stripe
from flask_cors import CORS
import re
from azure.storage.blob import BlobServiceClient
from mimetypes import guess_type


# Inicjalizacja klienta usługi Azure Blob Storage
connection_string = "DefaultEndpointsProtocol=https;AccountName=bibliotekaklaudia;AccountKey=KW+qSFOSstEbbeDs4QrZgSHHYkicem3ZG2iJr2QQ3Rv5DqAmIuqjYN1xBLR/FBP0uM1PYMrSPS7q+AStzSH0Ig==;EndpointSuffix=core.windows.net"
blob_service_client = BlobServiceClient.from_connection_string(connection_string)


stripe.api_key = 'sk_test_51OXsZtIG0JJr5IMEd4HYvEZU8ZOb3VEBfVEa4MrndczndI1kT1FQaVDsm9GAmBLg2NLzsq3Kov6YCQH2jdV4YcSJ00rmkIM4uW'


template_dir = os.path.abspath('./app/templates')
app = Flask(__name__, template_folder=template_dir)
app.secret_key = 'tajny_klucz'


# Ustawienia Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_api'

CORS(app, supports_credentials=True, origins=["http://localhost:8080"])


# Ustawienia bazy danych
db_session = scoped_session(sessionmaker(bind=engine))



@login_manager.user_loader
def load_user(user_id):
    return db_session.query(User).get(int(user_id))


@app.route('/api/books')
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


@app.route('/api/login', methods=['POST'])
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
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 401

@app.route('/api/register', methods=['POST'])
def register_api():
    if current_user.is_authenticated:
        # Przekieruj zalogowanych użytkowników
        return jsonify({'success': False, 'error': 'User already logged in'}), 400

    # Pobranie danych z żądania JSON
    data = request.json
    name = data.get('name')
    surname = data.get('surname')
    email = data.get('email')
    password = data.get('password')

    # Prosta walidacja imienia i nazwiska
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


    # Tworzenie nowego użytkownika
    hashed_password = generate_password_hash(password, method='sha256')
    new_user = User(
        name=name,
        surname=surname,
        email=email,
        password=hashed_password,
        role='czytelnik'  # Zakładając, że każdy nowy użytkownik ma rolę 'czytelnik'
    )
    db_session.add(new_user)
    db_session.commit()

    # Odpowiedź po pomyślnej rejestracji
    return jsonify({'success': True, 'message': 'Account successfully created'}), 201


@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'success': True, 'message': 'Zostałeś wylogowany.'}), 200


@app.route('/api/search_books', methods=['GET'])
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

    results = [
        {
            "book_id": book.id,
            "title": book.title,
            "author": book.author,
            "genre": book.genre,
            "year": book.publication_year,
            "available": any(copy.status == 'dostępna' for copy in book.book_copies)
            # Dodaj więcej informacji według potrzeb
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


@app.route('/api/add_to_cart', methods=['POST'])
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



@app.route('/api//update_cart_quantity/<int:book_copy_id>', methods=['POST'])
@login_required
def update_cart_quantity(book_copy_id):
    data = request.json
    new_quantity = data.get('quantity')

    if not str(new_quantity).isdigit() or int(new_quantity) < 1:
        flash('Nieprawidłowa ilość.', 'danger')
        return jsonify({'error': 'Nieprawidłowa ilość.'}), 400

    new_quantity = int(new_quantity)

    # Pobierz book_id z book_copy_id
    book_copy = db_session.query(BookCopy).get(book_copy_id)
    if not book_copy:
        flash('Nie znaleziono egzemplarza książki.', 'danger')
        return jsonify({'error': 'Nie znaleziono egzemplarza książki.'}), 404
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


@app.route('/api/reservation_cart', methods=['GET'])
@login_required
def get_reservation_cart():
    # Zapytanie, aby zwracać listę book_copy_id dla każdej książki
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


@app.route('/api/reservation_cart', methods=['POST'])
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
        flash(f'Egzemplarze książki "{book_title}" zostały zarezerwowane.', 'success')

        # Zwrócenie komunikatów o wyniku operacji w formacie JSON
        return jsonify({'messages': response_messages})


@app.after_request
def add_header(response):
    response.cache_control.no_store = True
    return response

@app.route('/api/remove_from_cart/<int:book_id>', methods=['POST'])
@login_required
def remove_from_cart(book_id):
    # Usuń wszystkie egzemplarze książki z koszyka
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



@app.route('/api/reserve_book', methods=['POST'])
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


@app.route('/api//mark_as_loan', methods=['POST'])
@login_required
def loan_book():
    if current_user.role != 'pracownik':
        return jsonify({'status': 'error', 'message': 'Tylko pracownicy mogą wypożyczać książki.'}), 403

    data = request.get_json()
    copy_id = data.get('copy_id')

    book_copy = db_session.query(BookCopy).filter_by(id=copy_id, status='do odbioru').first()
    if not book_copy:
        return jsonify({'status': 'error', 'message': 'Nie można wypożyczyć tej książki.'}), 400

    reservation = db_session.query(Reservation).filter_by(book_id=copy_id, status='aktywna').first()
    if reservation:
        reservation.status = 'zakończona'
        user_id = reservation.user_id
    else:
        return jsonify({'status': 'error', 'message': 'Brak aktywnej rezerwacji dla tego egzemplarza.'}), 400

    book_copy.status = 'wypożyczona'
    due_date = datetime.now() + timedelta(days=90)

    new_loan = Loan(
        user_id=user_id,
        book_id=copy_id,
        status='w trakcie',
        due_date=due_date
    )
    db_session.add(new_loan)
    db_session.commit()

    return jsonify({'status': 'success', 'message': 'Książka została wypożyczona.'})


@app.route('/api/my_books')
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

    return jsonify({
        'reserved_books': reserved_books_data,
        'loaned_books': loaned_books_data
    })


@app.route('/api/add_book', methods=['POST'])
@login_required
def add_book():
    if current_user.role != 'pracownik':
        return jsonify({'status': 'error', 'message': 'Tylko pracownicy mogą dodać książki.'}), 403

    data = request.get_json()
    isbn = data.get('isbn')
    title = data.get('title')
    author = data.get('author')
    genre = data.get('genre')
    description = data.get('description')
    publication_year = data.get('publication_year')
    quantity = int(data.get('quantity', 1))

    existing_book = db_session.query(Book).filter_by(ISBN=isbn).first()
    if existing_book:
        book_id = existing_book.id
        message = 'Liczba egzemplarzy książki została zaktualizowana.'
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
        db_session.flush()
        book_id = new_book.id
        message = f'Książka {title} została pomyślnie dodana.'

    for _ in range(quantity):
        new_copy = BookCopy(book_id=book_id, status='dostępna')
        db_session.add(new_copy)

    db_session.commit()
    return jsonify({'status': 'success', 'message': message})


@app.route('/api/edit_book/<int:book_id>', methods=['GET', 'POST'])
@login_required
def edit_book(book_id):
    if current_user.role != 'pracownik':
        return jsonify({'status': 'error', 'message': 'Tylko pracownicy mogą edytować książki.'}), 403

    book = db_session.query(Book).get(book_id)
    if book is None:
        return jsonify({'status': 'error', 'message': 'Książka nie została znaleziona.'}), 404

    if request.method == 'POST':
        data = request.get_json()
        book.ISBN = data.get('isbn')
        book.title = data.get('title')
        book.author = data.get('author')
        book.genre = data.get('genre')
        book.description = data.get('description')
        book.publication_year = data.get('publication_year')

        db_session.commit()
        return jsonify({'status': 'success', 'message': 'Książka została zaktualizowana.'})

    # GET - zwróć dane książki w formacie JSON
    return jsonify({
        'isbn': book.ISBN,
        'title': book.title,
        'author': book.author,
        'genre': book.genre,
        'description': book.description,
        'publication_year': book.publication_year
    })


@app.route('/api/manage_books')
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
            # Dodaj więcej pól według potrzeb
            'copies': [{
                'id': copy.id,
                'status': copy.status,
                # Możesz dodać więcej szczegółów o kopiach
            } for copy in book.book_copies]
        }
        books_json.append(book_data)

    return jsonify(books_json)


@app.route('/api/return_book/<int:copy_id>', methods=['POST'])
@login_required
def return_book(copy_id):
    if current_user.role != 'pracownik':
        return jsonify({'error': 'Tylko pracownicy mogą zarządzać zwrotami książek.'}), 403

    # Znajdź egzemplarz książki na podstawie ID
    book_copy = db_session.query(BookCopy).get(copy_id)
    if not book_copy:
        return jsonify({'error': 'Egzemplarz książki nie został znaleziony.'}), 404

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
        return jsonify({'message': f'Egzemplarz książki "{book_copy.book.title}" został zwrócony i jest teraz dostępny.'})
    else:
        return jsonify({'warning': 'Brak aktywnego wypożyczenia dla tego egzemplarza książki.'})

@app.route('/api/delete_book/<int:copy_id>', methods=['POST'])
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

    # Sprawdź, czy są inne egzemplarze tej książki
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

@app.route('/api/book_ready_for_pickup/<int:copy_id>', methods=['POST'])
@login_required
def book_ready_for_pickup(copy_id):
    if current_user.role != 'pracownik':
        return jsonify({'error': 'Brak uprawnień.'}), 403

    book_copy = db_session.query(BookCopy).get(copy_id)
    if not book_copy:
        return jsonify({'error': 'Egzemplarz książki nie został znaleziony.'}), 404

    if book_copy.status != 'zarezerwowana':
        return jsonify({'error': 'Egzemplarz nie jest w statusie zarezerwowanej.'}), 400

    user_id = book_copy.reservations[-1].user_id
    user = db_session.query(User).get(user_id)
    if user and user.wants_notifications:
        book_copy.status = 'do odbioru'
        db_session.commit()

        new_reminder = Reminder(
            user_id=user_id,
            book_id=copy_id,
            date_of_sending=datetime.now(),
            type='odbiór'
        )
        db_session.add(new_reminder)
        db_session.commit()
        return jsonify({'message': 'Książka jest gotowa do odbioru.'})
    else:
        return jsonify({'info': 'Użytkownik zrezygnował z otrzymywania powiadomień.'})


@app.route('/api/user_profile/<int:user_id>', methods=['GET'])
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


@app.route('/api/edit_user/<int:user_id>', methods=['POST'])
@login_required
def api_edit_user(user_id):
    # Uproszczona logika dla API
    user = db_session.query(User).get(user_id)
    if user is None:
        return jsonify({'error': 'Użytkownik nie został znaleziony.'}), 404

    if current_user.id != user_id and current_user.role != 'pracownik':
        return jsonify({'error': 'Nie masz uprawnień do edycji tego użytkownika.'}), 403

    data = request.get_json()
    user.name = data['name']
    user.surname = data['surname']

    # Pracownik nie może edytować swojego emaila
    if not current_user.role == 'pracownik':
        user.email = data['email']
        user.wants_notifications = data.get('wants_notifications', user.wants_notifications)

    if data.get('password'):
        user.password = generate_password_hash(data['password'])

    db_session.commit()
    return jsonify({'message': 'Dane użytkownika zostały zaktualizowane.'})


@app.route('/api/edit_user/<int:user_id>', methods=['GET'])
@login_required
def get_user_data(user_id):
    user = db_session.query(User).get(user_id)
    if user is None:
        return jsonify({'error': 'Użytkownik nie został znaleziony.'}), 404

    is_editing_self = current_user.id == user_id
    is_staff = current_user.role == 'pracownik'
    is_target_user_staff = user.role == 'pracownik'

    # Sprawdź uprawnienia do edycji profilu
    if not is_staff and not is_editing_self:
        return jsonify({'error': 'Nie masz uprawnień do edycji tego użytkownika.'}), 403

    # Zwróć dane użytkownika w formacie JSON
    user_data = {
        'id': user.id,
        'name': user.name,
        'surname': user.surname,
        'email': user.email if not is_target_user_staff else '', # Pracownik nie widzi swojego emaila
        'role': user.role,
        'is_editing_self': is_editing_self,
        'is_staff': is_staff,
        'is_target_user_staff': is_target_user_staff
    }

    return jsonify(user_data)


@app.route('/api/notifications')
@login_required
def api_notifications():
    if current_user.role != 'czytelnik':
        return jsonify({'error': 'Tylko czytelnicy mogą przeglądać powiadomienia.'}), 403

    user_notifications = db_session.query(Notification).filter_by(user_id=current_user.id).all()
    user_reminders = db_session.query(Reminder).filter_by(user_id=current_user.id).all()

    # Konwersja danych na format JSON
    notifications_data = [{'content': n.content, 'date_of_sending': n.date_of_sending.strftime('%Y-%m-%d %H:%M:%S')} for n in user_notifications]
    reminders_data = [{'type': r.type, 'title': r.book_copy.book.title, 'date_of_sending': r.date_of_sending.strftime('%Y-%m-%d %H:%M:%S')} for r in user_reminders]

    return jsonify({'notifications': notifications_data, 'reminders': reminders_data})


@app.route('/api/send_notification', methods=['POST'])
@login_required
def api_send_notification():
    if current_user.role != 'pracownik':
        return jsonify({'error': 'Tylko pracownicy mogą wysyłać powiadomienia.'}), 403

    data = request.json
    user_id = data.get('user_id')
    content = data.get('content')

    # Walidacja danych itp.

    new_notification = Notification(user_id=user_id, content=content)
    db_session.add(new_notification)
    db_session.commit()

    return jsonify({'message': 'Powiadomienie zostało wysłane.'})

@app.route('/api/users')
@login_required
def api_users():
    users = db_session.query(User).filter_by(wants_notifications=True).all()
    users_data = [{'id': user.id, 'name': user.name} for user in users]
    return jsonify(users_data)


@app.route('/api/user_debt/<int:user_id>', methods=['GET'])
@login_required
def get_user_debt(user_id):
    # Alias dla Loan
    loan_alias = aliased(Loan)

    # Złączenie tabel i obliczenie długu
    total_debt = db_session.query(func.sum(Payment.amount)) \
        .join(loan_alias, Payment.book_copy_id == loan_alias.book_id) \
        .join(BookCopy, loan_alias.book_id == BookCopy.id) \
        .filter(
        Payment.user_id == user_id,
        Payment.status == 'oczekująca',
        loan_alias.status == 'zakończone',
        loan_alias.return_date.isnot(None)
    ).scalar()

    # Pobieranie ID płatności
    payment_ids = db_session.query(Payment.id) \
        .join(loan_alias, Payment.book_copy_id == loan_alias.book_id) \
        .join(BookCopy, loan_alias.book_id == BookCopy.id) \
        .filter(
        Payment.user_id == user_id,
        Payment.status == 'oczekująca',
        loan_alias.status == 'zakończone',
        loan_alias.return_date.isnot(None)
    ).all()

    payment_ids = [payment.id for payment in payment_ids]  # Konwersja na listę ID

    return jsonify({'total_debt': total_debt or 0, 'payment_ids': payment_ids})


@app.route('/api/update_multiple_payments', methods=['POST'])
@login_required
def update_multiple_payments_status():
    data = request.json
    print("Otrzymane dane:", data)

    payment_ids = data.get('paymentIds')
    new_status = data.get('status', 'opłacona')

    if not payment_ids or not isinstance(payment_ids, list) or not all(isinstance(id, int) for id in payment_ids):
        return jsonify({'error': 'paymentIds musi być listą identyfikatorów (liczb całkowitych).'}), 400

    try:
        # Pobierz wszystkie płatności, które chcesz zaktualizować
        payments = db_session.query(Payment).filter(Payment.id.in_(payment_ids)).all()

        if payments:
            # Zaktualizuj statusy dla wszystkich znalezionych płatności
            for payment in payments:
                payment.status = new_status

            db_session.commit()
            return jsonify({'message': f'Statusy dla {len(payments)} płatności zostały zaktualizowane.'}), 200
        else:
            return jsonify({'error': 'Żadna płatność nie została znaleziona dla podanych identyfikatorów.'}), 404
    except Exception as e:
        db_session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/get_media', methods=['GET'])
def get_media():
    media_items = db_session.query(Media).all()
    media_data = [
        {
            "id": item.id,
            "media_type": item.media_type,
            "file_url": item.file_url,
            "title": item.title,
            "author": item.author,
            "publish_year": item.publish_year,
            "genre": item.genre,
            "description": item.description
        } for item in media_items
    ]
    return jsonify(media_data)


@app.route('/api/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        flash('Brak pliku w żądaniu')
        return redirect(request.url)

    file = request.files['file']
    if file.filename == '':
        flash('Nie wybrano pliku')
        return redirect(request.url)

    if file:
        blob_client = blob_service_client.get_blob_client(container="biblioteka", blob=file.filename)
        blob_client.upload_blob(file)

        # Odbieranie danych formularza
        media_type = request.form['media_type']
        title = request.form['title']
        author = request.form['author']
        publish_year = request.form['publish_year']
        genre = request.form['genre']
        description = request.form['description']

        # Weryfikacja, czy media_type to 'ebook' lub 'audiobook'
        if media_type not in ['ebook', 'audiobook']:
            return jsonify({"message": "Nieprawidłowy typ mediów."}), 400

        # Tworzenie nowego rekordu Media
        new_media = Media(
            media_type=media_type,
            file_url=blob_client.url,
            title=title,
            author=author,
            publish_year=publish_year,
            genre=genre,
            description=description
        )
        db_session.add(new_media)
        db_session.commit()

        return jsonify({"message": "Plik został przesłany.", "file_url": blob_client.url})


@app.route('/api/download/<filename>', methods=['GET'])
def download_file(filename):
    blob_client = blob_service_client.get_blob_client(container="biblioteka", blob=filename)
    download_stream = blob_client.download_blob()

    # Pobierz typ MIME na podstawie nazwy pliku
    mimetype = guess_type(filename)[0]

    # Sprawdź, czy typ MIME jest znany, w przeciwnym razie ustaw domyślny
    if mimetype is None:
        mimetype = 'application/octet-stream'

    # Ustaw nazwę pliku do pobrania
    download_name = os.path.basename(filename)

    return send_file(
        download_stream,
        mimetype=mimetype,
        as_attachment=True,
        download_name=download_name
    )


# To powinno być na samym końcu pliku
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)