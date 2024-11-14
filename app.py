import io
import json
import os
from hashlib import sha256
from io import BytesIO

from flask import Flask, render_template, session, abort, redirect, request, send_from_directory, after_this_request, \
    url_for, send_file, Response
from flask_sock import Sock # Подключение библиотеки для работы с WebSocket
from gevent.pywsgi import WSGIServer
from hashlib import sha256

import models
import service, crypto_methods
from database import engine, SessionLocal

# Экземпляр Flask приложения
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'default_secret_key')
app.config['SOCK_SERVER_OPTIONS'] = {'ping_interval': 25}
app.config['OUTER_WS'] = {}
app.config['INNER_WS'] = {}
app.config['SELECTED'] = {}
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("postgres://default:nRZIbqiPp0g8@ep-spring-cell-a4gw15l7.us-east-1.aws.neon.tech:5432/verceldb?sslmode=require")
app.config['AES_KEY'] = "abcdefghijklmnopqrstuvwxyz123456".encode() # Ключ для шифрования
app.config['UPLOAD_FOLDER'] = './uploads' # Папка для загрузки файлов
app.config['TEMP_FOLDER'] = './temp'  # Временная папка для файлов

WebSocket = Sock(app) # Инициализация WebSocket
models.Base.metadata.create_all(bind=engine) # Создание таблиц в базе данных
db = SessionLocal() # Инициализация сессии базы данных

chats = {}


@app.route('/')
def main():
    updateSession()
    user = session.get('user')
    return render_template('index.html', user=user)

# Чат
@app.route('/chat')
def chat():
    updateSession()
    user = session.get('user')
    return render_template('chat.html', user=user)

# Хранение файлов
@app.route('/storage')
def storage():
    updateSession()
    user = session.get('user')
    files = service.getUserFiles(db, user['id'])
    ls = []
    owner_ls = {}
    for file in files:
        print(file)
        if file[1] not in owner_ls.keys():
            owner = service.getUserById(db, file[1])
            owner_ls[file[1]] = owner.username
        volume = getFileVolume(file[2])
        ls.append(
            {'file_id': file[3], 'filename': file[0], 'owner': owner_ls[file[1]], 'volume': volume})
    users = service.getUsers(db, user['id'])
    return render_template('newStorage.html', files=ls, user=user, users=users)

# Функция для конвертации объема файла
def getFileVolume(volume_bytes):
    levels = {0: 'Bytes', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    level = 0
    while volume_bytes >= 1024:
        volume_bytes /= 1024
        level += 1
    return f"{round(volume_bytes, 2)} {levels.get(level)}"


@app.route("/file/<id>")
def showFile(id):
    updateSession()

    return redirect(url_for('login'))


@app.route('/login', methods=["POST", "GET"])
def login():
    user = session.get('user')
    if user:
        return redirect('/')
    if request.method == 'GET':
        warning = request.args.get('warning')
        warnings = {'notExist': "Пользователь не существует или неправильный пароль",
                    'authorize': "Авторизуйтесь для получения доступа!"}
        return render_template('login.html', warning=warnings.get(warning))
    else:
        username = request.form.get('username')
        password = request.form.get('password')
        encoded_password = sha256((password).encode('UTF-8')).hexdigest()
        user = service.getUserByName(db, username)
        if not user:
            return redirect('/login?warning=notExist')
        if user.password != encoded_password:
            return redirect('/login?warning=notExist')
        if user.password == encoded_password:
            session['login'] = True
            session['user'] = user.getInfo()
            return redirect('/')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


@app.route('/register', methods=['POST', "GET"])
def register():
    user = session.get('user')
    if user:
        return redirect('/')
    if request.method == 'GET':
        warning = request.args.get('warning')
        warnings = {'exist': "Пользователь с таким логином уже существует!"}
        return render_template('register.html', warning=warnings.get(warning))
    else:
        username = request.form.get('username')
        password = request.form.get('password')
        encoded_password = sha256((password).encode('UTF-8')).hexdigest()
        user = service.getUserByName(db, username)
        if user:
            return redirect('/register?warning=exist')
        user = service.addUser(db, username, encoded_password)
        session['login'] = True
        session['user'] = user.getInfo()
        return redirect('/')


@app.route('/upload_file', methods=['POST'])
def upload_file():
    updateSession()
    user = session.get('user')
    file = request.files.get('file')
    has_access_users = request.form.get('users')
    password = request.form.get('password')
    upload = os.path.join(app.config.get('UPLOAD_FOLDER'), str(user['id']))
    if not os.path.exists(upload):
        os.mkdir(upload)
    if file.filename != '':
        try:
            volume = crypto_methods.encrypt_file(file, os.path.join(upload, file.filename),
                                                 createAesHash(password).encode())
            newFile = models.File(
                file_name=file.filename,
                owner=user['id'],
                volume=volume
            )
            newFile = service.addFile(db, newFile)
            access = models.Access(
                file_id=newFile.id,
                user_id=user['id']
            )
            db.add(access)
            if has_access_users:
                for u in has_access_users:
                    access = models.Access(
                        file_id=newFile.id,
                        user_id=int(u)
                    )
                    db.add(access)
            db.commit()
        except Exception as e:
            print(e)

    return redirect('/storage')

# Вспомогательная функция для хеширования пароля AES
def createAesHash(password):
    hashed_pass = sha256((password).encode('utf-8')).hexdigest()
    return hashed_pass[0:32]


@app.route('/download/<id>')
def download_file(id):
    updateSession()
    user = session.get('user')
    file = service.getFile(db, file_id=id)
    password = request.args['password']
    if not file:
        abort(404)
    access = service.getAccess(db, file.id, user['id'])
    if not access:
        abort(403)
    uploads = os.path.join(app.config.get('UPLOAD_FOLDER'), str(file.owner))
    temps = os.path.join(app.config.get('TEMP_FOLDER'), str(user['id']))
    if not os.path.exists(temps):
        os.mkdir(temps)
    try:
        crypto_methods.decrypt_file(os.path.join(uploads, file.file_name), os.path.join(temps, file.file_name),
                                    createAesHash(password).encode())
        return send_from_directory(temps, file.file_name, as_attachment=True)
    except ValueError:
        return send_from_directory(uploads, file.file_name, as_attachment=True)

# Обработка ошибок 401 -Перенаправление на страницу входа
@app.errorhandler(401)
def redirectToLogin(error):
    return redirect('/login?warning=authorize')

# Обновление сессии пользователя
def updateSession():
    if session.get('user') is None:
        print("REDIRECTING")
        abort(401)
    else:
        user_id = session.get('user').get('id')
        rooms = app.config['INNER_WS']
        if rooms.get(user_id):
            rooms.pop(user_id)
        user = service.getUserById(db, user_id)
        if user is None:
            if session.get('login'):
                session.pop('login')
            if session.get('user'):
                session.pop('user')
            session.modified = True
            abort(401)

        session['user'] = user.getInfo()
    session.modified = True

# WebSocket для обмена сообщениями
@WebSocket.route('/<id>')
def sendMessage(ws, id):
    global chats
    id = int(id)
    rooms = app.config['INNER_WS']
    clients = app.config['OUTER_WS']
    private = app.config['SELECTED']
    clients[id] = ws
    if private.get(id) is not None:
        private.pop(id)
    while True:
        message = ws.receive()
        message = json.loads(message)
        if message['action'] == "connected":
            companions, updatedChat = service.getUserCompanions(db, id, chats, app.config['AES_KEY'])
            chats = updatedChat
            ws.send(f"companions|{json.dumps(companions)}")
        if message['action'] == "search":
            if message['message'] != "":
                people = service.getUsersLike(db, f"%{message['message']}%")
                ws.send(f"users|{json.dumps(people)}")

# WebSocket для получения диалога
@WebSocket.route('/private/<id>')
def getDialog(wss, id):
    global chats
    id = int(id)
    ls = []
    inners = app.config['INNER_WS']
    outers = app.config['OUTER_WS']
    selects = app.config['SELECTED']
    ws = None
    user_id = None
    last = None
    while True:
        new = False
        message = wss.receive()
        message = json.loads(message)
        if message['action'] == "connected":
            user_id = message['id']
            ws = outers.get(user_id)
            inners[user_id] = wss
            selects[user_id] = id
            service.makeChatRead(db, id, message['id'])
            messages = service.getChatMessages(db, id, message['id'], app.config['AES_KEY'])
            companions, updatedChat = service.getUserCompanions(db, user_id, chats, app.config['AES_KEY'])
            chats = updatedChat
            ws.send(f"companions|{json.dumps(companions)}")
            wss.send(json.dumps(messages))
        elif message['action'] == "send_message":
            content, iv = crypto_methods.encrypt_message(message['text'], app.config['AES_KEY'])
            msg = service.addMessage(db, sender=user_id, receiver=id, content=content, iv=iv)
            date = msg.message_date
            companion = outers.get(id)
            newMessage = {
                "message_id": msg.message_id,
                "sender_name": message['username'],
                "sender_id": msg.sender,
                "companion_id": msg.receiver,
                "owner": "you",
                "content": message['text'],
                "message_day": f"{date.day}.{date.month}.{date.year}",
                "message_time": f"{date.hour}:{date.minute}"
            }
            if companion is not None:
                if user_id == selects.get(id):
                    msg.receiver_seen = True
                    db.commit()
                    companion_wss = inners[id]
                    newMessage['owner'] = 'other'
                    companion_wss.send(json.dumps([newMessage]))
                user_id = message['id']
                # companion chat
                companions, updatedChat = service.getUserCompanions(db, id, chats, app.config['AES_KEY'])
                chats = updatedChat
                companion.send(f"companions|{json.dumps(companions)}")

            # user chat
            companions, updatedChat = service.getUserCompanions(db, user_id, chats, app.config['AES_KEY'])
            chats = updatedChat
            ws.send(f"companions|{json.dumps(companions)}")
            newMessage['owner'] = 'you'
            wss.send(json.dumps([newMessage]))


if __name__ == '__main__':
    if not app.secret_key:
        app.secret_key = "kefN@oaiwadsdasda"
    app.run(port=8000, debug=True)


