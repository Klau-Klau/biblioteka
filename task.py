from celery import Celery
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

# Konfiguracja Celery
celery_app = Celery('tasks', broker='redis://redis:6379/0')


# Konfiguracja połączenia z bazą danych
DATABASE_URI = 'mysql+pymysql://root:Maria@db/library'
engine = create_engine(DATABASE_URI)

def update_loan_statuses():
    try:
        with Session(engine) as session:
            # Aktualizacja statusów na "zakończone"
            session.execute(text("UPDATE loans SET status = 'zakończone' WHERE status != 'zakończone'"))
            session.commit()
            print("Wszystkie statusy zostały zaktualizowane na 'zakończone'.")
    except OperationalError as e:
        print(f"Wystąpił błąd operacyjny: {e}")


@celery_app.task()
def update_loan_statuses_task():
    update_loan_statuses()


