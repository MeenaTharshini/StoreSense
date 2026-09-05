// ============================================================
// STORESENSE DATA CENTER
// ============================================================


// ============================================================
// API HELPER
// ============================================================

async function api(url, options = {}) {

    const response = await fetch(url, {
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {})
        },
        ...options
    });

    let data;

    try {
        data = await response.json();
    } catch {
        throw new Error(
            `Invalid server response (${response.status})`
        );
    }

    if (!response.ok) {

        throw new Error(
            data.error ||
            data.detail ||
            data.message ||
            "Request failed"
        );
    }

    return data;
}


// ============================================================
// LOAD STORES
// ============================================================

async function loadStores() {

    const result = await api("/api/stores");

    /*
     * Supports both:
     *
     * [
     *   {...}
     * ]
     *
     * and:
     *
     * {
     *   stores: [...]
     * }
     */

    const stores = Array.isArray(result)
        ? result
        : (result.stores || []);


    // Inventory store dropdown

    const inventorySelect =
        document.getElementById("inventoryStore");

    if (inventorySelect) {

        inventorySelect.innerHTML =
            '<option value="">Select store</option>';

        stores.forEach(store => {

            const option =
                document.createElement("option");

            option.value =
                store.store_id;

            option.textContent =
                `${store.store_name || store.store_id} (${store.store_id})`;

            inventorySelect.appendChild(option);
        });
    }


    // Sales store dropdown

    const saleSelect =
        document.getElementById("saleStore");

    if (saleSelect) {

        saleSelect.innerHTML =
            '<option value="">Select store</option>';

        stores.forEach(store => {

            const option =
                document.createElement("option");

            option.value =
                store.store_id;

            option.textContent =
                `${store.store_name || store.store_id} (${store.store_id})`;

            saleSelect.appendChild(option);
        });
    }
}


// ============================================================
// LOAD PRODUCTS
// ============================================================

async function loadProducts() {

    const result = await api("/api/products");

    /*
     * Supports both:
     *
     * [
     *   {...}
     * ]
     *
     * and:
     *
     * {
     *   products: [...]
     * }
     */

    const products = Array.isArray(result)
        ? result
        : (result.products || []);


    // Inventory product dropdown

    const inventorySelect =
        document.getElementById("inventoryProduct");

    if (inventorySelect) {

        inventorySelect.innerHTML =
            '<option value="">Select product</option>';

        products.forEach(product => {

            const option =
                document.createElement("option");

            option.value =
                product.product_id;

            option.textContent =
                `${product.product_name || product.product_id} (${product.product_id})`;

            inventorySelect.appendChild(option);
        });
    }


    // Sales product dropdown

    const saleSelect =
        document.getElementById("saleProduct");

    if (saleSelect) {

        saleSelect.innerHTML =
            '<option value="">Select product</option>';

        products.forEach(product => {

            const option =
                document.createElement("option");

            option.value =
                product.product_id;

            option.textContent =
                `${product.product_name || product.product_id} (${product.product_id})`;

            saleSelect.appendChild(option);
        });
    }
}


// ============================================================
// ADD STORE
// ============================================================

function initializeStoreForm() {

    const form =
        document.getElementById("storeForm");

    if (!form) return;


    form.addEventListener(
        "submit",
        async event => {

            event.preventDefault();


            const message =
                document.getElementById(
                    "storeMessage"
                );


            try {

                const result =
                    await api(
                        "/api/stores",
                        {
                            method: "POST",

                            body: JSON.stringify({

                                store_id:
                                    document
                                        .getElementById("storeId")
                                        .value
                                        .trim(),

                                store_name:
                                    document
                                        .getElementById("storeName")
                                        .value
                                        .trim(),

                                location:
                                    document
                                        .getElementById("storeLocation")
                                        .value
                                        .trim()
                            })
                        }
                    );


                message.textContent =
                    result.message ||
                    "Store saved successfully.";

                message.className =
                    "form-message success";


                form.reset();


                await loadStores();
                await loadDatabaseCounts();

            } catch (error) {

                message.textContent =
                    error.message;

                message.className =
                    "form-message error";

                console.error(
                    "Add store failed:",
                    error
                );
            }
        }
    );
}


