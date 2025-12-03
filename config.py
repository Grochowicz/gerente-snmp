"""
Configuração mínima: não usamos mais SQLAlchemy nem PostgreSQL.
Os dados são mantidos em CSVs em `app/data` e acessados por `app.storage`.
"""
import os

BASE_DIR = os.path.dirname(__file__)
CSV_DATA_DIR = os.path.join(BASE_DIR, "app", "data")

# DEBUG flag para desenvolvimento local
DEBUG = True
