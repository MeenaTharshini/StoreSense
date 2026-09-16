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

# database.py is inside StoreSense/src/
# Project root is one directory above src/
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


class RetailData:
    """
    StoreSense PostgreSQL data layer with user-level isolation.

    Data ownership:

        users
          |
          +---- stores
          |       |
          |       +---- inventory
          |       +---- sales
          |       +---- inventory_history
          |
          +---- products
                  |
                  +---- inventory
                  +---- sales
                  +---- inventory_history

    Authentication users are stored separately by src/auth.py.

    Because the authentication database and retail database are
    separate systems, owner_user_id is stored as TEXT rather than
    using a PostgreSQL foreign key.

    IMPORTANT:
        Every RetailData instance belongs to exactly one user.

        RetailData(owner_user_id="user-123")

    All read and write operations are automatically scoped to
    that owner_user_id.
    """

    # ========================================================
    # INITIALIZATION
    # ========================================================

    def __init__(
        self,
        owner_user_id: str,
        data_dir: Path | None = None,
    ):
        owner_user_id = str(owner_user_id).strip()

        if not owner_user_id:
            raise ValueError(
                "owner_user_id is required. "
                "Retail data must always belong to an authenticated user."
            )

        self.owner_user_id = owner_user_id

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

        # Test connection.
        self._test_connection()

        # Create/migrate tables and indexes.
        self._initialize_database()

    # ============================================================
    # CONNECTION
    # ============================================================

    def _connect(self):
        """
        Create a new PostgreSQL connection.
        """

        return psycopg.connect(
            self.database_url,
            row_factory=dict_row,
            connect_timeout=10,
        )

    def _test_connection(self):
        """
        Verify that PostgreSQL is reachable.
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
                "Could not connect to PostgreSQL.\n"
                f"Database error: {exc}"
            ) from exc

    # ============================================================
    # DATABASE INITIALIZATION
    # ============================================================

    def _initialize_database(self):
        """
        Create the StoreSense schema and migrate older tables.

        Existing data is NOT deleted.

        For an older database that does not yet have owner_user_id,
        the column is added.

        Existing unowned rows can optionally be assigned to a
        development user by setting:

            STORESENSE_DEFAULT_OWNER_USER_ID=your-user-id

        in .env.

        New rows are always created with self.owner_user_id.
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

                owner_user_id TEXT,

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

                owner_user_id TEXT,

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
            # OWNER COLUMNS FOR EXISTING DATABASES
            # ----------------------------------------------------

            """
            ALTER TABLE stores
            ADD COLUMN IF NOT EXISTS owner_user_id TEXT
            """,

            """
            ALTER TABLE products
            ADD COLUMN IF NOT EXISTS owner_user_id TEXT
            """,

            # ----------------------------------------------------
            # INDEXES
            # ----------------------------------------------------

            """
            CREATE INDEX IF NOT EXISTS idx_stores_owner
            ON stores(owner_user_id)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_products_owner
            ON products(owner_user_id)
            """,

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
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_inventory_history_store
            ON inventory_history(store_id)
            """,

            """
            CREATE INDEX IF NOT EXISTS idx_inventory_history_product
            ON inventory_history(product_id)
            """,
        ]

        with self._connect() as conn:
            with conn.cursor() as cur:

                for statement in statements:
                    cur.execute(statement)

                # ------------------------------------------------
                # OPTIONAL DEVELOPMENT MIGRATION
                # ------------------------------------------------
                #
                # Existing rows from the old schema have NULL
                # owner_user_id.
                #
                # If the developer provides a default owner,
                # assign those old rows to that user.
                #
                # This does NOT move already-owned rows.
                # ------------------------------------------------

                default_owner = (
                    os.getenv(
                        "STORESENSE_DEFAULT_OWNER_USER_ID",
                        "",
                    )
                    .strip()
                )

                if default_owner:

                    cur.execute(
                        """
                        UPDATE stores
                        SET owner_user_id = %s
                        WHERE owner_user_id IS NULL
                        """,
                        (default_owner,),
                    )

                    cur.execute(
                        """
                        UPDATE products
                        SET owner_user_id = %s
                        WHERE owner_user_id IS NULL
                        """,
                        (default_owner,),
                    )

    # ============================================================
    # HEALTH CHECK
    # ============================================================

    def health_check(self) -> bool:
        """
        Check whether PostgreSQL is reachable.
        """

        try:

            with self._connect() as conn:
                with conn.cursor() as cur:

                    cur.execute(
                        "SELECT 1 AS ok"
                    )

                    result = cur.fetchone()

                    return bool(
                        result
                        and result["ok"] == 1
                    )

        except Exception:
            return False

    # ============================================================
    # INTERNAL OWNERSHIP HELPERS
    # ============================================================

    def _verify_store(
        self,
        cur,
        store_id: str,
    ) -> dict[str, Any] | None:
        """
        Return a store only if it belongs to the current user.
        """

        cur.execute(
            """
            SELECT
                store_id,
                store_name,
                location,
                owner_user_id,
                created_at
            FROM stores
            WHERE store_id = %s
              AND owner_user_id = %s
            """,
            (
                store_id,
                self.owner_user_id,
            ),
        )

        return cur.fetchone()

    def _verify_product(
        self,
        cur,
        product_id: str,
    ) -> dict[str, Any] | None:
        """
        Return a product only if it belongs to the current user.
        """

        cur.execute(
            """
            SELECT
                product_id,
                product_name,
                category,
                price,
                owner_user_id,
                created_at
            FROM products
            WHERE product_id = %s
              AND owner_user_id = %s
            """,
            (
                product_id,
                self.owner_user_id,
            ),
        )

        return cur.fetchone()

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
                location,
                owner_user_id
            )
            VALUES (
                %s,
                %s,
                %s,
                %s
            )
            RETURNING
                store_id,
                store_name,
                location,
                owner_user_id,
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
                            self.owner_user_id,
                        ),
                    )

                    return cur.fetchone()

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
                owner_user_id,
                created_at
            FROM stores
            WHERE owner_user_id = %s
            ORDER BY store_name
        """

        with self._connect() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    sql,
                    (self.owner_user_id,),
                )

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
                        owner_user_id,
                        created_at
                    FROM stores
                    WHERE store_id = %s
                      AND owner_user_id = %s
                    """,
                    (
                        store_id,
                        self.owner_user_id,
                    ),
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
                price,
                owner_user_id
            )
            VALUES (
                %s,
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
                owner_user_id,
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
                            self.owner_user_id,
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
                owner_user_id,
                created_at
            FROM products
            WHERE owner_user_id = %s
            ORDER BY product_name
        """

        with self._connect() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    sql,
                    (self.owner_user_id,),
                )

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
                        owner_user_id,
                        created_at
                    FROM products
                    WHERE product_id = %s
                      AND owner_user_id = %s
                    """,
                    (
                        product_id,
                        self.owner_user_id,
                    ),
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
        reason = (
            str(reason).strip()
            or "manual update"
        )

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
                # Verify store ownership
                # ------------------------------------------------

                store = self._verify_store(
                    cur,
                    store_id,
                )

                if store is None:
                    raise ValueError(
                        f"Store '{store_id}' does not exist "
                        "or does not belong to this user."
                    )

                # ------------------------------------------------
                # Verify product ownership
                # ------------------------------------------------

                product = self._verify_product(
                    cur,
                    product_id,
                )

                if product is None:
                    raise ValueError(
                        f"Product '{product_id}' does not exist "
                        "or does not belong to this user."
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
                # Insert/update inventory
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
                    "store_name": store["store_name"],
                    "product_name": product["product_name"],
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

            WHERE s.owner_user_id = %s
              AND p.owner_user_id = %s
        """

        params: list[Any] = [
            self.owner_user_id,
            self.owner_user_id,
        ]

        if store_id:

            sql += """
                AND i.store_id = %s
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
              AND s.owner_user_id = %s
              AND p.owner_user_id = %s
        """

        with self._connect() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    sql,
                    (
                        store_id,
                        product_id,
                        self.owner_user_id,
                        self.owner_user_id,
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

            # ----------------------------------------------------
            # Verify requested store belongs to user
            # ----------------------------------------------------

            with self._connect() as conn:
                with conn.cursor() as cur:

                    store = self._verify_store(
                        cur,
                        store_id,
                    )

                    if store is None:
                        raise ValueError(
                            f"Store '{store_id}' does not exist "
                            "or does not belong to this user."
                        )

                    sql = """
                        SELECT
                            p.product_id,
                            p.product_name,
                            p.category,
                            p.price,
                            COALESCE(
                                i.stock,
                                0
                            ) AS stock

                        FROM products p

                        LEFT JOIN inventory i
                            ON i.product_id = p.product_id
                           AND i.store_id = %s

                        WHERE p.owner_user_id = %s

                        ORDER BY p.product_name
                    """

                    cur.execute(
                        sql,
                        (
                            store_id,
                            self.owner_user_id,
                        ),
                    )

                    return cur.fetchall()

        # --------------------------------------------------------
        # All stores belonging to current user
        # --------------------------------------------------------

        sql = """
            SELECT
                p.product_id,
                p.product_name,
                p.category,
                p.price,

                COALESCE(
                    SUM(
                        CASE
                            WHEN s.owner_user_id = %s
                            THEN i.stock
                            ELSE 0
                        END
                    ),
                    0
                ) AS stock

            FROM products p

            LEFT JOIN inventory i
                ON i.product_id = p.product_id

            LEFT JOIN stores s
                ON s.store_id = i.store_id

            WHERE p.owner_user_id = %s

            GROUP BY
                p.product_id,
                p.product_name,
                p.category,
                p.price

            ORDER BY p.product_name
        """

        with self._connect() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    sql,
                    (
                        self.owner_user_id,
                        self.owner_user_id,
                    ),
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
                # Verify store ownership
                # ------------------------------------------------

                store = self._verify_store(
                    cur,
                    store_id,
                )

                if not store:
                    raise ValueError(
                        f"Store '{store_id}' does not exist "
                        "or does not belong to this user."
                    )

                # ------------------------------------------------
                # Verify product ownership
                # ------------------------------------------------

                product = self._verify_product(
                    cur,
                    product_id,
                )

                if not product:
                    raise ValueError(
                        f"Product '{product_id}' does not exist "
                        "or does not belong to this user."
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

            WHERE st.owner_user_id = %s
              AND p.owner_user_id = %s
        """

        params: list[Any] = [
            self.owner_user_id,
            self.owner_user_id,
        ]

        if store_id:

            sql += """
                AND s.store_id = %s
            """

            params.append(store_id)

        if product_id:

            sql += """
                AND s.product_id = %s
            """

            params.append(product_id)

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

            WHERE s.owner_user_id = %s
              AND p.owner_user_id = %s
        """

        params: list[Any] = [
            self.owner_user_id,
            self.owner_user_id,
        ]

        if store_id:

            sql += """
                AND h.store_id = %s
            """

            params.append(store_id)

        if product_id:

            sql += """
                AND h.product_id = %s
            """

            params.append(product_id)

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
                    df["units_sold"],
                    errors="coerce",
                )

            if "revenue" in df.columns:

                df["revenue"] = pd.to_numeric(
                    df["revenue"],
                    errors="coerce",
                )

        return df

    # ============================================================
    # DATABASE COUNTS
    # ============================================================

    def count_records(self) -> dict[str, int]:
        """
        Return record counts for the CURRENT USER only.
        """

        counts: dict[str, int] = {}

        with self._connect() as conn:
            with conn.cursor() as cur:

                # ------------------------------------------------
                # Stores
                # ------------------------------------------------

                cur.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM stores
                    WHERE owner_user_id = %s
                    """,
                    (self.owner_user_id,),
                )

                counts["stores"] = int(
                    cur.fetchone()["count"]
                )

                # ------------------------------------------------
                # Products
                # ------------------------------------------------

                cur.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM products
                    WHERE owner_user_id = %s
                    """,
                    (self.owner_user_id,),
                )

                counts["products"] = int(
                    cur.fetchone()["count"]
                )

                # ------------------------------------------------
                # Inventory
                # ------------------------------------------------

                cur.execute(
                    """
                    SELECT COUNT(*) AS count

                    FROM inventory i

                    INNER JOIN stores s
                        ON s.store_id = i.store_id

                    INNER JOIN products p
                        ON p.product_id = i.product_id

                    WHERE s.owner_user_id = %s
                      AND p.owner_user_id = %s
                    """,
                    (
                        self.owner_user_id,
                        self.owner_user_id,
                    ),
                )

                counts["inventory"] = int(
                    cur.fetchone()["count"]
                )

                # ------------------------------------------------
                # Inventory history
                # ------------------------------------------------

                cur.execute(
                    """
                    SELECT COUNT(*) AS count

                    FROM inventory_history h

                    INNER JOIN stores s
                        ON s.store_id = h.store_id

                    INNER JOIN products p
                        ON p.product_id = h.product_id

                    WHERE s.owner_user_id = %s
                      AND p.owner_user_id = %s
                    """,
                    (
                        self.owner_user_id,
                        self.owner_user_id,
                    ),
                )

                counts["inventory_history"] = int(
                    cur.fetchone()["count"]
                )

                # ------------------------------------------------
                # Sales
                # ------------------------------------------------

                cur.execute(
                    """
                    SELECT COUNT(*) AS count

                    FROM sales sa

                    INNER JOIN stores s
                        ON s.store_id = sa.store_id

                    INNER JOIN products p
                        ON p.product_id = sa.product_id

                    WHERE s.owner_user_id = %s
                      AND p.owner_user_id = %s
                    """,
                    (
                        self.owner_user_id,
                        self.owner_user_id,
                    ),
                )

                counts["sales"] = int(
                    cur.fetchone()["count"]
                )

        return counts

    # ============================================================
    # DATABASE STATUS
    # ============================================================

    def database_status(self) -> dict[str, Any]:
        """
        Return database status and counts for the current user.
        """

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

                "owner_user_id":
                    self.owner_user_id,

                "counts":
                    self.count_records(),
            }

        except Exception as exc:

            return {
                "connected": False,

                "database":
                    "Neon PostgreSQL",

                "owner_user_id":
                    self.owner_user_id,

                "error":
                    str(exc),
            }

    # ============================================================
    # DELETE PRODUCT
    # ============================================================

    def delete_product(
        self,
        product_id: str,
    ) -> None:

        product_id = str(product_id).strip()

        with self._connect() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    DELETE FROM products
                    WHERE product_id = %s
                      AND owner_user_id = %s
                    """,
                    (
                        product_id,
                        self.owner_user_id,
                    ),
                )

                if cur.rowcount == 0:

                    raise ValueError(
                        f"Product '{product_id}' "
                        "does not exist or does not belong "
                        "to this user."
                    )

    # ============================================================
    # DELETE STORE
    # ============================================================

    def delete_store(
        self,
        store_id: str,
    ) -> None:

        store_id = str(store_id).strip()

        with self._connect() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    DELETE FROM stores
                    WHERE store_id = %s
                      AND owner_user_id = %s
                    """,
                    (
                        store_id,
                        self.owner_user_id,
                    ),
                )

                if cur.rowcount == 0:

                    raise ValueError(
                        f"Store '{store_id}' "
                        "does not exist or does not belong "
                        "to this user."
                    )

    # ============================================================
    # DEVELOPMENT RESET
    # ============================================================

    def clear_all_data(self) -> None:
        """
        DEVELOPMENT ONLY.

        Delete ONLY the current user's retail data.

        This intentionally does NOT use TRUNCATE because TRUNCATE
        would remove every user's data.

        Child records are removed automatically because inventory,
        sales and inventory_history reference stores/products
        with ON DELETE CASCADE.
        """

        with self._connect() as conn:
            with conn.cursor() as cur:

                # Delete owned stores first.
                # This cascades to:
                #   inventory
                #   sales
                #   inventory_history

                cur.execute(
                    """
                    DELETE FROM stores
                    WHERE owner_user_id = %s
                    """,
                    (self.owner_user_id,),
                )

                # Delete owned products.
                # This also cascades to any remaining child rows.

                cur.execute(
                    """
                    DELETE FROM products
                    WHERE owner_user_id = %s
                    """,
                    (self.owner_user_id,),
                )