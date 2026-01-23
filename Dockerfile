# Utilise une image Python légère
FROM python:3.12-slim

# Définit le dossier de travail dans le conteneur
WORKDIR /app

# Copie le fichier des dépendances
COPY requirements.txt .

# Installe les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Copie tout le reste du code (bot.py, .env, etc.)
COPY . .

# Commande de lancement
CMD ["python", "bot.py"]