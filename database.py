from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config import settings

SQLALCHEMY_DATABASE_URL = 'postgresql://' + settings.POSTGRES_USER + ':' + settings.POSTGRES_PASSWORD + '@' + settings.POSTGRES_HOSTNAME + "/" + settings.POSTGRES_DB

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()