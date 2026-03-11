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
    
    # Создаем таблицу без комментариев в SQL
    c.execute('''CREATE TABLE IF NOT EXISTS commands
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  type TEXT,
                  message TEXT,
                  steam_id TEXT,
                  item TEXT,
                  count INTEGER DEFAULT 1,
                  created_at TIMESTAMP,
                  executed INTEGER DEFAULT 0)''')
    
    # Проверяем и добавляем новые колонки, если их нет
    try:
        c.execute("SELECT steam_id FROM commands LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE commands ADD COLUMN steam_id TEXT")
    
    try:
        c.execute("SELECT item FROM commands LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE commands ADD COLUMN item TEXT")
    
    try:
        c.execute("SELECT count FROM commands LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE commands ADD COLUMN count INTEGER DEFAULT 1")
    
    conn.commit()
    conn.close()
    print("Database initialized with give command support")

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
    
    if not data or 'type' not in data:
        return jsonify({"error": "Missing required fields"}), 400
    
    try:
        conn = sqlite3.connect('commands.db')
        c = conn.cursor()
        
        # Обработка разных типов команд
        if data['type'] == 'say':
            if 'message' not in data:
                return jsonify({"error": "Message required for say command"}), 400
                
            c.execute(
                "INSERT INTO commands (type, message, created_at) VALUES (?, ?, ?)",
                (data['type'], data['message'], datetime.now())
            )
            print(f"✅ Сохранена say команда: {data['message']}")
            
        elif data['type'] == 'give':
            if 'steam_id' not in data or 'item' not in data:
                return jsonify({"error": "steam_id and item required for give command"}), 400
            
            # Получаем количество (по умолчанию 1)
            count = data.get('count', 1)
            
            c.execute(
                "INSERT INTO commands (type, steam_id, item, count, created_at) VALUES (?, ?, ?, ?, ?)",
                (data['type'], data['steam_id'], data['item'], count, datetime.now())
            )
            print(f"✅ Сохранена give команда: steam_id={data['steam_id']}, item={data['item']}, count={count}")
        
        else:
            # Для неизвестных типов команд
            return jsonify({"error": f"Unknown command type: {data['type']}"}), 400
        
        conn.commit()
        command_id = c.lastrowid
        conn.close()
        
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
        
        # Получаем все невыполненные команды
        c.execute("SELECT id, type, message, steam_id, item, count FROM commands WHERE executed = 0")
        commands = c.fetchall()
        
        # Помечаем как выполненные
        c.execute("UPDATE commands SET executed = 1 WHERE executed = 0")
        conn.commit()
        conn.close()
        
        # Формируем массив команд в зависимости от типа
        commands_array = []
        for cmd in commands:
            cmd_id, cmd_type, message, steam_id, item, count = cmd
            
            if cmd_type == 'say':
                commands_array.append({
                    "id": cmd_id,
                    "type": cmd_type,
                    "message": message
                })
            elif cmd_type == 'give':
                commands_array.append({
                    "id": cmd_id,
                    "type": cmd_type,
                    "steam_id": steam_id,
                    "item": item,
                    "count": count
                })
        
        # Создаем компактный JSON
        result = {
            "commands": commands_array
        }
        
        # separators=(',', ':') убирает все пробелы между элементами
        response_data = json.dumps(result, ensure_ascii=False, separators=(',', ':'))
        
        response = make_response(response_data)
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        
        print(f"📤 Отправляем {len(commands_array)} команд: {response_data}")
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
        
        # Статистика по типам команд
        c.execute("SELECT type, COUNT(*) FROM commands GROUP BY type")
        stats = c.fetchall()
        
        conn.close()
        
        result = {
            "status": "online",
            "pending": pending,
            "total": total,
            "stats": dict(stats)
        }
        
        response_data = json.dumps(result, ensure_ascii=False, separators=(',', ':'))
        response = make_response(response_data)
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

# Добавляем эндпоинт для очистки старых команд (опционально)
@app.route('/dayz/cleanup', methods=['POST'])
def cleanup_old_commands():
    """Удаляет выполненные команды старше 24 часов"""
    try:
        conn = sqlite3.connect('commands.db')
        c = conn.cursor()
        
        c.execute("DELETE FROM commands WHERE executed = 1 AND created_at < datetime('now', '-1 day')")
        deleted = c.rowcount
        
        conn.commit()
        conn.close()
        
        return jsonify({"status": "ok", "deleted": deleted})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
