import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()


def get_db_url() -> str:
    url = os.environ.get("SPECTRA_DB_URL")
    if not url:
        sys.exit(
            "Missing SPECTRA_DB_URL.\n"
            "Copy .env.example to .env and fill in real values."
        )
    return url


engine = create_engine(get_db_url())
SessionLocal = sessionmaker(bind=engine)


def get_session() -> Session:
    return SessionLocal()
