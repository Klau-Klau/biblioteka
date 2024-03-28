from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
import time


Base = declarative_base()

DATABASE_URI = 'mysql+pymysql://root:Maria@host.docker.internal/library'

engine = create_engine(
    DATABASE_URI,
    echo=True,
    pool_size=10,  # Zwiększenie rozmiaru puli połączeń
    max_overflow=20  # Zwiększenie limitu przepełnienia puli połączeń
)

# Funkcja do sprawdzania połączenia
def check_connection(engine, max_attempts=5, delay=3):
    """Spróbuj połączyć się z bazą danych kilka razy z opóźnieniem."""
    for attempt in range(max_attempts):
        try:
            with Session(engine) as session:
                session.execute(text("SELECT 1"))
                print("Połączono z bazą danych.")
                return True  # Połączenie udane
        except OperationalError:
            print(f"Błąd połączenia. Próba {attempt + 1} z {max_attempts}.")
            time.sleep(delay)
    return False

# Wywołanie funkcji sprawdzającej połączenie
if not check_connection(engine):
    print("Nie udało się połączyć z bazą danych.")
    exit(1)


# Sprawdzenie połączenia wykonując zapytanie SELECT
with Session(engine) as session:
    result = session.execute(text("SELECT 1"))
    print(result.one())