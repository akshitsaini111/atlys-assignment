from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from app.core.config import settings

# Use Argon2 for password hashing (more modern and secure than bcrypt)
# No 72-byte limitation like bcrypt
ph = PasswordHasher(
    time_cost=2,        # Number of iterations
    memory_cost=65536,  # Memory usage in KiB (64 MB)
    parallelism=4,      # Number of parallel threads
    hash_len=32,        # Length of hash in bytes
    salt_len=16         # Length of salt in bytes
)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password"""
    try:
        ph.verify(hashed_password, plain_password)
        # Check if hash needs rehashing (if parameters changed)
        if ph.check_needs_rehash(hashed_password):
            # You might want to update the hash in the database here
            pass
        return True
    except VerifyMismatchError:
        return False
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """Hash a password for storing"""
    return ph.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str):
    """Decode a JWT access token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None

# Note: If you use this version, update requirements.txt:
# Add: argon2-cffi==23.1.0
# Remove: bcrypt and passlib