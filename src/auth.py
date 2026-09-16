# src/auth.py

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import bcrypt
from jose import JWTError, jwt
from dotenv import load_dotenv


# ---------------------------------------------------------
# Environment
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


# ---------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------

def _get_auth_database_path() -> Path:
    """
    Get a writable SQLite path.

    Vercel/serverless filesystems are read-only except for /tmp,
    so use /tmp in deployed serverless environments.
    """

    configured = os.getenv("STORESENSE_AUTH_DB")

    if configured:
        return Path(configured)

    if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        return Path("/tmp/storesense_auth.db")

    return BASE_DIR / "data" / "storesense_auth.db"


def _get_jwt_secret() -> str:
    """
    JWT signing secret.

    Set STORESENSE_JWT_SECRET in Vercel Environment Variables.
    """

    return os.getenv(
        "STORESENSE_JWT_SECRET",
        "storesense-development-secret-change-me",
    )


JWT_ALGORITHM = "HS256"


def _get_access_token_expire_minutes() -> int:
    try:
        return int(os.getenv("STORESENSE_ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    except (TypeError, ValueError):
        return 1440


# ---------------------------------------------------------
# Database
# ---------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """
    Open the authentication SQLite database.
    """

    db_path = _get_auth_database_path()

    parent = db_path.parent

    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        # In unusual serverless environments, /tmp should still be usable.
        db_path = Path("/tmp/storesense_auth.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row

    return connection


def init_auth_db() -> None:
    """
    Create the authentication table if it does not exist.
    Safe to call multiple times.
    """

    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'manager',
                created_at TEXT NOT NULL
            )
            """
        )

        conn.commit()


# ---------------------------------------------------------
# Password helpers
# ---------------------------------------------------------

def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    bcrypt supports a maximum password input of 72 bytes.
    """

    password_bytes = password.encode("utf-8")

    if len(password_bytes) > 72:
        raise ValueError("Password must be 72 bytes or fewer.")

    hashed = bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt(),
    )

    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a plaintext password against a bcrypt hash.
    """

    try:
        password_bytes = password.encode("utf-8")

        if len(password_bytes) > 72:
            return False

        return bcrypt.checkpw(
            password_bytes,
            password_hash.encode("utf-8"),
        )

    except (ValueError, TypeError, bcrypt.InvalidHashError):
        return False


# ---------------------------------------------------------
# User helpers
# ---------------------------------------------------------

def _row_to_user(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": str(row["id"]),
        "email": row["email"],
        "full_name": row["full_name"],
        "role": row["role"],
        "created_at": row["created_at"],
    }


def get_user_by_email(email: str) -> Optional[dict[str, Any]]:
    """
    Find a user by email.
    """

    init_auth_db()

    email = normalize_email(email)

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, email, full_name, role, created_at
            FROM users
            WHERE email = ?
            LIMIT 1
            """,
            (email,),
        ).fetchone()

    if row is None:
        return None

    return _row_to_user(row)


def get_user_by_id(user_id: str | int) -> Optional[dict[str, Any]]:
    """
    Find a user by ID.
    """

    init_auth_db()

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, email, full_name, role, created_at
            FROM users
            WHERE id = ?
            LIMIT 1
            """,
            (str(user_id),),
        ).fetchone()

    if row is None:
        return None

    return _row_to_user(row)


def create_user(
    email: str,
    password: str,
    full_name: str,
    role: str = "manager",
) -> dict[str, Any]:
    """
    Create a new user.
    """

    init_auth_db()

    email = normalize_email(email)
    full_name = full_name.strip()
    role = role.strip() or "manager"

    if not email:
        raise ValueError("Email is required.")

    if not password:
        raise ValueError("Password is required.")

    if not full_name:
        raise ValueError("Full name is required.")

    existing = get_user_by_email(email)

    if existing:
        raise ValueError("A user with this email already exists.")

    password_hash = hash_password(password)

    created_at = datetime.now(timezone.utc).isoformat()

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (
                    email,
                    password_hash,
                    full_name,
                    role,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    email,
                    password_hash,
                    full_name,
                    role,
                    created_at,
                ),
            )

            conn.commit()

            user_id = cursor.lastrowid

    except sqlite3.IntegrityError:
        raise ValueError("A user with this email already exists.")

    return {
        "id": user_id,
        "user_id": str(user_id),
        "email": email,
        "full_name": full_name,
        "role": role,
        "created_at": created_at,
    }


