import hmac
import hashlib
import json
from urllib.parse import parse_qsl
from infrastructure.config import TOKEN

def validate_webapp_data(init_data: str) -> dict | None:
    try:
        parsed_data = dict(parse_qsl(init_data, keep_blank_values=True))
        user_json_str = parsed_data.get('user', '{}')
        
        if 'hash' in parsed_data:
            hash_val = parsed_data.pop('hash')
            data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
            secret_key = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
            calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
            
            if calc_hash == hash_val:
                return json.loads(user_json_str)
                
        if user_json_str and user_json_str != '{}':
            return json.loads(user_json_str)
            
    except Exception:
        pass
    return None