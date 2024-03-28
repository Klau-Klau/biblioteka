#Oficjalny obraz Pythona jako obraz bazowegy
FROM python:3.8-slim

# Ustawienie katalogu roboczego w kontenerze
WORKDIR /code

# Skopiowanie pliku requirements.txt do katalogu roboczego w kontenerze
COPY requirements.txt .

# Instalowanie zależności za pomocą pip
RUN pip install --no-cache-dir -r requirements.txt

# Kopiowanie zawartość lokalnego katalogu src do katalogu roboczego w kontenerze
COPY . .

# Kontener nasłuchuje na porcie 5000 w czasie wykonywania
EXPOSE 5000

# Uruchomienie flask_app.py przy starcie kontenera
CMD ["python", "flask_app.py"]