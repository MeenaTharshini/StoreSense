# ============================================================
# StoreSense - Retail Sales & Inventory Copilot
# Analytics Engine
# ============================================================

import pandas as pd
from dataclasses import dataclass


# ============================================================
# EVIDENCE MODEL
# ============================================================

@dataclass
class EvidenceRow:
    product_id: str
    product_name: str
    store_id: str
    store_name: str
    recent_units: float
    previous_units: float
    revenue: float
    pct_change: float | None

    def to_dict(self):
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "store_id": self.store_id,
            "store_name": self.store_name,
            "recent_units": float(self.recent_units),
            "previous_units": float(self.previous_units),
            "revenue": float(self.revenue),
            "pct_change": (
                float(self.pct_change)
                if self.pct_change is not None
                else None
            ),
        }


# ============================================================
# RETAIL ANALYTICS
# ============================================================

class RetailAnalytics:

    def __init__(self, data):
        self.data = data
        self.end_date = self._determine_end_date()

    # ========================================================
    # SAFE VALUE HELPERS
    # ========================================================

    @staticmethod
    def _safe_float(value, default=0.0):
        try:
            if value is None or pd.isna(value):
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_int(value, default=0):
        try:
            if value is None or pd.isna(value):
                return default
            return int(float(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_string(value, default=""):
        if value is None or pd.isna(value):
            return default
        return str(value)

    # ========================================================
    # DATE NORMALIZATION
    # ========================================================

    def _determine_end_date(self):
        """
        Determine the latest usable sales date.

        If sales are unavailable or dates are invalid,
        today's date is used.
        """

        try:
            sales = self.data.sales.copy()
        except Exception:
            return pd.Timestamp.today().normalize()

        if sales.empty:
            return pd.Timestamp.today().normalize()

        date_column = None

        for column in (
            "date",
            "sale_date",
            "sold_at",
            "created_at",
        ):
            if column in sales.columns:
                date_column = column
                break

        if date_column is None:
            return pd.Timestamp.today().normalize()

        dates = pd.to_datetime(
            sales[date_column],
            errors="coerce",
        )

        dates = dates.dropna()

        if dates.empty:
            return pd.Timestamp.today().normalize()

        return dates.max().normalize()

    # ========================================================
    # SALES NORMALIZATION
    # ========================================================

    def _normalize_sales(self):
        """
        Normalize sales data from CSV/PostgreSQL.

        Expected internal structure:

            sale_id
            store_id
            product_id
            date
            units_sold
            revenue
        """

        try:
            sales = self.data.sales.copy()
        except Exception:
            return pd.DataFrame()

        if sales.empty:
            return sales

        # ----------------------------------------------------
        # Date
        # ----------------------------------------------------

        if "date" not in sales.columns:

            for alternative in (
                "sale_date",
                "sold_at",
                "created_at",
            ):
                if alternative in sales.columns:
                    sales["date"] = sales[alternative]
                    break

        if "date" not in sales.columns:
            return pd.DataFrame()

        sales["date"] = pd.to_datetime(
            sales["date"],
            errors="coerce",
        )

        sales = sales.dropna(
            subset=["date"]
        )

        # ----------------------------------------------------
        # Units
        # ----------------------------------------------------

        if "units_sold" not in sales.columns:

            for alternative in (
                "quantity",
                "units",
                "qty",
            ):
                if alternative in sales.columns:
                    sales["units_sold"] = sales[
                        alternative
                    ]
                    break

        if "units_sold" not in sales.columns:
            sales["units_sold"] = 0

        sales["units_sold"] = pd.to_numeric(
            sales["units_sold"],
            errors="coerce",
        ).fillna(0)

        # ----------------------------------------------------
        # Revenue
        # ----------------------------------------------------

        if "revenue" not in sales.columns:

            if (
                "units_sold" in sales.columns
                and "price" in sales.columns
            ):
                sales["revenue"] = (
                    sales["units_sold"]
                    * pd.to_numeric(
                        sales["price"],
                        errors="coerce",
                    ).fillna(0)
                )

            else:
                sales["revenue"] = 0

        sales["revenue"] = pd.to_numeric(
            sales["revenue"],
            errors="coerce",
        ).fillna(0)

        # ----------------------------------------------------
        # IDs
        # ----------------------------------------------------

        if "store_id" not in sales.columns:
            sales["store_id"] = ""

        if "product_id" not in sales.columns:
            sales["product_id"] = ""

        sales["store_id"] = (
            sales["store_id"]
            .fillna("")
            .astype(str)
        )

        sales["product_id"] = (
            sales["product_id"]
            .fillna("")
            .astype(str)
        )

        return sales

    # ========================================================
    # SALES WINDOW
    # ========================================================

    def _sales_window(self, days=30):

        days = max(int(days), 1)

        sales = self._normalize_sales()

        if sales.empty:
            return sales

        cutoff = (
            self.end_date
            - pd.Timedelta(days=days - 1)
        )

        return sales[
            sales["date"] >= cutoff
        ].copy()

    # ========================================================
    # INVENTORY NORMALIZATION
    # ========================================================

    def _latest_inventory(self):
        """
        Return the latest inventory record for every
        store/product combination.

        Supports:

        PostgreSQL:
            updated_at
            stock

        Older CSV:
            date
            quantity
        """

        try:
            inventory = self.data.inventory.copy()
        except Exception:
            return pd.DataFrame()

        if inventory.empty:
            return inventory

        # ----------------------------------------------------
        # Timestamp
        # ----------------------------------------------------

        if "updated_at" in inventory.columns:

            inventory["date"] = pd.to_datetime(
                inventory["updated_at"],
                errors="coerce",
            )

        elif "date" in inventory.columns:

            inventory["date"] = pd.to_datetime(
                inventory["date"],
                errors="coerce",
            )

        elif "created_at" in inventory.columns:

            inventory["date"] = pd.to_datetime(
                inventory["created_at"],
                errors="coerce",
            )

        else:

            inventory["date"] = pd.Timestamp.today()

        # ----------------------------------------------------
        # Stock
        # ----------------------------------------------------

        if "stock" not in inventory.columns:

            if "quantity" in inventory.columns:
                inventory["stock"] = inventory[
                    "quantity"
                ]

            elif "available_stock" in inventory.columns:
                inventory["stock"] = inventory[
                    "available_stock"
                ]

            else:
                inventory["stock"] = 0

        inventory["stock"] = pd.to_numeric(
            inventory["stock"],
            errors="coerce",
        ).fillna(0)

        # ----------------------------------------------------
        # IDs
        # ----------------------------------------------------

        if "store_id" not in inventory.columns:
            inventory["store_id"] = ""

        if "product_id" not in inventory.columns:
            inventory["product_id"] = ""

        inventory["store_id"] = (
            inventory["store_id"]
            .fillna("")
            .astype(str)
        )

        inventory["product_id"] = (
            inventory["product_id"]
            .fillna("")
            .astype(str)
        )

        # ----------------------------------------------------
        # Latest record
        # ----------------------------------------------------

        inventory = inventory.sort_values(
            [
                "store_id",
                "product_id",
                "date",
            ]
        )

        inventory = inventory.drop_duplicates(
            subset=[
                "store_id",
                "product_id",
            ],
            keep="last",
        )

        return inventory

    # ========================================================
    # SUMMARY
    # ========================================================

    def summary(self):

        sales = self._sales_window(30)

        if sales.empty:
            revenue = 0.0
            units = 0
            orders = 0

        else:
            revenue = self._safe_float(
                sales["revenue"].sum()
            )

            units = self._safe_int(
                sales["units_sold"].sum()
            )

            orders = len(sales)

        attention_items = self.attention(30)

        try:
            product_count = len(
                self.data.products
            )
        except Exception:
            product_count = 0

        try:
            store_count = len(
                self.data.stores
            )
        except Exception:
            store_count = 0

        return {
            "revenue_30d": round(
                revenue,
                2,
            ),
            "units_30d": units,
            "orders_30d": int(orders),
            "products": int(product_count),
            "stores": int(store_count),
            "attention_count": int(
                len(attention_items)
            ),
        }

    # ========================================================
    # CORE METRICS
    # ========================================================

    def _metrics(self, days=30):

        days = max(int(days), 1)

        inventory = self._latest_inventory()

        if inventory.empty:
            return pd.DataFrame()

        sales = self._sales_window(days)

        # ----------------------------------------------------
        # Aggregate sales
        # ----------------------------------------------------

        if (
            sales.empty
            or "store_id" not in sales.columns
            or "product_id" not in sales.columns
        ):

            grouped = pd.DataFrame(
                columns=[
                    "store_id",
                    "product_id",
                    "units_sold",
                    "revenue",
                ]
            )

        else:

            grouped = (
                sales
                .groupby(
                    [
                        "store_id",
                        "product_id",
                    ],
                    as_index=False,
                )
                .agg(
                    units_sold=(
                        "units_sold",
                        "sum",
                    ),
                    revenue=(
                        "revenue",
                        "sum",
                    ),
                )
            )

        # ----------------------------------------------------
        # Merge inventory + sales
        # ----------------------------------------------------

        m = inventory.merge(
            grouped,
            on=[
                "store_id",
                "product_id",
            ],
            how="left",
        )

        m["units_sold"] = pd.to_numeric(
            m["units_sold"],
            errors="coerce",
        ).fillna(0)

        m["revenue"] = pd.to_numeric(
            m["revenue"],
            errors="coerce",
        ).fillna(0)

        m["stock"] = pd.to_numeric(
            m["stock"],
            errors="coerce",
        ).fillna(0)

        # ----------------------------------------------------
        # Demand
        # ----------------------------------------------------

        m["avg_daily_sales"] = (
            m["units_sold"] / days
        )

        def calculate_days_inventory(row):

            demand = self._safe_float(
                row["avg_daily_sales"]
            )

            stock = self._safe_float(
                row["stock"]
            )

            if demand <= 0:
                return float("inf")

            return stock / demand

        m["days_of_inventory"] = m.apply(
            calculate_days_inventory,
            axis=1,
        )

        # ----------------------------------------------------
        # Product information
        # ----------------------------------------------------

        try:
            products = self.data.products.copy()
        except Exception:
            products = pd.DataFrame()

        if not products.empty:

            product_columns = [
                column
                for column in [
                    "product_id",
                    "product_name",
                    "category",
                    "price",
                ]
                if column in products.columns
            ]

            if "product_id" in product_columns:

                products["product_id"] = (
                    products["product_id"]
                    .fillna("")
                    .astype(str)
                )

                m = m.merge(
                    products[
                        product_columns
                    ],
                    on="product_id",
                    how="left",
                )

        # ----------------------------------------------------
        # Store information
        # ----------------------------------------------------

        try:
            stores = self.data.stores.copy()
        except Exception:
            stores = pd.DataFrame()

        if not stores.empty:

            store_columns = [
                column
                for column in [
                    "store_id",
                    "store_name",
                    "location",
                ]
                if column in stores.columns
            ]

            if "store_id" in store_columns:

                stores["store_id"] = (
                    stores["store_id"]
                    .fillna("")
                    .astype(str)
                )

                m = m.merge(
                    stores[
                        store_columns
                    ],
                    on="store_id",
                    how="left",
                    suffixes=(
                        "",
                        "_store",
                    ),
                )

        # ----------------------------------------------------
        # Safe names
        # ----------------------------------------------------

        if "product_name" not in m.columns:
            m["product_name"] = m[
                "product_id"
            ]

        if "store_name" not in m.columns:
            m["store_name"] = m[
                "store_id"
            ]

        m["product_name"] = (
            m["product_name"]
            .fillna(m["product_id"])
            .astype(str)
        )

        m["store_name"] = (
            m["store_name"]
            .fillna(m["store_id"])
            .astype(str)
        )

        return m

    # ========================================================
    # ATTENTION ENGINE
    # ========================================================

    def attention(self, days=30):

        days = max(int(days), 1)

        m = self._metrics(days)

        if m.empty:
            return []

        items = []

        # ====================================================
        # 1. LIKELY STOCK-OUT
        # ====================================================

        stockouts = m[
            (m["avg_daily_sales"] > 0)
            &
            (m["days_of_inventory"] <= 5)
        ]

        for _, row in stockouts.sort_values(
            "days_of_inventory"
        ).iterrows():

            daily_demand = self._safe_float(
                row["avg_daily_sales"]
            )

            current_stock = self._safe_float(
                row["stock"]
            )

            days_inventory = self._safe_float(
                row["days_of_inventory"]
            )

            suggested = max(
                1,
                round(
                    daily_demand * 7
                    - current_stock
                ),
            )

            priority = (
                "HIGH"
                if days_inventory <= 2
                else "MEDIUM"
            )

            reason = (
                f"{self._safe_int(current_stock)} units remain; "
                f"about {days_inventory:.1f} days "
                f"of inventory."
            )

            action = (
                f"Replenish about {suggested} units "
                f"to cover roughly one additional week."
            )

            items.append({
                "type": "stockout",
                "priority": priority,
                "severity": priority,

                "product_id": str(
                    row["product_id"]
                ),

                "product_name": str(
                    row["product_name"]
                ),

                "product": str(
                    row["product_name"]
                ),

                "store_id": str(
                    row["store_id"]
                ),

                "store_name": str(
                    row["store_name"]
                ),

                "store": str(
                    row["store_name"]
                ),

                "title": "Likely stock-out",

                "reason": reason,

                "message": reason,

                "action": action,

                "metrics": {
                    "current_stock": current_stock,
                    "30d_units": self._safe_float(
                        row["units_sold"]
                    ),
                    "daily_demand": daily_demand,
                    "avg_daily_sales": daily_demand,
                    "days_of_inventory": days_inventory,
                },

                "evidence": {
                    "current_stock": current_stock,
                    "30d_units": self._safe_float(
                        row["units_sold"]
                    ),
                    "daily_demand": daily_demand,
                    "avg_daily_sales": daily_demand,
                    "days_of_inventory": days_inventory,
                    "assumption": (
                        "Recent sales rate continues."
                    ),
                },
            })

        # ====================================================
        # 2. SLOW-MOVING STOCK
        # ====================================================

        slow = m[
            (m["stock"] >= 40)
            &
            (m["units_sold"] <= 8)
        ]

        for _, row in slow.sort_values(
            "units_sold"
        ).iterrows():

            current_stock = self._safe_float(
                row["stock"]
            )

            period_units = self._safe_float(
                row["units_sold"]
            )

            reason = (
                f"{self._safe_int(current_stock)} units "
                f"in stock, only "
                f"{self._safe_int(period_units)} sold "
                f"in {days} days."
            )

            action = (
                "Consider a promotion, bundle, "
                "or stock transfer before buying more."
            )

            items.append({
                "type": "slow_moving",
                "priority": "MEDIUM",
                "severity": "MEDIUM",

                "product_id": str(
                    row["product_id"]
                ),

                "product_name": str(
                    row["product_name"]
                ),

                "product": str(
                    row["product_name"]
                ),

                "store_id": str(
                    row["store_id"]
                ),

                "store_name": str(
                    row["store_name"]
                ),

                "store": str(
                    row["store_name"]
                ),

                "title": "Slow-moving stock",

                "reason": reason,

                "message": reason,

                "action": action,

                "metrics": {
                    "current_stock": current_stock,
                    "period_units": period_units,
                    "days": days,
                },

                "evidence": {
                    "current_stock": current_stock,
                    "period_units": period_units,
                    "days": days,
                    "assumption": (
                        "Recent demand weakness continues."
                    ),
                },
            })

        # ====================================================
        # 3. SALES SPIKES / DROPS
        # ====================================================

        sales = self._normalize_sales()

        if (
            not sales.empty
            and "store_id" in sales.columns
            and "product_id" in sales.columns
        ):

            current = (
                self._sales_window(days)
                .groupby(
                    [
                        "store_id",
                        "product_id",
                    ],
                    as_index=False,
                )
                ["units_sold"]
                .sum()
                .rename(
                    columns={
                        "units_sold": "current"
                    }
                )
            )

            previous_start = (
                self.end_date
                - pd.Timedelta(
                    days=(days * 2) - 1
                )
            )

            previous_end = (
                self.end_date
                - pd.Timedelta(
                    days=days
                )
            )

            previous = (
                sales[
                    (sales["date"] >= previous_start)
                    &
                    (sales["date"] <= previous_end)
                ]
                .groupby(
                    [
                        "store_id",
                        "product_id",
                    ],
                    as_index=False,
                )
                ["units_sold"]
                .sum()
                .rename(
                    columns={
                        "units_sold": "previous"
                    }
                )
            )

            changes = current.merge(
                previous,
                on=[
                    "store_id",
                    "product_id",
                ],
                how="left",
            )

            changes["previous"] = (
                changes["previous"]
                .fillna(0)
            )

            def calculate_percentage(row):

                previous_value = (
                    self._safe_float(
                        row["previous"]
                    )
                )

                current_value = (
                    self._safe_float(
                        row["current"]
                    )
                )

                if previous_value > 0:

                    return (
                        (
                            current_value
                            - previous_value
                        )
                        / previous_value
                        * 100
                    )

                if current_value > 0:
                    return 100.0

                return 0.0

            changes["pct"] = changes.apply(
                calculate_percentage,
                axis=1,
            )

            # Require meaningful volume AND meaningful change
            changes = changes[
                (
                    changes["current"]
                    + changes["previous"]
                    >= 20
                )
                &
                (
                    changes["pct"].abs()
                    >= 40
                )
            ]

            # ------------------------------------------------
            # Product/store lookup
            # ------------------------------------------------

            try:
                products = self.data.products.copy()
            except Exception:
                products = pd.DataFrame()

            try:
                stores = self.data.stores.copy()
            except Exception:
                stores = pd.DataFrame()

            if not products.empty:
                products["product_id"] = (
                    products["product_id"]
                    .astype(str)
                )

            if not stores.empty:
                stores["store_id"] = (
                    stores["store_id"]
                    .astype(str)
                )

            for _, row in changes.sort_values(
                "pct"
            ).iterrows():

                product_rows = (
                    products[
                        products["product_id"]
                        == str(
                            row["product_id"]
                        )
                    ]
                    if not products.empty
                    else pd.DataFrame()
                )

                store_rows = (
                    stores[
                        stores["store_id"]
                        == str(
                            row["store_id"]
                        )
                    ]
                    if not stores.empty
                    else pd.DataFrame()
                )

                if (
                    product_rows.empty
                    or store_rows.empty
                ):
                    continue

                product = product_rows.iloc[0]
                store = store_rows.iloc[0]

                pct = self._safe_float(
                    row["pct"]
                )

                current_units = (
                    self._safe_float(
                        row["current"]
                    )
                )

                previous_units = (
                    self._safe_float(
                        row["previous"]
                    )
                )

                spike = pct > 0

                alert_type = (
                    "sales_spike"
                    if spike
                    else "sales_drop"
                )

                title = (
                    "Sales spike"
                    if spike
                    else "Sales drop"
                )

                if spike:

                    action = (
                        "Check whether inventory can "
                        "support the increased demand "
                        "and investigate the cause."
                    )

                else:

                    action = (
                        "Investigate pricing, promotions, "
                        "availability, or demand changes "
                        "before replenishing."
                    )

                reason = (
                    f"{self._safe_int(current_units)} units "
                    f"vs "
                    f"{self._safe_int(previous_units)} "
                    f"previously "
                    f"({pct:+.1f}%)."
                )

                items.append({
                    "type": alert_type,
                    "priority": "MEDIUM",
                    "severity": "MEDIUM",

                    "product_id": str(
                        row["product_id"]
                    ),

                    "product_name": str(
                        product["product_name"]
                    ),

                    "product": str(
                        product["product_name"]
                    ),

                    "store_id": str(
                        row["store_id"]
                    ),

                    "store_name": str(
                        store["store_name"]
                    ),

                    "store": str(
                        store["store_name"]
                    ),

                    "title": title,

                    "reason": reason,

                    "message": reason,

                    "action": action,

                    "metrics": {
                        "current_period_units": current_units,
                        "previous_period_units": previous_units,
                        "change_percent": pct,
                        "period_days": days,
                    },

                    "evidence": {
                        "current_period_units": current_units,
                        "previous_period_units": previous_units,
                        "change_percent": pct,
                        "period_days": days,
                        "assumption": (
                            "The two comparison periods "
                            "are comparable and sales "
                            "records are complete."
                        ),
                    },
                })

        # ====================================================
        # LIMIT OUTPUT
        # ====================================================

        return items[:50]

    # ========================================================
    # BACKWARD COMPATIBILITY
    # ========================================================

    def attention_items(self):
        return self.attention(30)

    # ========================================================
    # STOCKOUT RISKS
    # ========================================================

    def stockout_risks(self, days=30):

        alerts = self.attention(days)

        results = []

        for alert in alerts:

            if alert.get("type") != "stockout":
                continue

            evidence = (
                alert.get("metrics")
                or alert.get("evidence")
                or {}
            )

            results.append({
                "product_id": alert[
                    "product_id"
                ],

                "product_name": alert[
                    "product_name"
                ],

                "store_id": alert[
                    "store_id"
                ],

                "store_name": alert[
                    "store_name"
                ],

                "stock": self._safe_float(
                    evidence.get(
                        "current_stock",
                        0,
                    )
                ),

                "daily_demand": self._safe_float(
                    evidence.get(
                        "daily_demand",
                        evidence.get(
                            "avg_daily_sales",
                            0,
                        ),
                    )
                ),

                "days_of_inventory": (
                    self._safe_float(
                        evidence.get(
                            "days_of_inventory",
                            0,
                        )
                    )
                ),

                "recent_units": self._safe_float(
                    evidence.get(
                        "30d_units",
                        0,
                    )
                ),

                "previous_units": 0,

                "pct_change": None,

                "severity": alert[
                    "severity"
                ],

                "reason": alert[
                    "reason"
                ],
            })

        return results

    # ========================================================
    # TOP PRIORITIES
    # ========================================================

    def top_priorities(
        self,
        days=30,
        limit=5,
    ):

        alerts = self.attention(days)

        priority_order = {
            "HIGH": 0,
            "MEDIUM": 1,
            "LOW": 2,
        }

        alerts.sort(
            key=lambda item: (
                priority_order.get(
                    str(
                        item.get(
                            "priority",
                            "MEDIUM",
                        )
                    ).upper(),
                    1,
                ),
                item.get(
                    "type",
                    "",
                ),
            )
        )

        return alerts[:limit]

    # ========================================================
    # PRODUCT PERFORMANCE
    # ========================================================

    def product_performance(
        self,
        product_name,
        store_name=None,
        days=30,
    ):

        try:
            products = self.data.products.copy()
        except Exception:
            products = pd.DataFrame()

        if products.empty:
            return {
                "found": False,
                "message": (
                    "No products are available."
                ),
                "store_breakdown": [],
            }

        matches = products[
            products["product_name"]
            .astype(str)
            .str.casefold()
            ==
            str(product_name).casefold()
        ]

        if matches.empty:

            return {
                "found": False,
                "message": (
                    f"Product '{product_name}' "
                    "was not found."
                ),
                "store_breakdown": [],
            }

        product = matches.iloc[0]

        try:
            stores = self.data.stores.copy()
        except Exception:
            stores = pd.DataFrame()

        if stores.empty:
            return {
                "found": True,
                "product": product.to_dict(),
                "store_breakdown": [],
            }

        target_stores = stores.copy()

        if store_name:

            target_stores = target_stores[
                target_stores["store_name"]
                .astype(str)
                .str.casefold()
                ==
                str(store_name).casefold()
            ]

            if target_stores.empty:

                return {
                    "found": False,
                    "message": (
                        f"Store '{store_name}' "
                        "was not found."
                    ),
                    "store_breakdown": [],
                }

        records = []

        for _, store in target_stores.iterrows():

            rows = self.evidence(
                product_name=product[
                    "product_name"
                ],
                store_name=store[
                    "store_name"
                ],
                days=days,
            )

            for row in rows:
                records.append(
                    row.to_dict()
                )

        return {
            "found": True,
            "product": product.to_dict(),
            "store_breakdown": records,
        }

    # ========================================================
    # EVIDENCE
    # ========================================================

    def evidence(
        self,
        product_name=None,
        store_name=None,
        days=30,
    ):

        sales = self._normalize_sales()

        if sales.empty:
            return []

        # ----------------------------------------------------
        # Date windows
        # ----------------------------------------------------

        days = max(int(days), 1)

        recent_start = (
            self.end_date
            - pd.Timedelta(
                days=days - 1
            )
        )

        previous_start = (
            self.end_date
            - pd.Timedelta(
                days=(days * 2) - 1
            )
        )

        previous_end = (
            self.end_date
            - pd.Timedelta(
                days=days
            )
        )

        recent = sales[
            sales["date"] >= recent_start
        ].copy()

        previous = sales[
            (sales["date"] >= previous_start)
            &
            (sales["date"] <= previous_end)
        ].copy()

        # ----------------------------------------------------
        # Product filter
        # ----------------------------------------------------

        if product_name:

            try:
                products = (
                    self.data.products.copy()
                )
            except Exception:
                return []

            product_rows = products[
                products["product_name"]
                .astype(str)
                .str.casefold()
                ==
                str(product_name).casefold()
            ]

            if product_rows.empty:
                return []

            product_id = str(
                product_rows.iloc[0][
                    "product_id"
                ]
            )

            recent = recent[
                recent["product_id"]
                .astype(str)
                .str.casefold()
                ==
                product_id.casefold()
            ]

            previous = previous[
                previous["product_id"]
                .astype(str)
                .str.casefold()
                ==
                product_id.casefold()
            ]

        # ----------------------------------------------------
        # Store filter
        # ----------------------------------------------------

        if store_name:

            try:
                stores = (
                    self.data.stores.copy()
                )
            except Exception:
                return []

            store_rows = stores[
                stores["store_name"]
                .astype(str)
                .str.casefold()
                ==
                str(store_name).casefold()
            ]

            if store_rows.empty:
                return []

            store_id = str(
                store_rows.iloc[0][
                    "store_id"
                ]
            )

            recent = recent[
                recent["store_id"]
                .astype(str)
                .str.casefold()
                ==
                store_id.casefold()
            ]

            previous = previous[
                previous["store_id"]
                .astype(str)
                .str.casefold()
                ==
                store_id.casefold()
            ]

        if recent.empty:
            return []

        # ----------------------------------------------------
        # Recent
        # ----------------------------------------------------

        recent_grouped = (
            recent
            .groupby(
                [
                    "store_id",
                    "product_id",
                ],
                as_index=False,
            )
            .agg(
                recent_units=(
                    "units_sold",
                    "sum",
                ),
                revenue=(
                    "revenue",
                    "sum",
                ),
            )
        )

        # ----------------------------------------------------
        # Previous
        # ----------------------------------------------------

        if previous.empty:

            previous_grouped = pd.DataFrame(
                columns=[
                    "store_id",
                    "product_id",
                    "previous_units",
                ]
            )

        else:

            previous_grouped = (
                previous
                .groupby(
                    [
                        "store_id",
                        "product_id",
                    ],
                    as_index=False,
                )
                .agg(
                    previous_units=(
                        "units_sold",
                        "sum",
                    )
                )
            )

        # ----------------------------------------------------
        # Merge
        # ----------------------------------------------------

        merged = recent_grouped.merge(
            previous_grouped,
            on=[
                "store_id",
                "product_id",
            ],
            how="left",
        )

        merged["previous_units"] = (
            merged["previous_units"]
            .fillna(0)
        )

        # ----------------------------------------------------
        # Names
        # ----------------------------------------------------

        try:
            products = self.data.products.copy()
            stores = self.data.stores.copy()
        except Exception:
            return []

        merged["product_id"] = (
            merged["product_id"]
            .astype(str)
        )

        merged["store_id"] = (
            merged["store_id"]
            .astype(str)
        )

        products["product_id"] = (
            products["product_id"]
            .astype(str)
        )

        stores["store_id"] = (
            stores["store_id"]
            .astype(str)
        )

        merged = merged.merge(
            products[
                [
                    "product_id",
                    "product_name",
                ]
            ],
            on="product_id",
            how="left",
        )

        merged = merged.merge(
            stores[
                [
                    "store_id",
                    "store_name",
                ]
            ],
            on="store_id",
            how="left",
        )

        # ----------------------------------------------------
        # Build evidence records
        # ----------------------------------------------------

        results = []

        for _, row in merged.iterrows():

            previous_units = (
                self._safe_float(
                    row["previous_units"]
                )
            )

            recent_units = (
                self._safe_float(
                    row["recent_units"]
                )
            )

            if previous_units > 0:

                pct_change = (
                    (
                        recent_units
                        - previous_units
                    )
                    / previous_units
                    * 100
                )

            elif recent_units > 0:

                pct_change = 100.0

            else:

                pct_change = None

            results.append(
                EvidenceRow(
                    product_id=str(
                        row["product_id"]
                    ),

                    product_name=str(
                        row.get(
                            "product_name",
                            row["product_id"],
                        )
                    ),

                    store_id=str(
                        row["store_id"]
                    ),

                    store_name=str(
                        row.get(
                            "store_name",
                            row["store_id"],
                        )
                    ),

                    recent_units=recent_units,

                    previous_units=previous_units,

                    revenue=self._safe_float(
                        row["revenue"]
                    ),

                    pct_change=pct_change,
                )
            )

        return results

    # ========================================================
    # PRODUCT EVIDENCE
    # ========================================================

    def product_evidence(
        self,
        product_id,
        store_id=None,
    ):

        try:
            products = (
                self.data.products.copy()
            )
        except Exception:
            return None

        if products.empty:
            return None

        rows = products[
            products["product_id"]
            .astype(str)
            .str.upper()
            ==
            str(product_id).upper()
        ]

        if rows.empty:
            return None

        product = rows.iloc[0]

        # ----------------------------------------------------
        # Sales
        # ----------------------------------------------------

        sales = self._sales_window(30)

        if not sales.empty:

            sales = sales[
                sales["product_id"]
                .astype(str)
                .str.upper()
                ==
                str(
                    product["product_id"]
                ).upper()
            ]

        # ----------------------------------------------------
        # Inventory
        # ----------------------------------------------------

        inventory = self._latest_inventory()

        if not inventory.empty:

            inventory = inventory[
                inventory["product_id"]
                .astype(str)
                .str.upper()
                ==
                str(
                    product["product_id"]
                ).upper()
            ]

        # ----------------------------------------------------
        # Store filter
        # ----------------------------------------------------

        if store_id:

            if not sales.empty:

                sales = sales[
                    sales["store_id"]
                    .astype(str)
                    .str.upper()
                    ==
                    str(store_id).upper()
                ]

            if not inventory.empty:

                inventory = inventory[
                    inventory["store_id"]
                    .astype(str)
                    .str.upper()
                    ==
                    str(store_id).upper()
                ]

        # ----------------------------------------------------
        # Inventory output
        # ----------------------------------------------------

        if inventory.empty:

            inventory_records = []

        else:

            inventory_columns = [
                column
                for column in [
                    "store_id",
                    "stock",
                    "date",
                ]
                if column in inventory.columns
            ]

            inventory_records = (
                inventory[
                    inventory_columns
                ]
                .to_dict(
                    orient="records"
                )
            )

            # Convert timestamps to JSON-safe strings
            for record in inventory_records:

                if isinstance(
                    record.get("date"),
                    pd.Timestamp,
                ):
                    record["date"] = (
                        record["date"]
                        .isoformat()
                    )

        # ----------------------------------------------------
        # Sales output
        # ----------------------------------------------------

        sales_units = (
            self._safe_int(
                sales["units_sold"].sum()
            )
            if not sales.empty
            else 0
        )

        sales_revenue = (
            self._safe_float(
                sales["revenue"].sum()
            )
            if not sales.empty
            else 0.0
        )

        return {
            "product": product.to_dict(),

            "sales_30d": {
                "units": sales_units,
                "revenue": round(
                    sales_revenue,
                    2,
                ),
            },

            "inventory": inventory_records,
        }

    # ========================================================
    # COPILOT CONTEXT
    # ========================================================

    def query_context(self, question):

        q = str(question).casefold()

        try:
            products = (
                self.data.products.copy()
            )
        except Exception:
            products = pd.DataFrame()

        try:
            stores = (
                self.data.stores.copy()
            )
        except Exception:
            stores = pd.DataFrame()

        # ----------------------------------------------------
        # Match products
        # ----------------------------------------------------

        matched_products = []

        if not products.empty:

            for _, product in products.iterrows():

                name = self._safe_string(
                    product.get(
                        "product_name",
                        ""
                    )
                )

                name_lower = name.casefold()

                words = [
                    word
                    for word in name_lower.split()
                    if len(word) > 3
                ]

                if (
                    name_lower in q
                    or any(
                        word in q
                        for word in words
                    )
                ):
                    matched_products.append(
                        product.to_dict()
                    )

        # ----------------------------------------------------
        # Match stores
        # ----------------------------------------------------

        matched_stores = []

        if not stores.empty:

            for _, store in stores.iterrows():

                name = self._safe_string(
                    store.get(
                        "store_name",
                        ""
                    )
                )

                name_lower = name.casefold()

                words = [
                    word
                    for word in name_lower.split()
                    if len(word) > 3
                ]

                if (
                    name_lower in q
                    or any(
                        word in q
                        for word in words
                    )
                ):
                    matched_stores.append(
                        store.to_dict()
                    )

        # ----------------------------------------------------
        # Context
        # ----------------------------------------------------

        context = {
            "summary": self.summary(),

            "attention": self.attention(30),

            "matched_products": (
                matched_products
            ),

            "matched_stores": (
                matched_stores
            ),

            "data_available": {
                "sales_records": len(
                    self._normalize_sales()
                ),

                "inventory_records": len(
                    self._latest_inventory()
                ),

                "products": len(
                    products
                ),

                "stores": len(
                    stores
                ),
            },
        }

        # ----------------------------------------------------
        # Product evidence
        # ----------------------------------------------------

        context["product_evidence"] = []

        for product in matched_products:

            evidence = self.product_evidence(
                product.get(
                    "product_id"
                )
            )

            if evidence is not None:
                context[
                    "product_evidence"
                ].append(
                    evidence
                )

        return context