# ---------------------------------------------------------
# Authentication
# ---------------------------------------------------------

def authenticate_user(
    email: str,
    password: str,
):
    init_auth_db()

    email = normalize_email(email)

    # --------------------------------------------------------
    # VERCEL / SERVERLESS FALLBACK
    # --------------------------------------------------------
    # SQLite under /tmp is ephemeral. If a fresh serverless
    # instance has no default manager, recreate it.
    # --------------------------------------------------------

    user = get_user_by_email(email)

    if (
        user is None
        and email == DEFAULT_MANAGER_EMAIL
    ):
        ensure_default_manager()
        user = get_user_by_email(email)

    if user is None:
        return None

    # --------------------------------------------------------
    # FETCH PASSWORD HASH
    # --------------------------------------------------------

    conn = get_connection()

    try:
        row = conn.execute(
            """
            SELECT password_hash
            FROM users
            WHERE email = ?
            """,
            (email,),
        ).fetchone()

    finally:
        conn.close()

    if row is None:
        return None

    password_hash = row["password_hash"]

    if not verify_password(
        password,
        password_hash,
    ):
        return None

    return user
# ---------------------------------------------------------
# JWT
# ---------------------------------------------------------

def create_access_token(
    user: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token.
    """

    user_id = user.get("user_id") or user.get("id")

    if user_id is None:
        raise ValueError("User ID is required to create an access token.")

    if expires_delta is None:
        expires_delta = timedelta(
            minutes=_get_access_token_expire_minutes()
        )

    expire = datetime.now(timezone.utc) + expires_delta

    payload = {
        "sub": str(user_id),
        "email": user.get("email"),
        "role": user.get("role", "manager"),
        "exp": expire,
    }

    return jwt.encode(
        payload,
        _get_jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    """
    Decode and validate a JWT.
    """

    try:
        payload = jwt.decode(
            token,
            _get_jwt_secret(),
            algorithms=[JWT_ALGORITHM],
        )

        subject = payload.get("sub")

        if subject is None:
            return None

        return payload

    except JWTError:
        return None


def get_user_from_token(token: str) -> Optional[dict[str, Any]]:
    """
    Decode JWT and retrieve the corresponding user.
    """

    payload = decode_access_token(token)

    if not payload:
        return None

    user_id = payload.get("sub")

    if not user_id:
        return None

    return get_user_by_id(user_id)


# ---------------------------------------------------------
# Public user representation
# ---------------------------------------------------------

def public_user(user: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """
    Return safe user information for the frontend.
    """

    if user is None:
        return None

    return {
        "id": user.get("id"),
        "user_id": str(user.get("user_id") or user.get("id")),
        "email": user.get("email"),
        "full_name": user.get("full_name"),
        "role": user.get("role", "manager"),
    }


# ---------------------------------------------------------
# Default manager
# ---------------------------------------------------------

def ensure_default_manager() -> dict[str, Any]:
    """
    Create the default StoreSense manager account if it does not exist.
    """

    init_auth_db()

    email = "manager@storesense.local"

    existing = get_user_by_email(email)

    if existing:
        return existing

    return create_user(
        email=email,
        password="StoreSense@123",
        full_name="Store Manager",
        role="manager",
    )


# ---------------------------------------------------------
# Application initialization
# ---------------------------------------------------------

def initialize_auth() -> None:
    """
    Initialize authentication storage.

    IMPORTANT:
    This function is intentionally NOT called automatically when
    this module is imported.

    This prevents import-time crashes on Vercel/serverless.
    """

    init_auth_db()
    ensure_default_manager()


# ---------------------------------------------------------
# IMPORTANT:
#
# DO NOT put this at the bottom:
#
# initialize_auth()
#
# Also DO NOT import anything from src.auth inside src.auth.
# ---------------------------------------------------------