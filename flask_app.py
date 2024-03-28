from flask import Flask, jsonify
from flask_login import LoginManager, login_required, current_user
import os
from database_setup import *
from sqlalchemy.orm import scoped_session, sessionmaker
import stripe
from flask_cors import CORS
from azure.storage.blob import BlobServiceClient
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
import numpy as np
import logging

from app.models import *


# Konfiguracja logowania
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    from app.routes.api import api_blueprint
    # Inicjalizacja klienta usługi Azure Blob Storage
    connection_string = "DefaultEndpointsProtocol=https;AccountName=bibliotekaklaudia;AccountKey=KW+qSFOSstEbbeDs4QrZgSHHYkicem3ZG2iJr2QQ3Rv5DqAmIuqjYN1xBLR/FBP0uM1PYMrSPS7q+AStzSH0Ig==;EndpointSuffix=core.windows.net"
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)


    stripe.api_key = 'sk_test_51OXsZtIG0JJr5IMEd4HYvEZU8ZOb3VEBfVEa4MrndczndI1kT1FQaVDsm9GAmBLg2NLzsq3Kov6YCQH2jdV4YcSJ00rmkIM4uW'

    template_dir = os.path.abspath('./app/templates')
    app = Flask(__name__, template_folder=template_dir)
    app.secret_key = 'tajny_klucz'
    app.register_blueprint(api_blueprint, url_prefix='/api')
    app.blob_service_client = blob_service_client


    # Ustawienia Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'api.login_api'

    CORS(app, supports_credentials=True, origins=["*"])


    # Ustawienia bazy danych
    db_session = scoped_session(sessionmaker(bind=engine))



    @login_manager.user_loader
    def load_user(user_id):
        return db_session.query(User).get(int(user_id))


    def create_ratings_matrix(user_ratings, other_ratings):
        # Słownik, gdzie kluczami są krotki (user_id, book_id)
        ratings_dict = {(r.user_id, r.book_id): r.rating for r in user_ratings + other_ratings}

        # Tworzenie ramki danych z tego słownika
        ratings_df = pd.DataFrame(list(ratings_dict.items()), columns=['user_book', 'rating'])
        ratings_df['user_id'], ratings_df['book_id'] = zip(*ratings_df.user_book)

        # Tworzenie tabeli przestawnej, która jest macierzą ocen użytkownik-książka
        ratings_matrix = ratings_df.pivot_table(index='user_id', columns='book_id', values='rating')

        # Zastąpienie NaN zerami, ponieważ brak oceny jest interpretowany jako 0
        ratings_matrix = ratings_matrix.fillna(0)

        return ratings_matrix


    def predict_ratings(similarity_matrix, ratings_matrix):
        # Przekształcenie macierzy pandas w macierz numpy
        ratings_np = ratings_matrix.values
        sim_np = similarity_matrix

        # Przewidywanie ocen przez obliczenie średniej ważonej
        # Używanie macierzy podobieństwa jako wag
        # Ignorowanie zer w macierzy ocen, ponieważ oznaczają one brak oceny
        user_ratings_mean = np.true_divide(ratings_np.sum(1), (ratings_np != 0).sum(1))
        ratings_diff = (ratings_np - user_ratings_mean[:, np.newaxis])
        ratings_diff[ratings_np == 0] = 0  # Zastąpienie zer w macierzy różnic, aby nie wpływały na wynik
        print("user_ratings_mean shape:", user_ratings_mean[:, np.newaxis].shape)
        print("sim_np shape:", sim_np.shape)
        print("ratings_diff shape:", ratings_diff.shape)
        print("sum shape:", np.array([np.abs(sim_np).sum(axis=1)]).T.shape)

        # Używanie macierzy podobieństwa jako wag do obliczenia przewidywanej oceny
        pred = user_ratings_mean[:, np.newaxis] + sim_np.dot(ratings_diff) / np.array([np.abs(sim_np).sum(axis=1)]).T
        pred = np.nan_to_num(pred)  # Zastąpienie NaN zerami

        # Przekształcenie wyników z powrotem do ramki danych
        predicted_ratings = pd.DataFrame(pred, columns=ratings_matrix.columns, index=ratings_matrix.index)

        return predicted_ratings


    def select_top_books(predicted_ratings, user_loans):
        # Znajdowanie identyfikatorów książek, które użytkownik już wypożyczył lub ocenił
        user_loaned_book_ids = {loan.book_id for loan in user_loans}

        # Filtrowanie przewidywanych ocen, usuwając książki, które użytkownik już wypożyczył
        filtered_ratings = predicted_ratings.drop(columns=user_loaned_book_ids, errors='ignore')

        # Szukanie książki z najwyższymi przewidywanymi ocenami, które nie są jeszcze wypożyczone
        top_books = filtered_ratings.idxmax(axis=1).sort_values(ascending=False).index.tolist()

        # Zwracanie listy identyfikatorów książek
        return top_books


    def calculate_similarity(ratings_matrix):
        # Obliczanie podobieństwa kosinusowego między wszystkimi parami użytkowników
        similarity = cosine_similarity(ratings_matrix)

        # Wypełnienie przekątnej macierzy wartościami NaN, aby uniknąć autorekomendacji
        np.fill_diagonal(similarity, np.nan)

        return similarity


    @app.route('/api/recommendations', methods=['GET'])
    @login_required
    def generate_recommendations():
        try:
            user_id = current_user.id
            logger.info(f"Generating recommendations for user: {user_id}")

            # Pobranie recenzji dla użytkownika
            user_reviews = db_session.query(Review).filter_by(user_id=user_id).all()
            logger.info(f"User reviews retrieved: {user_reviews}")

            # Utworzenie macierzy ocen wyłącznie na podstawie ocen użytkownika
            ratings_matrix = create_ratings_matrix(user_reviews, [])

            # Obliczenie podobieństwo między użytkownikami na podstawie ocen użytkownika
            similarity_matrix = calculate_similarity(ratings_matrix)

            # Przewidywanie ocen dla nieocenionych książek
            predicted_ratings = predict_ratings(similarity_matrix, ratings_matrix)

            # Pobranie wypożyczeń użytkownika
            user_loans = db_session.query(Loan).filter_by(user_id=user_id).all()
            logger.info(f"User loans retrieved: {user_loans}")

            # Wybieranie książek z najwyższymi przewidywanymi ocenami
            recommended_book_ids = select_top_books(predicted_ratings, user_loans)
            logger.info(f"Recommended book IDs: {recommended_book_ids}")

            # Pobranie szczegółów książek
            recommended_books = db_session.query(Book).filter(Book.id.in_(recommended_book_ids)).all()

            recommended_books_json = [
                {
                    "book_id": book.id,
                    "title": book.title,
                    "author": book.author,
                    "genre": book.genre,
                    "publication_year": book.publication_year
                }
                for book in recommended_books
            ]

            return jsonify(recommended_books=recommended_books_json)

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}", exc_info=True)
            return jsonify({'error': 'Internal server error'}), 500


    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=5000, debug=True)

    for rule in app.url_map.iter_rules():
        logger.info(f"{rule.endpoint}: {rule}")

    return app

app = create_app()