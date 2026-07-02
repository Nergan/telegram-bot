import hmac
import hashlib
import json
from urllib.parse import parse_qsl
from core.config import TOKEN

def validate_webapp_data(init_data: str) -> dict | None:
    """Validates Telegram WebApp initData securely."""
    try:
        parsed_data = dict(parse_qsl(init_data))
        if 'hash' not in parsed_data:
            return None
        
        hash_val = parsed_data.pop('hash')
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        
        secret_key = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
        calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        if calc_hash == hash_val:
            return json.loads(parsed_data.get('user', '{}'))
    except Exception:
        return None
    return None