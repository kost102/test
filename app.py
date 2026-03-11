from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False  # Для русского текста

# Инициализация БД
def init_db():
    conn = sqlite3.connect('commands.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS commands
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  type TEXT,
                  message TEXT,
                  created_at TIMESTAMP,
                  executed INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()
    print("Database initialized")

init_db()

# Токен для Discord бота
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'secret_token_123')

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "online",
        "message": "Discord-DayZ Bridge API",
        "endpoints": {
            "discord": "/discord (POST)",
            "get_commands": "/dayz/get_commands (GET)",
            "status": "/dayz/status (GET)"
        }
    })

@app.route('/discord', methods=['POST'])
def discord_webhook():
    auth = request.headers.get('Authorization')
    if auth != f'Bearer {BOT_TOKEN}':
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    
    # Валидация
    if not data or 'type' not in data or 'message' not in data:
        return jsonify({"error": "Missing required fields"}), 400
    
    try:
        conn = sqlite3.connect('commands.db')
        c = conn.cursor()
        
        # ИСПРАВЛЕНО: теперь 3 знака вопроса для 3 колонок
        c.execute(
            "INSERT INTO commands (type, message, created_at) VALUES (?, ?, ?)",
            (data['type'], data['message'], datetime.now())
        )
        
        conn.commit()
        command_id = c.lastrowid
        conn.close()
        
        print(f"✅ Сохранена команда: {data['type']} - {data['message']}")
        return jsonify({"status": "ok", "id": command_id})
        
    except Exception as e:
        print(f"❌ Error saving command: {e}")
        return jsonify({"error": "Database error"}), 500

@app.route('/dayz/get_commands', methods=['GET'])
def get_commands():
    """DayZ сервер забирает невыполненные команды"""
    try:
        conn = sqlite3.connect('commands.db')
        c = conn.cursor()
        
        # Получаем все невыполненные команды
        c.execute("SELECT id, type, message FROM commands WHERE executed = 0")
        commands = c.fetchall()
        
        # Отмечаем их как выполненные
        c.execute("UPDATE commands SET executed = 1 WHERE executed = 0")
        conn.commit()
        conn.close()
        
        # Форматируем ответ
        result = {
            "commands": [
                {
                    "id": cmd[0],
                    "type": cmd[1],
                    "message": cmd[2]
                } for cmd in commands
            ]
        }
        
        print(f"📤 Отправлено команд DayZ: {len(commands)}")
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ Error getting commands: {e}")
        return jsonify({"error": str(e), "commands": []}), 500

@app.route('/dayz/status', methods=['GET'])
def status():
    """Проверка статуса сервера"""
    try:
        conn = sqlite3.connect('commands.db')
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM commands WHERE executed = 0")
        pending = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM commands")
        total = c.fetchone()[0]
        conn.close()
        
        return jsonify({
            "status": "online",
            "pending_commands": pending,
            "total_commands": total,
            "version": "1.0"
        })
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
