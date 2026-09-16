from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import psycopg

from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
)
from fastapi.responses import (
    FileResponse,
    JSONResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from fastapi.encoders import jsonable_encoder

from pydantic import BaseModel, Field

from src.database import RetailData
from src.analytics import RetailAnalytics
from src.copilot import StoreSenseCopilot

from src.auth import (
    initialize_auth,
    authenticate_user,
    create_access_token,
    create_user,
    get_user_from_token,
    public_user,
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

FRONTEND_DIR = BASE_DIR / "frontend"

DATA_DIR = BASE_DIR / "data"


# ============================================================
# AUTHENTICATION INITIALIZATION
# ============================================================

initialize_auth()

security = HTTPBearer(
    auto_error=False
)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="StoreSense - Retail Sales & Inventory Copilot",
    version="1.0.0",
    description=(
        "AI-powered retail sales and inventory intelligence "
        "system with grounded Gemini Copilot."
    ),
)


# ============================================================
# AUTHENTICATION DEPENDENCY
# ============================================================

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        security
    ),
):
    """
    Validate the Bearer token and return the authenticated user.
    """

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
        )

    user = get_user_from_token(
        credentials.credentials
    )

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token.",
        )

    return user


# ============================================================
# USER ID HELPER
# ============================================================

def get_user_id(user) -> str:
    """
    Safely extract the authenticated user's ID.

    StoreSense authentication data may expose the identifier
    as either 'user_id' or 'id'.

    The database layer always receives the final string ID.
    """

    user_id = (
        user.get("user_id")
        if isinstance(user, dict)
        else None
    )

    if user_id is None and isinstance(user, dict):
        user_id = user.get("id")

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Authenticated user ID is missing.",
        )

    user_id = str(user_id).strip()

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authenticated user ID is invalid.",
        )

    return user_id


# ============================================================
# USER-SCOPED DATA DEPENDENCY
# ============================================================

def get_user_data(
    user=Depends(get_current_user),
) -> RetailData:
    """
    Create a RetailData instance scoped to the authenticated user.

    Every database query performed through this object is isolated
    to this user's owner_user_id.
    """

    user_id = get_user_id(user)

    return RetailData(
        owner_user_id=user_id,
        data_dir=DATA_DIR,
    )


# ============================================================
# USER-SCOPED ANALYTICS DEPENDENCY
# ============================================================

def get_user_analytics(
    data: RetailData = Depends(get_user_data),
) -> RetailAnalytics:
    """
    Create analytics using only the authenticated user's data.
    """

    return RetailAnalytics(data)


# ============================================================
# STATIC FRONTEND
# ============================================================

app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_DIR),
    name="static",
)


# ============================================================
# REQUEST MODELS
# ============================================================

class LoginRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    password: str = Field(min_length=6)


class StoreCreate(BaseModel):
    store_id: str = Field(min_length=1)
    store_name: str = Field(min_length=1)
    location: str = ""


class ProductCreate(BaseModel):
    product_id: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    category: str = ""
    price: float = Field(
        default=0,
        ge=0,
    )


class InventoryUpdate(BaseModel):
    store_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    stock: int = Field(ge=0)
    reason: str = "manual update"


class SaleCreate(BaseModel):
    store_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    units_sold: int = Field(gt=0)
    revenue: float | None = Field(
        default=None,
        ge=0,
    )


class CopilotRequest(BaseModel):
    question: str = Field(min_length=1)


# ============================================================
# FRONTEND PAGES
# ============================================================

@app.get(
    "/",
    include_in_schema=False,
)
def index():
    """
    Initial StoreSense entry point.

    The application starts at the login page.
    """

    return FileResponse(
        FRONTEND_DIR / "login.html"
    )


@app.get(
    "/login",
    include_in_schema=False,
)
def login_page():

    return FileResponse(
        FRONTEND_DIR / "login.html"
    )


@app.get(
    "/signin",
    include_in_schema=False,
)
def signin_page():

    return FileResponse(
        FRONTEND_DIR / "signin.html"
    )


@app.get(
    "/dashboard",
    include_in_schema=False,
)
def dashboard():

    return FileResponse(
        FRONTEND_DIR / "index.html"
    )


