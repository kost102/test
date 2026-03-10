from flask import Flask, request, jsonify
import sqlite3
import threading
from datetime import datetime

app = Flask(__name__)

# Инициализация БД
def init_db():
    conn = sqlite3.connect('commands.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS commands
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  type TEXT,
                  message TEXT,
                  player_name TEXT,
                  created_at TIMESTAMP,
                  executed INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

init_db()

# Токен для Discord бота
BOT_TOKEN = "secret_token_123"

@app.route('/discord', methods=['POST'])
def discord_webhook():
    """Discord бот отправляет команды сюда"""
    auth = request.headers.get('Authorization')
    if auth != f'Bearer {BOT_TOKEN}':
        return 'Unauthorized', 401

    data = request.json
    print(f"Получена команда: {data}")
    
    # Сохраняем в БД
    conn = sqlite3.connect('commands.db')
    c = conn.cursor()
    c.execute("INSERT INTO commands (type, message, player_name, created_at) VALUES (?, ?, ?, ?)",
              (data.get('type'), data.get('message'), data.get('player'), datetime.now()))
    conn.commit()
    conn.close()
    
    return jsonify({"status": "ok", "id": c.lastrowid})

@app.route('/dayz/get_commands', methods=['GET'])
def get_commands():
    """DayZ сервер забирает невыполненные команды"""
    conn = sqlite3.connect('commands.db')
    c = conn.cursor()
    
    # Получаем все невыполненные команды
    c.execute("SELECT id, type, message, player_name FROM commands WHERE executed = 0")
    commands = c.fetchall()
    
    # Отмечаем их как выполненные
    c.execute("UPDATE commands SET executed = 1 WHERE executed = 0")
    conn.commit()
    conn.close()
    
    # Форматируем ответ как в GameLabs
    result = {
        "commands": [
            {
                "id": cmd[0],
                "type": cmd[1],
                "message": cmd[2],
                "player": cmd[3]
            } for cmd in commands
        ]
    }
    
    return jsonify(result)

@app.route('/dayz/status', methods=['GET'])
def status():
    """Проверка статуса сервера"""
    conn = sqlite3.connect('commands.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM commands WHERE executed = 0")
    pending = c.fetchone()[0]
    conn.close()
    
    return jsonify({
        "status": "online",
        "pending_commands": pending,
        "version": "1.0"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)