from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
import hashlib
import textwrap

def strip_pem(pem_str: str) -> str:
    """Strips PEM headers/footers and newlines for clean Telegram display."""
    return pem_str.replace("-----BEGIN PRIVATE KEY-----", "") \
                  .replace("-----END PRIVATE KEY-----", "") \
                  .replace("\r", "") \
                  .replace("\n", "") \
                  .strip()

def restore_pem(key_str: str) -> str:
    """Restores standard PEM formatting if a user pastes a stripped key."""
    if "BEGIN PRIVATE KEY" in key_str:
        return key_str
    
    cleaned = key_str.replace("\r", "").replace("\n", "").replace(" ", "").strip()
    lines = "\n".join(textwrap.wrap(cleaned, 64))
    return f"-----BEGIN PRIVATE KEY-----\n{lines}\n-----END PRIVATE KEY-----"

def get_pem_and_user_id(private_key):
    """Derives public key, PEM strings, and user_id from a private key object."""
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')

    public_der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    user_id = hashlib.sha256(public_der).hexdigest()

    return private_pem, public_pem, user_id

def generate_keypair():
    """Generates a new RSA keypair and derives associated data."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    return get_pem_and_user_id(private_key)

def get_user_id_from_private_key(private_pem: str):
    """Loads a private key from PEM and derives its user_id."""
    try:
        private_key = serialization.load_pem_private_key(
            private_pem.encode('utf-8'),
            password=None
        )
        _, _, user_id = get_pem_and_user_id(private_key)
        return user_id
    except Exception:
        return None

def get_pem_and_user_id_from_private_key_string(private_pem: str):
    """Parses a private key string to output all parameters simultaneously"""
    private_key = serialization.load_pem_private_key(
        private_pem.encode('utf-8'),
        password=None
    )
    return get_pem_and_user_id(private_key)