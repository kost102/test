from flask import Flask, request, jsonify, make_response
import sqlite3
from datetime import datetime
import os
import json

app = Flask(__name__)

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
    
    if not data or 'type' not in data or 'message' not in data:
        return jsonify({"error": "Missing required fields"}), 400
    
    try:
        conn = sqlite3.connect('commands.db')
        c = conn.cursor()
        
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
    """DayZ сервер забирает невыполненные команды - КОМПАКТНЫЙ JSON"""
    try:
        conn = sqlite3.connect('commands.db')
        c = conn.cursor()
        
        c.execute("SELECT id, type, message FROM commands WHERE executed = 0")
        commands = c.fetchall()
        
        c.execute("UPDATE commands SET executed = 1 WHERE executed = 0")
        conn.commit()
        conn.close()
        
        # Формируем массив команд
        commands_array = []
        for cmd in commands:
            commands_array.append({
                "id": cmd[0],
                "type": cmd[1],
                "message": cmd[2]
            })
        
        # Создаем компактный JSON БЕЗ ПРОБЕЛОВ
        # {"commands":[{"id":1,"type":"say","message":"текст"}]}
        result = {
            "commands": commands_array
        }
        
        # separators=(',', ':') убирает все пробелы между элементами
        # ensure_ascii=False сохраняет русский текст
        response_data = json.dumps(result, ensure_ascii=False, separators=(',', ':'))
        
        response = make_response(response_data)
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        
        print(f"📤 Отправляем: {response_data}")
        return response
        
    except Exception as e:
        print(f"❌ Error getting commands: {e}")
        return jsonify({"error": str(e), "commands": []}), 500

@app.route('/dayz/status', methods=['GET'])
def status():
    try:
        conn = sqlite3.connect('commands.db')
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM commands WHERE executed = 0")
        pending = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM commands")
        total = c.fetchone()[0]
        conn.close()
        
        result = {
            "status": "online",
            "pending": pending,
            "total": total
        }
        
        response_data = json.dumps(result, ensure_ascii=False, separators=(',', ':'))
        response = make_response(response_data)
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