// ============================================================
// ADD PRODUCT
// ============================================================

function initializeProductForm() {

    const form =
        document.getElementById("productForm");

    if (!form) return;


    form.addEventListener(
        "submit",
        async event => {

            event.preventDefault();


            const message =
                document.getElementById(
                    "productMessage"
                );


            try {

                const priceValue =
                    document
                        .getElementById("productPrice")
                        .value;


                const payload = {

                    product_id:
                        document
                            .getElementById("productId")
                            .value
                            .trim(),

                    product_name:
                        document
                            .getElementById("productName")
                            .value
                            .trim(),

                    category:
                        document
                            .getElementById("productCategory")
                            .value
                            .trim(),

                    price:
                        priceValue === ""
                            ? 0
                            : Number(priceValue)
                };


                const result =
                    await api(
                        "/api/products",
                        {
                            method: "POST",

                            body:
                                JSON.stringify(payload)
                        }
                    );


                message.textContent =
                    result.message ||
                    "Product saved successfully.";

                message.className =
                    "form-message success";


                form.reset();


                await loadProducts();
                await loadDatabaseCounts();

            } catch (error) {

                message.textContent =
                    error.message;

                message.className =
                    "form-message error";

                console.error(
                    "Add product failed:",
                    error
                );
            }
        }
    );
}


// ============================================================
// SET INVENTORY
// ============================================================

function initializeInventoryForm() {

    const form =
        document.getElementById("inventoryForm");

    if (!form) return;


    form.addEventListener(
        "submit",
        async event => {

            event.preventDefault();


            const message =
                document.getElementById(
                    "inventoryMessage"
                );


            try {

                const payload = {

                    store_id:
                        document
                            .getElementById(
                                "inventoryStore"
                            )
                            .value,

                    product_id:
                        document
                            .getElementById(
                                "inventoryProduct"
                            )
                            .value,

                    stock:
                        Number(
                            document
                                .getElementById(
                                    "inventoryStock"
                                )
                                .value
                        ),

                    reason:
                        document
                            .getElementById(
                                "inventoryReason"
                            )
                            .value
                            .trim()
                };


                const result =
                    await api(
                        "/api/inventory",
                        {
                            method: "PUT",

                            body:
                                JSON.stringify(payload)
                        }
                    );


                message.textContent =
                    result.message ||
                    "Inventory saved successfully.";

                message.className =
                    "form-message success";


                form.reset();


                /*
                 * Reload database counts because
                 * inventory history may have changed.
                 */

                await loadDatabaseCounts();

            } catch (error) {

                message.textContent =
                    error.message;

                message.className =
                    "form-message error";

                console.error(
                    "Inventory update failed:",
                    error
                );
            }
        }
    );
}


// ============================================================
// RECORD SALE
// ============================================================

function initializeSaleForm() {

    const form =
        document.getElementById("saleForm");

    if (!form) return;


    form.addEventListener(
        "submit",
        async event => {

            event.preventDefault();


            const message =
                document.getElementById(
                    "saleMessage"
                );


            try {

                const storeId =
                    document
                        .getElementById("saleStore")
                        .value;

                const productId =
                    document
                        .getElementById("saleProduct")
                        .value;

                const units =
                    Number(
                        document
                            .getElementById("saleUnits")
                            .value
                    );

                const revenueInput =
                    document
                        .getElementById("saleRevenue")
                        .value
                        .trim();


                /*
                 * Basic validation
                 */

                if (!storeId) {
                    throw new Error(
                        "Please select a store."
                    );
                }


                if (!productId) {
                    throw new Error(
                        "Please select a product."
                    );
                }


                if (!Number.isInteger(units) || units <= 0) {
                    throw new Error(
                        "Units sold must be a positive whole number."
                    );
                }


                /*
                 * Build sale payload.
                 */

                const payload = {

                    store_id:
                        storeId,

                    product_id:
                        productId,

                    units_sold:
                        units
                };


                /*
                 * Revenue is optional.
                 *
                 * If the user enters it, send it.
                 * Otherwise let the backend calculate it
                 * if supported.
                 */

                if (revenueInput !== "") {

                    const revenue =
                        Number(revenueInput);


                    if (
                        Number.isNaN(revenue) ||
                        revenue < 0
                    ) {

                        throw new Error(
                            "Revenue must be a valid non-negative number."
                        );
                    }


                    payload.revenue =
                        revenue;
                }


                /*
                 * Send sale to backend.
                 */

                const result =
                    await api(
                        "/api/sales",
                        {
                            method: "POST",

                            body:
                                JSON.stringify(payload)
                        }
                    );


                /*
                 * Success message.
                 */

                message.textContent =
                    result.message ||
                    "Sale recorded successfully.";

                message.className =
                    "form-message success";


                /*
                 * Clear form.
                 */

                form.reset();


                /*
                 * Refresh database counts.
                 */

                await loadDatabaseCounts();


                /*
                 * Reload inventory/product data.
                 *
                 * This keeps the dropdown data fresh
                 * after a sale changes inventory.
                 */

                await loadStores();
                await loadProducts();

            } catch (error) {

                message.textContent =
                    error.message;

                message.className =
                    "form-message error";

                console.error(
                    "Record sale failed:",
                    error
                );
            }
        }
    );
}