@app.get(
    "/mobile",
    include_in_schema=False,
)
def mobile():

    return FileResponse(
        FRONTEND_DIR / "mobile.html"
    )


@app.get(
    "/data-center",
    include_in_schema=False,
)
def data_center():

    return FileResponse(
        FRONTEND_DIR / "data-center.html"
    )


@app.get(
    "/analytics",
    include_in_schema=False,
)
def analytics_page():

    return FileResponse(
        FRONTEND_DIR / "index.html"
    )


@app.get(
    "/attention",
    include_in_schema=False,
)
def attention_page():

    return FileResponse(
        FRONTEND_DIR / "index.html"
    )


@app.get(
    "/inventory",
    include_in_schema=False,
)
def inventory_page():

    return FileResponse(
        FRONTEND_DIR / "inventory.html"
    )


# ============================================================
# AUTHENTICATION APIs
# ============================================================

@app.post("/api/auth/register")
def register(
    payload: RegisterRequest,
):
    """
    Create a new StoreSense manager account.

    Registration automatically logs the user in.
    """

    try:

        name = payload.name.strip()

        email = payload.email.strip().lower()

        if not name:
            raise ValueError(
                "Full name is required."
            )

        if not email:
            raise ValueError(
                "Email is required."
            )

        user = create_user(
            email=email,
            password=payload.password,
            full_name=name,
            role="manager",
        )

        token = create_access_token(user)

        return {
            "ok": True,
            "message": "Account created successfully.",
            "access_token": token,
            "token_type": "bearer",
            "user": public_user(user),
        }

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@app.post("/api/auth/login")
def login(
    payload: LoginRequest,
):
    """
    Authenticate a StoreSense user.
    """

    email = payload.email.strip().lower()

    user = authenticate_user(
        email=email,
        password=payload.password,
    )

    if user is None:

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
        )

    token = create_access_token(user)

    return {
        "ok": True,
        "message": "Login successful.",
        "access_token": token,
        "token_type": "bearer",
        "user": public_user(user),
    }


@app.get("/api/auth/me")
def current_user(
    user=Depends(get_current_user),
):
    """
    Return the currently authenticated user.
    """

    return {
        "ok": True,
        "user": public_user(user),
    }


@app.post("/api/auth/logout")
def logout(
    user=Depends(get_current_user),
):
    """
    JWT authentication is stateless.

    The frontend removes the stored token.
    """

    return {
        "ok": True,
        "message": "Logged out successfully.",
    }


# ============================================================
# DASHBOARD APIs
# ============================================================

@app.get("/api/summary")
def summary(
    analytics: RetailAnalytics = Depends(
        get_user_analytics
    ),
):
    """
    Return dashboard KPIs for the authenticated user only.
    """

    try:

        return analytics.summary()

    except Exception as exc:

        print(
            "Summary endpoint error:",
            repr(exc),
        )

        return JSONResponse(
            content={
                "ok": False,
                "error": str(exc),
            },
            status_code=500,
        )


@app.get("/api/attention")
def attention(
    analytics: RetailAnalytics = Depends(
        get_user_analytics
    ),
):
    """
    Return retail attention signals for the authenticated
    user only.
    """

    try:

        return {
            "ok": True,
            "items": analytics.attention_items(),
        }

    except Exception as exc:

        print(
            "Attention endpoint error:",
            repr(exc),
        )

        return JSONResponse(
            content={
                "ok": False,
                "items": [],
                "error": str(exc),
            },
            status_code=500,
        )


@app.get("/api/evidence/{product_id}")
def evidence(
    product_id: str,
    store_id: str | None = None,
    analytics: RetailAnalytics = Depends(
        get_user_analytics
    ),
):
    """
    Return evidence for a specific product belonging to
    the authenticated user.
    """

    try:

        result = analytics.product_evidence(
            product_id=product_id,
            store_id=store_id,
        )

        if result is None:

            return JSONResponse(
                content={
                    "ok": False,
                    "error": "Product not found.",
                },
                status_code=404,
            )

        return {
            "ok": True,
            **result,
        }

    except Exception as exc:

        print(
            "Evidence endpoint error:",
            repr(exc),
        )

        return JSONResponse(
            content={
                "ok": False,
                "error": str(exc),
            },
            status_code=500,
        )


