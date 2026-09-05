from pathlib import Path
import os

import pandas as pd

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.database import RetailData
from src.analytics import RetailAnalytics
from src.copilot import StoreSenseCopilot


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = BASE_DIR / "data"


# ============================================================
# DATABASE / ANALYTICS / COPILOT
# ============================================================

data = RetailData(DATA_DIR)

analytics = RetailAnalytics(data)

copilot = StoreSenseCopilot(analytics)


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
# STATIC FRONTEND
# ============================================================

app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_DIR),
    name="static",
)


# ============================================================
# FRONTEND PAGES
# ============================================================

@app.get("/", include_in_schema=False)
def index():
    """Main StoreSense dashboard."""
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/mobile", include_in_schema=False)
def mobile():
    """Mobile / Quick Sale interface."""
    return FileResponse(FRONTEND_DIR / "mobile.html")


@app.get("/data-center", include_in_schema=False)
def data_center():
    """Retail data management page."""
    return FileResponse(FRONTEND_DIR / "data-center.html")


@app.get("/analytics", include_in_schema=False)
def analytics_page():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/attention", include_in_schema=False)
def attention_page():
    return FileResponse(FRONTEND_DIR / "index.html")



@app.get("/inventory", include_in_schema=False)
def inventory_page():
    """Dedicated Inventory Control Center."""
    return FileResponse(FRONTEND_DIR / "inventory.html")

# ============================================================
# REQUEST MODELS
# ============================================================

class StoreCreate(BaseModel):
    store_id: str = Field(min_length=1)
    store_name: str = Field(min_length=1)
    location: str = ""


class ProductCreate(BaseModel):
    product_id: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    category: str = ""
    price: float = Field(default=0, ge=0)


class InventoryUpdate(BaseModel):
    store_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    stock: int = Field(ge=0)
    reason: str = "manual update"


class SaleCreate(BaseModel):
    store_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    units_sold: int = Field(gt=0)
    revenue: float | None = Field(default=None, ge=0)


class CopilotRequest(BaseModel):
    question: str = Field(min_length=1)


# ============================================================
# DASHBOARD APIs
# ============================================================

@app.get("/api/summary")
def summary():
    """
    Return dashboard KPIs and summary metrics.
    """

    try:
        return analytics.summary()

    except Exception as exc:

        print("Summary endpoint error:", repr(exc))

        return JSONResponse(
            {
                "ok": False,
                "error": str(exc),
            },
            status_code=500,
        )


