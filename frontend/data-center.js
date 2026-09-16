// ============================================================
// STORESENSE DATA CENTER
// ============================================================

"use strict";


// ============================================================
// AUTHENTICATION KEYS
// ============================================================

const TOKEN_KEY = "storesense_access_token";
const USER_KEY = "storesense_user";


// ============================================================
// API HELPER
// ============================================================

async function api(url, options = {}) {

    const token =
        localStorage.getItem(TOKEN_KEY);


    // --------------------------------------------------------
    // AUTHENTICATION CHECK
    // --------------------------------------------------------

    if (!token) {

        console.warn(
            "StoreSense: No authentication token found."
        );

        redirectToLogin();

        throw new Error(
            "Authentication required."
        );
    }


    // --------------------------------------------------------
    // HEADERS
    // --------------------------------------------------------

    const headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",

        "Authorization":
            `Bearer ${token}`,

        ...(options.headers || {})
    };


    // --------------------------------------------------------
    // REQUEST
    // --------------------------------------------------------

    let response;

    try {

        response =
            await fetch(
                url,
                {
                    ...options,
                    headers
                }
            );

    } catch (error) {

        console.error(
            "StoreSense API connection failed:",
            error
        );

        throw new Error(
            "Unable to connect to StoreSense server."
        );
    }


    // --------------------------------------------------------
    // READ RESPONSE
    // --------------------------------------------------------

    let data = null;

    const contentType =
        response.headers.get(
            "content-type"
        ) || "";


    if (
        contentType.includes(
            "application/json"
        )
    ) {

        try {

            data =
                await response.json();

        } catch {

            data = null;

        }

    } else {

        try {

            const text =
                await response.text();

            data = text
                ? { message: text }
                : null;

        } catch {

            data = null;

        }

    }


    // --------------------------------------------------------
    // UNAUTHORIZED
    // --------------------------------------------------------

    if (response.status === 401) {

        console.warn(
            "StoreSense: Authentication expired or invalid."
        );


        // Remove invalid session

        localStorage.removeItem(
            TOKEN_KEY
        );

        localStorage.removeItem(
            USER_KEY
        );


        redirectToLogin();


        throw new Error(
            "Authentication required."
        );
    }


    // --------------------------------------------------------
    // OTHER SERVER ERRORS
    // --------------------------------------------------------

    if (!response.ok) {

        const message =
            data?.error ||
            data?.detail ||
            data?.message ||
            `Request failed (${response.status})`;


        throw new Error(message);
    }


    return data;
}


// ============================================================
// REDIRECT TO LOGIN
// ============================================================

function redirectToLogin() {

    const currentPath =
        window.location.pathname +
        window.location.search;


    const loginURL =
        `/login?next=${encodeURIComponent(
            currentPath
        )}`;


    // Avoid repeatedly redirecting

    if (
        window.location.pathname !==
        "/login"
    ) {

        window.location.replace(
            loginURL
        );
    }
}


// ============================================================
// LOAD STORES
// ============================================================

async function loadStores() {

    const result =
        await api(
            "/api/stores"
        );


    const stores =
        Array.isArray(result)
            ? result
            : (result?.stores || []);


    // --------------------------------------------------------
    // INVENTORY STORE DROPDOWN
    // --------------------------------------------------------

    const inventorySelect =
        document.getElementById(
            "inventoryStore"
        );


    if (inventorySelect) {

        inventorySelect.innerHTML =
            '<option value="">Select store</option>';


        stores.forEach(store => {

            const option =
                document.createElement(
                    "option"
                );


            option.value =
                store.store_id;


            option.textContent =
                `${store.store_name || store.store_id} (${store.store_id})`;


            inventorySelect.appendChild(
                option
            );

        });
    }


    // --------------------------------------------------------
    // SALES STORE DROPDOWN
    // --------------------------------------------------------

    const saleSelect =
        document.getElementById(
            "saleStore"
        );


    if (saleSelect) {

        saleSelect.innerHTML =
            '<option value="">Select store</option>';


        stores.forEach(store => {

            const option =
                document.createElement(
                    "option"
                );


            option.value =
                store.store_id;


            option.textContent =
                `${store.store_name || store.store_id} (${store.store_id})`;


            saleSelect.appendChild(
                option
            );

        });
    }
}


// ============================================================
// LOAD PRODUCTS
// ============================================================

