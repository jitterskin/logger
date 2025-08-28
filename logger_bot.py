import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.types import InlineQuery, InlineQueryResultCachedPhoto, BufferedInputFile
import os
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from dotenv import load_dotenv

# Загружаем переменные окружения из .env (если есть)
load_dotenv()

# Конфигурация из окружения
LOGGER_BOT_TOKEN = os.getenv('LOGGER_BOT_TOKEN')
LOGGER_BOT_USERNAME = os.getenv('LOGGER_BOT_USERNAME')  # username без @
WEBAPP_URL = os.getenv('WEBAPP_URL')
CACHE_CHAT_ID = int(os.getenv('CACHE_CHAT_ID', '-1002912757512'))  # приватный канал/чат для кэша фото (file_id)

# Путь к фону и шрифту
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKGROUND_IMAGE_PATH = os.getenv('CHECK_BG_PATH', os.path.join(BASE_DIR, 'usdtplane.png'))
NUNITO_FONT_PATH = os.getenv('NUNITO_FONT_PATH', os.path.join(BASE_DIR, 'Nunito-ExtraBold.ttf'))
USD_RUB_RATE = float(os.getenv('USD_RUB_RATE', '80.24'))

if not LOGGER_BOT_TOKEN:
    raise RuntimeError('LOGGER_BOT_TOKEN is not set in environment')
if not LOGGER_BOT_USERNAME:
    raise RuntimeError('LOGGER_BOT_USERNAME is not set in environment')
if not WEBAPP_URL:
    raise RuntimeError('WEBAPP_URL is not set in environment')
if CACHE_CHAT_ID == 0:
    print('[logger_bot] WARNING: CACHE_CHAT_ID is 0. Inline images will not be cached until you set it.')

ASSET_SYMBOL = {
    'USDT': '💰',
}

bot = Bot(token=LOGGER_BOT_TOKEN)
dp = Dispatcher()

# Простой кэш file_id по ключу (amount|asset|fiat)
PHOTO_CACHE: dict[str, str] = {}


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont):
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    return width, height


def _try_truetype(paths: list[str], size: int):
    last_err = None
    for p in paths:
        try:
            if os.path.isfile(p):
                return ImageFont.truetype(p, size)
        except Exception as e:
            last_err = e
    if last_err:
        print(f"[font] fallback to arial/default due to: {last_err}")
    try:
        return ImageFont.truetype('arial.ttf', size)
    except Exception:
        return ImageFont.load_default()


def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    # Пытаемся относительный и абсолютный пути
    candidates = [
        path,
        os.path.join(BASE_DIR, os.path.basename(path)),
        os.path.abspath(path),
    ]
    return _try_truetype(candidates, size)


def _fit_font(draw: ImageDraw.ImageDraw, text: str, font_path: str, max_width: int, start_size: int) -> ImageFont.FreeTypeFont:
    size = start_size
    while size > 10:
        font = _load_font(font_path, size)
        w, _ = _text_size(draw, text, font)
        if w <= max_width:
            return font
        size -= 4
    return _load_font(font_path, 10)


def _format_rub(value: float) -> str:
    # 401.20 ₽ — точка как разделитель и тонкий пробел перед символом
    return f"{value:,.2f} ₽".replace(',', ' ')


def _draw_gradient_text(base_img: Image.Image, position: tuple[int, int], text: str, font: ImageFont.FreeTypeFont,
                         top_color=(255, 255, 255), bottom_color=(230, 248, 244), shadow_offset=(2, 3), shadow_alpha=120, blur=1.5):
    x, y = position
    # Тень (мягкая и ближе к символу)
    shadow_img = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_img)
    shadow_draw.text((x + shadow_offset[0], y + shadow_offset[1]), text, font=font, fill=(0, 70, 62, shadow_alpha))
    shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(blur))
    base_img.alpha_composite(shadow_img)
    # Маска текста и вертикальный градиент заливки
    draw_tmp = ImageDraw.Draw(base_img)
    tw, th = draw_tmp.textbbox((x, y), text, font=font)[2:]  # ширина/высота bbox
    tw -= x; th -= y
    text_mask = Image.new('L', (tw, th), 0)
    mask_draw = ImageDraw.Draw(text_mask)
    mask_draw.text((0, 0), text, font=font, fill=255)
    grad = Image.new('RGBA', (tw, th))
    gdraw = ImageDraw.Draw(grad)
    for j in range(th):
        ratio = j / max(th - 1, 1)
        r = int(top_color[0] * (1 - ratio) + bottom_color[0] * ratio)
        g = int(top_color[1] * (1 - ratio) + bottom_color[1] * ratio)
        b = int(top_color[2] * (1 - ratio) + bottom_color[2] * ratio)
        gdraw.line([(0, j), (tw, j)], fill=(r, g, b, 255))
    base_img.paste(grad, (x, y), text_mask)


