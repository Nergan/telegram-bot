from motor.motor_asyncio import AsyncIOMotorClient
from cryptography.fernet import Fernet
import base64
import hashlib
from config import settings
import logging

client = None
db = None
vault_col = None
fernet = None

async def init_vault():
    global client, db, vault_col, fernet
    
    logging.info("Initializing Bot Key Vault...")
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client.bot_vault
    vault_col = db.keys
    
    # Ensure optimal lookup performance for user contexts
    await vault_col.create_index("telegram_id", unique=True)
    
    if settings.bot_master_key:
        key_bytes = settings.bot_master_key.encode('utf-8')
        if len(key_bytes) != 44:
            key_bytes = base64.urlsafe_b64encode(hashlib.sha256(key_bytes).digest())
        fernet = Fernet(key_bytes)
    else:
        logging.warning("BOT_MASTER_KEY not provided! Private keys will be stored as unencrypted plaintext.")

async def save_key(telegram_id: int, user_id: str, public_pem: str, private_pem: str):
    enc_private = fernet.encrypt(private_pem.encode('utf-8')).decode('utf-8') if fernet else private_pem
    await vault_col.update_one(
        {"telegram_id": telegram_id},
        {"$set": {"user_id": user_id, "public_pem": public_pem, "private_pem": enc_private}},
        upsert=True
    )

async def get_key(telegram_id: int) -> dict:
    doc = await vault_col.find_one({"telegram_id": telegram_id})
    if not doc: 
        return None
        
    private_pem = doc["private_pem"]
    if fernet:
        try:
            private_pem = fernet.decrypt(private_pem.encode('utf-8')).decode('utf-8')
        except Exception as e:
            logging.error(f"Failed to decrypt private key for {telegram_id}: {e}")
            
    return {
        "user_id": doc["user_id"], 
        "public_pem": doc["public_pem"], 
        "private_pem": private_pem
    }

async def delete_key(telegram_id: int):
    await vault_col.delete_one({"telegram_id": telegram_id})