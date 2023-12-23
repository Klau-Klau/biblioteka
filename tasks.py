

@celery_app.task
def generate_payment_reminders():
    overdue_loans = db_session.query(Loan).filter(
        Loan.status == 'w trakcie',
        Loan.due_date < datetime.now()
    ).all()
    for loan in overdue_loans:
        # Obliczenie opłaty
        days_overdue = (datetime.now() - loan.due_date).days - 5
        fee = max(0, ((days_overdue // 10) + 1) * 5)
        if fee > 0 and days_overdue % 10 == 6:
            book = db_session.query(Book).get(loan.book_id)
            reminder_content = f"Masz do zapłaty {fee} zł za książkę {book.title}"
            # Dodajemy przypomnienie o zapłacie
            new_reminder = Reminder(
                user_id=loan.user_id,
                book_id=loan.book_id,
                date_of_sending=datetime.now(),
                type='zapłata'
            )
            db_session.add(new_reminder)
    db_session.commit()