# ============================================================
# PRODUCTS APIs
# ============================================================

@app.get("/api/products")
def products(
    data: RetailData = Depends(get_user_data),
):
    """
    Return products belonging to the authenticated user only.
    """

    try:

        product_records = data.products.to_dict(
            orient="records"
        )

        return {
            "ok": True,
            "products": jsonable_encoder(
                product_records
            ),
        }

    except Exception as exc:

        print(
            "Products endpoint error:",
            repr(exc),
        )

        return JSONResponse(
            content={
                "ok": False,
                "products": [],
                "error": str(exc),
            },
            status_code=500,
        )


@app.post("/api/products")
def create_product(
    payload: ProductCreate,
    data: RetailData = Depends(get_user_data),
):
    """
    Create a product owned by the authenticated user.
    """

    try:

        product = data.create_product(
            product_id=payload.product_id.strip(),
            product_name=payload.product_name.strip(),
            category=payload.category.strip(),
            price=payload.price,
        )

        return {
            "ok": True,
            "message": "Product added successfully.",
            "product": jsonable_encoder(product),
        }

    except Exception as exc:

        return JSONResponse(
            content={
                "ok": False,
                "error": str(exc),
            },
            status_code=400,
        )


# ============================================================
# STORES APIs
# ============================================================

@app.get("/api/stores")
def stores(
    data: RetailData = Depends(get_user_data),
):
    """
    Return stores belonging to the authenticated user only.
    """

    try:

        store_records = data.stores.to_dict(
            orient="records"
        )

        return {
            "ok": True,
            "stores": jsonable_encoder(
                store_records
            ),
        }

    except Exception as exc:

        print(
            "Stores endpoint error:",
            repr(exc),
        )

        return JSONResponse(
            content={
                "ok": False,
                "stores": [],
                "error": str(exc),
            },
            status_code=500,
        )


@app.post("/api/stores")
def create_store(
    payload: StoreCreate,
    data: RetailData = Depends(get_user_data),
):
    """
    Create a store owned by the authenticated user.
    """

    try:

        store = data.create_store(
            store_id=payload.store_id.strip(),
            store_name=payload.store_name.strip(),
            location=payload.location.strip(),
        )

        return {
            "ok": True,
            "message": "Store added successfully.",
            "store": jsonable_encoder(store),
        }

    except Exception as exc:

        return JSONResponse(
            content={
                "ok": False,
                "error": str(exc),
            },
            status_code=400,
        )


# ============================================================
# INVENTORY APIs
# ============================================================

@app.get("/api/inventory")
def inventory(
    store_id: str | None = None,
    data: RetailData = Depends(get_user_data),
):
    """
    Return inventory belonging to the authenticated user.

    Optional:
        ?store_id=STORE001
    """

    try:

        items = data.inventory_list(
            store_id=store_id
        )

        return {
            "ok": True,
            "items": jsonable_encoder(items),
        }

    except Exception as exc:

        print(
            "Inventory endpoint error:",
            repr(exc),
        )

        return JSONResponse(
            content={
                "ok": False,
                "items": [],
                "error": str(exc),
            },
            status_code=500,
        )


@app.put("/api/inventory")
def update_inventory(
    payload: InventoryUpdate,
    data: RetailData = Depends(get_user_data),
):
    """
    Update inventory only for a store/product owned by
    the authenticated user.
    """

    try:

        result = data.set_inventory(
            store_id=payload.store_id.strip(),
            product_id=payload.product_id.strip(),
            stock=payload.stock,
            reason=payload.reason.strip(),
        )

        return {
            "ok": True,
            "message": "Inventory updated successfully.",
            "inventory": jsonable_encoder(result),
        }

    except Exception as exc:

        return JSONResponse(
            content={
                "ok": False,
                "error": str(exc),
            },
            status_code=400,
        )


# ============================================================
# SALES APIs
# ============================================================

