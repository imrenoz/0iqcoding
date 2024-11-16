import io
import json
import os
from hashlib import sha256
from io import BytesIO

from flask import Flask, render_template, session, abort, redirect, request, send_from_directory, url_for, Response, jsonify
from flask_sock import Sock
from flask_cors import CORS
from gevent.pywsgi import WSGIServer

import models
import service, crypto_methods
from database import engine, SessionLocal

# Экземпляр Flask приложения
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'kefN@oaiwadsdasda')
app.config['SOCK_SERVER_OPTIONS'] = {'ping_interval': 25}
app.config['OUTER_WS'] = {}
app.config['INNER_WS'] = {}
app.config['SELECTED'] = {}
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    "postgres://default:nRZIbqiPp0g8@ep-spring-cell-a4gw15l7.us-east-1.aws.neon.tech:5432/verceldb?sslmode=require"
)
app.config['AES_KEY'] = "abcdefghijklmnopqrstuvwxyz123456".encode()
app.config['UPLOAD_FOLDER'] = './uploads'
app.config['TEMP_FOLDER'] = './temp'

# Настройка CORS для разрешения запросов с Vercel
CORS(app, resources={r"/*": {"origins": "*"}})

WebSocket = Sock(app)
models.Base.metadata.create_all(bind=engine)
db = SessionLocal()

chats = {}

# API для поиска пользователей через HTTP-запросы
@app.route('/api/search', methods=['GET'])
def api_search():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])  # Возвращаем пустой список при отсутствии запроса
    users = service.getUsersLike(db, f"%{query}%")
    return jsonify(users)

# Обновление сессии пользователя
def updateSession():
    try:
        if session.get('user') is None:
            abort(401)
        else:
            user_id = session.get('user').get('id')
            rooms = app.config['INNER_WS']
            if rooms.get(user_id):
                rooms.pop(user_id)
            user = service.getUserById(db, user_id)
            if user is None:
                session.clear()
                abort(401)

            session['user'] = user.getInfo()
        session.modified = True
    except Exception as e:
        print(f"Ошибка при обновлении сессии: {e}")
        abort(401)

@app.errorhandler(401)
def redirectToLogin(error):
    return redirect('/login?warning=authorize')

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
    inners = app.config['INNER_WS']
    outers = app.config['OUTER_WS']
    selects = app.config['SELECTED']
    user_id = None
    while True:
        message = wss.receive()
        message = json.loads(message)
        if message['action'] == "connected":
            user_id = message['id']
            inners[user_id] = wss
            selects[user_id] = id
            service.makeChatRead(db, id, message['id'])
            messages = service.getChatMessages(db, id, message['id'], app.config['AES_KEY'])
            wss.send(json.dumps(messages))
        elif message['action'] == "send_message":
            content, iv = crypto_methods.encrypt_message(message['text'], app.config['AES_KEY'])
            msg = service.addMessage(db, sender=user_id, receiver=id, content=content, iv=iv)
            companion = outers.get(id)
            if companion:
                companion_wss = inners[id]
                companion_wss.send(json.dumps([{
                    "message_id": msg.message_id,
                    "sender_id": user_id,
                    "content": message['text']
                }]))
            wss.send(json.dumps([{
                "message_id": msg.message_id,
                "sender_id": user_id,
                "content": message['text']
            }]))

# Маршруты для авторизации и других страниц остаются без изменений
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

if __name__ == '__main__':
    app.run(port=8000, debug=True)
