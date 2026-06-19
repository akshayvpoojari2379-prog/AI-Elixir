import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv

load_dotenv()

user = os.getenv("POSTGRES_USER")
password = os.getenv("POSTGRES_PASSWORD")
host = os.getenv("POSTGRES_HOST")
port = os.getenv("POSTGRES_PORT")
db_name = os.getenv("POSTGRES_DB")

try:
    # Connect to the default 'postgres' database
    conn = psycopg2.connect(dbname='postgres', user=user, password=password, host=host, port=port)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    # Create database
    cursor.execute(f"CREATE DATABASE {db_name};")
    print(f"Database '{db_name}' created successfully!")
    
    cursor.close()
    conn.close()
except psycopg2.errors.DuplicateDatabase:
    print(f"Database '{db_name}' already exists.")
except Exception as e:
    print(f"Error creating database: {e}")

try:
    # Connect to the new database and create pgvector extension
    conn = psycopg2.connect(dbname=db_name, user=user, password=password, host=host, port=port)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    print("pgvector extension created successfully!")
    
    cursor.close()
    conn.close()
except Exception as e:
    print(f"Error creating pgvector extension: {e}")
