import aiohttp
import json
from typing import Optional, Dict, Any
from config import CRYPTO_BOT_TOKEN

class CryptoBot:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://pay.crypt.bot/api"
    
    async def create_invoice(self, amount: float, asset: str = "USDT", description: str = "Subscription payment") -> Optional[Dict[str, Any]]:
        """Create payment invoice"""
        if not self.token:
            return None
        
        url = f"{self.base_url}/createInvoice"
        headers = {"Crypto-Pay-API-Token": self.token}
        
        data = {
            "amount": str(amount),
            "asset": asset,
            "description": description,
            "paid_btn_name": "callback",
            "paid_btn_url": "https://t.me/your_bot_username",
            "payload": "subscription_payment"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("ok"):
                            return result.get("result")
                    return None
        except Exception as e:
            print(f"Error creating invoice: {e}")
            return None
    
    async def get_invoice_status(self, invoice_id: str) -> Optional[str]:
        """Get invoice status"""
        if not self.token:
            return None
        
        url = f"{self.base_url}/getInvoices"
        headers = {"Crypto-Pay-API-Token": self.token}
        
        params = {"invoice_ids": json.dumps([invoice_id])}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("ok") and result.get("result"):
                            invoice = result["result"][0]
                            return invoice.get("status")
                    return None
        except Exception as e:
            print(f"Error getting invoice status: {e}")
            return None
    
    async def get_exchange_rates(self) -> Optional[Dict[str, Any]]:
        """Get exchange rates"""
        if not self.token:
            return None
        
        url = f"{self.base_url}/getExchangeRates"
        headers = {"Crypto-Pay-API-Token": self.token}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("ok"):
                            return result.get("result")
                    return None
        except Exception as e:
            print(f"Error getting exchange rates: {e}")
            return None
