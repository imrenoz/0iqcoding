from sqlalchemy import or_, func, null, text, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.testing import db_spec

import crypto_methods  # Модуль с методами шифрования и дешифрования
import models # Модель базы данных

# Получение пользователя по ID
def getUserById(db: Session, user_id) -> models.User:
    # Возможно, стоит использовать .filter(models.User.id == user_id)
    return db.query(models.User).filter_by(id=user_id).first()

# Получение пользователя по имени
def getUserByName(db: Session, username) -> models.User:
    return db.query(models.User).filter_by(username=username.lower()).first()

# Добавление нового пользователя
def addUser(db: Session, username, password):
    user = models.User(
        username=username.lower(),
        password=password
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

# Получение списка пользователя
def getUserCompanions(db: Session, user_id, chats, aes_key):
    sql = f"""
    WITH cte AS (
        SELECT message_id, LEAST(sender, receiver) AS user1, GREATEST(sender, receiver) AS user2, 
               content, message_date, iv
        FROM messages 
        WHERE sender = :s OR receiver = :s
    ),
    cte2 AS (
        SELECT message_id, user1, user2, content, message_date, iv, 
               ROW_NUMBER() OVER (PARTITION BY user1, user2 ORDER BY message_id DESC) AS rn 
        FROM cte
    )
    SELECT message_id, user1, user2, content, message_date, iv 
    FROM cte2 
    WHERE rn = 1 
    ORDER BY message_id DESC;
    """
    try:
        companions = db.execute(text(sql), {'s': user_id})
    except Exception as e:
        print(e)
        return getUserCompanions(db, user_id, chats)  # Рекурсивный вызов, если что-то пошло не так
    companions_json = []
    for companion in companions:
        date = companion[4]
        if companion[1] not in chats:
            sender = getUserById(db, companion[1])
            chats[companion[1]] = sender.username
        if companion[2] not in chats:
            receiver = getUserById(db, companion[2])
            chats[companion[2]] = receiver.username
        companion_id = companion[2] if companion[1] == user_id else companion[1]
        sender_id = companion[1] if companion[1] != user_id else companion[2]
        
        unreadMessages = getChatUnreadMessagesNum(db, sender_id, companion_id)  # Можно обернуть в try-except
        message_date = f"{date.day}.{date.month}.{date.year} {date.hour}:{date.minute}:{date.second}"
        content = crypto_methods.decrypt_message(companion[3], aes_key, companion[5])
        
        message = {
            "not_seen": unreadMessages,
            "companion_id": companion_id,
            "message_id": companion[0],
            "companion_name": chats[companion[1]] if companion[1] != user_id else chats[companion[2]],
            "content": content,
            "message_date": f"{date.day}.{date.month}.{date.year}",
            "message_time": f"{date.hour}:{date.minute}:{date.second}",
            "message_full_date": message_date
        }
        companions_json.append(message)
    return companions_json, chats

# Обозначение чата как прочитанного
def makeChatRead(db: Session, sender_id, user_id):
    db.query(models.Message).filter(models.Message.sender == sender_id).filter(
        models.Message.receiver == user_id).update({'receiver_seen': True})
    try:
        db.commit()
    except:
        db.rollback()

# Получение сообщений чата между двумя пользователями
def getChatMessages(db: Session, first_user, second_user, aes_key, start_limit=0, end_limit=100):
    sql = "select * from messages where (sender=:f and receiver=:s or sender=:s and receiver=:f) " \
          "order by message_id asc"
    messages = db.execute(text(sql), {'f': first_user, 's': second_user, 'el': end_limit, 'sl': start_limit}).all()
    ls = []
    senders = {}
    for message in messages:
        if message[1] not in senders.keys():
            sender = getUserById(db, message[1])
            senders[message[1]] = sender.username
        date = message[4]
        content = crypto_methods.decrypt_message(message[3], aes_key, message[6])
        data = {
            "message_id": message[0],
            "sender_name": senders[message[1]],
            "sender_id": message[1],
            "owner": "you" if int(second_user) == message[1] else "other",
            "content": content,
            "message_day": f"{date.day}.{date.month}.{date.year}",
            "message_time": f"{date.hour}:{'0' if date.minute<10 else ''}{date.minute}"
        }
        ls.append(data)
    return ls


def getChatNewMessages(db: Session, first_user, second_user, start_limit=0, end_limit=100, last_msg_id=0):
    sql = "select * from messages where (sender=:f and receiver=:s or sender=:s and receiver=:f) and message_id>:l " \
          "order by message_id asc"
    try:
        messages = db.execute(text(sql), {'f': first_user, 's': second_user, 'el': end_limit, 'sl': start_limit,
                                          'l': last_msg_id}).all()
    except:
        return getChatMessages(db, first_user, second_user, start_limit, end_limit)
    ls = []
    senders = {}
    for message in messages:
        if message[1] not in senders.keys():
            sender = getUserById(db, message[1])
            senders[message[1]] = sender.username
        date = message[4]
        data = {
            "message_id": message[0],
            "sender_name": senders[message[1]],
            "sender_id": message[1],
            "owner": "you" if int(second_user) == message[1] else "other",
            "content": message[3],
            "message_day": f"{date.day}.{date.month}.{date.year}",
            "message_time": f"{date.hour}:{date.minute}"
        }
        ls.append(data)
    return ls


def addMessage(db: Session, sender, receiver, content, iv):
    try:
        message = models.Message(sender=sender, receiver=receiver, content=content, iv=iv)
        db.add(message)
        db.commit()
        db.refresh(message)
        return message
    except Exception as e:
        print(e)
        db.rollback()

# Получение списка пользователей с именем, похожим на заданное
def getUsersLike(db: Session, name):
    sql = "select * from users where lower(username) like lower(:n) limit 5"
    l = []
    ls = db.execute(text(sql), {'n': name}).all()
    for user in ls:
        message = {
            "companion_id": user[0],
            "companion_name": user[1],
            "content": "",
        }
        l.append(message)
    return l

# Получение количества непрочитанных сообщений
def getChatUnreadMessagesNum(db: Session, receiver_id, sender_id):
    ls = db.query(models.Message).filter(models.Message.sender == sender_id).filter(
        models.Message.receiver == receiver_id) \
        .filter(or_(models.Message.receiver_seen == null(), models.Message.receiver_seen == False)).all()
    return len(ls)

# Добавление файла
def addFile(db: Session, file: models.File)->models.File|None:
    db.add(file)
    db.commit()
    db.refresh(file)
    return file

# Проверка доступа пользователя к файлу
def getFile(db: Session, file_id)-> models.File | None:
    return db.query(models.File).filter_by(id=file_id).first()

def getAccess(db: Session, file_id, user_id)->bool:
    return db.query(models.Access).filter_by(file_id=file_id, user_id=user_id).first()

def getUserFiles(db: Session, user_id):
    sql = 'select file_name, owner, volume, files.id from accesses join files on files.id = file_id where user_id = :u'
    return db.execute(text(sql),{'u':user_id}).all()


def getUsers(db: Session, user_id=None)->[models.User]:
    if user_id:
        return db.query(models.User).filter(models.User.id!=user_id).all()
    else:
        return db.query(models.User).all()
