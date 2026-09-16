"""
StoreSense Authentication
=========================

Authentication utilities for the StoreSense FastAPI application.

Features:
- SQLite user storage
- Secure bcrypt password hashing
- JWT access tokens
- Token validation
- Current-user extraction
- Automatic default manager creation
- Serverless-safe lazy database initialization

Environment variables:

    STORESENSE_AUTH_DB
    STORESENSE_JWT_SECRET
    STORESENSE_ACCESS_TOKEN_EXPIRE_MINUTES

Example:

    STORESENSE_JWT_SECRET=your-long-random-secret
    STORESENSE_ACCESS_TOKEN_EXPIRE_MINUTES=480

Important:
- The authentication database is separate from retail data.
- The SQLite database is initialized lazily.
- No database is created merely by importing this module.
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


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"


# ============================================================
# AUTH DATABASE LOCATION
# ============================================================

def _get_auth_database_path() -> Path:
    """
    Determine the SQLite authentication database path.

    Priority:

    1. STORESENSE_AUTH_DB environment variable
    2. /tmp on serverless environments
    3. local data/storesense_auth.db

    Serverless platforms generally do not allow reliable writes
    to the application directory. /tmp is writable, although
    its contents are not guaranteed to persist between instances.
    """

    configured_path = os.getenv(
        "STORESENSE_AUTH_DB",
        "",
    ).strip()

    if configured_path:
        return Path(
            configured_path
        ).expanduser()

    # Vercel / common serverless environment.
    if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        return Path(
            "/tmp/storesense_auth.db"
        )

    return DATA_DIR / "storesense_auth.db"


AUTH_DB = _get_auth_database_path()


# ============================================================
# JWT CONFIGURATION
# ============================================================

JWT_ALGORITHM = "HS256"


def _get_jwt_secret() -> str:
    """
    Get the JWT secret at runtime.

    A development fallback is provided so the application can
    still run locally without a .env file.

    For deployment, STORESENSE_JWT_SECRET should always be set.
    """

    secret = os.getenv(
        "STORESENSE_JWT_SECRET",
        "",
    ).strip()

    if secret:
        return secret

    return "storesense-development-secret-change-me"


def _get_access_token_expire_minutes() -> int:
    """
    Read JWT expiration configuration safely.
    """

    raw_value = os.getenv(
        "STORESENSE_ACCESS_TOKEN_EXPIRE_MINUTES",
        "480",
    ).strip()

    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        value = 480

    if value <= 0:
        value = 480

    return value


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection() -> sqlite3.Connection:
    """
    Create a SQLite authentication database connection.

    The directory is created only when a database connection is
    actually requested.

    This is intentionally NOT executed during module import.
    """

    database_path = AUTH_DB

    try:
        database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
    except OSError as exc:
        raise RuntimeError(
            "Unable to create the StoreSense authentication "
            f"database directory: {database_path.parent}"
        ) from exc

    try:
        connection = sqlite3.connect(
            str(database_path),
            check_same_thread=False,
            timeout=30,
        )
    except sqlite3.Error as exc:
        raise RuntimeError(
            "Unable to open the StoreSense authentication database."
        ) from exc

    connection.row_factory = sqlite3.Row

    return connection


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_auth_db() -> None:
    """
    Create the authentication database and users table.

    Safe to call repeatedly.
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

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_users_email
            ON users(email)
            """
        )

        connection.commit()


# ============================================================
# PASSWORD HASHING
# ============================================================

def hash_password(
    password: str,
) -> str:
    """
    Hash a password using bcrypt.

    The plaintext password is never stored.
    """

    if not isinstance(password, str):
        raise TypeError(
            "Password must be a string."
        )

    if not password:
        raise ValueError(
            "Password cannot be empty."
        )

    password_bytes = password.encode(
        "utf-8"
    )

    if len(password_bytes) > 72:
        raise ValueError(
            "Password is too long for bcrypt. "
            "Please use 72 bytes or fewer."
        )

    hashed = bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt(),
    )

    return hashed.decode(
        "utf-8"
    )


def verify_password(
    plain_password: str,
    password_hash: str,
) -> bool:
    """
    Verify a plaintext password against a bcrypt hash.
    """

    if not isinstance(
        plain_password,
        str,
    ):
        return False

    if not isinstance(
        password_hash,
        str,
    ):
        return False

    if not plain_password:
        return False

    if not password_hash:
        return False

    try:

        return bcrypt.checkpw(
            plain_password.encode(
                "utf-8"
            ),
            password_hash.encode(
                "utf-8"
            ),
        )

    except (
        ValueError,
        TypeError,
        bcrypt.InvalidHashError,
    ):
        return False


# ============================================================
# EMAIL HELPERS
# ============================================================

def normalize_email(
    email: str,
) -> str:
    """
    Normalize an email address.
    """

    if not isinstance(
        email,
        str,
    ):
        return ""

    return email.strip().lower()


# ============================================================
# CREATE USER
# ============================================================

def create_user(
    email: str,
    password: str,
    full_name: str = "Store Manager",
    role: str = "manager",
) -> dict[str, Any]:
    """
    Create a new StoreSense user.

    Raises:
        ValueError:
            If input is invalid or email already exists.
    """

    # Ensure DB exists before accessing it.
    init_auth_db()

    email = normalize_email(
        email
    )

    full_name = (
        full_name.strip()
        if isinstance(
            full_name,
            str,
        )
        else ""
    )

    role = (
        role.strip()
        if isinstance(
            role,
            str,
        )
        else "manager"
    )

    if not email:
        raise ValueError(
            "Email is required."
        )

    if "@" not in email:
        raise ValueError(
            "Please enter a valid email address."
        )

    if len(email) > 320:
        raise ValueError(
            "Email address is too long."
        )

    if not isinstance(
        password,
        str,
    ):
        raise ValueError(
            "Password is required."
        )

    if len(password) < 6:
        raise ValueError(
            "Password must contain at least 6 characters."
        )

    if len(
        password.encode("utf-8")
    ) > 72:
        raise ValueError(
            "Password is too long for bcrypt. "
            "Please use 72 bytes or fewer."
        )

    if not full_name:
        raise ValueError(
            "Full name is required."
        )

    if len(full_name) > 150:
        raise ValueError(
            "Full name is too long."
        )

    if not role:
        role = "manager"

    password_hash = hash_password(
        password
    )

    now = datetime.now(
        timezone.utc
    ).isoformat()

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
                    full_name,
                    password_hash,
                    role,
                    1,
                    now,
                    now,
                ),
            )

            connection.commit()

            user_id = cursor.lastrowid

    except sqlite3.IntegrityError as exc:

        if "email" in str(
            exc
        ).lower():

            raise ValueError(
                "A user with this email already exists."
            ) from exc

        raise ValueError(
            "Unable to create the user."
        ) from exc

    return {
        "id": user_id,
        "email": email,
        "full_name": full_name,
        "role": role,
        "is_active": True,
        "created_at": now,
    }


# ============================================================
# GET USER BY EMAIL
# ============================================================

def get_user_by_email(
    email: str,
) -> dict[str, Any] | None:
    """
    Find a user by email address.
    """

    init_auth_db()

    email = normalize_email(
        email
    )

    if not email:
        return None

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


# ============================================================
# GET USER BY ID
# ============================================================

def get_user_by_id(
    user_id: int | str,
) -> dict[str, Any] | None:
    """
    Find a user by numeric database ID.
    """

    init_auth_db()

    try:
        user_id = int(
            user_id
        )
    except (
        TypeError,
        ValueError,
    ):
        return None

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


# ============================================================
# PUBLIC USER
# ============================================================

def public_user(
    user: dict[str, Any],
) -> dict[str, Any]:
    """
    Return safe user information.

    Password hashes are never returned.
    """

    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "role": user["role"],
        "is_active": bool(
            user["is_active"]
        ),
        "created_at": user["created_at"],
    }


# ============================================================
# AUTHENTICATE USER
# ============================================================

def authenticate_user(
    email: str,
    password: str,
) -> dict[str, Any] | None:
    """
    Authenticate a user using email and password.

    Returns:
        User dictionary if successful.
        None otherwise.
    """

    user = get_user_by_email(
        email
    )

    if user is None:
        return None

    if not bool(
        user["is_active"]
    ):
        return None

    if not verify_password(
        password,
        user["password_hash"],
    ):
        return None

    return user


# ============================================================
# CREATE ACCESS TOKEN
# ============================================================

def create_access_token(
    user: dict[str, Any],
    expires_minutes: int | None = None,
) -> str:
    """
    Create a signed JWT access token.
    """

    if expires_minutes is None:
        expires_minutes = (
            _get_access_token_expire_minutes()
        )

    if expires_minutes <= 0:
        expires_minutes = 480

    now = datetime.now(
        timezone.utc
    )

    expires_at = (
        now
        + timedelta(
            minutes=expires_minutes
        )
    )

    payload = {
        "sub": str(
            user["id"]
        ),
        "email": user["email"],
        "role": user["role"],
        "iat": int(
            now.timestamp()
        ),
        "exp": int(
            expires_at.timestamp()
        ),
    }

    return jwt.encode(
        payload,
        _get_jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )


# ============================================================
# DECODE ACCESS TOKEN
# ============================================================

def decode_access_token(
    token: str,
) -> dict[str, Any] | None:
    """
    Decode and validate a JWT access token.
    """

    if not isinstance(
        token,
        str,
    ):
        return None

    token = token.strip()

    if not token:
        return None

    try:

        payload = jwt.decode(
            token,
            _get_jwt_secret(),
            algorithms=[
                JWT_ALGORITHM
            ],
        )

        user_id = payload.get(
            "sub"
        )

        if not user_id:
            return None

        return payload

    except (
        JWTError,
        TypeError,
        ValueError,
    ):
        return None


# ============================================================
# GET USER FROM TOKEN
# ============================================================

def get_user_from_token(
    token: str,
) -> dict[str, Any] | None:
    """
    Resolve a JWT token to an active StoreSense user.
    """

    payload = decode_access_token(
        token
    )

    if payload is None:
        return None

    try:

        user_id = int(
            payload["sub"]
        )

    except (
        KeyError,
        TypeError,
        ValueError,
    ):
        return None

    user = get_user_by_id(
        user_id
    )

    if user is None:
        return None

    if not bool(
        user["is_active"]
    ):
        return None

    return user


# ============================================================
# DEFAULT MANAGER ACCOUNT
# ============================================================

DEFAULT_MANAGER_EMAIL = (
    "manager@storesense.local"
)

DEFAULT_MANAGER_PASSWORD = (
    "StoreSense@123"
)

DEFAULT_MANAGER_NAME = (
    "Store Manager"
)

DEFAULT_MANAGER_ROLE = (
    "manager"
)


def ensure_default_manager() -> dict[str, Any]:
    """
    Ensure that the default manager account exists.

    Existing accounts are never overwritten.
    """

    init_auth_db()

    existing = get_user_by_email(
        DEFAULT_MANAGER_EMAIL
    )

    if existing is not None:
        return existing

    try:

        return create_user(
            email=DEFAULT_MANAGER_EMAIL,
            password=DEFAULT_MANAGER_PASSWORD,
            full_name=DEFAULT_MANAGER_NAME,
            role=DEFAULT_MANAGER_ROLE,
        )

    except ValueError as exc:

        # Another request may have created the account
        # simultaneously.
        if "already exists" in str(
            exc
        ).lower():

            existing = get_user_by_email(
                DEFAULT_MANAGER_EMAIL
            )

            if existing is not None:
                return existing

        raise


# ============================================================
# INITIALIZE AUTH
# ============================================================

def initialize_auth() -> None:
    """
    Initialize the authentication system.

    Safe to call multiple times.

    IMPORTANT:
    This function is intentionally NOT called automatically
    when the module is imported.
    """

    init_auth_db()

    ensure_default_manager()