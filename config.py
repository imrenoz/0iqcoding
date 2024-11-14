from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pydantic import BaseSettings

# Класс для загрузки настроек из .env файла
class Settings(BaseSettings):
    DATABASE_PORT: int
    POSTGRES_PASSWORD: str
    POSTGRES_USER: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_HOSTNAME: str

    class Config:
        env_file = '.env'  # Указываем, что настройки должны загружаться из .env файла

settings = Settings()

# Формируем строку подключения к базе данных
SQLALCHEMY_DATABASE_URL = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@" \
                          f"{settings.POSTGRES_HOST}:{settings.DATABASE_PORT}/{settings.POSTGRES_DB}?sslmode=require"

# Создание SQLAlchemy движка и сессии
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