async function loadProducts() {

    const result =
        await api(
            "/api/products"
        );


    const products =
        Array.isArray(result)
            ? result
            : (result?.products || []);


    // --------------------------------------------------------
    // INVENTORY PRODUCT DROPDOWN
    // --------------------------------------------------------

    const inventorySelect =
        document.getElementById(
            "inventoryProduct"
        );


    if (inventorySelect) {

        inventorySelect.innerHTML =
            '<option value="">Select product</option>';


        products.forEach(product => {

            const option =
                document.createElement(
                    "option"
                );


            option.value =
                product.product_id;


            option.textContent =
                `${product.product_name || product.product_id} (${product.product_id})`;


            inventorySelect.appendChild(
                option
            );

        });
    }


    // --------------------------------------------------------
    // SALES PRODUCT DROPDOWN
    // --------------------------------------------------------

    const saleSelect =
        document.getElementById(
            "saleProduct"
        );


    if (saleSelect) {

        saleSelect.innerHTML =
            '<option value="">Select product</option>';


        products.forEach(product => {

            const option =
                document.createElement(
                    "option"
                );


            option.value =
                product.product_id;


            option.textContent =
                `${product.product_name || product.product_id} (${product.product_id})`;


            saleSelect.appendChild(
                option
            );

        });
    }
}


// ============================================================
// ADD STORE
// ============================================================

