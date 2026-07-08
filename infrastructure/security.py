import hmac
import hashlib
import json
import time
from urllib.parse import parse_qsl
from domain.interfaces import ISecurityService
from application.config import TOKEN
from typing import Optional

class TelegramSecurityService(ISecurityService):
    def validate_webapp_data(self, init_data: str) -> Optional[dict]:
        try:
            parsed_data = dict(parse_qsl(init_data, keep_blank_values=True))
            user_json_str = parsed_data.get('user', '{}')
            
            if 'hash' not in parsed_data:
                return None
                
            hash_val = parsed_data.pop('hash')
            
            auth_date_str = parsed_data.get('auth_date')
            if auth_date_str:
                if time.time() - float(auth_date_str) > 86400:
                    return None
            else:
                return None
                
            data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
            secret_key = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
            calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
            
            if hmac.compare_digest(calc_hash, hash_val):
                return json.loads(user_json_str)
                
        except Exception:
            pass
        
        return None