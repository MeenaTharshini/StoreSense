"""
StoreSense - Retail Sales & Inventory Copilot
==============================================

FastAPI application for the StoreSense retail intelligence platform.

Features:
- JWT authentication
- User-scoped retail data
- Retail sales analytics
- Inventory intelligence
- Attention alerts
- Evidence-backed recommendations
- Gemini-powered retail copilot
- Static frontend serving

Run locally:

    python app.py

Server:

    http://localhost:8000

Environment variables:

    GEMINI_API_KEY
    DATABASE_URL
    STORESENSE_JWT_SECRET
    STORESENSE_ACCESS_TOKEN_EXPIRE_MINUTES
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    JSONResponse,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.auth import (
    authenticate_user,
    create_access_token,
    create_user,
    get_user_from_token,
    initialize_auth,
    public_user,
)

from src.analytics import RetailAnalytics
from src.copilot import StoreSenseCopilot
from src.database import RetailData


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent

FRONTEND_DIR = PROJECT_ROOT / "frontend"
DATA_DIR = PROJECT_ROOT / "data"


# ============================================================
# ENVIRONMENT CONFIGURATION
# ============================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "",
).strip()

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY",
    "",
).strip()


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="StoreSense",
    description=(
        "Retail Sales & Inventory Copilot"
    ),
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# AUTHENTICATION
# ============================================================

security = HTTPBearer(
    auto_error=False
)


def get_user_id(
    user: dict[str, Any],
) -> str:
    """
    Return the authenticated user's ID.

    RetailData uses this value to isolate each
    user's stores, products, inventory and sales.
    """

    value = (
        user.get("user_id")
        or user.get("id")
    )

    if value is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authenticated user ID is missing.",
        )

    return str(value)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        security
    ),
) -> dict[str, Any]:
    """
    Resolve the current authenticated user from
    the Bearer JWT token.
    """

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    token = credentials.credentials

    user = get_user_from_token(token)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    return user


# ============================================================
# USER-SCOPED DATA DEPENDENCIES
# ============================================================

def get_user_data(
    user: dict[str, Any] = Depends(
        get_current_user
    ),
) -> RetailData:
    """
    Create a RetailData instance scoped to the
    authenticated user.

    IMPORTANT:
    Never create one global RetailData instance for
    all users.
    """

    return RetailData(
        owner_user_id=get_user_id(user),
        data_dir=DATA_DIR,
    )


def get_user_analytics(
    data: RetailData = Depends(
        get_user_data
    ),
) -> RetailAnalytics:
    """
    Create analytics using only the current
    user's RetailData.
    """

    return RetailAnalytics(data)


# ============================================================
# REQUEST MODELS
# ============================================================

class LoginRequest(BaseModel):
    email: str = Field(
        ...,
        min_length=3,
        max_length=320,
    )

    password: str = Field(
        ...,
        min_length=1,
        max_length=200,
    )


class RegisterRequest(BaseModel):
    email: str = Field(
        ...,
        min_length=3,
        max_length=320,
    )

    password: str = Field(
        ...,
        min_length=6,
        max_length=72,
    )

    full_name: str = Field(
        ...,
        min_length=1,
        max_length=150,
    )


class CopilotRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
    )


class SaleRequest(BaseModel):
    store_id: str
    product_id: str
    units_sold: int = Field(
        ...,
        gt=0,
    )


class InventoryUpdateRequest(BaseModel):
    store_id: str
    product_id: str
    stock: int = Field(
        ...,
        ge=0,
    )


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
def startup_event() -> None:
    """
    Initialize StoreSense authentication.

    The function is safe to call repeatedly.
    """

    initialize_auth()


# ============================================================
# ROOT / FRONTEND
# ============================================================

@app.get(
    "/",
    include_in_schema=False,
)
async def root():
    """
    Serve the StoreSense landing/login page.
    """

    index_file = FRONTEND_DIR / "index.html"

    if index_file.exists():
        return FileResponse(index_file)

    return JSONResponse(
        {
            "ok": True,
            "service": "StoreSense",
            "message": "StoreSense API is running.",
        }
    )


@app.get(
    "/login",
    include_in_schema=False,
)
async def login_page():
    file = FRONTEND_DIR / "login.html"

    if not file.exists():
        raise HTTPException(
            status_code=404,
            detail="Login page not found.",
        )

    return FileResponse(file)


@app.get(
    "/signin",
    include_in_schema=False,
)
async def signin_page():
    file = FRONTEND_DIR / "signin.html"

    if not file.exists():
        raise HTTPException(
            status_code=404,
            detail="Signin page not found.",
        )

    return FileResponse(file)


@app.get(
    "/dashboard",
    include_in_schema=False,
)
async def dashboard_page():
    file = FRONTEND_DIR / "index.html"

    if not file.exists():
        raise HTTPException(
            status_code=404,
            detail="Dashboard page not found.",
        )

    return FileResponse(file)


@app.get(
    "/mobile",
    include_in_schema=False,
)
async def mobile_page():
    file = FRONTEND_DIR / "mobile.html"

    if not file.exists():
        raise HTTPException(
            status_code=404,
            detail="Mobile page not found.",
        )

    return FileResponse(file)


@app.get(
    "/data-center",
    include_in_schema=False,
)
async def data_center_page():
    file = FRONTEND_DIR / "data-center.html"

    if not file.exists():
        raise HTTPException(
            status_code=404,
            detail="Data Center page not found.",
        )

    return FileResponse(file)


@app.get(
    "/analytics",
    include_in_schema=False,
)
async def analytics_page():
    """
    Serve analytics page.

    If a dedicated analytics.html exists, use it.
    Otherwise fall back to dashboard.
    """

    file = FRONTEND_DIR / "analytics.html"

    if file.exists():
        return FileResponse(file)

    fallback = FRONTEND_DIR / "index.html"

    if fallback.exists():
        return FileResponse(fallback)

    raise HTTPException(
        status_code=404,
        detail="Analytics page not found.",
    )


@app.get(
    "/attention",
    include_in_schema=False,
)
async def attention_page():
    """
    Serve attention page if available.
    """

    file = FRONTEND_DIR / "attention.html"

    if file.exists():
        return FileResponse(file)

    fallback = FRONTEND_DIR / "index.html"

    if fallback.exists():
        return FileResponse(fallback)

    raise HTTPException(
        status_code=404,
        detail="Attention page not found.",
    )


@app.get(
    "/inventory",
    include_in_schema=False,
)
async def inventory_page():
    file = FRONTEND_DIR / "inventory.html"

    if not file.exists():
        raise HTTPException(
            status_code=404,
            detail="Inventory page not found.",
        )

    return FileResponse(file)


# ============================================================
# AUTH API
# ============================================================

@app.post(
    "/api/auth/register",
)
async def register(
    payload: RegisterRequest,
):
    """
    Create a new StoreSense user.
    """

    try:

        user = create_user(
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            role="manager",
        )

        token = create_access_token(
            user
        )

        return {
            "ok": True,
            "message": "Account created successfully.",
            "access_token": token,
            "token_type": "bearer",
            "user": public_user(user),
        }

    except ValueError as exc:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        print(
            "Registration error:",
            repr(exc),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create the account.",
        ) from exc


@app.post(
    "/api/auth/login",
)
async def login(
    payload: LoginRequest,
):
    """
    Authenticate a StoreSense user and return a JWT.
    """

    user = authenticate_user(
        payload.email,
        payload.password,
    )

    if user is None:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    token = create_access_token(
        user
    )

    return {
        "ok": True,
        "message": "Login successful.",
        "access_token": token,
        "token_type": "bearer",
        "user": public_user(user),
    }


@app.get(
    "/api/auth/me",
)
async def auth_me(
    user: dict[str, Any] = Depends(
        get_current_user
    ),
):
    """
    Return the currently authenticated user's
    safe public information.
    """

    return {
        "ok": True,
        "user": public_user(user),
    }


@app.post(
    "/api/auth/logout",
)
async def logout(
    user: dict[str, Any] = Depends(
        get_current_user
    ),
):
    """
    JWT logout endpoint.

    JWTs are stateless, so the frontend removes the token.
    """

    return {
        "ok": True,
        "message": "Logged out successfully.",
    }


# ============================================================
# HEALTH
# ============================================================

@app.get(
    "/api/health",
)
async def health():
    """
    Public system health endpoint.

    This endpoint deliberately does NOT require JWT
    authentication so the deployment can be diagnosed
    independently of user sessions.
    """

    database_connected = False
    database_error = None

    if DATABASE_URL:

        try:

            with psycopg.connect(
                DATABASE_URL,
                connect_timeout=5,
            ) as connection:

                with connection.cursor() as cursor:

                    cursor.execute(
                        "SELECT 1"
                    )

                    cursor.fetchone()

            database_connected = True

        except Exception as exc:

            database_error = str(exc)

    return {
        "ok": True,
        "service": "StoreSense",
        "status": "healthy",
        "database": "Neon PostgreSQL",
        "database_configured": bool(
            DATABASE_URL
        ),
        "database_connected": database_connected,
        "database_error": database_error,
        "gemini_configured": bool(
            GEMINI_API_KEY
        ),
    }


# ============================================================
# DASHBOARD SUMMARY
# ============================================================

@app.get(
    "/api/summary",
)
async def summary(
    analytics: RetailAnalytics = Depends(
        get_user_analytics
    ),
):
    """
    Return user-scoped dashboard KPIs.
    """

    try:

        result = analytics.summary()

        if isinstance(result, dict):
            return result

        return {
            "ok": True,
            **result,
        }

    except Exception as exc:

        print(
            "Summary error:",
            repr(exc),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to calculate dashboard summary.",
        ) from exc


# ============================================================
# ATTENTION
# ============================================================

@app.get(
    "/api/attention",
)
async def attention(
    analytics: RetailAnalytics = Depends(
        get_user_analytics
    ),
):
    """
    Return evidence-backed attention items for
    the authenticated user's retail data.
    """

    try:

        result = analytics.attention()

        if isinstance(result, dict):
            return result

        return {
            "ok": True,
            "items": result,
        }

    except Exception as exc:

        print(
            "Attention error:",
            repr(exc),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to calculate attention items.",
        ) from exc


# ============================================================
# EVIDENCE
# ============================================================

@app.get(
    "/api/evidence",
)
async def evidence(
    analytics: RetailAnalytics = Depends(
        get_user_analytics
    ),
):
    """
    Return evidence information used by
    StoreSense analytics.
    """

    try:

        result = analytics.evidence()

        if isinstance(result, dict):
            return result

        return {
            "ok": True,
            "evidence": result,
        }

    except AttributeError:

        return {
            "ok": True,
            "evidence": [],
        }

    except Exception as exc:

        print(
            "Evidence error:",
            repr(exc),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve evidence.",
        ) from exc


# ============================================================
# PRODUCTS
# ============================================================

@app.get(
    "/api/products",
)
async def products(
    data: RetailData = Depends(
        get_user_data
    ),
):
    """
    Return products belonging to the current user.
    """

    try:

        frame = data.products

        if hasattr(frame, "to_dict"):

            records = frame.to_dict(
                orient="records"
            )

        else:
            records = frame

        return {
            "ok": True,
            "products": records,
            "count": len(records),
        }

    except Exception as exc:

        print(
            "Products error:",
            repr(exc),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve products.",
        ) from exc


# ============================================================
# STORES
# ============================================================

@app.get(
    "/api/stores",
)
async def stores(
    data: RetailData = Depends(
        get_user_data
    ),
):
    """
    Return stores belonging to the current user.
    """

    try:

        frame = data.stores

        if hasattr(frame, "to_dict"):

            records = frame.to_dict(
                orient="records"
            )

        else:
            records = frame

        return {
            "ok": True,
            "stores": records,
            "count": len(records),
        }

    except Exception as exc:

        print(
            "Stores error:",
            repr(exc),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve stores.",
        ) from exc


# ============================================================
# INVENTORY
# ============================================================

@app.get(
    "/api/inventory",
)
async def inventory(
    data: RetailData = Depends(
        get_user_data
    ),
):
    """
    Return user-scoped inventory.
    """

    try:

        frame = data.inventory

        if hasattr(frame, "to_dict"):

            records = frame.to_dict(
                orient="records"
            )

        else:
            records = frame

        return {
            "ok": True,
            "inventory": records,
            "count": len(records),
        }

    except Exception as exc:

        print(
            "Inventory error:",
            repr(exc),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve inventory.",
        ) from exc


# ============================================================
# SALES
# ============================================================

@app.get(
    "/api/sales",
)
async def sales(
    data: RetailData = Depends(
        get_user_data
    ),
):
    """
    Return user-scoped sales records.
    """

    try:

        frame = data.sales

        if hasattr(frame, "to_dict"):

            records = frame.to_dict(
                orient="records"
            )

        else:
            records = frame

        return {
            "ok": True,
            "sales": records,
            "count": len(records),
        }

    except Exception as exc:

        print(
            "Sales error:",
            repr(exc),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve sales.",
        ) from exc


# ============================================================
# DATABASE INFORMATION
# ============================================================

@app.get(
    "/api/database",
)
async def database_info(
    data: RetailData = Depends(
        get_user_data
    ),
):
    """
    Return user-scoped database record counts.
    """

    try:

        counts = data.count_records()

        return {
            "ok": True,
            "database": "Neon PostgreSQL",
            "counts": counts,
        }

    except Exception as exc:

        print(
            "Database info error:",
            repr(exc),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve database information.",
        ) from exc


# ============================================================
# SALES TREND
# ============================================================

@app.get(
    "/api/sales/trend",
)
async def sales_trend(
    analytics: RetailAnalytics = Depends(
        get_user_analytics
    ),
):
    """
    Return user-scoped sales trend data.
    """

    try:

        result = analytics.sales_trend()

        if isinstance(result, dict):
            return result

        return {
            "ok": True,
            "points": result,
        }

    except Exception as exc:

        print(
            "Sales trend error:",
            repr(exc),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to calculate sales trend.",
        ) from exc


# ============================================================
# PERFORMANCE
# ============================================================

@app.get(
    "/api/performance",
)
async def performance(
    analytics: RetailAnalytics = Depends(
        get_user_analytics
    ),
):
    """
    Return user-scoped business performance data.
    """

    try:

        result = analytics.performance()

        if isinstance(result, dict):
            return result

        return {
            "ok": True,
            "performance": result,
        }

    except Exception as exc:

        print(
            "Performance error:",
            repr(exc),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to calculate business performance.",
        ) from exc


# ============================================================
# COPILOT
# ============================================================

@app.post(
    "/api/copilot",
)
async def copilot(
    payload: CopilotRequest,
    analytics: RetailAnalytics = Depends(
        get_user_analytics
    ),
):
    """
    Process a natural-language retail question.

    The Copilot is instantiated per request using
    the authenticated user's analytics context.
    """

    question = payload.question.strip()

    if not question:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty.",
        )

    try:

        assistant = StoreSenseCopilot(
            analytics
        )

        result = assistant.ask(
            question
        )

        if isinstance(result, dict):

            return {
                "ok": True,
                **result,
            }

        return {
            "ok": True,
            "answer": str(result),
        }

    except Exception as exc:

        print(
            "Copilot error:",
            repr(exc),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "StoreSense could not process "
                "the requested analysis."
            ),
        ) from exc


# ============================================================
# MOBILE PRODUCT SEARCH
# ============================================================

@app.get(
    "/api/mobile/products",
)
async def mobile_products(
    data: RetailData = Depends(
        get_user_data
    ),
):
    """
    Mobile-friendly product endpoint.
    """

    try:

        frame = data.products

        if hasattr(frame, "to_dict"):

            records = frame.to_dict(
                orient="records"
            )

        else:
            records = frame

        return {
            "ok": True,
            "products": records,
        }

    except Exception as exc:

        print(
            "Mobile products error:",
            repr(exc),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve mobile products.",
        ) from exc


# ============================================================
# MOBILE INVENTORY
# ============================================================

@app.get(
    "/api/mobile/inventory",
)
async def mobile_inventory(
    data: RetailData = Depends(
        get_user_data
    ),
):
    """
    Mobile-friendly inventory endpoint.
    """

    try:

        frame = data.inventory

        if hasattr(frame, "to_dict"):

            records = frame.to_dict(
                orient="records"
            )

        else:
            records = frame

        return {
            "ok": True,
            "inventory": records,
        }

    except Exception as exc:

        print(
            "Mobile inventory error:",
            repr(exc),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve mobile inventory.",
        ) from exc


# ============================================================
# MOBILE SALE
# ============================================================

@app.post(
    "/api/mobile/sale",
)
async def mobile_sale(
    payload: SaleRequest,
    data: RetailData = Depends(
        get_user_data
    ),
):
    """
    Record a sale for the authenticated user's
    store/product combination.
    """

    try:

        # Validate ownership before writing.
        products = data.products
        stores = data.stores

        product_ids = set(
            products["product_id"].astype(str)
            if hasattr(products, "__getitem__")
            else []
        )

        store_ids = set(
            stores["store_id"].astype(str)
            if hasattr(stores, "__getitem__")
            else []
        )

        if str(payload.product_id) not in product_ids:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found.",
            )

        if str(payload.store_id) not in store_ids:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Store not found.",
            )

        # Use the database layer's sale method if available.
        if hasattr(data, "record_sale"):

            result = data.record_sale(
                store_id=payload.store_id,
                product_id=payload.product_id,
                units_sold=payload.units_sold,
            )

            return {
                "ok": True,
                "sale": result,
            }

        if hasattr(data, "add_sale"):

            result = data.add_sale(
                store_id=payload.store_id,
                product_id=payload.product_id,
                units_sold=payload.units_sold,
            )

            return {
                "ok": True,
                "sale": result,
            }

        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                "The current database layer does not "
                "expose a sale creation method."
            ),
        )

    except HTTPException:
        raise

    except Exception as exc:

        print(
            "Mobile sale error:",
            repr(exc),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to record the sale.",
        ) from exc


# ============================================================
# INVENTORY UPDATE
# ============================================================

@app.post(
    "/api/mobile/inventory",
)
async def update_mobile_inventory(
    payload: InventoryUpdateRequest,
    data: RetailData = Depends(
        get_user_data
    ),
):
    """
    Update stock for a product at a store.

    The database layer is responsible for maintaining
    inventory history.
    """

    try:

        if hasattr(data, "update_inventory"):

            result = data.update_inventory(
                store_id=payload.store_id,
                product_id=payload.product_id,
                stock=payload.stock,
            )

            return {
                "ok": True,
                "inventory": result,
            }

        if hasattr(data, "set_inventory"):

            result = data.set_inventory(
                store_id=payload.store_id,
                product_id=payload.product_id,
                stock=payload.stock,
            )

            return {
                "ok": True,
                "inventory": result,
            }

        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                "The current database layer does not "
                "expose an inventory update method."
            ),
        )

    except HTTPException:
        raise

    except Exception as exc:

        print(
            "Inventory update error:",
            repr(exc),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update inventory.",
        ) from exc


# ============================================================
# STATIC FILES
# ============================================================

if FRONTEND_DIR.exists():

    app.mount(
        "/static",
        StaticFiles(
            directory=str(FRONTEND_DIR)
        ),
        name="static",
    )


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.exception_handler(
    StarletteHTTPException
)
async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
):
    """
    Return consistent JSON for API errors.
    """

    if request.url.path.startswith("/api/"):

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "ok": False,
                "detail": exc.detail,
            },
            headers=exc.headers,
        )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
        },
        headers=exc.headers,
    )


@app.exception_handler(
    Exception
)
async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
):
    """
    Prevent raw internal errors from being exposed
    to the browser.
    """

    print(
        "Unhandled StoreSense error:",
        repr(exc),
    )

    if request.url.path.startswith("/api/"):

        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "detail": (
                    "StoreSense encountered an "
                    "unexpected server error."
                ),
            },
        )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error."
        },
    )


# ============================================================
# APPLICATION START
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )