from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_main_menu() -> ReplyKeyboardMarkup:
    """Main menu keyboard"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔗 Логгеры")],
            [KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="💎 Купить подписку")],
            [KeyboardButton(text="📊 Мои логгеры")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие"
    )
    return keyboard

def get_subscription_menu() -> InlineKeyboardMarkup:
    """Subscription options keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="📅 Неделя - $3",
        callback_data="sub_week"
    )
    builder.button(
        text="📅 Месяц - $4", 
        callback_data="sub_month"
    )
    builder.button(
        text="♾️ Навсегда - $6",
        callback_data="sub_forever"
    )
    builder.button(
        text="🔙 Назад",
        callback_data="back_to_main"
    )
    
    builder.adjust(1)
    return builder.as_markup()

def get_logger_actions(logger_id: int) -> InlineKeyboardMarkup:
    """Logger actions keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="📊 Статистика",
        callback_data=f"stats_{logger_id}"
    )
    builder.button(
        text="🗑️ Удалить",
        callback_data=f"delete_{logger_id}"
    )
    builder.button(
        text="🔙 Назад",
        callback_data="back_to_loggers"
    )
    
    builder.adjust(1)
    return builder.as_markup()

def get_back_to_main() -> InlineKeyboardMarkup:
    """Back to main menu button"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Главное меню", callback_data="back_to_main")
    return builder.as_markup()

def get_confirm_delete(logger_id: int) -> InlineKeyboardMarkup:
    """Confirm deletion keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="✅ Да, удалить",
        callback_data=f"confirm_delete_{logger_id}"
    )
    builder.button(
        text="❌ Отмена",
        callback_data=f"cancel_delete_{logger_id}"
    )
    
    builder.adjust(2)
    return builder.as_markup()