// ============================================================
// DATABASE COUNTS
// ============================================================

async function loadDatabaseCounts() {

    const container =
        document.getElementById(
            "databaseCounts"
        );


    if (!container) return;


    try {

        const result =
            await api(
                "/api/database"
            );


        const counts =
            result.counts || {};


        container.innerHTML = `

            <div class="database-count">

                <span class="database-count-label">
                    Stores
                </span>

                <strong class="database-count-value">
                    ${counts.stores || 0}
                </strong>

            </div>


            <div class="database-count">

                <span class="database-count-label">
                    Products
                </span>

                <strong class="database-count-value">
                    ${counts.products || 0}
                </strong>

            </div>


            <div class="database-count">

                <span class="database-count-label">
                    Inventory
                </span>

                <strong class="database-count-value">
                    ${counts.inventory || 0}
                </strong>

            </div>


            <div class="database-count">

                <span class="database-count-label">
                    Sales
                </span>

                <strong class="database-count-value">
                    ${counts.sales || 0}
                </strong>

            </div>


            <div class="database-count">

                <span class="database-count-label">
                    Inventory History
                </span>

                <strong class="database-count-value">
                    ${counts.inventory_history || 0}
                </strong>

            </div>

        `;


        /*
         * Update the small record status
         * shown near the top of the page.
         */

        const recordStatus =
            document.getElementById(
                "recordStatus"
            );


        if (recordStatus) {

            recordStatus.textContent =
                `${counts.stores || 0} stores · ` +
                `${counts.products || 0} products · ` +
                `${counts.inventory || 0} inventory records · ` +
                `${counts.sales || 0} sales`;
        }


    } catch (error) {

        container.innerHTML = `
            <div class="loading-state">
                ${escapeHTML(error.message)}
            </div>
        `;


        const recordStatus =
            document.getElementById(
                "recordStatus"
            );


        if (recordStatus) {

            recordStatus.textContent =
                "Unable to load records.";
        }


        console.error(
            "Database count loading failed:",
            error
        );
    }
}


// ============================================================
// ESCAPE HTML
// ============================================================

function escapeHTML(value) {

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


// ============================================================
// INITIALIZE
// ============================================================

async function initialize() {

    try {

        /*
         * Initialize forms first.
         */

        initializeStoreForm();
        initializeProductForm();
        initializeInventoryForm();
        initializeSaleForm();


        /*
         * Load database information.
         */

        await Promise.all([
            loadStores(),
            loadProducts(),
            loadDatabaseCounts()
        ]);


        console.log(
            "StoreSense Data Center initialized."
        );


    } catch (error) {

        console.error(
            "Data Center initialization failed:",
            error
        );
    }
}


// ============================================================
// START APPLICATION
// ============================================================

if (
    document.readyState === "loading"
) {

    document.addEventListener(
        "DOMContentLoaded",
        initialize
    );

} else {

    initialize();
}