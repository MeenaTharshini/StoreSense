/* =========================================================
   StoreSense - Sign Up
   ========================================================= */

const signupForm = document.getElementById("signupForm");
const signupButton = document.getElementById("signupButton");
const signupError = document.getElementById("signupError");

/* ---------------------------------------------------------
   Password visibility
   --------------------------------------------------------- */

document.querySelectorAll(".toggle-password").forEach((button) => {

    button.addEventListener("click", () => {

        const targetId = button.dataset.target;
        const input = document.getElementById(targetId);

        if (!input) {
            return;
        }

        const isPassword = input.type === "password";

        input.type = isPassword ? "text" : "password";
        button.textContent = isPassword ? "Hide" : "Show";
    });

});

/* ---------------------------------------------------------
   Sign Up
   --------------------------------------------------------- */

signupForm.addEventListener("submit", async (event) => {

    event.preventDefault();

    signupError.textContent = "";

    const name = document.getElementById("name").value.trim();
    const email = document.getElementById("email").value.trim().toLowerCase();
    const password = document.getElementById("password").value;
    const confirmPassword =
        document.getElementById("confirmPassword").value;

    /* -----------------------------------------------------
       Validation
       ----------------------------------------------------- */

    if (!name) {
        signupError.textContent = "Please enter your name.";
        return;
    }

    if (!email) {
        signupError.textContent = "Please enter your email.";
        return;
    }

    if (password.length < 6) {
        signupError.textContent =
            "Password must contain at least 6 characters.";
        return;
    }

    if (password !== confirmPassword) {
        signupError.textContent =
            "Passwords do not match.";
        return;
    }

    signupButton.disabled = true;
    signupButton.textContent = "Creating account...";

    try {

        /* -------------------------------------------------
           Send registration request
           ------------------------------------------------- */

        const response = await fetch("/api/auth/register", {
            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                name: name,
                email: email,
                password: password
            })
        });

        let data = {};

        try {
            data = await response.json();
        } catch {
            data = {};
        }

        if (!response.ok) {

            throw new Error(
                data.detail ||
                data.message ||
                "Unable to create account."
            );
        }

        /* -------------------------------------------------
           If backend automatically logs user in
           ------------------------------------------------- */

        if (data.access_token) {

            localStorage.setItem(
                "storesense_access_token",
                data.access_token
            );

            if (data.user) {
                localStorage.setItem(
                    "storesense_user",
                    JSON.stringify(data.user)
                );
            }

            window.location.href = "/";

            return;
        }

        /* -------------------------------------------------
           If registration only creates account
           ------------------------------------------------- */

        alert(
            data.message ||
            "Account created successfully. Please sign in."
        );

        window.location.href = "/static/login.html";

    } catch (error) {

        console.error("Sign up error:", error);

        signupError.textContent =
            error.message ||
            "Unable to create your account. Please try again.";

    } finally {

        signupButton.disabled = false;
        signupButton.textContent = "Create Account";
    }

});