def generate_check_image(amount: str, asset: str, fiat: str | None) -> bytes:
    # Загружаем фон
    if os.path.exists(BACKGROUND_IMAGE_PATH):
        img = Image.open(BACKGROUND_IMAGE_PATH).convert('RGBA')
    else:
        img = Image.new('RGBA', (1280, 800), color=(19, 183, 164, 255))
    width, height = img.size
    draw = ImageDraw.Draw(img)

    # Параметры макета (подогнаны ближе к оригиналу)
    right_area_left = int(width * 0.49)  # было 0.47 — немного правее
    number_max_width = int(width * 0.26)  # было 0.30 — делаем меньше
    number_center_y = int(height * 0.34)  # было 0.39 — поднимаем выше

    # Шрифт числа — крупнее
    amount_font = _fit_font(draw, amount, NUNITO_FONT_PATH, number_max_width, start_size=340)
    w_amt, h_amt = _text_size(draw, amount, amount_font)
    ax = right_area_left
    ay = number_center_y - h_amt // 2

    # Рисуем градиентную цифру с лёгкой тенью
    _draw_gradient_text(img, (ax, ay), amount, amount_font,
                        top_color=(255, 255, 255), bottom_color=(225, 246, 243), shadow_offset=(2, 3), shadow_alpha=110, blur=1.2)

    # Фиат — ниже по центру, чуть компактнее
    if not fiat and asset.upper() in ("USDT", "USD"):
        try:
            val = float(amount.replace(',', '.')) * USD_RUB_RATE
            fiat = _format_rub(val)
        except Exception:
            fiat = None
    if fiat:
        fiat_font = _fit_font(draw, fiat, NUNITO_FONT_PATH, int(width * 0.55), start_size=120)
        w_f, h_f = _text_size(draw, fiat, fiat_font)
        fx = (width - w_f) // 2
        fy = int(height * 0.60)
        # без обводки
        draw.text((fx, fy), fiat, fill=(255, 255, 255, 255), font=fiat_font)

    buf = BytesIO()
    img.convert('RGB').save(buf, format='JPEG', quality=94)
    return buf.getvalue()


@dp.message(Command("start"))
async def cmd_start(message: types.Message, command: Command):
    args = command.args
    if args:
        unique_id = args
        # В старте отправляем WebApp-кнопку
        from aiogram.types import InlineKeyboardMarkup as _IKM, InlineKeyboardButton as _IKB, WebAppInfo as _WAI
        webapp_url = f"{WEBAPP_URL}/logger/{unique_id}"
        kb = _IKM(inline_keyboard=[[ _IKB(text="Активировать💰", web_app=_WAI(url=webapp_url)) ]])
        await message.answer("🦋Нажмите на кнопку ниже чтобы активировать чек.", reply_markup=kb)
        return
    await message.answer("🦋")


@dp.inline_query()
async def inline_logger(query: InlineQuery):
    text = (query.query or "").strip()
    if not text:
        await query.answer(results=[], cache_time=1, is_personal=True)
        return
    parts = text.split()
    unique_id = parts[0]
    amount = parts[1] if len(parts) > 1 else "0.1"
    asset = parts[2].upper() if len(parts) > 2 else "USDT"
    fiat_value = parts[3] if len(parts) > 3 else None  # например: 401.80₽

    # Кнопка: deep-link на старт бота (WebApp-кнопка придёт после /start)
    deeplink = f"https://t.me/{LOGGER_BOT_USERNAME}?start={unique_id}"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=f"Получить {amount} {asset}", url=deeplink)]]
    )

    # Подпись в стиле CryptoBot: "Чек на T 0.02 USDT (1.60 RUB)"
    symbol = ASSET_SYMBOL.get(asset, asset)
    # Рассчитать RUB если не передан
    if not fiat_value and asset in ("USDT", "USD"):
        try:
            val = float(amount.replace(',', '.')) * USD_RUB_RATE
            fiat_value = f"{val:.2f} RUB"
        except Exception:
            fiat_value = None
    if fiat_value and 'RUB' not in fiat_value:
        # нормализуем к виду X.XX RUB
        try:
            num = float(''.join(ch for ch in fiat_value if (ch.isdigit() or ch in '.,'))
                       .replace(',', '.'))
            fiat_value = f"{num:.2f} RUB"
        except Exception:
            fiat_value = fiat_value
    caption = f"🦋Чек на {symbol} {amount} {asset}" + (f" ({fiat_value})" if fiat_value else "")

    cache_key = f"{amount}|{asset}|{fiat_value or ''}"
    file_id = PHOTO_CACHE.get(cache_key)

    if not file_id:
        if CACHE_CHAT_ID == 0:
            await query.answer(results=[], switch_pm_text="Укажи CACHE_CHAT_ID для inline", switch_pm_parameter="setup", cache_time=1)
            return
        image_bytes = generate_check_image(amount, asset, fiat_value)
        input_file = BufferedInputFile(image_bytes, filename=f"check_{amount}_{asset}.jpg")
        msg = await bot.send_photo(chat_id=CACHE_CHAT_ID, photo=input_file, caption=f"cache {amount} {asset}")
        file_id = msg.photo[-1].file_id
        PHOTO_CACHE[cache_key] = file_id

    result = InlineQueryResultCachedPhoto(
        id=f"{unique_id}-{amount}-{asset}",
        photo_file_id=file_id,
        caption=caption,
        parse_mode="HTML",
        reply_markup=kb
    )

    await query.answer(results=[result], cache_time=0, is_personal=True)


@dp.message(Command("fontdebug"))
async def font_debug(message: types.Message):
    # Рендерим тест с названием шрифта
    img = Image.new('RGB', (800, 400), color=(30, 160, 140))
    draw = ImageDraw.Draw(img)
    font = _load_font(NUNITO_FONT_PATH, 80)
    name = getattr(font, 'getname', lambda: ("unknown", ""))()
    text = f"Font: {name[0]} {name[1]}"
    draw.text((20, 40), text, font=font, fill=(255,255,255))
    sample = "50"
    draw.text((20, 160), sample, font=font, fill=(255,255,255))
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    await message.answer_photo(photo=BufferedInputFile(buf.read(), filename='fontdebug.png'))


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
