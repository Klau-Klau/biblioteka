# Użyj oficjalnego obrazu Pythona jako obrazu bazowego
FROM python:3.8-slim

# Ustaw katalog roboczy w kontenerze
WORKDIR /code

# Skopiuj plik requirements.txt do katalogu roboczego w kontenerze
COPY requirements.txt .

# Zainstaluj zależności za pomocą pip
RUN pip install --no-cache-dir -r requirements.txt

# Skopiuj zawartość lokalnego katalogu src do katalogu roboczego w kontenerze
COPY . .

# Poinformuj Docker, że kontener nasłuchuje na porcie 5000 w czasie wykonywania
EXPOSE 5000

# Uruchom app.py przy starcie kontenera
CMD ["python", "app.py"]