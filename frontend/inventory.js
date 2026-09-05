/* ============================================================
   StoreSense
   Inventory Control Center
   frontend/inventory.js

   Responsibilities:
   - Load inventory, stores, products and alerts
   - Calculate inventory health
   - Filter / search / sort
   - Show evidence
   - Update stock
   - Export visible inventory
   - Never fabricate historical movement data
   ============================================================ */

(() => {
    "use strict";

    /* =========================================================
       STATE
       ========================================================= */

    const state = {
        stores: [],
        products: [],
        inventory: [],
        attention: [],
        filteredInventory: [],
        selectedItem: null,
        currentStatus: "all",
        loading: false,
        savingStock: false
    };


    /* =========================================================
       DOM
       ========================================================= */

    const $ = (id) => document.getElementById(id);

    const el = {
        /* Filters */
        storeFilter: $("storeFilter"),
        searchInput: $("searchInput"),
        categoryFilter: $("categoryFilter"),
        statusFilter: $("statusFilter"),
        sortFilter: $("sortFilter"),
        clearFilterBtn: $("clearFilterBtn"),
        emptyClearBtn: $("emptyClearBtn"),

        /* Actions */
        retryBtn: $("retryBtn"),
        refreshBtn: $("refreshBtn"),
        addStockBtn: $("addStockBtn"),
        exportBtn: $("exportBtn"),

        /* Status counts */
        healthyCount: $("healthyCount"),
        lowCount: $("lowCount"),
        stockoutCount: $("stockoutCount"),
        slowCount: $("slowCount"),

        /* Summary */
        totalStock: $("totalStock"),
        totalProducts: $("totalProducts"),
        immediateRisk: $("immediateRisk"),
        excessRisk: $("excessRisk"),
        recordCount: $("recordCount"),
        registerState: $("registerState"),

        /* Main states */
        loadingState: $("loadingState"),
        errorState: $("errorState"),
        errorMessage: $("errorMessage"),
        emptyState: $("emptyState"),
        tableWrapper: $("tableWrapper"),
        tableBody: $("inventoryTableBody"),

        /* Attention */
        attentionGrid: $("attentionGrid"),

        /* Movement */
        selectedProduct: $("selectedProduct"),
        movementEmpty: $("movementEmpty"),
        movementContent: $("movementContent"),
        movementStock: $("movementStock"),
        movementSales: $("movementSales"),
        movementDaily: $("movementDaily"),
        movementDays: $("movementDays"),
        movementPercent: $("movementPercent"),
        movementBarFill: $("movementBarFill"),
        movementCoverageLabel: $("movementCoverageLabel"),
        movementInsightText: $("movementInsightText"),

        /* Product modal */
        productModal: $("productModal"),
        closeProductModal: $("closeProductModal"),
        modalCloseBtn: $("modalCloseBtn"),
        modalActionBtn: $("modalActionBtn"),
        modalProductName: $("modalProductName"),
        modalProductMeta: $("modalProductMeta"),
        modalStatus: $("modalStatus"),
        modalStock: $("modalStock"),
        modalDailySales: $("modalDailySales"),
        modalDaysLeft: $("modalDaysLeft"),
        modal30DaySales: $("modal30DaySales"),
        modalRecommendation: $("modalRecommendation"),
        modalEvidence: $("modalEvidence"),

        /* Stock modal */
        stockModal: $("stockModal"),
        closeStockModal: $("closeStockModal"),
        cancelStockBtn: $("cancelStockBtn"),
        stockForm: $("stockForm"),
        stockStore: $("stockStore"),
        stockProduct: $("stockProduct"),
        stockQuantity: $("stockQuantity"),
        stockReason: $("stockReason"),
        stockFormError: $("stockFormError"),
        saveStockBtn: $("saveStockBtn"),

        /* Status buttons */
        statusButtons: document.querySelectorAll("[data-status]")
    };


    /* =========================================================
       BASIC UTILITIES
       ========================================================= */

    function num(value, fallback = 0) {
        const n = Number(value);
        return Number.isFinite(n) ? n : fallback;
    }


    function integer(value) {
        return Math.round(num(value)).toLocaleString("en-IN");
    }


    function decimal(value, digits = 1) {
        return num(value).toLocaleString(
            "en-IN",
            {
                minimumFractionDigits: digits,
                maximumFractionDigits: digits
            }
        );
    }


    function escapeHTML(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }


    function show(node) {
        if (!node) return;
        node.classList.remove("hidden");
    }


    function hide(node) {
        if (!node) return;
        node.classList.add("hidden");
    }


    function text(node, value) {
        if (node) {
            node.textContent = value ?? "";
        }
    }


    function arrayFrom(payload, keys = []) {
        if (Array.isArray(payload)) {
            return payload;
        }

        for (const key of keys) {
            if (Array.isArray(payload?.[key])) {
                return payload[key];
            }
        }

        return [];
    }


    function safeLower(value) {
        return String(value ?? "").trim().toLowerCase();
    }


    /* =========================================================
       API
       ========================================================= */

    async function request(url, options = {}) {
        const response = await fetch(
            url,
            {
                ...options,
                headers: {
                    "Content-Type": "application/json",
                    ...(options.headers || {})
                }
            }
        );

        let payload = {};

        try {
            payload = await response.json();
        } catch (_) {
            payload = {};
        }

        if (!response.ok) {
            throw new Error(
                payload.detail ||
                payload.message ||
                `Request failed (${response.status})`
            );
        }

        return payload;
    }


    /* =========================================================
       IDENTIFIERS
       ========================================================= */

    function getProductId(item) {
        return String(
            item?.product_id ??
            item?.productId ??
            item?.id ??
            ""
        );
    }


    function getStoreId(item) {
        return String(
            item?.store_id ??
            item?.storeId ??
            item?.store ??
            ""
        );
    }


    function getProductName(product) {
        return (
            product?.product_name ??
            product?.productName ??
            product?.name ??
            getProductId(product)
        );
    }


    function getStoreName(store) {
        return (
            store?.store_name ??
            store?.storeName ??
            store?.name ??
            getStoreId(store)
        );
    }


    /* =========================================================
       LOOKUPS
       ========================================================= */

    function findProduct(productId) {
        return state.products.find(
            product =>
                getProductId(product) === String(productId)
        );
    }


    function findStore(storeId) {
        return state.stores.find(
            store =>
                getStoreId(store) === String(storeId)
        );
    }


    function findInventoryItem(productId, storeId) {
        return state.inventory.find(
            item =>
                String(item.product_id) === String(productId) &&
                String(item.store_id) === String(storeId)
        );
    }


    /* =========================================================
       NORMALIZE INVENTORY
       ========================================================= */

    function normalizeInventory(raw) {
        const productId = getProductId(raw);
        const storeId = getStoreId(raw);

        const product = findProduct(productId) || {};
        const store = findStore(storeId) || {};

        return {
            ...raw,

            product_id: productId,
            store_id: storeId,

            product_name:
                raw.product_name ??
                raw.productName ??
                product.product_name ??
                product.name ??
                `Product ${productId}`,

            category:
                raw.category ??
                product.category ??
                "Uncategorized",

            store_name:
                raw.store_name ??
                raw.storeName ??
                store.store_name ??
                store.name ??
                `Store ${storeId}`,

            stock: num(
                raw.stock ??
                raw.quantity ??
                raw.current_stock ??
                0
            ),

            price: num(
                raw.price ??
                product.price ??
                0
            )
        };
    }


    /* =========================================================
       ALERT HELPERS
       ========================================================= */

    function alertType(alert) {
        return safeLower(
            alert?.type ??
            alert?.alert_type ??
            alert?.category ??
            ""
        );
    }


    function isInventoryAlert(alert) {
        const type = alertType(alert);

        return (
            type.includes("stockout") ||
            type.includes("stock-out") ||
            type.includes("stock out") ||
            type.includes("low stock") ||
            type === "low" ||
            type.includes("stock risk") ||
            type.includes("slow") ||
            type.includes("non-moving") ||
            type.includes("nonmoving")
        );
    }


    function attentionFor(item) {
        const pid = String(item.product_id);
        const sid = String(item.store_id);

        /*
         * Prefer store-specific alerts.
         */
        const storeSpecific = state.attention.find(alert => {
            const alertPid = getProductId(alert);
            const alertSid = getStoreId(alert);

            if (alertPid !== pid) {
                return false;
            }

            if (!alertSid || alertSid !== sid) {
                return false;
            }

            return true;
        });

        if (storeSpecific) {
            return storeSpecific;
        }

        /*
         * Then allow product-level alerts.
         */
        return state.attention.find(alert => {
            const alertPid = getProductId(alert);
            const alertSid = getStoreId(alert);

            return (
                alertPid === pid &&
                !alertSid
            );
        });
    }


    function inventoryAlertFor(item) {
        const pid = String(item.product_id);
        const sid = String(item.store_id);

        const storeSpecific = state.attention.find(alert => {
            const alertPid = getProductId(alert);
            const alertSid = getStoreId(alert);

            return (
                alertPid === pid &&
                alertSid === sid &&
                isInventoryAlert(alert)
            );
        });

        if (storeSpecific) {
            return storeSpecific;
        }

        return state.attention.find(alert => {
            const alertPid = getProductId(alert);
            const alertSid = getStoreId(alert);

            return (
                alertPid === pid &&
                !alertSid &&
                isInventoryAlert(alert)
            );
        });
    }


    /* =========================================================
       SALES SIGNALS
       ========================================================= */

    function sales30(item) {
        const alert = attentionFor(item);

        const candidates = [
            item?.units_30d,
            item?.sales_30d,
            item?.units_sold_30d,
            alert?.units_30d,
            alert?.sales_30d,
            alert?.units_sold_30d
        ];

        for (const value of candidates) {
            if (
                value !== undefined &&
                value !== null &&
                Number.isFinite(Number(value))
            ) {
                return Number(value);
            }
        }

        return 0;
    }


    function dailySales(item) {
        const explicit =
            item?.avg_daily_sales ??
            item?.average_daily_sales ??
            item?.daily_sales;

        if (
            explicit !== undefined &&
            explicit !== null &&
            num(explicit) > 0
        ) {
            return num(explicit);
        }

        const units = sales30(item);

        return units > 0
            ? units / 30
            : 0;
    }


    function daysLeft(item) {
        const explicit =
            item?.days_to_stockout ??
            item?.days_left ??
            item?.days_remaining;

        if (
            explicit !== undefined &&
            explicit !== null &&
            Number.isFinite(Number(explicit))
        ) {
            return Math.max(
                0,
                Number(explicit)
            );
        }

        const daily = dailySales(item);

        if (daily <= 0) {
            return null;
        }

        return num(item.stock) / daily;
    }


    /* =========================================================
       INVENTORY STATUS
       ========================================================= */

    function statusFor(item) {
        const stock = num(item.stock);
        const alert = inventoryAlertFor(item);
        const type = alertType(alert);

        /*
         * Backend inventory signal first.
         */

        if (
            type.includes("stockout") ||
            type.includes("stock-out") ||
            type.includes("stock out")
        ) {
            return "stockout";
        }


        if (
            type.includes("slow") ||
            type.includes("non-moving") ||
            type.includes("nonmoving")
        ) {
            return "slow";
        }


        if (
            type.includes("low stock") ||
            type === "low" ||
            type.includes("stock risk")
        ) {
            return "low";
        }


        /*
         * Direct stock evidence.
         */

        if (stock <= 0) {
            return "stockout";
        }


        const days = daysLeft(item);

        if (
            days !== null &&
            days <= 3
        ) {
            return "stockout";
        }


        if (
            days !== null &&
            days <= 7
        ) {
            return "low";
        }


        /*
         * Slow-moving requires BOTH:
         * - significant stock
         * - very low recent sales
         */

        const recentSales = sales30(item);

        if (
            stock >= 50 &&
            recentSales <= 5
        ) {
            return "slow";
        }


        return "healthy";
    }


    function statusLabel(status) {
        const labels = {
            healthy: "Healthy",
            low: "Low Stock",
            stockout: "Stock-out Risk",
            slow: "Slow-moving"
        };

        return labels[status] || "Healthy";
    }


    function statusRank(status) {
        return {
            stockout: 4,
            low: 3,
            slow: 2,
            healthy: 1
        }[status] || 0;
    }


    /* =========================================================
       LOAD STORES
       ========================================================= */

    async function loadStores() {

    const payload =
        await request(
            "/api/stores"
        );

    state.stores =
        arrayFrom(
            payload,
            [
                "stores",
                "items",
                "data"
            ]
        );

    // Main inventory filter
    populateStores();

    // Add Stock modal store dropdown
    populateStockStores();
}


    /* =========================================================
       LOAD PRODUCTS
       ========================================================= */

    async function loadProducts() {
        const payload = await request("/api/products");

        state.products = arrayFrom(
            payload,
            [
                "products",
                "items",
                "data"
            ]
        );

        populateCategories();
        populateStockProducts();
    }


    /* =========================================================
       LOAD INVENTORY
       ========================================================= */

    async function loadInventory() {
        const store =
            el.storeFilter?.value ||
            "all";

        let url = "/api/inventory";

        if (store !== "all") {
            url +=
                `?store_id=${encodeURIComponent(store)}`;
        }

        const payload = await request(url);

        state.inventory = arrayFrom(
            payload,
            [
                "items",
                "inventory",
                "data"
            ]
        ).map(normalizeInventory);
    }


    /* =========================================================
       LOAD ATTENTION
       ========================================================= */

    async function loadAttention() {
        const payload =
            await request("/api/attention");

        state.attention = arrayFrom(
            payload,
            [
                "items",
                "attention",
                "alerts",
                "data"
            ]
        );
    }


    /* =========================================================
       LOAD ALL
       ========================================================= */

    async function loadAll() {
        if (state.loading) {
            return;
        }

        state.loading = true;

        setLoadingState(true);
        hide(el.errorState);

        try {
            /*
             * Reference data first.
             */
            await Promise.all([
                loadStores(),
                loadProducts()
            ]);

            /*
             * Inventory + attention after
             * reference data is available.
             */
            await Promise.all([
                loadInventory(),
                loadAttention()
            ]);

            state.inventory =
                state.inventory.map(
                    normalizeInventory
                );

            render();

        } catch (error) {
            console.error(
                "Inventory load failed:",
                error
            );

            show(el.errorState);

            text(
                el.errorMessage,
                error.message ||
                "Unable to load inventory."
            );

            hide(el.tableWrapper);
            hide(el.emptyState);

        } finally {
            state.loading = false;
            setLoadingState(false);
        }
    }


    /* =========================================================
       LOADING UI
       ========================================================= */

    function setLoadingState(loading) {
        if (loading) {
            show(el.loadingState);
            hide(el.tableWrapper);
            hide(el.emptyState);

            text(
                el.registerState,
                "Synchronising..."
            );

            if (el.refreshBtn) {
                el.refreshBtn.disabled = true;
            }

        } else {
            hide(el.loadingState);

            text(
                el.registerState,
                `${state.inventory.length} records`
            );

            if (el.refreshBtn) {
                el.refreshBtn.disabled = false;
            }
        }
    }


    /* =========================================================
       FILTER OPTIONS
       ========================================================= */

    function populateStores() {
        if (!el.storeFilter) {
            return;
        }

        const current =
            el.storeFilter.value;

        el.storeFilter.innerHTML =
            `<option value="all">All Stores</option>`;

        state.stores.forEach(store => {
            const id =
                getStoreId(store);

            if (!id) {
                return;
            }

            const option =
                document.createElement("option");

            option.value = id;
            option.textContent =
                getStoreName(store);

            el.storeFilter.appendChild(option);
        });

        if (
            [...el.storeFilter.options].some(
                option =>
                    option.value === current
            )
        ) {
            el.storeFilter.value = current;
        }
    }


    function populateCategories() {
        if (!el.categoryFilter) {
            return;
        }

        const current =
            el.categoryFilter.value;

        const categories = [
            ...new Set(
                state.products
                    .map(
                        product =>
                            product.category
                    )
                    .filter(Boolean)
            )
        ].sort(
            (a, b) =>
                String(a).localeCompare(
                    String(b)
                )
        );

        el.categoryFilter.innerHTML =
            `<option value="all">All Categories</option>`;

        categories.forEach(category => {
            const option =
                document.createElement("option");

            option.value = category;
            option.textContent = category;

            el.categoryFilter.appendChild(option);
        });

        if (
            categories.includes(current)
        ) {
            el.categoryFilter.value =
                current;
        }
    }


    function populateStockStores() {
        if (!el.stockStore) {
            return;
        }

        const current =
            el.stockStore.value;

        el.stockStore.innerHTML =
            `<option value="">Select store</option>`;

        state.stores.forEach(store => {
            const id =
                getStoreId(store);

            if (!id) {
                return;
            }

            const option =
                document.createElement("option");

            option.value = id;
            option.textContent =
                getStoreName(store);

            el.stockStore.appendChild(option);
        });

        if (
            [...el.stockStore.options].some(
                option =>
                    option.value === current
            )
        ) {
            el.stockStore.value =
                current;
        }
    }


    function populateStockProducts() {
        if (!el.stockProduct) {
            return;
        }

        el.stockProduct.innerHTML =
            `<option value="">Select product</option>`;

        state.products.forEach(product => {
            const id =
                getProductId(product);

            if (!id) {
                return;
            }

            const option =
                document.createElement("option");

            option.value = id;
            option.textContent =
                getProductName(product);

            el.stockProduct.appendChild(option);
        });
    }


    /* =========================================================
       FILTERS
       ========================================================= */

    function applyFilters() {
        const search =
            String(
                el.searchInput?.value ||
                ""
            )
            .trim()
            .toLowerCase();

        const category =
            el.categoryFilter?.value ||
            "all";

        const status =
            el.statusFilter?.value ||
            state.currentStatus ||
            "all";

        const store =
            el.storeFilter?.value ||
            "all";

        let items =
            [...state.inventory];

        if (store !== "all") {
            items =
                items.filter(
                    item =>
                        String(item.store_id) ===
                        String(store)
                );
        }

        if (category !== "all") {
            items =
                items.filter(
                    item =>
                        String(item.category) ===
                        String(category)
                );
        }

        if (search) {
            items =
                items.filter(item => {
                    const searchable = [
                        item.product_name,
                        item.product_id,
                        item.category,
                        item.store_name
                    ]
                    .join(" ")
                    .toLowerCase();

                    return searchable.includes(
                        search
                    );
                });
        }

        if (status !== "all") {
            items =
                items.filter(
                    item =>
                        statusFor(item) ===
                        status
                );
        }

        items = sortItems(items);

        state.filteredInventory = items;

        renderTable(items);

        text(
            el.recordCount,
            `${integer(items.length)} ${items.length === 1 ? "record" : "records"}`
        );

        updateClearFilterVisibility();
    }


    function sortItems(items) {
        const sort =
            el.sortFilter?.value ||
            "risk";

        return items.sort((a, b) => {
            switch (sort) {

                case "stock-high":
                    return b.stock - a.stock;


                case "stock-low":
                    return a.stock - b.stock;


                case "days-low": {
                    const ad = daysLeft(a);
                    const bd = daysLeft(b);

                    return (
                        (ad ?? Infinity) -
                        (bd ?? Infinity)
                    );
                }


                case "name":
                    return String(
                        a.product_name
                    ).localeCompare(
                        String(
                            b.product_name
                        )
                    );


                case "risk":
                default:
                    return (
                        riskScore(b) -
                        riskScore(a)
                    );
            }
        });
    }


    function riskScore(item) {
        const status =
            statusFor(item);

        const score =
            statusRank(status);

        const days =
            daysLeft(item);

        if (days !== null) {
            return (
                score * 1000 +
                Math.max(
                    0,
                    100 - days
                )
            );
        }

        return score * 1000;
    }


    function hasActiveFilters() {
        return (
            (
                el.searchInput?.value ||
                ""
            ).trim() !== "" ||

            (
                el.categoryFilter?.value ||
                "all"
            ) !== "all" ||

            (
                el.statusFilter?.value ||
                "all"
            ) !== "all" ||

            (
                el.storeFilter?.value ||
                "all"
            ) !== "all"
        );
    }


    function updateClearFilterVisibility() {
        if (!el.clearFilterBtn) {
            return;
        }

        if (hasActiveFilters()) {
            show(el.clearFilterBtn);
        } else {
            hide(el.clearFilterBtn);
        }
    }


    function clearFilters() {
        if (el.searchInput) {
            el.searchInput.value = "";
        }

        if (el.categoryFilter) {
            el.categoryFilter.value = "all";
        }

        if (el.statusFilter) {
            el.statusFilter.value = "all";
        }

        if (el.storeFilter) {
            el.storeFilter.value = "all";
        }

        state.currentStatus = "all";

        el.statusButtons.forEach(button => {
            button.classList.toggle(
                "active",
                button.dataset.status === "all"
            );
        });

        /*
         * Re-load all-store inventory because
         * store filtering changes the API request.
         */
        loadInventory()
            .then(() => {
                render();
            })
            .catch(error => {
                console.error(
                    "Unable to reset inventory:",
                    error
                );

                applyFilters();
            });
    }


    /* =========================================================
       SUMMARY
       ========================================================= */

    function renderSummary() {
        const items =
            state.inventory;

        const totalStock =
            items.reduce(
                (sum, item) =>
                    sum + num(item.stock),
                0
            );

        const products =
            new Set(
                items.map(
                    item =>
                        item.product_id
                )
            );

        let immediate = 0;
        let excess = 0;

        items.forEach(item => {
            const status =
                statusFor(item);

            if (
                status === "stockout" ||
                status === "low"
            ) {
                immediate++;
            }

            if (status === "slow") {
                excess++;
            }
        });

        text(
            el.totalStock,
            integer(totalStock)
        );

        text(
            el.totalProducts,
            integer(products.size)
        );

        text(
            el.immediateRisk,
            integer(immediate)
        );

        text(
            el.excessRisk,
            integer(excess)
        );
    }


    /* =========================================================
       STATUS COUNTS
       ========================================================= */

    function renderStatusCounts() {
        const counts = {
            healthy: 0,
            low: 0,
            stockout: 0,
            slow: 0
        };

        state.inventory.forEach(item => {
            const status =
                statusFor(item);

            if (
                Object.prototype.hasOwnProperty.call(
                    counts,
                    status
                )
            ) {
                counts[status]++;
            }
        });

        text(
            el.healthyCount,
            integer(counts.healthy)
        );

        text(
            el.lowCount,
            integer(counts.low)
        );

        text(
            el.stockoutCount,
            integer(counts.stockout)
        );

        text(
            el.slowCount,
            integer(counts.slow)
        );
    }


    /* =========================================================
       TABLE
       ========================================================= */

    function renderTable(items) {
        if (!el.tableBody) {
            return;
        }

        el.tableBody.innerHTML = "";

        if (!items.length) {
            hide(el.tableWrapper);
            show(el.emptyState);
            return;
        }

        hide(el.emptyState);
        show(el.tableWrapper);

        items.forEach(item => {
            const status =
                statusFor(item);

            const daily =
                dailySales(item);

            const days =
                daysLeft(item);

            const row =
                document.createElement("tr");

            row.dataset.productId =
                item.product_id;

            row.dataset.storeId =
                item.store_id;

            const priority =
                status === "stockout"
                    ? "Immediate"
                    : status === "low"
                        ? "Review"
                        : status === "slow"
                            ? "Monitor"
                            : "Stable";

            row.innerHTML = `
                <td>
                    <div class="product-cell">
                        <strong>
                            ${escapeHTML(
                                item.product_name
                            )}
                        </strong>

                        <span>
                            ${escapeHTML(
                                item.product_id
                            )}
                        </span>
                    </div>
                </td>

                <td>
                    ${escapeHTML(
                        item.category
                    )}
                </td>

                <td>
                    ${escapeHTML(
                        item.store_name
                    )}
                </td>

                <td>
                    <div class="stock-cell">
                        <strong>
                            ${integer(item.stock)}
                        </strong>

                        ${
                            item.stock <= 0
                                ? `<span class="stock-warning">Out</span>`
                                : ""
                        }
                    </div>
                </td>

                <td>
                    ${
                        daily > 0
                            ? `${decimal(daily)}`
                            : "—"
                    }
                </td>

                <td>
                    <span
                        class="days-left ${daysClass(days)}"
                    >
                        ${
                            days === null
                                ? "No sales data"
                                : `${decimal(days)} days`
                        }
                    </span>
                </td>

                <td>
                    <div class="status-cell">
                        <span
                            class="inventory-status status-${status}"
                        >
                            ${statusLabel(status)}
                        </span>

                        <small>
                            ${priority}
                        </small>
                    </div>
                </td>

                <td>
                    <button
                        type="button"
                        class="table-action"
                        data-action="view"
                        data-product-id="${escapeHTML(
                            item.product_id
                        )}"
                        data-store-id="${escapeHTML(
                            item.store_id
                        )}"
                    >
                        Inspect
                    </button>
                </td>
            `;

            el.tableBody.appendChild(row);
        });
    }


    function daysClass(days) {
        if (days === null) {
            return "days-unknown";
        }

        if (days <= 3) {
            return "days-critical";
        }

        if (days <= 7) {
            return "days-warning";
        }

        return "days-good";
    }


    /* =========================================================
       ATTENTION
       ========================================================= */

    function renderAttention() {
        if (!el.attentionGrid) {
            return;
        }

        const alerts =
            state.attention.slice(0, 6);

        if (!alerts.length) {
            el.attentionGrid.innerHTML = `
                <div class="attention-empty">
                    <strong>
                        No active attention signals
                    </strong>

                    <span>
                        StoreSense has not detected an
                        inventory condition requiring attention.
                    </span>
                </div>
            `;

            return;
        }

        el.attentionGrid.innerHTML =
            alerts
                .map(
                    alert =>
                        renderAttentionCard(alert)
                )
                .join("");
    }


    function renderAttentionCard(alert) {
        const pid =
            getProductId(alert);

        const sid =
            getStoreId(alert);

        const product =
            alert.product_name ??
            getProductName(
                findProduct(pid)
            );

        const store =
            alert.store_name ??
            getStoreName(
                findStore(sid)
            );

        const type =
            alert.type ??
            alert.alert_type ??
            alert.category ??
            "Attention";

        const priority =
            alert.priority ??
            alert.severity ??
            "Review";

        const stock =
            alert.current_stock ??
            alert.stock;

        const units =
            alert.units_30d ??
            alert.sales_30d ??
            alert.units_sold_30d;

        const days =
            alert.days_to_stockout ??
            alert.days_left ??
            alert.days_remaining;

        const change =
            alert.change_pct ??
            alert.percent_change;

        let facts = "";

        if (
            stock !== undefined &&
            stock !== null &&
            Number.isFinite(Number(stock))
        ) {
            facts += `
                <span>
                    Stock
                    <strong>
                        ${integer(stock)}
                    </strong>
                </span>
            `;
        }

        if (
            days !== undefined &&
            days !== null &&
            Number.isFinite(Number(days))
        ) {
            facts += `
                <span>
                    Days left
                    <strong>
                        ${decimal(days)}
                    </strong>
                </span>
            `;
        }

        if (
            units !== undefined &&
            units !== null &&
            Number.isFinite(Number(units))
        ) {
            facts += `
                <span>
                    30d sales
                    <strong>
                        ${integer(units)}
                    </strong>
                </span>
            `;
        }

        if (
            change !== undefined &&
            change !== null &&
            Number.isFinite(Number(change))
        ) {
            facts += `
                <span>
                    Change
                    <strong>
                        ${formatChange(change)}
                    </strong>
                </span>
            `;
        }

        return `
            <button
                type="button"
                class="attention-card"
                data-alert-product="${escapeHTML(pid)}"
                data-alert-store="${escapeHTML(sid)}"
            >
                <div class="attention-card-top">
                    <span class="attention-type">
                        ${escapeHTML(
                            formatAlertType(type)
                        )}
                    </span>

                    <span class="attention-priority">
                        ${escapeHTML(
                            String(priority)
                        )}
                    </span>
                </div>

                <h4>
                    ${escapeHTML(product)}
                </h4>

                <p>
                    ${escapeHTML(
                        store ||
                        "Store-level signal"
                    )}
                </p>

                <div class="attention-facts">
                    ${facts}
                </div>

                <div class="attention-open">
                    Inspect evidence →
                </div>
            </button>
        `;
    }


    function formatAlertType(value) {
        return String(
            value || "Attention"
        )
            .replace(/[-_]/g, " ")
            .replace(
                /\b\w/g,
                c => c.toUpperCase()
            );
    }


    function formatChange(value) {
        const n = num(value);

        return n > 0
            ? `+${decimal(n)}%`
            : `${decimal(n)}%`;
    }


    /* =========================================================
       PRODUCT INSPECTION
       ========================================================= */

    async function inspectProduct(
        productId,
        storeId
    ) {
        let item =
            findInventoryItem(
                productId,
                storeId
            );

        /*
         * If the current inventory view is filtered
         * and does not contain the item, try loading
         * the selected store directly.
         */
        if (!item && storeId) {
            try {
                const payload =
                    await request(
                        `/api/inventory?store_id=${encodeURIComponent(
                            storeId
                        )}`
                    );

                const records =
                    arrayFrom(
                        payload,
                        [
                            "items",
                            "inventory",
                            "data"
                        ]
                    ).map(normalizeInventory);

                item =
                    records.find(
                        record =>
                            String(
                                record.product_id
                            ) ===
                            String(productId)
                    );

            } catch (error) {
                console.warn(
                    "Unable to load inspection item:",
                    error
                );
            }
        }

        if (!item) {
            console.warn(
                "Inventory item not found",
                productId,
                storeId
            );

            return;
        }

        state.selectedItem = item;

        renderMovement(item);
        renderModal(item);

        show(el.productModal);

        try {
            const query =
                storeId
                    ? `?store_id=${encodeURIComponent(
                        storeId
                    )}`
                    : "";

            const payload =
                await request(
                    `/api/evidence/${encodeURIComponent(
                        productId
                    )}${query}`
                );

            renderEvidence(
                payload,
                item
            );

        } catch (error) {
            console.warn(
                "Evidence endpoint unavailable:",
                error
            );

            renderEvidence(
                null,
                item
            );
        }
    }


    /* =========================================================
       PRODUCT MODAL
       ========================================================= */

    function renderModal(item) {
        const status =
            statusFor(item);

        const daily =
            dailySales(item);

        const days =
            daysLeft(item);

        const recentSales =
            sales30(item);

        text(
            el.modalProductName,
            item.product_name
        );

        text(
            el.modalProductMeta,
            `${item.category} • ${item.store_name}`
        );

        if (el.modalStatus) {
            el.modalStatus.textContent =
                statusLabel(status);

            el.modalStatus.className =
                `modal-status inventory-status status-${status}`;
        }

        text(
            el.modalStock,
            integer(item.stock)
        );

        text(
            el.modalDailySales,
            daily > 0
                ? decimal(daily)
                : "—"
        );

        text(
            el.modalDaysLeft,
            days === null
                ? "—"
                : `${decimal(days)} days`
        );

        text(
            el.modal30DaySales,
            integer(recentSales)
        );

        renderRecommendation(item);

        if (el.modalEvidence) {
            el.modalEvidence.innerHTML = `
                <div class="evidence-loading">
                    Loading verified evidence...
                </div>
            `;
        }
    }


    function renderRecommendation(item) {
        const status =
            statusFor(item);

        const alert =
            attentionFor(item);

        let recommendation = "";

        if (alert?.recommendation) {
            recommendation =
                alert.recommendation;

        } else if (alert?.action) {
            recommendation =
                alert.action;

        } else if (status === "stockout") {
            recommendation =
                "Review replenishment immediately. " +
                "Current stock coverage indicates a near-term " +
                "stock-out condition.";

        } else if (status === "low") {
            recommendation =
                "Plan replenishment before projected stock " +
                "coverage reaches zero.";

        } else if (status === "slow") {
            recommendation =
                "Avoid automatically increasing stock. " +
                "Review the current inventory level against " +
                "recent sales velocity.";

        } else {
            recommendation =
                "No immediate inventory action is indicated " +
                "by the available stock and sales signals.";
        }

        text(
            el.modalRecommendation,
            recommendation
        );
    }


    /* =========================================================
       EVIDENCE
       ========================================================= */

    function renderEvidence(
        payload,
        item
    ) {
        if (!el.modalEvidence) {
            return;
        }

        const daily =
            dailySales(item);

        const days =
            daysLeft(item);

        const recentSales =
            sales30(item);

        let html = `
            <div class="evidence-row">
                <span>
                    Current stock
                </span>

                <strong>
                    ${integer(item.stock)} units
                </strong>
            </div>

            <div class="evidence-row">
                <span>
                    30-day units sold
                </span>

                <strong>
                    ${integer(recentSales)}
                </strong>
            </div>

            <div class="evidence-row">
                <span>
                    Average daily sales
                </span>

                <strong>
                    ${
                        daily > 0
                            ? `${decimal(daily)} units/day`
                            : "No sales data"
                    }
                </strong>
            </div>

            <div class="evidence-row">
                <span>
                    Estimated coverage
                </span>

                <strong>
                    ${
                        days === null
                            ? "Not calculable"
                            : `${decimal(days)} days`
                    }
                </strong>
            </div>
        `;

        const evidence =
            payload?.evidence ??
            payload?.records ??
            payload?.items ??
            payload?.data;

        if (
            evidence &&
            typeof evidence === "object"
        ) {
            const entries =
                Array.isArray(evidence)
                    ? evidence.slice(0, 5)
                    : Object.entries(evidence)
                        .filter(
                            ([key, value]) =>
                                value !== null &&
                                value !== undefined &&
                                ![
                                    "product_id",
                                    "store_id"
                                ].includes(key)
                        )
                        .slice(0, 8);

            if (entries.length) {
                html += `
                    <div class="evidence-api">
                        <div class="evidence-api-title">
                            BACKEND EVIDENCE
                        </div>
                `;

                if (
                    Array.isArray(evidence)
                ) {
                    entries.forEach(record => {
                        html += `
                            <div class="evidence-row">
                                <span>
                                    Record
                                </span>

                                <strong>
                                    ${escapeHTML(
                                        JSON.stringify(record)
                                    )}
                                </strong>
                            </div>
                        `;
                    });

                } else {
                    entries.forEach(
                        ([key, value]) => {
                            let display = value;

                            if (
                                typeof value ===
                                "object"
                            ) {
                                display =
                                    JSON.stringify(
                                        value
                                    );
                            }

                            html += `
                                <div class="evidence-row">
                                    <span>
                                        ${escapeHTML(
                                            prettifyKey(key)
                                        )}
                                    </span>

                                    <strong>
                                        ${escapeHTML(
                                            display
                                        )}
                                    </strong>
                                </div>
                            `;
                        }
                    );
                }

                html += `
                    </div>
                `;
            }
        }

        el.modalEvidence.innerHTML =
            html;
    }


    function prettifyKey(key) {
        return String(key)
            .replace(/_/g, " ")
            .replace(
                /\b\w/g,
                c => c.toUpperCase()
            );
    }


    /* =========================================================
       STOCK POSITION
       ========================================================= */

    function renderMovement(item) {
        if (!item) {
            show(el.movementEmpty);
            hide(el.movementContent);

            text(
                el.selectedProduct,
                "No product selected"
            );

            return;
        }

        hide(el.movementEmpty);
        show(el.movementContent);

        text(
            el.selectedProduct,
            `${item.product_name} • ${item.store_name}`
        );

        const stock =
            num(item.stock);

        const sales =
            sales30(item);

        const daily =
            dailySales(item);

        const days =
            daysLeft(item);

        text(
            el.movementStock,
            integer(stock)
        );

        text(
            el.movementSales,
            integer(sales)
        );

        text(
            el.movementDaily,
            daily > 0
                ? decimal(daily)
                : "—"
        );

        text(
            el.movementDays,
            days === null
                ? "—"
                : `${decimal(days)} days`
        );

        /*
         * Coverage bar:
         * 30 days = full planning horizon.
         */

        let percentage = 0;

        if (days !== null) {
            percentage =
                Math.min(
                    100,
                    Math.max(
                        0,
                        days / 30 * 100
                    )
                );
        }

        if (el.movementBarFill) {
            el.movementBarFill.style.width =
                `${percentage}%`;
        }

        let coverageLabel =
            "No sales basis";

        let insight =
            "There is not enough recent sales data " +
            "to estimate stock coverage.";

        if (days !== null) {
            if (days <= 3) {
                coverageLabel =
                    "Critical";

                insight =
                    `At the current sales rate, approximately ` +
                    `${decimal(days)} days of stock coverage remain. ` +
                    `Immediate review is recommended.`;

            } else if (days <= 7) {
                coverageLabel =
                    "Low";

                insight =
                    `Current stock provides approximately ` +
                    `${decimal(days)} days of coverage at the observed ` +
                    `sales velocity.`;

            } else {
                coverageLabel =
                    "Adequate";

                insight =
                    `Current stock provides approximately ` +
                    `${decimal(days)} days of coverage at the observed ` +
                    `sales velocity.`;
            }
        }

        text(
            el.movementCoverageLabel,
            coverageLabel
        );

        text(
            el.movementInsightText,
            insight
        );

        const alert =
            attentionFor(item);

        const change =
            alert?.change_pct ??
            alert?.percent_change;

        text(
            el.movementPercent,
            change !== undefined &&
            change !== null &&
            Number.isFinite(Number(change))
                ? formatChange(change)
                : "No trend signal"
        );
    }


    /* =========================================================
       STOCK UPDATE
       ========================================================= */

    function openStockModal(prefill = {}) {
        hideStockError();

        populateStockStores();
        populateStockProducts();

        if (el.stockStore) {
            el.stockStore.value =
                prefill.storeId || "";
        }

        if (el.stockProduct) {
            el.stockProduct.value =
                prefill.productId || "";
        }

        if (el.stockQuantity) {
            el.stockQuantity.value = "";
        }

        if (el.stockReason) {
            el.stockReason.value =
                "replenishment";
        }

        show(el.stockModal);

        setTimeout(
            () => {
                el.stockQuantity?.focus();
            },
            50
        );
    }


    function closeStockModal() {
        hide(el.stockModal);
        hideStockError();
    }


    function hideStockError() {
        if (!el.stockFormError) {
            return;
        }

        el.stockFormError.textContent = "";

        hide(el.stockFormError);
    }


    function stockError(message) {
        if (!el.stockFormError) {
            return;
        }

        text(
            el.stockFormError,
            message
        );

        show(el.stockFormError);
    }


    async function saveStock() {
        if (state.savingStock) {
            return;
        }

        hideStockError();

        const storeId =
            el.stockStore?.value ||
            "";

        const productId =
            el.stockProduct?.value ||
            "";

        const quantity =
            Number(
                el.stockQuantity?.value
            );

        const reason =
            (
                el.stockReason?.value ||
                "replenishment"
            ).trim();

        if (!storeId) {
            stockError(
                "Select a store."
            );
            return;
        }

        if (!productId) {
            stockError(
                "Select a product."
            );
            return;
        }

        if (
            !Number.isFinite(quantity) ||
            quantity <= 0
        ) {
            stockError(
                "Enter a quantity greater than 0."
            );
            return;
        }

        /*
         * Backend PUT /api/inventory sets
         * absolute stock.
         *
         * Therefore:
         *
         * newStock = existingStock + quantity
         */

        state.savingStock = true;
        setSaveState(true);

        try {
            /*
             * Always fetch selected store's
             * current inventory first.
             */
            const payload =
                await request(
                    `/api/inventory?store_id=${encodeURIComponent(
                        storeId
                    )}`
                );

            const records =
                arrayFrom(
                    payload,
                    [
                        "items",
                        "inventory",
                        "data"
                    ]
                );

            const existingRaw =
                records.find(
                    record =>
                        String(
                            getProductId(record)
                        ) ===
                        String(productId)
                );

            const currentStock =
                num(
                    existingRaw?.stock ??
                    existingRaw?.quantity ??
                    existingRaw?.current_stock ??
                    0
                );

            const newStock =
                currentStock + quantity;

            await request(
                "/api/inventory",
                {
                    method: "PUT",

                    body: JSON.stringify({
                        store_id:
                            storeId,

                        product_id:
                            productId,

                        stock:
                            newStock,

                        reason:
                            reason ||
                            "replenishment"
                    })
                }
            );

            closeStockModal();

            /*
             * Reload the page data.
             */
            await loadAll();

            /*
             * Restore selected item.
             */
            const updated =
                findInventoryItem(
                    productId,
                    storeId
                );

            if (updated) {
                state.selectedItem =
                    updated;

                renderMovement(
                    updated
                );
            }

        } catch (error) {
            console.error(
                "Stock update failed:",
                error
            );

            stockError(
                error.message ||
                "Unable to update inventory."
            );

        } finally {
            state.savingStock = false;
            setSaveState(false);
        }
    }


    function setSaveState(saving) {
        if (!el.saveStockBtn) {
            return;
        }

        el.saveStockBtn.disabled =
            saving;

        el.saveStockBtn.textContent =
            saving
                ? "Updating..."
                : "Add Stock";
    }


    /* =========================================================
       EXPORT
       ========================================================= */

    function exportInventory() {
        const items =
            state.filteredInventory.length
                ? state.filteredInventory
                : state.inventory;

        if (!items.length) {
            window.alert(
                "There is no inventory data to export."
            );

            return;
        }

        const headers = [
            "Product ID",
            "Product",
            "Category",
            "Store ID",
            "Store",
            "Stock",
            "Avg Daily Sales",
            "Days Left",
            "Status"
        ];

        const rows =
            items.map(item => [
                item.product_id,
                item.product_name,
                item.category,
                item.store_id,
                item.store_name,
                item.stock,
                dailySales(item),
                daysLeft(item) ?? "",
                statusLabel(
                    statusFor(item)
                )
            ]);

        const csv =
            [
                headers,
                ...rows
            ]
                .map(row =>
                    row
                        .map(value =>
                            `"${String(
                                value ?? ""
                            ).replace(
                                /"/g,
                                '""'
                            )}"`
                        )
                        .join(",")
                )
                .join("\n");

        const blob =
            new Blob(
                [csv],
                {
                    type:
                        "text/csv;charset=utf-8;"
                }
            );

        const url =
            URL.createObjectURL(blob);

        const link =
            document.createElement("a");

        link.href = url;

        link.download =
            `storesense-inventory-${new Date()
                .toISOString()
                .slice(0, 10)}.csv`;

        document.body.appendChild(link);

        link.click();

        link.remove();

        URL.revokeObjectURL(url);
    }


    /* =========================================================
       STATUS TILE
       ========================================================= */

    function setStatus(status) {
        state.currentStatus =
            status || "all";

        if (el.statusFilter) {
            el.statusFilter.value =
                state.currentStatus;
        }

        el.statusButtons.forEach(button => {
            button.classList.toggle(
                "active",
                button.dataset.status ===
                state.currentStatus
            );
        });

        applyFilters();
    }


    /* =========================================================
       MODALS
       ========================================================= */

    function closeProductModal() {
        hide(el.productModal);
    }


    /* =========================================================
       EVENTS
       ========================================================= */

    function bindEvents() {

        /* -----------------------------------------------------
           Store filter
           ----------------------------------------------------- */

        el.storeFilter?.addEventListener(
            "change",
            async () => {
                try {
                    await loadInventory();
                    render();
                } catch (error) {
                    console.error(
                        "Store filter failed:",
                        error
                    );

                    show(el.errorState);

                    text(
                        el.errorMessage,
                        error.message ||
                        "Unable to load inventory."
                    );
                }
            }
        );


        /* -----------------------------------------------------
           Search
           ----------------------------------------------------- */

        el.searchInput?.addEventListener(
            "input",
            applyFilters
        );


        /* -----------------------------------------------------
           Category
           ----------------------------------------------------- */

        el.categoryFilter?.addEventListener(
            "change",
            applyFilters
        );


        /* -----------------------------------------------------
           Status dropdown
           ----------------------------------------------------- */

        el.statusFilter?.addEventListener(
            "change",
            event =>
                setStatus(
                    event.target.value
                )
        );


        /* -----------------------------------------------------
           Sort
           ----------------------------------------------------- */

        el.sortFilter?.addEventListener(
            "change",
            applyFilters
        );


        /* -----------------------------------------------------
           Clear filters
           ----------------------------------------------------- */

        el.clearFilterBtn?.addEventListener(
            "click",
            clearFilters
        );

        el.emptyClearBtn?.addEventListener(
            "click",
            clearFilters
        );


        /* -----------------------------------------------------
           Status cards
           ----------------------------------------------------- */

        el.statusButtons.forEach(button => {
            button.addEventListener(
                "click",
                () =>
                    setStatus(
                        button.dataset.status
                    )
            );
        });


        /* -----------------------------------------------------
           Refresh
           ----------------------------------------------------- */

        el.refreshBtn?.addEventListener(
            "click",
            loadAll
        );


        /* -----------------------------------------------------
           Retry
           ----------------------------------------------------- */

        el.retryBtn?.addEventListener(
            "click",
            loadAll
        );


        /* -----------------------------------------------------
           Add stock
           ----------------------------------------------------- */

        el.addStockBtn?.addEventListener(
            "click",
            () =>
                openStockModal()
        );


        /* -----------------------------------------------------
           Export
           ----------------------------------------------------- */

        el.exportBtn?.addEventListener(
            "click",
            exportInventory
        );


        /*
         * Also support buttons with data-action="export".
         */
        document.addEventListener(
            "click",
            event => {
                const button =
                    event.target.closest(
                        "[data-action='export']"
                    );

                if (button) {
                    exportInventory();
                }
            }
        );


        /* -----------------------------------------------------
           Inventory table
           ----------------------------------------------------- */

        el.tableBody?.addEventListener(
            "click",
            event => {
                const button =
                    event.target.closest(
                        "[data-action='view']"
                    );

                if (!button) {
                    return;
                }

                inspectProduct(
                    button.dataset.productId,
                    button.dataset.storeId
                );
            }
        );


        /* -----------------------------------------------------
           Attention cards
           ----------------------------------------------------- */

        el.attentionGrid?.addEventListener(
            "click",
            event => {
                const card =
                    event.target.closest(
                        "[data-alert-product]"
                    );

                if (!card) {
                    return;
                }

                inspectProduct(
                    card.dataset.alertProduct,
                    card.dataset.alertStore
                );
            }
        );


        /* -----------------------------------------------------
           Product modal
           ----------------------------------------------------- */

        el.closeProductModal?.addEventListener(
            "click",
            closeProductModal
        );

        el.modalCloseBtn?.addEventListener(
            "click",
            closeProductModal
        );


        /* -----------------------------------------------------
           Modal action = Add Stock
           ----------------------------------------------------- */

        el.modalActionBtn?.addEventListener(
            "click",
            () => {
                const item =
                    state.selectedItem;

                if (!item) {
                    return;
                }

                closeProductModal();

                openStockModal({
                    storeId:
                        item.store_id,

                    productId:
                        item.product_id
                });
            }
        );


        /* -----------------------------------------------------
           Stock modal
           ----------------------------------------------------- */

        el.closeStockModal?.addEventListener(
            "click",
            closeStockModal
        );

        el.cancelStockBtn?.addEventListener(
            "click",
            closeStockModal
        );


        /*
         * Important:
         * Handle the form submit itself.
         * This prevents browser page reload.
         */
        el.stockForm?.addEventListener(
            "submit",
            event => {
                event.preventDefault();
                saveStock();
            }
        );


        /* -----------------------------------------------------
           Outside click
           ----------------------------------------------------- */

        el.productModal?.addEventListener(
            "click",
            event => {
                if (
                    event.target ===
                    el.productModal
                ) {
                    closeProductModal();
                }
            }
        );


        el.stockModal?.addEventListener(
            "click",
            event => {
                if (
                    event.target ===
                    el.stockModal
                ) {
                    closeStockModal();
                }
            }
        );


        /* -----------------------------------------------------
           Escape
           ----------------------------------------------------- */

        document.addEventListener(
            "keydown",
            event => {
                if (
                    event.key !==
                    "Escape"
                ) {
                    return;
                }

                closeProductModal();
                closeStockModal();
            }
        );


        /* -----------------------------------------------------
           Keyboard shortcut
           R = refresh
           ----------------------------------------------------- */

        document.addEventListener(
            "keydown",
            event => {
                if (
                    event.key.toLowerCase() ===
                    "r" &&

                    ![
                        "INPUT",
                        "TEXTAREA",
                        "SELECT"
                    ].includes(
                        document.activeElement?.tagName
                    )
                ) {
                    loadAll();
                }
            }
        );
    }


    /* =========================================================
       SIDEBAR LAYOUT SYNC
       ========================================================= */

    function syncSidebarLayout() {
        const sidebar =
            document.getElementById(
                "storeSidebar"
            );

        const collapseButton =
            document.getElementById(
                "sidebarCollapseButton"
            );

        if (!sidebar) {
            return;
        }

        const collapsed =
            sidebar.classList.contains(
                "collapsed"
            ) ||

            sidebar.classList.contains(
                "is-collapsed"
            ) ||

            sidebar.getAttribute(
                "data-collapsed"
            ) === "true" ||

            collapseButton?.getAttribute(
                "aria-expanded"
            ) === "false";

        document.body.classList.toggle(
            "sidebar-collapsed",
            collapsed
        );
    }


    /* =========================================================
       WATCH SIDEBAR CHANGES
       ========================================================= */

    function initializeSidebarLayoutSync() {
        /*
         * Sidebar is injected asynchronously.
         */

        const observer =
            new MutationObserver(() => {
                syncSidebarLayout();

                const collapseButton =
                    document.getElementById(
                        "sidebarCollapseButton"
                    );

                if (
                    collapseButton &&
                    !collapseButton.dataset
                        .layoutBound
                ) {
                    collapseButton.dataset
                        .layoutBound = "true";

                    collapseButton.addEventListener(
                        "click",
                        () => {
                            requestAnimationFrame(
                                () => {
                                    syncSidebarLayout();
                                }
                            );
                        }
                    );
                }
            });

        observer.observe(
            document.body,
            {
                childList: true,
                subtree: true,
                attributes: true,
                attributeFilter: [
                    "class",
                    "aria-expanded",
                    "data-collapsed"
                ]
            }
        );

        syncSidebarLayout();
    }


    /* =========================================================
       RENDER EVERYTHING
       ========================================================= */

    function render() {
        renderSummary();
        renderStatusCounts();
        renderAttention();
        applyFilters();

        /*
         * Keep selected product alive after refresh.
         */
        if (state.selectedItem) {
            const updated =
                findInventoryItem(
                    state.selectedItem.product_id,
                    state.selectedItem.store_id
                );

            if (updated) {
                state.selectedItem =
                    updated;

                renderMovement(
                    updated
                );
            }
        }
    }
    function populateStockStores() {

    if (!el.stockStore) {
        return;
    }

    const current = el.stockStore.value;

    el.stockStore.innerHTML =
        `<option value="">Select store</option>`;

    state.stores.forEach(store => {

        const id = getStoreId(store);

        if (!id) {
            return;
        }

        const option =
            document.createElement("option");

        option.value = id;

        option.textContent =
            getStoreName(store);

        el.stockStore.appendChild(option);

    });

    if (
        [...el.stockStore.options]
            .some(option => option.value === current)
    ) {
        el.stockStore.value = current;
    }
}

    /* =========================================================
       INITIALIZATION
       ========================================================= */

    async function init() {
        console.log(
            "StoreSense Inventory Control Center initialized."
        );

        bindEvents();

        state.currentStatus = "all";

        if (el.statusFilter) {
            el.statusFilter.value = "all";
        }

        el.statusButtons.forEach(button => {
            button.classList.toggle(
                "active",
                button.dataset.status === "all"
            );
        });

        renderMovement(null);

        initializeSidebarLayoutSync();

        await loadAll();
    }


    /* =========================================================
       START
       ========================================================= */

    if (
        document.readyState ===
        "loading"
    ) {
        document.addEventListener(
            "DOMContentLoaded",
            init
        );
    } else {
        init();
    }

})();