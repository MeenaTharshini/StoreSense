(function () {
    "use strict";

    const TOKEN_KEY = "storesense_access_token";
    const USER_KEY = "storesense_user";

    function redirectToLogin() {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);

        const currentPath =
            window.location.pathname +
            window.location.search;

        const loginUrl =
            "/login?next=" +
            encodeURIComponent(currentPath);

        window.location.replace(loginUrl);
    }

    async function validateSession() {
        const token = localStorage.getItem(TOKEN_KEY);

        // No token → definitely not authenticated
        if (!token) {
            redirectToLogin();
            return null;
        }

        try {
            const response = await fetch(
                "/api/auth/me",
                {
                    method: "GET",
                    headers: {
                        "Authorization": `Bearer ${token}`,
                        "Accept": "application/json"
                    },
                    cache: "no-store"
                }
            );

            if (!response.ok) {
                throw new Error(
                    `Authentication failed: ${response.status}`
                );
            }

            const data = await response.json();

            if (!data.ok || !data.user) {
                throw new Error(
                    "Invalid authentication response."
                );
            }

            // Keep the latest user information
            localStorage.setItem(
                USER_KEY,
                JSON.stringify(data.user)
            );

            // Make user available to other frontend scripts
            window.storeSenseUser = data.user;

            // Notify sidebar / other components
            window.dispatchEvent(
                new CustomEvent(
                    "storesense-authenticated",
                    {
                        detail: data.user
                    }
                )
            );

            return data.user;

        } catch (error) {
            console.warn(
                "StoreSense authentication check failed:",
                error
            );

            redirectToLogin();
            return null;
        }
    }

    // Expose useful authentication helpers
    window.StoreSenseAuth = {
        getToken: function () {
            return localStorage.getItem(TOKEN_KEY);
        },

        getUser: function () {
            try {
                const storedUser =
                    localStorage.getItem(USER_KEY);

                return storedUser
                    ? JSON.parse(storedUser)
                    : null;
            } catch {
                return null;
            }
        },

        isAuthenticated: function () {
            return Boolean(
                localStorage.getItem(TOKEN_KEY)
            );
        },

        logout: async function () {
            const token =
                localStorage.getItem(TOKEN_KEY);

            try {
                if (token) {
                    await fetch(
                        "/api/auth/logout",
                        {
                            method: "POST",
                            headers: {
                                "Authorization":
                                    `Bearer ${token}`,
                                "Accept":
                                    "application/json"
                            }
                        }
                    );
                }
            } catch (error) {
                console.warn(
                    "Logout request failed:",
                    error
                );
            } finally {
                localStorage.removeItem(
                    TOKEN_KEY
                );

                localStorage.removeItem(
                    USER_KEY
                );

                window.location.replace(
                    "/login"
                );
            }
        },

        validate: validateSession
    };

    // Start authentication check immediately.
    validateSession();

})();