@app.post("/api/sales")
def record_sale(
    payload: SaleCreate,
    data: RetailData = Depends(get_user_data),
):
    """
    Record a sale belonging to the authenticated user.

    Database layer handles:
        1. ownership validation
        2. stock validation
        3. sale recording
        4. inventory reduction
        5. inventory history
    """

    try:

        result = data.record_sale(
            store_id=payload.store_id.strip(),
            product_id=payload.product_id.strip(),
            units_sold=payload.units_sold,
            revenue=payload.revenue,
        )

        return {
            "ok": True,
            "message": "Sale recorded successfully.",
            "sale": jsonable_encoder(result),
        }

    except Exception as exc:

        return JSONResponse(
            content={
                "ok": False,
                "error": str(exc),
            },
            status_code=400,
        )


# ============================================================
# MOBILE / QUICK SALE APIs
# ============================================================

@app.get("/api/mobile/products")
def mobile_products(
    store_id: str | None = None,
    data: RetailData = Depends(get_user_data),
):
    """
    Return mobile products belonging to the authenticated user.
    """

    try:

        products = data.mobile_products(
            store_id=store_id
        )

        return {
            "ok": True,
            "products": jsonable_encoder(products),
        }

    except Exception as exc:

        return JSONResponse(
            content={
                "ok": False,
                "products": [],
                "error": str(exc),
            },
            status_code=500,
        )


@app.get("/api/mobile/inventory")
def mobile_inventory(
    store_id: str | None = None,
    data: RetailData = Depends(get_user_data),
):
    """
    Return mobile inventory belonging to the authenticated user.
    """

    try:

        items = data.inventory_list(
            store_id=store_id
        )

        return {
            "ok": True,
            "items": jsonable_encoder(items),
        }

    except Exception as exc:

        return JSONResponse(
            content={
                "ok": False,
                "items": [],
                "error": str(exc),
            },
            status_code=500,
        )


@app.post("/api/mobile/sale")
def mobile_sale(
    payload: SaleCreate,
    data: RetailData = Depends(get_user_data),
):
    """
    Record a mobile / Quick Sale for the authenticated user.
    """

    try:

        result = data.record_sale(
            store_id=payload.store_id.strip(),
            product_id=payload.product_id.strip(),
            units_sold=payload.units_sold,
            revenue=payload.revenue,
        )

        return {
            "ok": True,
            "message": "Sale recorded successfully.",
            "sale": jsonable_encoder(result),
        }

    except Exception as exc:

        return JSONResponse(
            content={
                "ok": False,
                "error": str(exc),
            },
            status_code=400,
        )


# ============================================================
# GEMINI AI COPILOT
# ============================================================

@app.post("/api/copilot")
def ask_copilot(
    payload: CopilotRequest,
    analytics: RetailAnalytics = Depends(
        get_user_analytics
    ),
):
    """
    Ask StoreSense AI Copilot using ONLY the authenticated
    user's retail data.

    User question
          ↓
    Intent detection
          ↓
    User-scoped Python analytics
          ↓
    Evidence packet
          ↓
    Gemini
          ↓
    Grounded answer
    """

    question = payload.question.strip()

    if not question:

        return {
            "ok": False,
            "answer": "Please enter a question.",
            "evidence": None,
        }

    try:

        # IMPORTANT:
        # A fresh Copilot is created using this user's
        # user-scoped analytics object.

        user_copilot = StoreSenseCopilot(
            analytics
        )

        result = user_copilot.answer(
            question
        )

        return jsonable_encoder(result)

    except Exception as exc:

        print(
            "Copilot endpoint error:",
            repr(exc),
        )

        return JSONResponse(
            content={
                "ok": False,
                "answer": (
                    "The Copilot could not complete the request "
                    "because the analysis service returned an error."
                ),
                "evidence": None,
                "error": str(exc),
            },
            status_code=500,
        )


# ============================================================
# PUBLIC SYSTEM HEALTH
# ============================================================

@app.get("/api/health")
def health():
    """
    Basic public system health.

    This endpoint does NOT access user-specific retail data.

    It only checks:
        - PostgreSQL connectivity
        - Gemini API key configuration
    """

    database_ok = False
    database_error = None

    database_url = (
        os.getenv(
            "DATABASE_URL",
            "",
        )
        .strip()
    )

    if database_url:

        try:

            with psycopg.connect(
                database_url,
                connect_timeout=10,
            ) as conn:

                with conn.cursor() as cur:

                    cur.execute(
                        "SELECT 1"
                    )

                    cur.fetchone()

            database_ok = True

        except Exception as exc:

            database_error = str(exc)

    else:

        database_error = (
            "DATABASE_URL is not configured."
        )

    gemini_configured = bool(
        os.getenv("GEMINI_API_KEY")
    )

    result = {
        "status": (
            "ok"
            if database_ok
            else "error"
        ),

        "database":
            "Neon PostgreSQL",

        "database_connected":
            database_ok,

        "gemini_configured":
            gemini_configured,
    }

    if database_error:
        result["database_error"] = database_error

    return result


