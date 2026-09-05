from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


# ============================================================
# ENVIRONMENT
# ============================================================

# Load .env from the project root.
# database.py is inside StoreSense/src/
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


class RetailData:
    """
    StoreSense PostgreSQL data layer.

    Neon stores all persistent retail data:

        stores
        products
        inventory
        inventory_history
        sales

    The rest of the application talks to Neon through this class.

    Important:
        - No data is stored only in memory.
        - Every create/update/sale operation is committed to Neon.
        - Inventory changes create an inventory_history record.
        - Sales automatically reduce inventory.
    """

    def __init__(self, data_dir: Path | None = None):

        self.data_dir = (
            data_dir
            if data_dir is not None
            else BASE_DIR / "data"
        )

        self.database_url = (
            os.getenv("DATABASE_URL", "")
            .strip()
        )

        if not self.database_url:
            raise RuntimeError(
                "DATABASE_URL is not configured.\n"
                f"Expected .env file at:\n{ENV_FILE}\n"
                "Add your Neon PostgreSQL connection string as:\n"
                "DATABASE_URL=your_neon_connection_string"
            )

        # Test the connection immediately.
        self._test_connection()

        # Create tables/indexes if necessary.
        self._initialize_database()

    # ============================================================
    # CONNECTION
    # ============================================================

    def _connect(self):
        """
        Create a new Neon PostgreSQL connection.
        """

        return psycopg.connect(
            self.database_url,
            row_factory=dict_row,
            connect_timeout=10,
        )

    def _test_connection(self):
        """
        Verify that Neon is reachable.
        """

        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT NOW() AS server_time"
                    )
                    cur.fetchone()

        except Exception as exc:
            raise RuntimeError(
                "Could not connect to Neon PostgreSQL.\n"
                f"Database error: {exc}"
            ) from exc

    # ============================================================
    # DATABASE INITIALIZATION
    # ============================================================

    def _initialize_database(self):
        """
        Create the StoreSense database schema.

        Existing data is NOT deleted.
        """

        statements = [

            # ----------------------------------------------------
            # STORES
            # ----------------------------------------------------

            """
            CREATE TABLE IF NOT EXISTS stores (
                store_id TEXT PRIMARY KEY,

                store_name TEXT NOT NULL,

                location TEXT DEFAULT '',

                created_at TIMESTAMPTZ
                    NOT NULL DEFAULT NOW()
            )
            """,

            # ----------------------------------------------------
            # PRODUCTS
            # ----------------------------------------------------

            """
            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,

                product_name TEXT NOT NULL,

                category TEXT DEFAULT '',

                price NUMERIC(12, 2)
                    NOT NULL DEFAULT 0,

                created_at TIMESTAMPTZ
                    NOT NULL DEFAULT NOW(),

                CHECK (price >= 0)
            )
            """,

            # ----------------------------------------------------
            # INVENTORY
            # ----------------------------------------------------

            """
            CREATE TABLE IF NOT EXISTS inventory (
                store_id TEXT NOT NULL,

                product_id TEXT NOT NULL,

                stock INTEGER
                    NOT NULL DEFAULT 0,

                updated_at TIMESTAMPTZ
                    NOT NULL DEFAULT NOW(),

                PRIMARY KEY (
                    store_id,
                    product_id
                ),

                FOREIGN KEY (store_id)
                    REFERENCES stores(store_id)
                    ON DELETE CASCADE,

                FOREIGN KEY (product_id)
                    REFERENCES products(product_id)
                    ON DELETE CASCADE,

                CHECK (stock >= 0)
            )
            """,

            # ----------------------------------------------------
            # INVENTORY HISTORY
            # ----------------------------------------------------

            """
            CREATE TABLE IF NOT EXISTS inventory_history (
                id BIGSERIAL PRIMARY KEY,

                store_id TEXT NOT NULL,

                product_id TEXT NOT NULL,

                previous_stock INTEGER
                    NOT NULL,

                new_stock INTEGER
                    NOT NULL,

                change_quantity INTEGER
                    NOT NULL,

                reason TEXT
                    NOT NULL DEFAULT 'manual update',

                created_at TIMESTAMPTZ
                    NOT NULL DEFAULT NOW(),

                FOREIGN KEY (store_id)
                    REFERENCES stores(store_id)
                    ON DELETE CASCADE,

                FOREIGN KEY (product_id)
                    REFERENCES products(product_id)
                    ON DELETE CASCADE
            )
            """,

            # ----------------------------------------------------
            # SALES
            # ----------------------------------------------------

            """
            CREATE TABLE IF NOT EXISTS sales (
                sale_id BIGSERIAL PRIMARY KEY,

                store_id TEXT NOT NULL,

                product_id TEXT NOT NULL,

                date TIMESTAMPTZ
                    NOT NULL DEFAULT NOW(),

                units_sold INTEGER
                    NOT NULL,

                revenue NUMERIC(12, 2)
                    NOT NULL,

                FOREIGN KEY (store_id)
                    REFERENCES stores(store_id)
                    ON DELETE CASCADE,

                FOREIGN KEY (product_id)
                    REFERENCES products(product_id)
                    ON DELETE CASCADE,

                CHECK (units_sold > 0),

                CHECK (revenue >= 0)
            )
            """,

            # ----------------------------------------------------
            # INDEXES
            # ----------------------------------------------------

            """
            CREATE INDEX IF NOT EXISTS idx_sales_date
            ON sales(date)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_sales_store
            ON sales(store_id)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_sales_product
            ON sales(product_id)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_inventory_store
            ON inventory(store_id)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_inventory_product
            ON inventory(product_id)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_inventory_history_date
            ON inventory_history(created_at)
            """
        ]

        with self._connect() as conn:

            with conn.cursor() as cur:

                for statement in statements:
                    cur.execute(statement)

    # ============================================================
    # HEALTH CHECK
    # ============================================================

    def health_check(self) -> bool:

        try:

            with self._connect() as conn:

                with conn.cursor() as cur:

                    cur.execute(
                        "SELECT 1 AS ok"
                    )

                    result = cur.fetchone()

                    return bool(
                        result and result["ok"] == 1
                    )

        except Exception:

            return False

    # ============================================================
    # STORES
    # ============================================================

    def create_store(
        self,
        store_id: str,
        store_name: str,
        location: str = "",
    ) -> dict[str, Any]:

        store_id = str(store_id).strip()
        store_name = str(store_name).strip()
        location = str(location).strip()

        if not store_id:
            raise ValueError(
                "Store ID is required."
            )

        if not store_name:
            raise ValueError(
                "Store name is required."
            )

        sql = """
            INSERT INTO stores (
                store_id,
                store_name,
                location
            )
            VALUES (
                %s,
                %s,
                %s
            )
            RETURNING
                store_id,
                store_name,
                location,
                created_at
        """

        try:

            with self._connect() as conn:

                with conn.cursor() as cur:

                    cur.execute(
                        sql,
                        (
                            store_id,
                            store_name,
                            location,
                        ),
                    )

                    result = cur.fetchone()

                    return result

        except psycopg.errors.UniqueViolation:

            raise ValueError(
                f"Store '{store_id}' already exists."
            )

    # ============================================================
    # GET STORES
    # ============================================================

    def get_stores(self) -> list[dict[str, Any]]:

        sql = """
            SELECT
                store_id,
                store_name,
                location,
                created_at
            FROM stores
            ORDER BY store_name
        """

        with self._connect() as conn:

            with conn.cursor() as cur:

                cur.execute(sql)

                return cur.fetchall()

    # ============================================================
    # SINGLE STORE
    # ============================================================

    def get_store(
        self,
        store_id: str,
    ) -> dict[str, Any] | None:

        with self._connect() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        store_id,
                        store_name,
                        location,
                        created_at
                    FROM stores
                    WHERE store_id = %s
                    """,
                    (store_id,),
                )

                return cur.fetchone()

    # ============================================================
    # PRODUCTS
    # ============================================================

    def create_product(
        self,
        product_id: str,
        product_name: str,
        category: str = "",
        price: float = 0,
    ) -> dict[str, Any]:

        product_id = str(product_id).strip()
        product_name = str(product_name).strip()
        category = str(category).strip()

        if not product_id:
            raise ValueError(
                "Product ID is required."
            )

        if not product_name:
            raise ValueError(
                "Product name is required."
            )

        price = float(price)

        if price < 0:
            raise ValueError(
                "Price cannot be negative."
            )

        sql = """
            INSERT INTO products (
                product_id,
                product_name,
                category,
                price
            )
            VALUES (
                %s,
                %s,
                %s,
                %s
            )
            RETURNING
                product_id,
                product_name,
                category,
                price,
                created_at
        """

        try:

            with self._connect() as conn:

                with conn.cursor() as cur:

                    cur.execute(
                        sql,
                        (
                            product_id,
                            product_name,
                            category,
                            price,
                        ),
                    )

                    return cur.fetchone()

        except psycopg.errors.UniqueViolation:

            raise ValueError(
                f"Product '{product_id}' already exists."
            )

    # ============================================================
    # GET PRODUCTS
    # ============================================================

    def get_products(self) -> list[dict[str, Any]]:

        sql = """
            SELECT
                product_id,
                product_name,
                category,
                price,
                created_at
            FROM products
            ORDER BY product_name
        """

        with self._connect() as conn:

            with conn.cursor() as cur:

                cur.execute(sql)

                return cur.fetchall()

    # ============================================================
    # SINGLE PRODUCT
    # ============================================================

    def get_product(
        self,
        product_id: str,
    ) -> dict[str, Any] | None:

        with self._connect() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        product_id,
                        product_name,
                        category,
                        price,
                        created_at
                    FROM products
                    WHERE product_id = %s
                    """,
                    (product_id,),
                )

                return cur.fetchone()

    # ============================================================
    # SET INVENTORY
    # ============================================================

    def set_inventory(
        self,
        store_id: str,
        product_id: str,
        stock: int,
        reason: str = "manual update",
    ) -> dict[str, Any]:

        store_id = str(store_id).strip()
        product_id = str(product_id).strip()
        reason = str(reason).strip() or "manual update"

        stock = int(stock)

        if not store_id:
            raise ValueError(
                "Store ID is required."
            )

        if not product_id:
            raise ValueError(
                "Product ID is required."
            )

        if stock < 0:
            raise ValueError(
                "Stock cannot be negative."
            )

        with self._connect() as conn:

            with conn.cursor() as cur:

                # ------------------------------------------------
                # Verify store
                # ------------------------------------------------

                cur.execute(
                    """
                    SELECT store_id
                    FROM stores
                    WHERE store_id = %s
                    """,
                    (store_id,),
                )

                if cur.fetchone() is None:

                    raise ValueError(
                        f"Store '{store_id}' does not exist."
                    )

                # ------------------------------------------------
                # Verify product
                # ------------------------------------------------

                cur.execute(
                    """
                    SELECT product_id
                    FROM products
                    WHERE product_id = %s
                    """,
                    (product_id,),
                )

                if cur.fetchone() is None:

                    raise ValueError(
                        f"Product '{product_id}' does not exist."
                    )

                # ------------------------------------------------
                # Get existing inventory
                # ------------------------------------------------

                cur.execute(
                    """
                    SELECT stock
                    FROM inventory
                    WHERE store_id = %s
                      AND product_id = %s
                    FOR UPDATE
                    """,
                    (
                        store_id,
                        product_id,
                    ),
                )

                existing = cur.fetchone()

                if existing:

                    previous_stock = int(
                        existing["stock"]
                    )

                else:

                    previous_stock = 0

                # ------------------------------------------------
                # Insert / update inventory
                # ------------------------------------------------

                cur.execute(
                    """
                    INSERT INTO inventory (
                        store_id,
                        product_id,
                        stock,
                        updated_at
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        NOW()
                    )

                    ON CONFLICT (
                        store_id,
                        product_id
                    )

                    DO UPDATE SET
                        stock = EXCLUDED.stock,
                        updated_at = NOW()

                    RETURNING
                        store_id,
                        product_id,
                        stock,
                        updated_at
                    """,
                    (
                        store_id,
                        product_id,
                        stock,
                    ),
                )

                inventory = cur.fetchone()

                # ------------------------------------------------
                # Record history
                # ------------------------------------------------

                cur.execute(
                    """
                    INSERT INTO inventory_history (
                        store_id,
                        product_id,
                        previous_stock,
                        new_stock,
                        change_quantity,
                        reason
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    RETURNING
                        id,
                        created_at
                    """,
                    (
                        store_id,
                        product_id,
                        previous_stock,
                        stock,
                        stock - previous_stock,
                        reason,
                    ),
                )

                history = cur.fetchone()

                return {
                    **inventory,
                    "previous_stock": previous_stock,
                    "change_quantity": (
                        stock - previous_stock
                    ),
                    "history_id": history["id"],
                }

    # ============================================================
    # GET INVENTORY
    # ============================================================

    def inventory_list(
        self,
        store_id: str | None = None,
    ) -> list[dict[str, Any]]:

        sql = """
            SELECT
                i.store_id,
                s.store_name,

                i.product_id,
                p.product_name,

                p.category,
                p.price,

                i.stock,
                i.updated_at

            FROM inventory i

            INNER JOIN stores s
                ON s.store_id = i.store_id

            INNER JOIN products p
                ON p.product_id = i.product_id
        """

        params: list[Any] = []

        if store_id:

            sql += """
                WHERE i.store_id = %s
            """

            params.append(store_id)

        sql += """
            ORDER BY
                s.store_name,
                p.product_name
        """

        with self._connect() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    sql,
                    params,
                )

                return cur.fetchall()

    # ============================================================
    # SINGLE INVENTORY RECORD
    # ============================================================

    def inventory_for(
        self,
        store_id: str,
        product_id: str,
    ) -> dict[str, Any] | None:

        sql = """
            SELECT
                i.store_id,
                s.store_name,

                i.product_id,
                p.product_name,

                p.category,
                p.price,

                i.stock,
                i.updated_at

            FROM inventory i

            INNER JOIN stores s
                ON s.store_id = i.store_id

            INNER JOIN products p
                ON p.product_id = i.product_id

            WHERE i.store_id = %s
              AND i.product_id = %s
        """

        with self._connect() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    sql,
                    (
                        store_id,
                        product_id,
                    ),
                )

                return cur.fetchone()

    # ============================================================
    # MOBILE PRODUCTS
    # ============================================================

    def mobile_products(
        self,
        store_id: str | None = None,
    ) -> list[dict[str, Any]]:

        if store_id:

            sql = """
                SELECT
                    p.product_id,
                    p.product_name,
                    p.category,
                    p.price,
                    COALESCE(i.stock, 0) AS stock

                FROM products p

                LEFT JOIN inventory i
                    ON i.product_id = p.product_id
                   AND i.store_id = %s

                ORDER BY p.product_name
            """

            params = [store_id]

        else:

            sql = """
                SELECT
                    p.product_id,
                    p.product_name,
                    p.category,
                    p.price,

                    COALESCE(
                        SUM(i.stock),
                        0
                    ) AS stock

                FROM products p

                LEFT JOIN inventory i
                    ON i.product_id = p.product_id

                GROUP BY
                    p.product_id,
                    p.product_name,
                    p.category,
                    p.price

                ORDER BY p.product_name
            """

            params = []

        with self._connect() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    sql,
                    params,
                )

                return cur.fetchall()

    # ============================================================
    # RECORD SALE
    # ============================================================

    def record_sale(
        self,
        store_id: str,
        product_id: str,
        units_sold: int,
        revenue: float | None = None,
    ) -> dict[str, Any]:

        store_id = str(store_id).strip()
        product_id = str(product_id).strip()

        units_sold = int(units_sold)

        if not store_id:
            raise ValueError(
                "Store ID is required."
            )

        if not product_id:
            raise ValueError(
                "Product ID is required."
            )

        if units_sold <= 0:
            raise ValueError(
                "Units sold must be greater than zero."
            )

        with self._connect() as conn:

            with conn.cursor() as cur:

                # ------------------------------------------------
                # Verify store
                # ------------------------------------------------

                cur.execute(
                    """
                    SELECT
                        store_id,
                        store_name
                    FROM stores
                    WHERE store_id = %s
                    """,
                    (store_id,),
                )

                store = cur.fetchone()

                if not store:

                    raise ValueError(
                        f"Store '{store_id}' does not exist."
                    )

                # ------------------------------------------------
                # Get product
                # ------------------------------------------------

                cur.execute(
                    """
                    SELECT
                        product_id,
                        product_name,
                        price
                    FROM products
                    WHERE product_id = %s
                    """,
                    (product_id,),
                )

                product = cur.fetchone()

                if not product:

                    raise ValueError(
                        f"Product '{product_id}' does not exist."
                    )

                # ------------------------------------------------
                # Lock inventory row
                # ------------------------------------------------

                cur.execute(
                    """
                    SELECT
                        stock
                    FROM inventory

                    WHERE store_id = %s
                      AND product_id = %s

                    FOR UPDATE
                    """,
                    (
                        store_id,
                        product_id,
                    ),
                )

                inventory = cur.fetchone()

                if not inventory:

                    raise ValueError(
                        "Inventory record does not exist "
                        "for this store and product."
                    )

                previous_stock = int(
                    inventory["stock"]
                )

                # ------------------------------------------------
                # Prevent negative inventory
                # ------------------------------------------------

                if units_sold > previous_stock:

                    raise ValueError(
                        "Insufficient stock. "
                        f"Available: {previous_stock}. "
                        f"Requested: {units_sold}."
                    )

                new_stock = (
                    previous_stock - units_sold
                )

                # ------------------------------------------------
                # Calculate revenue
                # ------------------------------------------------

                if revenue is None:

                    revenue = (
                        float(product["price"])
                        * units_sold
                    )

                revenue = float(revenue)

                if revenue < 0:

                    raise ValueError(
                        "Revenue cannot be negative."
                    )

                # ------------------------------------------------
                # INSERT SALE
                # ------------------------------------------------

                cur.execute(
                    """
                    INSERT INTO sales (
                        store_id,
                        product_id,
                        date,
                        units_sold,
                        revenue
                    )

                    VALUES (
                        %s,
                        %s,
                        NOW(),
                        %s,
                        %s
                    )

                    RETURNING
                        sale_id,
                        store_id,
                        product_id,
                        date,
                        units_sold,
                        revenue
                    """,
                    (
                        store_id,
                        product_id,
                        units_sold,
                        revenue,
                    ),
                )

                sale = cur.fetchone()

                # ------------------------------------------------
                # UPDATE INVENTORY
                # ------------------------------------------------

                cur.execute(
                    """
                    UPDATE inventory

                    SET
                        stock = %s,
                        updated_at = NOW()

                    WHERE store_id = %s
                      AND product_id = %s
                    """,
                    (
                        new_stock,
                        store_id,
                        product_id,
                    ),
                )

                # ------------------------------------------------
                # RECORD INVENTORY HISTORY
                # ------------------------------------------------

                cur.execute(
                    """
                    INSERT INTO inventory_history (
                        store_id,
                        product_id,
                        previous_stock,
                        new_stock,
                        change_quantity,
                        reason
                    )

                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )

                    RETURNING id
                    """,
                    (
                        store_id,
                        product_id,
                        previous_stock,
                        new_stock,
                        -units_sold,
                        "sale",
                    ),
                )

                history = cur.fetchone()

                # The transaction commits automatically when
                # leaving the connection context successfully.

                return {
                    **sale,

                    "store_name":
                        store["store_name"],

                    "product_name":
                        product["product_name"],

                    "previous_stock":
                        previous_stock,

                    "new_stock":
                        new_stock,

                    "inventory_history_id":
                        history["id"],
                }

    # ============================================================
    # SALES
    # ============================================================

    def get_sales(
        self,
        store_id: str | None = None,
        product_id: str | None = None,
    ) -> list[dict[str, Any]]:

        sql = """
            SELECT
                s.sale_id,

                s.store_id,
                st.store_name,

                s.product_id,
                p.product_name,

                p.category,

                s.date,
                s.units_sold,
                s.revenue

            FROM sales s

            INNER JOIN stores st
                ON st.store_id = s.store_id

            INNER JOIN products p
                ON p.product_id = s.product_id
        """

        conditions = []
        params: list[Any] = []

        if store_id:

            conditions.append(
                "s.store_id = %s"
            )

            params.append(store_id)

        if product_id:

            conditions.append(
                "s.product_id = %s"
            )

            params.append(product_id)

        if conditions:

            sql += (
                " WHERE "
                + " AND ".join(conditions)
            )

        sql += """
            ORDER BY s.date DESC
        """

        with self._connect() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    sql,
                    params,
                )

                return cur.fetchall()

    # ============================================================
    # INVENTORY HISTORY
    # ============================================================

    def get_inventory_history(
        self,
        store_id: str | None = None,
        product_id: str | None = None,
    ) -> list[dict[str, Any]]:

        sql = """
            SELECT
                h.id,

                h.store_id,
                s.store_name,

                h.product_id,
                p.product_name,

                h.previous_stock,
                h.new_stock,
                h.change_quantity,

                h.reason,
                h.created_at

            FROM inventory_history h

            INNER JOIN stores s
                ON s.store_id = h.store_id

            INNER JOIN products p
                ON p.product_id = h.product_id
        """

        conditions = []
        params: list[Any] = []

        if store_id:

            conditions.append(
                "h.store_id = %s"
            )

            params.append(store_id)

        if product_id:

            conditions.append(
                "h.product_id = %s"
            )

            params.append(product_id)

        if conditions:

            sql += (
                " WHERE "
                + " AND ".join(conditions)
            )

        sql += """
            ORDER BY h.created_at DESC
        """

        with self._connect() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    sql,
                    params,
                )

                return cur.fetchall()

    # ============================================================
    # PANDAS: STORES
    # ============================================================

    @property
    def stores(self) -> pd.DataFrame:

        rows = self.get_stores()

        return pd.DataFrame(rows)

    # ============================================================
    # PANDAS: PRODUCTS
    # ============================================================

    @property
    def products(self) -> pd.DataFrame:

        rows = self.get_products()

        return pd.DataFrame(rows)

    # ============================================================
    # PANDAS: INVENTORY
    # ============================================================

    @property
    def inventory(self) -> pd.DataFrame:

        rows = self.inventory_list()

        return pd.DataFrame(rows)

    # ============================================================
    # PANDAS: SALES
    # ============================================================

    @property
    def sales(self) -> pd.DataFrame:

        rows = self.get_sales()

        df = pd.DataFrame(rows)

        if not df.empty:

            if "date" in df.columns:

                df["date"] = pd.to_datetime(
                    df["date"]
                )

            if "units_sold" in df.columns:

                df["units_sold"] = pd.to_numeric(
                    df["units_sold"]
                )

            if "revenue" in df.columns:

                df["revenue"] = pd.to_numeric(
                    df["revenue"]
                )

        return df

    # ============================================================
    # DATABASE COUNTS
    # ============================================================

    def count_records(self) -> dict[str, int]:

        tables = [
            "stores",
            "products",
            "inventory",
            "inventory_history",
            "sales",
        ]

        counts: dict[str, int] = {}

        with self._connect() as conn:

            with conn.cursor() as cur:

                for table in tables:

                    cur.execute(
                        f"""
                        SELECT COUNT(*) AS count
                        FROM {table}
                        """
                    )

                    row = cur.fetchone()

                    counts[table] = int(
                        row["count"]
                    )

        return counts

    # ============================================================
    # DATABASE STATUS
    # ============================================================

    def database_status(self) -> dict[str, Any]:

        try:

            with self._connect() as conn:

                with conn.cursor() as cur:

                    cur.execute(
                        """
                        SELECT
                            NOW() AS server_time,
                            current_database()
                                AS database_name
                        """
                    )

                    result = cur.fetchone()

            return {
                "connected": True,
                "database":
                    "Neon PostgreSQL",

                "database_name":
                    result["database_name"],

                "server_time":
                    result["server_time"],

                "counts":
                    self.count_records(),
            }

        except Exception as exc:

            return {
                "connected": False,
                "database":
                    "Neon PostgreSQL",

                "error": str(exc),
            }

    # ============================================================
    # DELETE PRODUCT
    # ============================================================

    def delete_product(
        self,
        product_id: str,
    ) -> None:

        with self._connect() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    DELETE FROM products
                    WHERE product_id = %s
                    """,
                    (product_id,),
                )

                if cur.rowcount == 0:

                    raise ValueError(
                        f"Product '{product_id}' "
                        "does not exist."
                    )

    # ============================================================
    # DELETE STORE
    # ============================================================

    def delete_store(
        self,
        store_id: str,
    ) -> None:

        with self._connect() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    DELETE FROM stores
                    WHERE store_id = %s
                    """,
                    (store_id,),
                )

                if cur.rowcount == 0:

                    raise ValueError(
                        f"Store '{store_id}' "
                        "does not exist."
                    )

    # ============================================================
    # DEVELOPMENT RESET
    # ============================================================

    def clear_all_data(self) -> None:
        """
        DEVELOPMENT ONLY.

        Deletes all StoreSense data from Neon.

        Do NOT expose this through a public API route.
        """

        with self._connect() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    TRUNCATE TABLE
                        inventory_history,
                        sales,
                        inventory,
                        products,
                        stores
                    RESTART IDENTITY
                    CASCADE
                    """
                )