@app.get("/api/attention")
def attention():
    """
    Return retail attention signals.

    Examples:
    - likely stock-outs
    - slow/non-moving inventory
    - sales spikes
    - sales drops
    """

    try:

        return {
            "ok": True,
            "items": analytics.attention_items(),
        }

    except Exception as exc:

        print("Attention endpoint error:", repr(exc))

        return JSONResponse(
            {
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
):
    """
    Return evidence for a specific product.

    Every AI claim should ultimately be traceable
    to real data returned by the analytics layer.
    """

    try:

        result = analytics.product_evidence(
            product_id=product_id,
            store_id=store_id,
        )

        if result is None:

            return JSONResponse(
                {
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

        print("Evidence endpoint error:", repr(exc))

        return JSONResponse(
            {
                "ok": False,
                "error": str(exc),
            },
            status_code=500,
        )


# ============================================================
# PRODUCTS APIs
# ============================================================

@app.get("/api/products")
def products():
    """Return all products."""

    try:

        return {
            "ok": True,
            "products": data.products.to_dict(
                orient="records"
            ),
        }

    except Exception as exc:

        print("Products endpoint error:", repr(exc))

        return JSONResponse(
            {
                "ok": False,
                "products": [],
                "error": str(exc),
            },
            status_code=500,
        )


@app.post("/api/products")
def create_product(payload: ProductCreate):
    """Create a new product."""

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
            "product": product,
        }

    except Exception as exc:

        return JSONResponse(
            {
                "ok": False,
                "error": str(exc),
            },
            status_code=400,
        )


# ============================================================
# STORES APIs
# ============================================================

@app.get("/api/stores")
def stores():
    """Return all stores."""

    try:

        return {
            "ok": True,
            "stores": data.stores.to_dict(
                orient="records"
            ),
        }

    except Exception as exc:

        print("Stores endpoint error:", repr(exc))

        return JSONResponse(
            {
                "ok": False,
                "stores": [],
                "error": str(exc),
            },
            status_code=500,
        )


@app.post("/api/stores")
def create_store(payload: StoreCreate):
    """Create a new retail store."""

    try:

        store = data.create_store(
            store_id=payload.store_id.strip(),
            store_name=payload.store_name.strip(),
            location=payload.location.strip(),
        )

        return {
            "ok": True,
            "message": "Store added successfully.",
            "store": store,
        }

    except Exception as exc:

        return JSONResponse(
            {
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
):
    """
    Return inventory.

    Optional:
        ?store_id=STORE001
    """

    try:

        return {
            "ok": True,
            "items": data.inventory_list(
                store_id=store_id
            ),
        }

    except Exception as exc:

        print("Inventory endpoint error:", repr(exc))

        return JSONResponse(
            {
                "ok": False,
                "items": [],
                "error": str(exc),
            },
            status_code=500,
        )


@app.put("/api/inventory")
def update_inventory(
    payload: InventoryUpdate,
):
    """Manually adjust inventory."""

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
            "inventory": result,
        }

    except Exception as exc:

        return JSONResponse(
            {
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
):
    """
    Record a retail sale.

    Database layer handles:
    1. stock validation
    2. sale recording
    3. inventory reduction
    4. inventory history
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
            "sale": result,
        }

    except Exception as exc:

        return JSONResponse(
            {
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
):
    """Return products for mobile / Quick Sale."""

    try:

        return {
            "ok": True,
            "products": data.mobile_products(
                store_id=store_id
            ),
        }

    except Exception as exc:

        return JSONResponse(
            {
                "ok": False,
                "products": [],
                "error": str(exc),
            },
            status_code=500,
        )


@app.get("/api/mobile/inventory")
def mobile_inventory(
    store_id: str | None = None,
):
    """Return inventory for the mobile interface."""

    try:

        return {
            "ok": True,
            "items": data.inventory_list(
                store_id=store_id
            ),
        }

    except Exception as exc:

        return JSONResponse(
            {
                "ok": False,
                "items": [],
                "error": str(exc),
            },
            status_code=500,
        )


@app.post("/api/mobile/sale")
def mobile_sale(
    payload: SaleCreate,
):
    """Record a mobile / Quick Sale."""

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
            "sale": result,
        }

    except Exception as exc:

        return JSONResponse(
            {
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
):
    """
    Ask StoreSense AI Copilot.

    User question
          ↓
    Intent detection
          ↓
    Python analytics
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

        result = copilot.answer(question)

        return result

    except Exception as exc:

        print("Copilot endpoint error:", repr(exc))

        return JSONResponse(
            {
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
# DATABASE / SYSTEM HEALTH
# ============================================================

@app.get("/api/health")
def health():
    """
    Basic system health.

    Checks:
    - database
    - Gemini configuration
    """

    try:

        database_ok = data.health_check()

        return {
            "status": "ok" if database_ok else "error",
            "database": "Neon PostgreSQL",
            "neon_connected": database_ok,
            "gemini_configured": bool(
                os.getenv("GEMINI_API_KEY")
            ),
        }

    except Exception as exc:

        print("Health endpoint error:", repr(exc))

        return {
            "status": "error",
            "database": "Neon PostgreSQL",
            "neon_connected": False,
            "gemini_configured": bool(
                os.getenv("GEMINI_API_KEY")
            ),
            "error": str(exc),
        }


@app.get("/api/database")
def database_status():
    """
    Return database connection and record counts.
    """

    try:

        counts = data.count_records()

        return {
            "ok": True,
            "database": "Neon PostgreSQL",
            "connected": True,
            "counts": counts,
        }

    except Exception as exc:

        print("Database endpoint error:", repr(exc))

        return JSONResponse(
            {
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
def sales_trend():
    """
    Return daily revenue and units sold
    for the latest 30 days.
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
                as_index=False
            )
            .agg(
                revenue=("revenue", "sum"),
                units_sold=("units_sold", "sum"),
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
                    "date": str(row["date"]),
                    "revenue": float(
                        row["revenue"] or 0
                    ),
                    "units_sold": int(
                        row["units_sold"] or 0
                    ),
                }

                for _, row in daily.iterrows()
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
            repr(exc)
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
def performance():
    """
    Return dashboard business-performance data.

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

            # Normalize timestamps safely
            sales["date"] = pd.to_datetime(
                sales["date"],
                errors="coerce",
                utc=True,
            )

            sales = sales.dropna(
                subset=["date"]
            )

            if not sales.empty:

                # Last 30 days
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
                            as_index=False
                        )
                        .agg(
                            revenue=(
                                "revenue",
                                "sum"
                            )
                        )
                        .sort_values("day")
                    )

                    revenue = [
                        {
                            "date": str(row["day"]),
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

        inventory = analytics._latest_inventory()

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

                attention_items = analytics.attention(
                    30
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
                    repr(attention_error)
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
            repr(exc)
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
    """

    return {
        "name": "StoreSense",

        "description": (
            "Retail Sales & Inventory Copilot"
        ),

        "version": "1.0.0",

        "status": "running",

        "endpoints": {

            "dashboard": "/",

            "mobile": "/mobile",

            "data_center": "/data-center",

            "summary": "/api/summary",

            "attention": "/api/attention",

            "evidence": "/api/evidence/{product_id}",

            "products": "/api/products",

            "stores": "/api/stores",

            "inventory": "/api/inventory",

            "sales": "/api/sales",

            "mobile_products":
                "/api/mobile/products",

            "mobile_inventory":
                "/api/mobile/inventory",

            "mobile_sale":
                "/api/mobile/sale",

            "copilot": "/api/copilot",

            "health": "/api/health",

            "database": "/api/database",

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