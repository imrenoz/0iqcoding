from sqlalchemy import Column, ForeignKey, Integer, String, Date, Boolean, DateTime, func, Float, Text, LargeBinary
from sqlalchemy.orm import relationship
from database import Base

# Модель юзера
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), nullable=False, unique=True)
    password = Column(Text, nullable=False)

    def getInfo(self):
        return {"id": self.id, "username": self.username, "password": self.password}

# Модель сообщения
class Message(Base):
    __tablename__ = 'messages'
    message_id = Column(Integer, autoincrement=True, primary_key=True)
    sender = Column(Integer, ForeignKey('users.id'), index=True)  # Индекс для поиска сообщений по отправителю
    receiver = Column(Integer, ForeignKey('users.id'), index=True)  # Индекс для поиска сообщений по получателю
    content = Column(LargeBinary, nullable=False)
    message_date = Column(DateTime(timezone=True), server_default=func.now(), index=True)  # Индекс для времени сообщений
    receiver_seen = Column(Boolean, default=False)  # Статус прочтения сообщения получателем (по умолчанию False)
    iv = Column(LargeBinary, nullable=False)  # Вектор инициализации для шифрования сообщения

    # Связь с пользователем
    sender_user = relationship("User", foreign_keys=[sender])
    receiver_user = relationship("User", foreign_keys=[receiver])

# Модель файла
class File(Base):
    __tablename__ = 'files'
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey('messages.message_id'))
    file_name = Column(String(255), nullable=False)
    owner = Column(Integer, ForeignKey('users.id'))
    volume = Column(Integer, nullable=False)  # Объем файла в байтах
    uploadTime = Column(DateTime, server_default=func.now())  # Дата и время загрузки файла

    # Связь с сообщением и пользователем
    message = relationship("Message", backref="files")
    user = relationship("User", foreign_keys=[owner])

# Модель доступа к файлам
class Access(Base):
    __tablename__ = 'accesses'
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey('files.id'))  # ID файла, к которому предоставляется доступ
    user_id = Column(Integer, ForeignKey('users.id'))  # ID пользователя, которому предоставлен доступ к файлу

    # Связи с файлами и пользователями
    file = relationship("File", backref="accesses")
    user = relationship("User", backref="accesses")
