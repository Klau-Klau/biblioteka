from datetime import datetime, timedelta
from celery import Celery
from celery.schedules import crontab
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from database_setup import engine, Loan, Payment, User, Reminder
from sqlalchemy import select, func, or_

# Konfiguracja Celery
celery_app = Celery('tasks', broker='redis://redis:6379/0')
celery_app.conf.timezone = 'Europe/Warsaw'

@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        crontab(hour=22, minute=26),
        update_loan_statuses_task.s(),
    )


def update_loan_statuses():
    try:
        with Session(engine) as session:
            # Aktualizacja statusów na "książka przetrzymana" dla przekroczeń terminu zwrotu
            session.execute(text(
                "UPDATE loans SET status = 'książka przetrzymana' WHERE due_date < current_date() AND status = 'w trakcie'"
            ))
            session.commit()
            print("Statusy pożyczek z przekroczonym terminem zwrotu zostały zaktualizowane na 'książka przetrzymana'.")
    except OperationalError as e:
        print(f"Wystąpił błąd operacyjny: {e}")



@celery_app.task()
def update_loan_statuses_task():
    update_loan_statuses()
    add_overdue_payments()
    create_payment_notifications()
    create_return_reminders()


def calculate_fine(due_date, current_date):
    """Oblicz opłatę za przetrzymanie książki na podstawie liczby dni po terminie zwrotu."""
    days_overdue = (current_date - due_date).days
    if days_overdue <= 5:
        return 5
    else:
        additional_fine = ((days_overdue - 5) // 10) * 5
        return 5 + additional_fine


def add_overdue_payments():
    with Session(engine) as session:
        overdue_loans = select(Loan).where(
        Loan.due_date < datetime.now(),
        Loan.status == 'książka przetrzymana'
        )
        for loan in session.execute(overdue_loans).scalars():
            # Oblicz opłatę
            fine_amount = calculate_fine(loan.due_date, datetime.now())
            # Sprawdź, czy istnieje już opłata dla tego wypożyczenia
            existing_payment = select(func.count(Payment.id)).where(
                Payment.user_id == loan.user_id,
                Payment.book_copy_id == loan.book_id,  # Zaktualizowano
                Payment.status != 'opłacona'
            )

            if session.execute(existing_payment).scalar() == 0:
                # Stwórz nową opłatę, jeśli nie istnieje
                new_payment = Payment(
                    user_id=loan.user_id,
                    book_copy_id=loan.book_id,  # Zaktualizowano
                    amount=fine_amount,
                    status='oczekująca'
                )
                session.add(new_payment)

            # Zatwierdź zmiany
        session.commit()


def create_payment_notifications():
    with Session(engine) as session:
        # Sprawdzenie nowych płatności od ostatniego uruchomienia zadania
        last_day = datetime.now() - timedelta(days=1)
        new_payments = session.query(Payment).filter(
            Payment.date_of_payment > last_day,
            Payment.status == 'oczekująca'
        ).all()

        for payment in new_payments:
            user = session.query(User).get(payment.user_id)
            if user and user.wants_notifications:
                # Utworzenie przypomnienia
                content = f"Twoja płatność w wysokości {payment.amount} zł została zarejestrowana."
                new_reminder = Reminder(
                    user_id=user.id,
                    book_id=payment.book_copy_id,  # Przypisanie odpowiedniego ID egzemplarza książki
                    date_of_sending=datetime.now(),
                    type='zapłata'
                )
                session.add(new_reminder)

        session.commit()

def create_return_reminders():
    with Session(engine) as session:
        # Oblicz datę, która jest 5 dni od teraz
        five_days_from_now = datetime.now() + timedelta(days=5)

        # Znajdź wszystkie wypożyczenia, których termin zwrotu jest w ciągu najbliższych 5 dni
        loans_due_soon = select(Loan).where(
            Loan.due_date <= five_days_from_now,
            Loan.status == 'w trakcie'
        )

        for loan in session.execute(loans_due_soon).scalars():
            user = session.query(User).get(loan.user_id)
            if user and user.wants_notifications:
                # Utworzenie przypomnienia
                content = f"Przypomnienie: termin zwrotu książki {loan.book_copy.book.title} upływa {loan.due_date.strftime('%Y-%m-%d')}."
                new_reminder = Reminder(
                    user_id=user.id,
                    book_id=loan.book_id,
                    date_of_sending=datetime.now(),
                    type='zwrot'
                )
                session.add(new_reminder)

        session.commit()
