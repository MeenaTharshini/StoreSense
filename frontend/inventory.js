/* ============================================================
   StoreSense — Inventory Control Center
   frontend/inventory.js
   ============================================================ */

(() => {
    "use strict";

    // ---------------------------------------------------------
    // State
    // ---------------------------------------------------------

    const state = {
        stores: [],
        products: [],
        inventory: [],
        attention: [],
        filteredInventory: [],
        selectedItem: null,
        currentStatus: "all",
        currentStore: "all"
    };

    // ---------------------------------------------------------
    // DOM helpers
    // ---------------------------------------------------------

    const $ = (id) => document.getElementById(id);

    const elements = {
        storeFilter: $("storeFilter"),
        searchInput: $("searchInput"),
        categoryFilter: $("categoryFilter"),
        statusFilter: $("statusFilter"),
        sortFilter: $("sortFilter"),

        totalStock: $("totalStock"),
        totalProducts: $("totalProducts"),
        immediateRisk: $("immediateRisk"),
        excessRisk: $("excessRisk"),
        recordCount: $("recordCount"),

        inventoryTableBody: $("inventoryTableBody"),
        inventoryLoading: $("inventoryLoading"),
        inventoryError: $("inventoryError"),
        inventoryEmpty: $("inventoryEmpty"),

        attentionGrid: $("attentionGrid"),

        selectedProduct: $("selectedProduct"),
        movementEmpty: $("movementEmpty"),
        movementContent: $("movementContent"),
        movementStock: $("movementStock"),
        movementSales: $("movementSales"),
        movementDaily: $("movementDaily"),
        movementDays: $("movementDays"),
        movementPercent: $("movementPercent"),
        movementBarFill: $("movementBarFill"),

        productModal: $("productModal"),
        modalProductName: $("modalProductName"),
        modalProductMeta: $("modalProductMeta"),
        modalStatus: $("modalStatus"),
        modalStock: $("modalStock"),
        modalDailySales: $("modalDailySales"),
        modalDaysLeft: $("modalDaysLeft"),
        modal30DaySales: $("modal30DaySales"),
        modalRecommendation: $("modalRecommendation"),
        modalEvidence: $("modalEvidence"),
        modalCloseBtn: $("modalCloseBtn"),
        modalActionBtn: $("modalActionBtn"),

        stockModal: $("stockModal"),
        stockStore: $("stockStore"),
        stockProduct: $("stockProduct"),
        stockQuantity: $("stockQuantity"),
        stockReason: $("stockReason"),
        stockFormError: $("stockFormError"),
        saveStockBtn: $("saveStockBtn"),

        refreshBtn: $("refreshBtn"),
        addStockBtn: $("addStockBtn"),

        statusButtons: document.querySelectorAll("[data-status]")
    };

    // ---------------------------------------------------------
    // Utility functions
    // ---------------------------------------------------------

    function number(value, fallback = 0) {
        const n = Number(value);
        return Number.isFinite(n) ? n : fallback;
    }

    function formatNumber(value) {
        return number(value).toLocaleString("en-IN", {
            maximumFractionDigits: 1
        });
    }

    function formatInteger(value) {
        return Math.round(number(value)).toLocaleString("en-IN");
    }

    function formatDays(value) {
        const n = number(value);

        if (!Number.isFinite(n) || n <= 0) {
            return "—";
        }

        return `${n.toFixed(1)} days`;
    }

    function escapeHTML(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function show(element) {
        if (element) {
            element.style.display = "";
        }
    }

    function hide(element) {
        if (element) {
            element.style.display = "none";
        }
    }

    function setText(element, value) {
        if (element) {
            element.textContent = value ?? "";
        }
    }

    function getArray(payload, keys = []) {
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

    async function fetchJSON(url, options = {}) {
        const response = await fetch(url, {
            ...options,
            headers: {
                "Content-Type": "application/json",
                ...(options.headers || {})
            }
        });

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

    // ---------------------------------------------------------
    // Data normalization
    // ---------------------------------------------------------

    function productId(item) {
        return String(
            item?.product_id ??
            item?.productId ??
            item?.id ??
            ""
        );
    }

    function storeId(item) {
        return String(
            item?.store_id ??
            item?.storeId ??
            item?.store ??
            ""
        );
    }

    function normalizeInventory(item) {
        const pid = productId(item);
        const sid = storeId(item);

        const product =
            state.products.find(
                p => productId(p) === pid
            ) || {};

        const store =
            state.stores.find(
                s => storeId(s) === sid
            ) || {};

        return {
            ...item,

            product_id: pid,
            store_id: sid,

            product_name:
                item.product_name ??
                item.productName ??
                product.product_name ??
                product.name ??
                `Product ${pid}`,

            category:
                item.category ??
                product.category ??
                "Uncategorized",

            store_name:
                item.store_name ??
                item.storeName ??
                store.store_name ??
                store.name ??
                `Store ${sid}`,

            stock: number(
                item.stock ??
                item.quantity ??
                item.current_stock ??
                0
            ),

            price: number(
                item.price ??
                product.price ??
                0
            )
        };
    }

    function findAttention(item) {
        const pid = productId(item);
        const sid = storeId(item);

        return state.attention.find(alert => {
            const alertPid = productId(alert);
            const alertSid = storeId(alert);

            return (
                alertPid === pid &&
                (!alertSid || !sid || alertSid === sid)
            );
        });
    }

    // ---------------------------------------------------------
    // Inventory status calculation
    // ---------------------------------------------------------

    function getInventoryStatus(item) {
        const stock = number(item.stock);
        const alert = findAttention(item);

        const alertType = String(
            alert?.type ??
            alert?.alert_type ??
            alert?.category ??
            ""
        ).toLowerCase();

        if (
            alertType.includes("stockout") ||
            alertType.includes("stock-out") ||
            alertType.includes("stock out")
        ) {
            return "stockout";
        }

        if (
            alertType.includes("slow") ||
            alertType.includes("non-moving") ||
            alertType.includes("nonmoving")
        ) {
            return "slow";
        }

        if (
            alertType.includes("drop") ||
            alertType.includes("low")
        ) {
            return "low";
        }

        const days = getDaysLeft(item);

        if (stock <= 0) {
            return "stockout";
        }

        if (days !== null && days <= 3) {
            return "stockout";
        }

        if (days !== null && days <= 7) {
            return "low";
        }

        const units30 = get30DaySales(item);

        if (
            stock >= 50 &&
            units30 <= 5
        ) {
            return "slow";
        }

        return "healthy";
    }

    function getStatusLabel(status) {
        const labels = {
            healthy: "Healthy",
            low: "Low Stock",
            stockout: "Stock-out Risk",
            slow: "Slow-moving"
        };

        return labels[status] || "Healthy";
    }

    function getStatusClass(status) {
        return `status-${status}`;
    }

    // ---------------------------------------------------------
    // Evidence helpers
    // ---------------------------------------------------------

    function get30DaySales(item) {
        const alert = findAttention(item);

        if (alert) {
            return number(
                alert.units_30d ??
                alert.sales_30d ??
                alert.units_sold_30d ??
                0
            );
        }

        return number(
            item.units_30d ??
            item.sales_30d ??
            item.units_sold_30d ??
            0
        );
    }

    function getDailySales(item) {
        const explicit = number(
            item.avg_daily_sales ??
            item.average_daily_sales ??
            item.daily_sales ??
            0
        );

        if (explicit > 0) {
            return explicit;
        }

        const units30 = get30DaySales(item);

        return units30 > 0 ? units30 / 30 : 0;
    }

    function getDaysLeft(item) {
        const explicit =
            item.days_to_stockout ??
            item.days_left ??
            item.days_remaining;

        if (
            explicit !== undefined &&
            explicit !== null &&
            Number.isFinite(Number(explicit))
        ) {
            return Math.max(0, Number(explicit));
        }

        const dailySales = getDailySales(item);

        if (dailySales <= 0) {
            return null;
        }

        return number(item.stock) / dailySales;
    }

    function getPriority(item) {
        const alert = findAttention(item);

        return String(
            alert?.priority ??
            alert?.severity ??
            ""
        ).toLowerCase();
    }

    // ---------------------------------------------------------
    // Load data
    // ---------------------------------------------------------

    async function loadStores() {
        const payload = await fetchJSON("/api/stores");

        state.stores = getArray(payload, [
            "stores",
            "items",
            "data"
        ]);

        populateStoreFilters();
        populateStockStores();
    }

    async function loadProducts() {
        const payload = await fetchJSON("/api/products");

        state.products = getArray(payload, [
            "products",
            "items",
            "data"
        ]);

        populateCategoryFilter();
        populateStockProducts();
    }

    async function loadInventory() {
        const selectedStore =
            elements.storeFilter?.value || "all";

        let url = "/api/inventory";

        if (
            selectedStore &&
            selectedStore !== "all"
        ) {
            url += `?store_id=${encodeURIComponent(selectedStore)}`;
        }

        const payload = await fetchJSON(url);

        const rawInventory = getArray(payload, [
            "items",
            "inventory",
            "data"
        ]);

        state.inventory = rawInventory.map(normalizeInventory);
    }

    async function loadAttention() {
        const payload = await fetchJSON("/api/attention");

        state.attention = getArray(payload, [
            "items",
            "attention",
            "alerts",
            "data"
        ]);
    }

    async function loadAll() {
        setLoading(true);
        hide(elements.inventoryError);

        try {
            await Promise.all([
                loadStores(),
                loadProducts()
            ]);

            await Promise.all([
                loadInventory(),
                loadAttention()
            ]);

            // Re-normalize after all reference data exists.
            state.inventory = state.inventory.map(
                normalizeInventory
            );

            renderEverything();

        } catch (error) {
            console.error("Inventory load error:", error);

            setText(
                elements.inventoryError,
                `Unable to load inventory: ${error.message}`
            );

            show(elements.inventoryError);

        } finally {
            setLoading(false);
        }
    }

    // ---------------------------------------------------------
    // Loading states
    // ---------------------------------------------------------

    function setLoading(isLoading) {
        if (isLoading) {
            show(elements.inventoryLoading);
            hide(elements.inventoryEmpty);
        } else {
            hide(elements.inventoryLoading);
        }
    }

    // ---------------------------------------------------------
    // Filter controls
    // ---------------------------------------------------------

    function populateStoreFilters() {
        if (!elements.storeFilter) return;

        const current = elements.storeFilter.value;

        elements.storeFilter.innerHTML =
            `<option value="all">All Stores</option>`;

        state.stores.forEach(store => {
            const id = storeId(store);

            if (!id) return;

            const name =
                store.store_name ??
                store.name ??
                id;

            const option =
                document.createElement("option");

            option.value = id;
            option.textContent = name;

            elements.storeFilter.appendChild(option);
        });

        if (
            [...elements.storeFilter.options]
                .some(option => option.value === current)
        ) {
            elements.storeFilter.value = current;
        }
    }

    function populateStockStores() {
        if (!elements.stockStore) return;

        elements.stockStore.innerHTML =
            `<option value="">Select store</option>`;

        state.stores.forEach(store => {
            const id = storeId(store);

            if (!id) return;

            const option =
                document.createElement("option");

            option.value = id;
            option.textContent =
                store.store_name ??
                store.name ??
                id;

            elements.stockStore.appendChild(option);
        });
    }

    function populateStockProducts() {
        if (!elements.stockProduct) return;

        elements.stockProduct.innerHTML =
            `<option value="">Select product</option>`;

        state.products.forEach(product => {
            const id = productId(product);

            if (!id) return;

            const option =
                document.createElement("option");

            option.value = id;
            option.textContent =
                product.product_name ??
                product.name ??
                id;

            elements.stockProduct.appendChild(option);
        });
    }

    function populateCategoryFilter() {
        if (!elements.categoryFilter) return;

        const current =
            elements.categoryFilter.value;

        const categories = [
            ...new Set(
                state.products
                    .map(p =>
                        p.category
                    )
                    .filter(Boolean)
            )
        ].sort();

        elements.categoryFilter.innerHTML =
            `<option value="all">All Categories</option>`;

        categories.forEach(category => {
            const option =
                document.createElement("option");

            option.value = category;
            option.textContent = category;

            elements.categoryFilter.appendChild(option);
        });

        if (
            categories.includes(current)
        ) {
            elements.categoryFilter.value = current;
        }
    }

    function applyFilters() {
        const search =
            String(
                elements.searchInput?.value || ""
            ).trim().toLowerCase();

        const category =
            elements.categoryFilter?.value || "all";

        const status =
            elements.statusFilter?.value ||
            state.currentStatus ||
            "all";

        const store =
            elements.storeFilter?.value || "all";

        let items = [...state.inventory];

        if (store !== "all") {
            items = items.filter(
                item =>
                    String(item.store_id) ===
                    String(store)
            );
        }

        if (category !== "all") {
            items = items.filter(
                item =>
                    String(item.category) ===
                    String(category)
            );
        }

        if (search) {
            items = items.filter(item => {
                const text = [
                    item.product_name,
                    item.category,
                    item.store_name,
                    item.product_id
                ]
                    .join(" ")
                    .toLowerCase();

                return text.includes(search);
            });
        }

        if (status !== "all") {
            items = items.filter(
                item =>
                    getInventoryStatus(item) ===
                    status
            );
        }

        items = sortInventory(items);

        state.filteredInventory = items;

        renderInventoryTable(items);
        updateRecordCount(items.length);
    }

    function sortInventory(items) {
        const sort =
            elements.sortFilter?.value ||
            "risk";

        return items.sort((a, b) => {
            switch (sort) {
                case "stock-high":
                    return b.stock - a.stock;

                case "stock-low":
                    return a.stock - b.stock;

                case "days-low": {
                    const ad = getDaysLeft(a);
                    const bd = getDaysLeft(b);

                    return (
                        (ad ?? Infinity) -
                        (bd ?? Infinity)
                    );
                }

                case "name":
                    return String(
                        a.product_name
                    ).localeCompare(
                        String(b.product_name)
                    );

                case "risk":
                default:
                    return riskScore(b) - riskScore(a);
            }
        });
    }

    function riskScore(item) {
        const status =
            getInventoryStatus(item);

        const statusScore = {
            stockout: 4,
            low: 3,
            slow: 2,
            healthy: 1
        };

        return (
            statusScore[status] || 0
        );
    }

    // ---------------------------------------------------------
    // Render summary
    // ---------------------------------------------------------

    function renderSummary() {
        const inventory = state.inventory;

        const totalStock = inventory.reduce(
            (sum, item) =>
                sum + number(item.stock),
            0
        );

        const products = new Set(
            inventory.map(
                item => item.product_id
            )
        );

        const immediateRisk =
            inventory.filter(item => {
                const status =
                    getInventoryStatus(item);

                return (
                    status === "stockout" ||
                    status === "low"
                );
            }).length;

        const excessRisk =
            inventory.filter(item =>
                getInventoryStatus(item) ===
                "slow"
            ).length;

        setText(
            elements.totalStock,
            formatInteger(totalStock)
        );

        setText(
            elements.totalProducts,
            formatInteger(products.size)
        );

        setText(
            elements.immediateRisk,
            formatInteger(immediateRisk)
        );

        setText(
            elements.excessRisk,
            formatInteger(excessRisk)
        );
    }

    function updateRecordCount(count) {
        setText(
            elements.recordCount,
            formatInteger(count)
        );
    }

    // ---------------------------------------------------------
    // Render inventory table
    // ---------------------------------------------------------

    function renderInventoryTable(items) {
        if (!elements.inventoryTableBody) {
            return;
        }

        elements.inventoryTableBody.innerHTML = "";

        if (!items.length) {
            show(elements.inventoryEmpty);
            return;
        }

        hide(elements.inventoryEmpty);

        items.forEach(item => {
            const status =
                getInventoryStatus(item);

            const dailySales =
                getDailySales(item);

            const daysLeft =
                getDaysLeft(item);

            const row =
                document.createElement("tr");

            row.dataset.productId =
                item.product_id;

            row.dataset.storeId =
                item.store_id;

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
                    <strong>
                        ${formatInteger(
                            item.stock
                        )}
                    </strong>
                </td>

                <td>
                    ${dailySales > 0
                        ? dailySales.toFixed(1)
                        : "—"}
                </td>

                <td>
                    <span class="days-left ${getDaysClass(
                        daysLeft
                    )}">
                        ${formatDays(daysLeft)}
                    </span>
                </td>

                <td>
                    <span class="inventory-status ${getStatusClass(
                        status
                    )}">
                        ${getStatusLabel(status)}
                    </span>
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
                        View
                    </button>
                </td>
            `;

            elements.inventoryTableBody
                .appendChild(row);
        });
    }

    function getDaysClass(days) {
        if (days === null) {
            return "";
        }

        if (days <= 3) {
            return "days-critical";
        }

        if (days <= 7) {
            return "days-warning";
        }

        return "days-good";
    }

    // ---------------------------------------------------------
    // Attention section
    // ---------------------------------------------------------

    function renderAttention() {
        if (!elements.attentionGrid) {
            return;
        }

        const alerts =
            [...state.attention];

        if (!alerts.length) {
            elements.attentionGrid.innerHTML = `
                <div class="attention-empty">
                    <strong>No active inventory alerts</strong>
                    <span>
                        Current inventory does not contain
                        any detected attention signals.
                    </span>
                </div>
            `;

            return;
        }

        const limited =
            alerts.slice(0, 6);

        elements.attentionGrid.innerHTML =
            limited.map(alert => {
                const type =
                    String(
                        alert.type ??
                        alert.alert_type ??
                        alert.category ??
                        "attention"
                    );

                const pid =
                    productId(alert);

                const sid =
                    storeId(alert);

                const product =
                    alert.product_name ??
                    state.products.find(
                        p => productId(p) === pid
                    )?.product_name ??
                    "Unknown product";

                const store =
                    alert.store_name ??
                    state.stores.find(
                        s => storeId(s) === sid
                    )?.store_name ??
                    "";

                const stock =
                    alert.current_stock ??
                    alert.stock ??
                    0;

                const days =
                    alert.days_to_stockout ??
                    alert.days_left;

                const units =
                    alert.units_30d ??
                    alert.sales_30d;

                const change =
                    alert.change_pct ??
                    alert.percent_change;

                return `
                    <button
                        type="button"
                        class="attention-card"
                        data-alert-product="${escapeHTML(
                            pid
                        )}"
                        data-alert-store="${escapeHTML(
                            sid
                        )}"
                    >
                        <div class="attention-card-top">
                            <span class="attention-type">
                                ${escapeHTML(
                                    formatAlertType(type)
                                )}
                            </span>

                            <span class="attention-priority">
                                ${escapeHTML(
                                    alert.priority ??
                                    alert.severity ??
                                    ""
                                )}
                            </span>
                        </div>

                        <h4>
                            ${escapeHTML(product)}
                        </h4>

                        <p>
                            ${escapeHTML(store)}
                        </p>

                        <div class="attention-facts">
                            ${stock !== undefined
                                ? `<span>
                                    Stock:
                                    <strong>${formatInteger(stock)}</strong>
                                   </span>`
                                : ""}

                            ${days !== undefined
                                ? `<span>
                                    Days left:
                                    <strong>${number(days).toFixed(1)}</strong>
                                   </span>`
                                : ""}

                            ${units !== undefined
                                ? `<span>
                                    30d sales:
                                    <strong>${formatInteger(units)}</strong>
                                   </span>`
                                : ""}

                            ${change !== undefined
                                ? `<span>
                                    Change:
                                    <strong>${formatChange(change)}</strong>
                                   </span>`
                                : ""}
                        </div>
                    </button>
                `;
            }).join("");
    }

    function formatAlertType(type) {
        const value =
            String(type || "")
                .replace(/[-_]/g, " ")
                .trim();

        if (!value) {
            return "Attention";
        }

        return value
            .split(" ")
            .map(word =>
                word.charAt(0).toUpperCase() +
                word.slice(1)
            )
            .join(" ");
    }

    function formatChange(value) {
        const n = number(value);

        if (n > 0) {
            return `+${n.toFixed(1)}%`;
        }

        return `${n.toFixed(1)}%`;
    }

    // ---------------------------------------------------------
    // Product detail / evidence
    // ---------------------------------------------------------

    async function openProductModal(
        productIdValue,
        storeIdValue
    ) {
        const item =
            state.inventory.find(
                inventoryItem =>
                    String(
                        inventoryItem.product_id
                    ) === String(productIdValue) &&
                    (
                        !storeIdValue ||
                        String(
                            inventoryItem.store_id
                        ) === String(storeIdValue)
                    )
            );

        if (!item) {
            console.warn(
                "Inventory item not found",
                productIdValue,
                storeIdValue
            );

            return;
        }

        state.selectedItem = item;

        renderModalBase(item);

        show(elements.productModal);

        // Evidence is optional.
        // The modal remains useful even if the endpoint
        // cannot provide additional evidence.
        try {
            const params =
                storeIdValue
                    ? `?store_id=${encodeURIComponent(
                        storeIdValue
                    )}`
                    : "";

            const payload =
                await fetchJSON(
                    `/api/evidence/${encodeURIComponent(
                        productIdValue
                    )}${params}`
                );

            renderEvidence(payload, item);

        } catch (error) {
            console.warn(
                "Evidence unavailable:",
                error
            );

            renderEvidence(
                null,
                item
            );
        }
    }

    function renderModalBase(item) {
        const status =
            getInventoryStatus(item);

        const dailySales =
            getDailySales(item);

        const days =
            getDaysLeft(item);

        const sales30 =
            get30DaySales(item);

        setText(
            elements.modalProductName,
            item.product_name
        );

        setText(
            elements.modalProductMeta,
            `${item.category} • ${item.store_name}`
        );

        if (elements.modalStatus) {
            elements.modalStatus.textContent =
                getStatusLabel(status);

            elements.modalStatus.className =
                `inventory-status ${getStatusClass(status)}`;
        }

        setText(
            elements.modalStock,
            formatInteger(item.stock)
        );

        setText(
            elements.modalDailySales,
            dailySales > 0
                ? dailySales.toFixed(1)
                : "—"
        );

        setText(
            elements.modalDaysLeft,
            formatDays(days)
        );

        setText(
            elements.modal30DaySales,
            formatInteger(sales30)
        );

        renderRecommendation(item);

        if (elements.modalEvidence) {
            elements.modalEvidence.innerHTML = `
                <div class="evidence-loading">
                    Loading evidence...
                </div>
            `;
        }
    }

    function renderRecommendation(item) {
        const status =
            getInventoryStatus(item);

        const alert =
            findAttention(item);

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
                "The current stock level and sales rate " +
                "indicate near-term stock-out risk.";
        } else if (status === "low") {
            recommendation =
                "Monitor stock closely and plan replenishment " +
                "before projected stock reaches zero.";
        } else if (status === "slow") {
            recommendation =
                "Review this item's inventory level before " +
                "ordering more. Sales velocity is currently low.";
        } else {
            recommendation =
                "No immediate inventory action is indicated " +
                "by the available stock and sales signals.";
        }

        setText(
            elements.modalRecommendation,
            recommendation
        );
    }

    function renderEvidence(payload, item) {
        if (!elements.modalEvidence) {
            return;
        }

        const evidence =
            payload?.evidence ??
            payload?.records ??
            payload?.items ??
            payload?.data ??
            payload;

        let html = "";

        const stock =
            item.stock;

        const daily =
            getDailySales(item);

        const days =
            getDaysLeft(item);

        const sales30 =
            get30DaySales(item);

        html += `
            <div class="evidence-row">
                <span>Current stock</span>
                <strong>
                    ${formatInteger(stock)} units
                </strong>
            </div>
        `;

        html += `
            <div class="evidence-row">
                <span>30-day units sold</span>
                <strong>
                    ${formatInteger(sales30)}
                </strong>
            </div>
        `;

        html += `
            <div class="evidence-row">
                <span>Average daily sales</span>
                <strong>
                    ${daily > 0
                        ? daily.toFixed(1)
                        : "No sales data"}
                </strong>
            </div>
        `;

        html += `
            <div class="evidence-row">
                <span>Projected stock coverage</span>
                <strong>
                    ${formatDays(days)}
                </strong>
            </div>
        `;

        // If the API gives explicit evidence, show it.
        if (
            evidence &&
            typeof evidence === "object" &&
            !Array.isArray(evidence)
        ) {
            const usefulEntries =
                Object.entries(evidence)
                    .filter(([key, value]) =>
                        value !== null &&
                        value !== undefined &&
                        ![
                            "product_id",
                            "store_id"
                        ].includes(key)
                    )
                    .slice(0, 8);

            if (usefulEntries.length) {
                html += `
                    <div class="evidence-extra">
                        <div class="evidence-extra-title">
                            API evidence
                        </div>
                `;

                usefulEntries.forEach(
                    ([key, value]) => {
                        let display = value;

                        if (
                            typeof value === "object"
                        ) {
                            display =
                                JSON.stringify(value);
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

                html += `</div>`;
            }
        }

        elements.modalEvidence.innerHTML =
            html;
    }

    function prettifyKey(key) {
        return String(key)
            .replace(/_/g, " ")
            .replace(/\b\w/g, c =>
                c.toUpperCase()
            );
    }

    // ---------------------------------------------------------
    // Movement section
    // ---------------------------------------------------------

    function renderMovement(item) {
        if (!item) {
            show(elements.movementEmpty);
            hide(elements.movementContent);

            setText(
                elements.selectedProduct,
                "Select a product to inspect movement"
            );

            return;
        }

        hide(elements.movementEmpty);
        show(elements.movementContent);

        setText(
            elements.selectedProduct,
            `${item.product_name} • ${item.store_name}`
        );

        const stock =
            number(item.stock);

        const sales =
            get30DaySales(item);

        const daily =
            getDailySales(item);

        const days =
            getDaysLeft(item);

        setText(
            elements.movementStock,
            formatInteger(stock)
        );

        setText(
            elements.movementSales,
            formatInteger(sales)
        );

        setText(
            elements.movementDaily,
            daily > 0
                ? daily.toFixed(1)
                : "—"
        );

        setText(
            elements.movementDays,
            formatDays(days)
        );

        const status =
            getInventoryStatus(item);

        let coveragePercent = 0;

        if (days !== null) {
            coveragePercent =
                Math.min(
                    100,
                    Math.max(
                        0,
                        (days / 30) * 100
                    )
                );
        }

        if (elements.movementBarFill) {
            elements.movementBarFill.style.width =
                `${coveragePercent}%`;
        }

        let movementPercent = "No trend data";

        const alert =
            findAttention(item);

        if (alert) {
            const change =
                alert.change_pct ??
                alert.percent_change;

            if (
                change !== undefined &&
                change !== null
            ) {
                movementPercent =
                    formatChange(change);
            }
        }

        setText(
            elements.movementPercent,
            movementPercent
        );

        // No inventory history API currently exists in the
        // backend, so we deliberately do NOT fabricate a
        // historical stock chart.
        if (
            elements.movementDaily
        ) {
            elements.movementDaily.title =
                "Calculated from available 30-day sales data";
        }
    }

    // ---------------------------------------------------------
    // Add stock modal
    // ---------------------------------------------------------

    function openStockModal(prefill = {}) {
        if (!elements.stockModal) {
            return;
        }

        hideStockFormError();

        if (elements.stockStore) {
            elements.stockStore.value =
                prefill.storeId || "";
        }

        if (elements.stockProduct) {
            elements.stockProduct.value =
                prefill.productId || "";
        }

        if (elements.stockQuantity) {
            elements.stockQuantity.value = "";
        }

        if (elements.stockReason) {
            elements.stockReason.value =
                "replenishment";
        }

        show(elements.stockModal);
    }

    function closeStockModal() {
        hide(elements.stockModal);
        hideStockFormError();
    }

    function hideStockFormError() {
        if (!elements.stockFormError) {
            return;
        }

        elements.stockFormError.textContent = "";
        elements.stockFormError.style.display =
            "none";
    }

    function showStockFormError(message) {
        if (!elements.stockFormError) {
            return;
        }

        elements.stockFormError.textContent =
            message;

        elements.stockFormError.style.display =
            "";
    }

    async function saveStock() {
        hideStockFormError();

        const storeIdValue =
            elements.stockStore?.value || "";

        const productIdValue =
            elements.stockProduct?.value || "";

        const quantity =
            number(
                elements.stockQuantity?.value,
                NaN
            );

        const reason =
            elements.stockReason?.value ||
            "replenishment";

        if (!storeIdValue) {
            showStockFormError(
                "Please select a store."
            );
            return;
        }

        if (!productIdValue) {
            showStockFormError(
                "Please select a product."
            );
            return;
        }

        if (
            !Number.isFinite(quantity) ||
            quantity <= 0
        ) {
            showStockFormError(
                "Enter a stock quantity greater than 0."
            );
            return;
        }

        // The backend PUT endpoint currently sets the
        // absolute stock value rather than incrementing it.
        // Therefore we calculate:
        //
        // new stock = current stock + quantity
        //
        const existing =
            state.inventory.find(
                item =>
                    String(item.store_id) ===
                    String(storeIdValue) &&
                    String(item.product_id) ===
                    String(productIdValue)
            );

        const currentStock =
            number(existing?.stock);

        const newStock =
            currentStock + quantity;

        setSaveButton(true);

        try {
            await fetchJSON(
                "/api/inventory",
                {
                    method: "PUT",
                    body: JSON.stringify({
                        store_id: storeIdValue,
                        product_id: productIdValue,
                        stock: newStock,
                        reason
                    })
                }
            );

            closeStockModal();

            await loadAll();

            // Keep the updated product selected.
            const updated =
                state.inventory.find(
                    item =>
                        String(item.store_id) ===
                        String(storeIdValue) &&
                        String(item.product_id) ===
                        String(productIdValue)
                );

            if (updated) {
                renderMovement(updated);
            }

        } catch (error) {
            console.error(
                "Stock update failed:",
                error
            );

            showStockFormError(
                error.message ||
                "Unable to update stock."
            );

        } finally {
            setSaveButton(false);
        }
    }

    function setSaveButton(saving) {
        if (!elements.saveStockBtn) {
            return;
        }

        elements.saveStockBtn.disabled =
            saving;

        elements.saveStockBtn.textContent =
            saving
                ? "Saving..."
                : "Save Stock";
    }

    // ---------------------------------------------------------
    // Status tiles
    // ---------------------------------------------------------

    function setStatusFilter(status) {
        state.currentStatus =
            status || "all";

        if (elements.statusFilter) {
            elements.statusFilter.value =
                state.currentStatus;
        }

        elements.statusButtons
            .forEach(button => {
                button.classList.toggle(
                    "active",
                    button.dataset.status ===
                    state.currentStatus
                );
            });

        applyFilters();
    }

    function renderStatusCounts() {
        const counts = {
            healthy: 0,
            low: 0,
            stockout: 0,
            slow: 0
        };

        state.inventory.forEach(item => {
            const status =
                getInventoryStatus(item);

            if (counts[status] !== undefined) {
                counts[status]++;
            }
        });

        elements.statusButtons
            .forEach(button => {
                const status =
                    button.dataset.status;

                const count =
                    button.querySelector(
                        "[data-count]"
                    );

                if (
                    count &&
                    counts[status] !== undefined
                ) {
                    count.textContent =
                        counts[status];
                }
            });
    }

    // ---------------------------------------------------------
    // Events
    // ---------------------------------------------------------

    function bindEvents() {
        elements.storeFilter?.addEventListener(
            "change",
            async () => {
                try {
                    await loadInventory();

                    state.inventory =
                        state.inventory.map(
                            normalizeInventory
                        );

                    renderEverything();
                } catch (error) {
                    console.error(error);

                    setText(
                        elements.inventoryError,
                        error.message
                    );

                    show(
                        elements.inventoryError
                    );
                }
            }
        );

        elements.searchInput?.addEventListener(
            "input",
            applyFilters
        );

        elements.categoryFilter?.addEventListener(
            "change",
            applyFilters
        );

        elements.statusFilter?.addEventListener(
            "change",
            event => {
                setStatusFilter(
                    event.target.value
                );
            }
        );

        elements.sortFilter?.addEventListener(
            "change",
            applyFilters
        );

        elements.statusButtons
            .forEach(button => {
                button.addEventListener(
                    "click",
                    () => {
                        setStatusFilter(
                            button.dataset.status
                        );
                    }
                );
            });

        elements.inventoryTableBody
            ?.addEventListener(
                "click",
                event => {
                    const button =
                        event.target.closest(
                            "[data-action='view']"
                        );

                    if (!button) return;

                    openProductModal(
                        button.dataset.productId,
                        button.dataset.storeId
                    );
                }
            );

        elements.attentionGrid
            ?.addEventListener(
                "click",
                event => {
                    const card =
                        event.target.closest(
                            "[data-alert-product]"
                        );

                    if (!card) return;

                    openProductModal(
                        card.dataset.alertProduct,
                        card.dataset.alertStore
                    );
                }
            );

        elements.refreshBtn?.addEventListener(
            "click",
            loadAll
        );

        elements.addStockBtn?.addEventListener(
            "click",
            () => openStockModal()
        );

        elements.saveStockBtn?.addEventListener(
            "click",
            saveStock
        );

        elements.modalCloseBtn?.addEventListener(
            "click",
            closeProductModal
        );

        elements.modalActionBtn?.addEventListener(
            "click",
            () => {
                const item =
                    state.selectedItem;

                if (!item) return;

                closeProductModal();

                openStockModal({
                    storeId: item.store_id,
                    productId: item.product_id
                });
            }
        );

        // Close modals when clicking outside.
        elements.productModal
            ?.addEventListener(
                "click",
                event => {
                    if (
                        event.target ===
                        elements.productModal
                    ) {
                        closeProductModal();
                    }
                }
            );

        elements.stockModal
            ?.addEventListener(
                "click",
                event => {
                    if (
                        event.target ===
                        elements.stockModal
                    ) {
                        closeStockModal();
                    }
                }
            );

        // Escape closes modals.
        document.addEventListener(
            "keydown",
            event => {
                if (event.key !== "Escape") {
                    return;
                }

                closeProductModal();
                closeStockModal();
            }
        );
    }

    function closeProductModal() {
        hide(elements.productModal);
    }

    // ---------------------------------------------------------
    // Render everything
    // ---------------------------------------------------------

    function renderEverything() {
        renderSummary();
        renderStatusCounts();
        renderAttention();
        applyFilters();

        if (state.selectedItem) {
            const updated =
                state.inventory.find(
                    item =>
                        item.product_id ===
                        state.selectedItem.product_id &&
                        item.store_id ===
                        state.selectedItem.store_id
                );

            if (updated) {
                state.selectedItem =
                    updated;

                renderMovement(updated);
            }
        }
    }

    // ---------------------------------------------------------
    // Initialization
    // ---------------------------------------------------------

    async function init() {
        console.log(
            "StoreSense Inventory Control Center initialized."
        );

        bindEvents();

        // Initial state
        state.currentStatus = "all";

        if (elements.statusFilter) {
            elements.statusFilter.value =
                "all";
        }

        renderMovement(null);

        await loadAll();
    }

    // Start only after DOM is ready.
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