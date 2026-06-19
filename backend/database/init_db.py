import os
import sys

# Add backend directory to path
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

from database.session import engine
from database.models import Base

def init_database():
    print("Initializing Enterprise Workflow Operating System database tables...")
    Base.metadata.create_all(bind=engine)
    print("All enterprise operational tables initialized successfully in PostgreSQL!")

if __name__ == "__main__":
    init_database()
