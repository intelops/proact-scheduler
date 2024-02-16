from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

def get_postgres_db_url():

    # Try to read the environment variable
    host = os.getenv('PROACT_PG_HOST', 'localhost')
    port = os.getenv('PROACT_PG_PORT', '5432')
    user = os.getenv('PROACT_PG_USER', 'postgres')
    password = os.getenv('PROACT_PG_PASSWORD', 'password')
    database = os.getenv('PROACT_PG_DATABASE', 'scsctl')

    url = f"postgresql://{user}:{password}@{host}:{port}/{database}"

    return url

SQLALCHEMY_DATABASE_URL = get_postgres_db_url()
engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