function initializeStoreForm() {

    const form =
        document.getElementById(
            "storeForm"
        );


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

                            body:
                                JSON.stringify({

                                    store_id:
                                        document
                                            .getElementById(
                                                "storeId"
                                            )
                                            .value
                                            .trim(),

                                    store_name:
                                        document
                                            .getElementById(
                                                "storeName"
                                            )
                                            .value
                                            .trim(),

                                    location:
                                        document
                                            .getElementById(
                                                "storeLocation"
                                            )
                                            .value
                                            .trim()

                                })
                        }
                    );


                if (message) {

                    message.textContent =
                        result?.message ||
                        "Store saved successfully.";

                    message.className =
                        "form-message success";

                }


                form.reset();


                await loadStores();
                await loadDatabaseCounts();

            } catch (error) {

                if (message) {

                    message.textContent =
                        error.message;

                    message.className =
                        "form-message error";

                }


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
        document.getElementById(
            "productForm"
        );


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
                        .getElementById(
                            "productPrice"
                        )
                        .value;


                const payload = {

                    product_id:
                        document
                            .getElementById(
                                "productId"
                            )
                            .value
                            .trim(),

                    product_name:
                        document
                            .getElementById(
                                "productName"
                            )
                            .value
                            .trim(),

                    category:
                        document
                            .getElementById(
                                "productCategory"
                            )
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
                                JSON.stringify(
                                    payload
                                )
                        }
                    );


                if (message) {

                    message.textContent =
                        result?.message ||
                        "Product saved successfully.";

                    message.className =
                        "form-message success";

                }


                form.reset();


                await loadProducts();
                await loadDatabaseCounts();

            } catch (error) {

                if (message) {

                    message.textContent =
                        error.message;

                    message.className =
                        "form-message error";

                }


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
        document.getElementById(
            "inventoryForm"
        );


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


                if (!payload.store_id) {

                    throw new Error(
                        "Please select a store."
                    );

                }


                if (!payload.product_id) {

                    throw new Error(
                        "Please select a product."
                    );

                }


                if (
                    !Number.isInteger(
                        payload.stock
                    ) ||
                    payload.stock < 0
                ) {

                    throw new Error(
                        "Stock must be a non-negative whole number."
                    );

                }


                const result =
                    await api(
                        "/api/inventory",
                        {
                            method: "PUT",

                            body:
                                JSON.stringify(
                                    payload
                                )
                        }
                    );


                if (message) {

                    message.textContent =
                        result?.message ||
                        "Inventory saved successfully.";

                    message.className =
                        "form-message success";

                }


                form.reset();


                await loadDatabaseCounts();

            } catch (error) {

                if (message) {

                    message.textContent =
                        error.message;

                    message.className =
                        "form-message error";

                }


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
        document.getElementById(
            "saleForm"
        );


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
                        .getElementById(
                            "saleStore"
                        )
                        .value;


                const productId =
                    document
                        .getElementById(
                            "saleProduct"
                        )
                        .value;


                const units =
                    Number(
                        document
                            .getElementById(
                                "saleUnits"
                            )
                            .value
                    );


                const revenueInput =
                    document
                        .getElementById(
                            "saleRevenue"
                        )
                        .value
                        .trim();


                // ------------------------------------------------
                // VALIDATION
                // ------------------------------------------------

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


                if (
                    !Number.isInteger(
                        units
                    ) ||
                    units <= 0
                ) {

                    throw new Error(
                        "Units sold must be a positive whole number."
                    );

                }


                // ------------------------------------------------
                // PAYLOAD
                // ------------------------------------------------

                const payload = {

                    store_id:
                        storeId,

                    product_id:
                        productId,

                    units_sold:
                        units

                };


                // ------------------------------------------------
                // OPTIONAL REVENUE
                // ------------------------------------------------

                if (
                    revenueInput !== ""
                ) {

                    const revenue =
                        Number(
                            revenueInput
                        );


                    if (
                        Number.isNaN(
                            revenue
                        ) ||
                        revenue < 0
                    ) {

                        throw new Error(
                            "Revenue must be a valid non-negative number."
                        );

                    }


                    payload.revenue =
                        revenue;

                }


                // ------------------------------------------------
                // SEND SALE
                // ------------------------------------------------

                const result =
                    await api(
                        "/api/sales",
                        {
                            method: "POST",

                            body:
                                JSON.stringify(
                                    payload
                                )
                        }
                    );


                if (message) {

                    message.textContent =
                        result?.message ||
                        "Sale recorded successfully.";

                    message.className =
                        "form-message success";

                }


                form.reset();


                await loadDatabaseCounts();

                await loadStores();

                await loadProducts();

            } catch (error) {

                if (message) {

                    message.textContent =
                        error.message;

                    message.className =
                        "form-message error";

                }


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
            result?.counts || {};


        container.innerHTML = `

            <div class="database-count">

                <span class="database-count-label">
                    Stores
                </span>

                <strong class="database-count-value">
                    ${Number(counts.stores || 0)}
                </strong>

            </div>


            <div class="database-count">

                <span class="database-count-label">
                    Products
                </span>

                <strong class="database-count-value">
                    ${Number(counts.products || 0)}
                </strong>

            </div>


            <div class="database-count">

                <span class="database-count-label">
                    Inventory
                </span>

                <strong class="database-count-value">
                    ${Number(counts.inventory || 0)}
                </strong>

            </div>


            <div class="database-count">

                <span class="database-count-label">
                    Sales
                </span>

                <strong class="database-count-value">
                    ${Number(counts.sales || 0)}
                </strong>

            </div>


            <div class="database-count">

                <span class="database-count-label">
                    Inventory History
                </span>

                <strong class="database-count-value">
                    ${Number(counts.inventory_history || 0)}
                </strong>

            </div>

        `;


        // ------------------------------------------------------
        // RECORD STATUS
        // ------------------------------------------------------

        const recordStatus =
            document.getElementById(
                "recordStatus"
            );


        if (recordStatus) {

            recordStatus.textContent =
                `${Number(counts.stores || 0)} stores · ` +
                `${Number(counts.products || 0)} products · ` +
                `${Number(counts.inventory || 0)} inventory records · ` +
                `${Number(counts.sales || 0)} sales`;

        }


    } catch (error) {

        container.innerHTML = `

            <div class="loading-state">

                ${escapeHTML(
                    error.message
                )}

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

        .replace(
            /&/g,
            "&amp;"
        )

        .replace(
            /</g,
            "&lt;"
        )

        .replace(
            />/g,
            "&gt;"
        )

        .replace(
            /"/g,
            "&quot;"
        )

        .replace(
            /'/g,
            "&#039;"
        );
}


// ============================================================
// INITIALIZE
// ============================================================

async function initialize() {

    try {

        // ------------------------------------------------------
        // FORMS
        // ------------------------------------------------------

        initializeStoreForm();

        initializeProductForm();

        initializeInventoryForm();

        initializeSaleForm();


        // ------------------------------------------------------
        // LOAD DATA
        // ------------------------------------------------------

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
    document.readyState ===
    "loading"
) {

    document.addEventListener(
        "DOMContentLoaded",
        initialize
    );

} else {

    initialize();

}