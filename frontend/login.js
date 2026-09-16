(function () {
    "use strict";

    const TOKEN_KEY = "storesense_access_token";
    const USER_KEY = "storesense_user";

    document.addEventListener("DOMContentLoaded", initializeLogin);

    function initializeLogin() {
        setupPasswordToggle();
        setupLoginForm();

        // IMPORTANT:
        // Do NOT automatically redirect an existing session.
        // The login page must remain the default entry page.
        clearError();
    }

    // ============================================================
    // PASSWORD VISIBILITY
    // ============================================================

    function setupPasswordToggle() {
        const passwordInput =
            document.getElementById("password");

        const toggleButton =
            document.getElementById("togglePassword");

        if (!passwordInput || !toggleButton) {
            return;
        }

        toggleButton.addEventListener("click", function () {
            const isPassword =
                passwordInput.type === "password";

            passwordInput.type =
                isPassword ? "text" : "password";

            toggleButton.setAttribute(
                "aria-label",
                isPassword
                    ? "Hide password"
                    : "Show password"
            );

            toggleButton.textContent =
                isPassword ? "Hide" : "Show";
        });
    }

    // ============================================================
    // LOGIN FORM
    // ============================================================

    function setupLoginForm() {
        const form =
            document.getElementById("loginForm");

        if (!form) {
            console.error(
                "StoreSense login form not found."
            );
            return;
        }

        form.addEventListener(
            "submit",
            handleLogin
        );
    }

    // ============================================================
    // HANDLE LOGIN
    // ============================================================

    async function handleLogin(event) {
        event.preventDefault();

        const form =
            event.currentTarget;

        const emailInput =
            document.getElementById("email");

        const passwordInput =
            document.getElementById("password");

        const submitButton =
            document.getElementById("loginButton");

        if (!emailInput || !passwordInput) {
            showError(
                "Login form is incomplete."
            );
            return;
        }

        const email =
            emailInput.value
                .trim()
                .toLowerCase();

        const password =
            passwordInput.value;

        // --------------------------------------------------------
        // VALIDATION
        // --------------------------------------------------------

        if (!email) {
            showError(
                "Please enter your email."
            );

            emailInput.focus();
            return;
        }

        if (!password) {
            showError(
                "Please enter your password."
            );

            passwordInput.focus();
            return;
        }

        clearError();

        // --------------------------------------------------------
        // DISABLE BUTTON
        // --------------------------------------------------------

        if (submitButton) {
            submitButton.disabled = true;

            submitButton.dataset.originalText =
                submitButton.textContent;

            submitButton.textContent =
                "Signing in...";
        }

        try {
            // ----------------------------------------------------
            // LOGIN API
            // ----------------------------------------------------

            const response =
                await fetch(
                    "/api/auth/login",
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json",

                            "Accept":
                                "application/json"
                        },

                        body: JSON.stringify({
                            email: email,
                            password: password
                        })
                    }
                );

            // ----------------------------------------------------
            // READ RESPONSE
            // ----------------------------------------------------

            let data = null;

            try {
                data =
                    await response.json();
            } catch {
                data = null;
            }

            // ----------------------------------------------------
            // API ERROR
            // ----------------------------------------------------

            if (!response.ok) {
                const message =
                    data?.detail ||
                    data?.message ||
                    "Invalid email or password.";

                throw new Error(message);
            }

            // ----------------------------------------------------
            // VALIDATE LOGIN RESPONSE
            // ----------------------------------------------------

            if (
                !data ||
                !data.ok ||
                !data.access_token
            ) {
                throw new Error(
                    "Login succeeded but no authentication token was returned."
                );
            }

            // ----------------------------------------------------
            // SAVE JWT TOKEN
            // ----------------------------------------------------

            localStorage.setItem(
                TOKEN_KEY,
                data.access_token
            );

            // ----------------------------------------------------
            // SAVE USER
            // ----------------------------------------------------

            if (data.user) {
                localStorage.setItem(
                    USER_KEY,
                    JSON.stringify(data.user)
                );

                // Make user available globally
                window.storeSenseUser =
                    data.user;
            }

            // ----------------------------------------------------
            // SUCCESS
            // ----------------------------------------------------

            redirectAfterLogin();

        } catch (error) {
            console.error(
                "StoreSense login error:",
                error
            );

            showError(
                error?.message ||
                "Unable to sign in. Please try again."
            );

            // Re-enable button
            if (submitButton) {
                submitButton.disabled = false;

                submitButton.textContent =
                    submitButton.dataset.originalText ||
                    "Sign In";
            }
        }
    }

    // ============================================================
    // REDIRECT AFTER LOGIN
    // ============================================================

    function redirectAfterLogin() {
        const params =
            new URLSearchParams(
                window.location.search
            );

        const next =
            params.get("next");

        /*
         * Only allow internal paths.
         *
         * Valid:
         *   /dashboard
         *   /inventory
         *   /mobile
         *
         * Invalid:
         *   https://example.com
         *   //example.com
         */

        if (
            next &&
            next.startsWith("/") &&
            !next.startsWith("//")
        ) {
            window.location.replace(next);
            return;
        }

        // Normal login → dashboard
        window.location.replace(
            "/dashboard"
        );
    }

    // ============================================================
    // ERROR DISPLAY
    // ============================================================

    function showError(message) {
        let errorElement =
            document.getElementById(
                "loginError"
            );

        if (!errorElement) {
            const form =
                document.getElementById(
                    "loginForm"
                );

            if (!form) {
                alert(message);
                return;
            }

            errorElement =
                document.createElement(
                    "div"
                );

            errorElement.id =
                "loginError";

            errorElement.className =
                "error-message";

            form.prepend(
                errorElement
            );
        }

        errorElement.textContent =
            message;

        errorElement.style.display =
            "block";
    }

    // ============================================================
    // CLEAR ERROR
    // ============================================================

    function clearError() {
        const errorElement =
            document.getElementById(
                "loginError"
            );

        if (errorElement) {
            errorElement.textContent = "";

            errorElement.style.display =
                "none";
        }
    }

})();