# ============================================================
# DATABASE STATUS
# ============================================================

@app.get("/api/database")
def database_status(
    data: RetailData = Depends(get_user_data),
):
    """
    Return database connection information and record counts
    for the authenticated user only.
    """

    try:

        counts = data.count_records()

        return {
            "ok": True,
            "database": "Neon PostgreSQL",
            "connected": True,
            "owner_user_id": data.owner_user_id,
            "counts": counts,
        }

    except Exception as exc:

        print(
            "Database endpoint error:",
            repr(exc),
        )

        return JSONResponse(
            content={
                "ok": False,
                "database": "Neon PostgreSQL",
                "connected": False,
                "error": str(exc),
            },
            status_code=500,
        )


# ============================================================
# SALES TREND API
# ============================================================

@app.get("/api/sales/trend")
def sales_trend(
    analytics: RetailAnalytics = Depends(
        get_user_analytics
    ),
):
    """
    Return daily revenue and units sold for the latest
    30 days for the authenticated user.
    """

    try:

        sales = analytics._normalize_sales()

        if sales is None or sales.empty:

            return {
                "ok": True,
                "points": [],
                "total_revenue": 0,
                "total_units": 0,
            }

        sales = sales.copy()

        # ----------------------------------------------------
        # Normalize timestamps safely
        # ----------------------------------------------------

        sales["date"] = pd.to_datetime(
            sales["date"],
            errors="coerce",
            utc=True,
        )

        sales = sales.dropna(
            subset=["date"]
        )

        if sales.empty:

            return {
                "ok": True,
                "points": [],
                "total_revenue": 0,
                "total_units": 0,
            }

        # ----------------------------------------------------
        # Convert to date
        # ----------------------------------------------------

        sales["date"] = (
            sales["date"]
            .dt.tz_convert(None)
            .dt.date
        )

        # ----------------------------------------------------
        # Group by day
        # ----------------------------------------------------

        daily = (
            sales
            .groupby(
                "date",
                as_index=False,
            )
            .agg(
                revenue=(
                    "revenue",
                    "sum",
                ),
                units_sold=(
                    "units_sold",
                    "sum",
                ),
            )
            .sort_values("date")
        )

        daily = daily.tail(30)

        # ----------------------------------------------------
        # Response
        # ----------------------------------------------------

        return {
            "ok": True,

            "points": [
                {
                    "date": str(
                        row["date"]
                    ),

                    "revenue": float(
                        row["revenue"] or 0
                    ),

                    "units_sold": int(
                        row["units_sold"] or 0
                    ),
                }

                for _, row
                in daily.iterrows()
            ],

            "total_revenue": float(
                daily["revenue"].sum()
            ),

            "total_units": int(
                daily["units_sold"].sum()
            ),
        }

    except Exception as exc:

        print(
            "Sales trend endpoint error:",
            repr(exc),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Unable to load sales trend: {exc}"
            ),
        )


# ============================================================
# BUSINESS PERFORMANCE API
# ============================================================

