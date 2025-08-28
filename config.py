import os
from dotenv import load_dotenv

load_dotenv()

# Bot configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
CRYPTO_BOT_TOKEN = os.getenv('CRYPTO_BOT_TOKEN')

# Database
DATABASE_PATH = 'database.db'

# Subscription limits
FREE_USER_LINKS_LIMIT = 1
PREMIUM_USER_LINKS_LIMIT = 10

# Subscription prices (in USD)
SUBSCRIPTION_PRICES = {
    'week': 3.0,
    'month': 4.0,
    'forever': 6.0
}

# Web app URL (replace with your actual domain)
WEBAPP_URL = os.getenv('WEBAPP_URL', 'ш')
