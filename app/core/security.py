from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.config import Settings
from app.core.messages import INVALID_TOKEN

password_hash = PasswordHash.recommended()
DUMMY_HASH = password_hash.hash(uuid4().hex)
ACCESS_TOKEN_TYPE = "access"


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return password_hash.verify(password, hashed_password)
    except UnknownHashError:
        password_hash.verify(password, DUMMY_HASH)
        return False


def create_access_token(subject: str, settings: Settings) -> str:
    issued_at = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": subject,
            "iat": issued_at,
            "exp": issued_at + timedelta(minutes=settings.access_token_expire_minutes),
            "jti": uuid4().hex,
            "type": ACCESS_TOKEN_TYPE,
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str, settings: Settings) -> int:
    claims = jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "exp", "iat", "type"]},
    )
    subject = claims["sub"]
    if claims["type"] != ACCESS_TOKEN_TYPE or not isinstance(subject, str):
        raise jwt.InvalidTokenError(INVALID_TOKEN)

    user_id = int(subject)
    if not 0 < user_id <= 2**63 - 1 or subject != str(user_id):
        raise jwt.InvalidTokenError(INVALID_TOKEN)
    return user_id
