"""
StoreSense Authentication
-------------------------

Local authentication utilities for the StoreSense FastAPI application.

Features:
- SQLite user storage
- Secure password hashing with bcrypt
- JWT access tokens
- Token validation
- Current-user extraction
- Automatic default manager creation

Environment variables:
    STORESENSE_AUTH_DB
    STORESENSE_JWT_SECRET
    STORESENSE_ACCESS_TOKEN_EXPIRE_MINUTES

Recommended:
    Set STORESENSE_JWT_SECRET in your .env file.

Example:
    STORESENSE_JWT_SECRET=your-long-random-secret
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import bcrypt
from dotenv import load_dotenv
from jose import JWTError, jwt


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

load_dotenv()


# ---------------------------------------------------------------------------
# Paths / configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

DEFAULT_AUTH_DB = DATA_DIR / "storesense_auth.db"

AUTH_DB = Path(
    os.getenv("STORESENSE_AUTH_DB", str(DEFAULT_AUTH_DB))
)

JWT_SECRET = os.getenv("STORESENSE_JWT_SECRET", "").strip()

JWT_ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("STORESENSE_ACCESS_TOKEN_EXPIRE_MINUTES", "480")
)


# ---------------------------------------------------------------------------
# Safety check
# ---------------------------------------------------------------------------

def _get_jwt_secret() -> str:
    """
    Return the configured JWT secret.

    A development fallback is allowed so the application can start without
    configuration, but production/hackathon deployment should always set
    STORESENSE_JWT_SECRET.
    """

    if JWT_SECRET:
        return JWT_SECRET

    # Development-only fallback.
    #
    # IMPORTANT:
    # Set STORESENSE_JWT_SECRET in .env for the real application.
    return "storesense-development-secret-change-me"


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """
    Create a SQLite connection for the authentication database.
    """

    AUTH_DB.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        AUTH_DB,
        check_same_thread=False,
    )

    connection.row_factory = sqlite3.Row

    return connection


def init_auth_db() -> None:
    """
    Create the authentication tables if they do not exist.
    """

    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                full_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'manager',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.commit()


# ---------------------------------------------------------------------------
# Password utilities
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """
    Hash a plain-text password using bcrypt.
    """

    if not isinstance(password, str):
        raise TypeError("Password must be a string.")

    if not password:
        raise ValueError("Password cannot be empty.")

    password_bytes = password.encode("utf-8")

    hashed = bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt(),
    )

    return hashed.decode("utf-8")


def verify_password(
    plain_password: str,
    password_hash: str,
) -> bool:
    """
    Verify a plain-text password against a bcrypt hash.
    """

    if not plain_password or not password_hash:
        return False

    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# User utilities
# ---------------------------------------------------------------------------

def normalize_email(email: str) -> str:
    """
    Normalize an email address.
    """

    return email.strip().lower()


def create_user(
    email: str,
    password: str,
    full_name: str = "Store Manager",
    role: str = "manager",
) -> dict[str, Any]:
    """
    Create a new user.

    Raises:
        ValueError: if the email already exists or input is invalid.
    """

    email = normalize_email(email)

    if not email:
        raise ValueError("Email is required.")

    if "@" not in email:
        raise ValueError("Please enter a valid email address.")

    if len(password) < 6:
        raise ValueError(
            "Password must contain at least 6 characters."
        )

    if not full_name.strip():
        raise ValueError("Full name is required.")

    now = datetime.now(timezone.utc).isoformat()

    password_hash = hash_password(password)

    try:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (
                    email,
                    full_name,
                    password_hash,
                    role,
                    is_active,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    email,
                    full_name.strip(),
                    password_hash,
                    role.strip() or "manager",
                    1,
                    now,
                    now,
                ),
            )

            connection.commit()

            user_id = cursor.lastrowid

    except sqlite3.IntegrityError:
        raise ValueError(
            "A user with this email already exists."
        )

    return {
        "id": user_id,
        "email": email,
        "full_name": full_name.strip(),
        "role": role.strip() or "manager",
        "is_active": True,
        "created_at": now,
    }


def get_user_by_email(email: str) -> dict[str, Any] | None:
    """
    Find a user by email.
    """

    email = normalize_email(email)

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                email,
                full_name,
                password_hash,
                role,
                is_active,
                created_at,
                updated_at
            FROM users
            WHERE email = ?
            LIMIT 1
            """,
            (email,),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    """
    Find a user by numeric ID.
    """

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                email,
                full_name,
                password_hash,
                role,
                is_active,
                created_at,
                updated_at
            FROM users
            WHERE id = ?
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    """
    Remove sensitive fields before returning user information to the frontend.
    """

    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "role": user["role"],
        "is_active": bool(user["is_active"]),
        "created_at": user["created_at"],
    }


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def authenticate_user(
    email: str,
    password: str,
) -> dict[str, Any] | None:
    """
    Authenticate a user using email and password.

    Returns:
        User dictionary if authentication succeeds.
        None if authentication fails.
    """

    user = get_user_by_email(email)

    if user is None:
        return None

    if not bool(user["is_active"]):
        return None

    if not verify_password(
        password,
        user["password_hash"],
    ):
        return None

    return user


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def create_access_token(
    user: dict[str, Any],
    expires_minutes: int | None = None,
) -> str:
    """
    Create a signed JWT access token.
    """

    if expires_minutes is None:
        expires_minutes = ACCESS_TOKEN_EXPIRE_MINUTES

    now = datetime.now(timezone.utc)

    expires_at = now + timedelta(
        minutes=expires_minutes
    )

    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }

    token = jwt.encode(
        payload,
        _get_jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )

    return token


def decode_access_token(
    token: str,
) -> dict[str, Any] | None:
    """
    Decode and validate a JWT access token.

    Returns:
        JWT payload if valid.
        None if invalid or expired.
    """

    if not token:
        return None

    try:
        payload = jwt.decode(
            token,
            _get_jwt_secret(),
            algorithms=[JWT_ALGORITHM],
        )

        user_id = payload.get("sub")

        if not user_id:
            return None

        return payload

    except JWTError:
        return None


def get_user_from_token(
    token: str,
) -> dict[str, Any] | None:
    """
    Resolve a JWT token to the corresponding active user.
    """

    payload = decode_access_token(token)

    if payload is None:
        return None

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None

    user = get_user_by_id(user_id)

    if user is None:
        return None

    if not bool(user["is_active"]):
        return None

    return user


# ---------------------------------------------------------------------------
# Default StoreSense account
# ---------------------------------------------------------------------------

def ensure_default_manager() -> dict[str, Any]:
    """
    Ensure that StoreSense has at least one manager account.

    Default development credentials:

        Email:
            manager@storesense.local

        Password:
            StoreSense@123

    IMPORTANT:
    Change this password for any real deployment.
    """

    init_auth_db()

    default_email = "manager@storesense.local"

    existing = get_user_by_email(default_email)

    if existing is not None:
        return existing

    return create_user(
        email=default_email,
        password="StoreSense@123",
        full_name="Store Manager",
        role="manager",
    )


# ---------------------------------------------------------------------------
# Startup initialization
# ---------------------------------------------------------------------------

def initialize_auth() -> None:
    """
    Initialize the authentication system.

    Call this once when StoreSense starts.
    """

    init_auth_db()
    ensure_default_manager()


# ---------------------------------------------------------------------------
# Module initialization
# ---------------------------------------------------------------------------

initialize_auth()