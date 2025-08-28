import sqlite3
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                subscription_type TEXT DEFAULT 'free',
                subscription_expires TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Loggers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS loggers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                unique_id TEXT UNIQUE,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # IP logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ip_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                logger_id INTEGER,
                ip_address TEXT,
                user_agent TEXT,
                telegram_user_id INTEGER,
                telegram_username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (logger_id) REFERENCES loggers (id)
            )
        ''')
        
        # Admins table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY
            )
        ''')
        
        conn.commit()
        conn.close()
    
    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        def _get_user():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, username, first_name, subscription_type, 
                       subscription_expires, created_at
                FROM users WHERE user_id = ?
            ''', (user_id,))
            row = cursor.fetchone()
            conn.close()
            return row
        
        loop = asyncio.get_event_loop()
        row = await loop.run_in_executor(None, _get_user)
        
        if row:
            return {
                'user_id': row[0],
                'username': row[1],
                'first_name': row[2],
                'subscription_type': row[3],
                'subscription_expires': row[4],
                'created_at': row[5]
            }
        return None
    
    async def create_user(self, user_id: int, username: str, first_name: str):
        """Create new user"""
        def _create_user():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, username, first_name)
                VALUES (?, ?, ?)
            ''', (user_id, username, first_name))
            conn.commit()
            conn.close()
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _create_user)
    
    async def update_subscription(self, user_id: int, subscription_type: str, duration_days: int):
        """Update user subscription"""
        def _update_subscription():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if subscription_type == 'forever':
                expires = datetime.now() + timedelta(days=36500)  # 100 years
            else:
                expires = datetime.now() + timedelta(days=duration_days)
            
            cursor.execute('''
                UPDATE users 
                SET subscription_type = ?, subscription_expires = ?
                WHERE user_id = ?
            ''', (subscription_type, expires, user_id))
            conn.commit()
            conn.close()
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _update_subscription)
    
    async def create_logger(self, user_id: int, unique_id: str, name: str) -> bool:
        """Create new logger"""
        def _create_logger():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check user's current logger count
            cursor.execute('SELECT COUNT(*) FROM loggers WHERE user_id = ? AND is_active = TRUE', (user_id,))
            current_count = cursor.fetchone()[0]
            
            # Get user subscription info
            cursor.execute('SELECT subscription_type, subscription_expires FROM users WHERE user_id = ?', (user_id,))
            user_info = cursor.fetchone()
            
            if not user_info:
                conn.close()
                return False
            
            subscription_type, expires = user_info
            
            # Check limits
            limit = 10 if subscription_type != 'free' and expires and datetime.fromisoformat(expires) > datetime.now() else 3
            
            if current_count >= limit:
                conn.close()
                return False
            
            # Create logger
            cursor.execute('''
                INSERT INTO loggers (user_id, unique_id, name)
                VALUES (?, ?, ?)
            ''', (user_id, unique_id, name))
            
            conn.commit()
            conn.close()
            return True
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _create_logger)
    
    async def get_user_loggers(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all loggers for user"""
        def _get_loggers():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, unique_id, name, created_at, is_active
                FROM loggers WHERE user_id = ? ORDER BY created_at DESC
            ''', (user_id,))
            rows = cursor.fetchall()
            conn.close()
            return rows
        
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(None, _get_loggers)
        
        return [
            {
                'id': row[0],
                'unique_id': row[1],
                'name': row[2],
                'created_at': row[3],
                'is_active': row[4]
            }
            for row in rows
        ]
    
    async def delete_logger(self, logger_id: int, user_id: int) -> bool:
        """Delete logger"""
        def _delete_logger():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE loggers SET is_active = FALSE 
                WHERE id = ? AND user_id = ?
            ''', (logger_id, user_id))
            success = cursor.rowcount > 0
            conn.commit()
            conn.close()
            return success
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _delete_logger)
    
    async def log_ip(self, logger_id: str, ip_address: str, user_agent: str, 
                     telegram_user_id: int = None, telegram_username: str = None):
        """Log IP address"""
        def _log_ip():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get logger by unique_id
            cursor.execute('SELECT id FROM loggers WHERE unique_id = ? AND is_active = TRUE', (logger_id,))
            logger_row = cursor.fetchone()
            
            if not logger_row:
                conn.close()
                return False
            
            actual_logger_id = logger_row[0]
            
            cursor.execute('''
                INSERT INTO ip_logs (logger_id, ip_address, user_agent, telegram_user_id, telegram_username)
                VALUES (?, ?, ?, ?, ?)
            ''', (actual_logger_id, ip_address, user_agent, telegram_user_id, telegram_username))
            
            conn.commit()
            conn.close()
            return True
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _log_ip)
    
    async def get_logger_stats(self, logger_id: int) -> Dict[str, Any]:
        """Get logger statistics"""
        def _get_stats():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM ip_logs WHERE logger_id = ?', (logger_id,))
            total_logs = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT ip_address, telegram_username, created_at 
                FROM ip_logs 
                WHERE logger_id = ? 
                ORDER BY created_at DESC 
                LIMIT 10
            ''', (logger_id,))
            recent_logs = cursor.fetchall()
            
            conn.close()
            return total_logs, recent_logs
        
        loop = asyncio.get_event_loop()
        total_logs, recent_logs = await loop.run_in_executor(None, _get_stats)
        
        return {
            'total_logs': total_logs,
            'recent_logs': [
                {
                    'ip_address': log[0],
                    'telegram_username': log[1],
                    'created_at': log[2]
                }
                for log in recent_logs
            ]
        }

    async def get_all_users(self):
        def _get():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, username, first_name, subscription_type, subscription_expires, created_at FROM users')
            rows = cursor.fetchall()
            conn.close()
            return rows
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get)

    async def get_all_loggers(self):
        def _get():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT id, user_id, unique_id, name, created_at, is_active FROM loggers')
            rows = cursor.fetchall()
            conn.close()
            return rows
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get)

    async def get_all_iplogs(self):
        def _get():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT id, logger_id, ip_address, user_agent, telegram_user_id, telegram_username, created_at FROM ip_logs')
            rows = cursor.fetchall()
            conn.close()
            return rows
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get)

    async def get_admin_ids(self):
        def _get():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM admins')
            rows = cursor.fetchall()
            conn.close()
            return [row[0] for row in rows]
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get)

    async def add_admin(self, user_id: int):
        def _add():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (user_id,))
            conn.commit()
            conn.close()
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _add)

    async def remove_admin(self, user_id: int):
        def _remove():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM admins WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _remove)

    async def revoke_subscription(self, user_id: int):
        """Revoke user's subscription (set to free)"""
        def _revoke():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET subscription_type = 'free', subscription_expires = NULL
                WHERE user_id = ?
            ''', (user_id,))
            conn.commit()
            conn.close()
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _revoke)
