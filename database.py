from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

# Строка подключения для MySQL на PythonAnywhere
DATABASE_URL = "mysql+pymysql://moeno1337:shedmaster@moeno1337.mysql.pythonanywhere-services.com/moeno1337$default"

# Создание движка и сессии
engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20, pool_timeout=60, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