@app.get("/api/performance")
def performance(
    analytics: RetailAnalytics = Depends(
        get_user_analytics
    ),
):
    """
    Return business-performance data for the authenticated
    user only.

    Includes:
        - last 30 days revenue trend
        - inventory health
    """

    try:

        # ====================================================
        # SALES / REVENUE TREND
        # ====================================================

        sales = analytics._normalize_sales()

        revenue = []

        if sales is not None and not sales.empty:

            sales = sales.copy()

            sales["date"] = pd.to_datetime(
                sales["date"],
                errors="coerce",
                utc=True,
            )

            sales = sales.dropna(
                subset=["date"]
            )

            if not sales.empty:

                cutoff = (
                    pd.Timestamp.now(tz="UTC")
                    - pd.Timedelta(days=29)
                )

                recent = sales[
                    sales["date"] >= cutoff
                ].copy()

                if not recent.empty:

                    recent["day"] = (
                        recent["date"]
                        .dt.tz_convert(None)
                        .dt.date
                    )

                    daily = (
                        recent
                        .groupby(
                            "day",
                            as_index=False,
                        )
                        .agg(
                            revenue=(
                                "revenue",
                                "sum",
                            )
                        )
                        .sort_values("day")
                    )

                    revenue = [
                        {
                            "date": str(
                                row["day"]
                            ),

                            "revenue": float(
                                row["revenue"] or 0
                            ),
                        }

                        for _, row
                        in daily.iterrows()
                    ]

        # ====================================================
        # INVENTORY HEALTH
        # ====================================================

        inventory = (
            analytics._latest_inventory()
        )

        if inventory is None:
            inventory = pd.DataFrame()

        inventory = inventory.copy()

        total = len(inventory)

        stockout = 0

        low_stock = 0

        slow_moving = 0

        # ----------------------------------------------------
        # Inventory classification
        # ----------------------------------------------------

        if total > 0:

            # Stock-out

            stockout = int(
                (
                    inventory["stock"] <= 0
                ).sum()
            )

            # Low stock: 1–5 units

            low_stock = int(
                (
                    (inventory["stock"] > 0)
                    &
                    (inventory["stock"] <= 5)
                ).sum()
            )

            # Slow / non-moving

            try:

                attention_items = (
                    analytics.attention(30)
                )

                if not attention_items:
                    attention_items = []

                slow_moving = len(
                    [
                        item
                        for item in attention_items
                        if item.get("type")
                        in (
                            "slow_moving",
                            "non_moving",
                        )
                    ]
                )

            except Exception as attention_error:

                print(
                    "Slow-moving calculation error:",
                    repr(attention_error),
                )

                slow_moving = 0

        # ----------------------------------------------------
        # Healthy inventory
        # ----------------------------------------------------

        healthy = max(
            total
            - stockout
            - low_stock
            - slow_moving,
            0,
        )

        # ====================================================
        # RESPONSE
        # ====================================================

        return {
            "ok": True,

            "revenue": revenue,

            "inventory": {
                "total": total,
                "healthy": healthy,
                "low_stock": low_stock,
                "stockout": stockout,
                "slow_moving": slow_moving,
            },
        }

    except Exception as exc:

        print(
            "Performance endpoint error:",
            repr(exc),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Unable to load performance data: {exc}"
            ),
        )


# ============================================================
# ROOT API INFORMATION
# ============================================================

@app.get("/api")
def api_info():
    """
    Simple API discovery endpoint.

    Kept public.
    """

    return {
        "name": "StoreSense",

        "description": (
            "Retail Sales & Inventory Copilot"
        ),

        "version": "1.0.0",

        "status": "running",

        "authentication": {
            "type": "JWT Bearer Token",
            "register": "/api/auth/register",
            "login": "/api/auth/login",
            "current_user": "/api/auth/me",
            "logout": "/api/auth/logout",
        },

        "data_isolation": {
            "enabled": True,
            "description": (
                "Retail data is isolated using the authenticated "
                "user owner_user_id."
            ),
        },

        "endpoints": {

            "initial_entry": "/",

            "login": "/login",

            "signin": "/signin",

            "dashboard": "/dashboard",

            "mobile": "/mobile",

            "data_center": "/data-center",

            "analytics": "/analytics",

            "attention_page": "/attention",

            "inventory_page": "/inventory",

            "summary":
                "/api/summary",

            "attention":
                "/api/attention",

            "evidence":
                "/api/evidence/{product_id}",

            "products":
                "/api/products",

            "stores":
                "/api/stores",

            "inventory":
                "/api/inventory",

            "sales":
                "/api/sales",

            "mobile_products":
                "/api/mobile/products",

            "mobile_inventory":
                "/api/mobile/inventory",

            "mobile_sale":
                "/api/mobile/sale",

            "copilot":
                "/api/copilot",

            "health":
                "/api/health",

            "database":
                "/api/database",

            "sales_trend":
                "/api/sales/trend",

            "performance":
                "/api/performance",
        },
    }


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
    )