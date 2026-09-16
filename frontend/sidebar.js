/* =========================================================
   StoreSense - Shared Sidebar
   Authentication + Navigation + Responsive Drawer
   ========================================================= */

(function () {

    "use strict";


    /* =========================================================
       CONFIGURATION
       ========================================================= */

    const TOKEN_KEY =
        "storesense_access_token";

    const USER_KEY =
        "storesense_user";


    /* =========================================================
       INITIALIZATION
       ========================================================= */

    function initializeSidebar() {

        const sidebar =
            document.getElementById(
                "sharedSidebar"
            );


        if (!sidebar) {
            return;
        }


        setupNavigation();

        setupUserInformation();

        setupLogout();

        setupMobileSidebar();

        setupActivePage();

    }


    /* =========================================================
       NAVIGATION
       ========================================================= */

    function setupNavigation() {

        const links =
            document.querySelectorAll(
                "#sharedSidebar a"
            );


        links.forEach(
            link => {

                link.addEventListener(
                    "click",
                    function () {

                        const href =
                            this.getAttribute(
                                "href"
                            );


                        if (!href) {
                            return;
                        }


                        /*
                         * Allow normal browser navigation.
                         * Authentication is handled by auth-guard.js
                         */

                    }
                );

            }
        );

    }


    /* =========================================================
       ACTIVE PAGE
       ========================================================= */

    function setupActivePage() {

        const currentPath =
            window.location.pathname;


        const links =
            document.querySelectorAll(
                "#sharedSidebar a"
            );


        links.forEach(
            link => {

                link.classList.remove(
                    "active"
                );


                const href =
                    link.getAttribute(
                        "href"
                    );


                if (!href) {
                    return;
                }


                /*
                 * Normalize paths
                 */

                const linkPath =
                    href.split("?")[0];


                if (
                    linkPath ===
                    currentPath
                ) {

                    link.classList.add(
                        "active"
                    );

                    return;

                }


                /*
                 * Dashboard aliases
                 */

                if (
                    currentPath ===
                        "/analytics" &&
                    linkPath ===
                        "/dashboard"
                ) {

                    link.classList.add(
                        "active"
                    );

                }


                if (
                    currentPath ===
                        "/attention" &&
                    linkPath ===
                        "/dashboard"
                ) {

                    link.classList.add(
                        "active"
                    );

                }

            }
        );

    }


    /* =========================================================
       USER INFORMATION
       ========================================================= */

    function setupUserInformation() {

        updateUserInformation();

    }


    function updateUserInformation() {

        let user = null;


        /*
         * Prefer the authentication helper.
         */

        if (
            window.StoreSenseAuth &&
            typeof
                window.StoreSenseAuth.getUser ===
                "function"
        ) {

            user =
                window.StoreSenseAuth.getUser();

        }


        /*
         * Fallback to localStorage.
         */

        if (!user) {

            try {

                const stored =
                    localStorage.getItem(
                        USER_KEY
                    );


                if (stored) {

                    user =
                        JSON.parse(
                            stored
                        );

                }

            }

            catch (error) {

                console.warn(
                    "Unable to read StoreSense user:",
                    error
                );

            }

        }


        if (!user) {
            return;
        }


        const fullName =
            user.full_name ||
            user.name ||
            "Store Manager";


        const email =
            user.email ||
            "—";


        const role =
            user.role ||
            "manager";


        /*
         * Name
         */

        const nameElements =
            document.querySelectorAll(
                "[data-user-name], .user-name, #userName"
            );


        nameElements.forEach(
            element => {

                element.textContent =
                    fullName;

            }
        );


        /*
         * Email
         */

        const emailElements =
            document.querySelectorAll(
                "[data-user-email], .user-email, #userEmail"
            );


        emailElements.forEach(
            element => {

                element.textContent =
                    email;

            }
        );


        /*
         * Role
         */

        const roleElements =
            document.querySelectorAll(
                "[data-user-role], .user-role, #userRole"
            );


        roleElements.forEach(
            element => {

                element.textContent =
                    formatRole(role);

            }
        );


        /*
         * Avatar initials
         */

        const avatarElements =
            document.querySelectorAll(
                "[data-user-avatar], .sidebar-user-avatar, #userAvatar"
            );


        const initials =
            getInitials(
                fullName
            );


        avatarElements.forEach(
            element => {

                element.textContent =
                    initials;

            }
        );

    }


    /* =========================================================
       FORMAT ROLE
       ========================================================= */

    function formatRole(role) {

        return String(
            role || "manager"
        )
            .replace(
                /[_-]/g,
                " "
            )
            .replace(
                /\b\w/g,
                letter =>
                    letter.toUpperCase()
            );

    }


    /* =========================================================
       USER INITIALS
       ========================================================= */

    function getInitials(name) {

        const words =
            String(
                name || "Store Manager"
            )
                .trim()
                .split(
                    /\s+/
                )
                .filter(
                    Boolean
                );


        if (!words.length) {
            return "SM";
        }


        if (words.length === 1) {

            return words[0]
                .substring(
                    0,
                    2
                )
                .toUpperCase();

        }


        return (
            words[0][0] +
            words[words.length - 1][0]
        ).toUpperCase();

    }


    /* =========================================================
       LOGOUT
       ========================================================= */

    function setupLogout() {

        const logoutButtons =
            document.querySelectorAll(
                "[data-action='logout'], #logoutButton, .logout-button"
            );


        logoutButtons.forEach(
            button => {

                /*
                 * Prevent duplicate listeners.
                 */

                if (
                    button.dataset
                        .storesenseLogoutBound ===
                    "true"
                ) {

                    return;

                }


                button.dataset
                    .storesenseLogoutBound =
                    "true";


                button.addEventListener(
                    "click",
                    async function (event) {

                        event.preventDefault();

                        await logout();

                    }
                );

            }
        );

    }


    /* =========================================================
       LOGOUT ACTION
       ========================================================= */

    async function logout() {

        /*
         * Prefer central authentication helper.
         */

        if (
            window.StoreSenseAuth &&
            typeof
                window.StoreSenseAuth.logout ===
                "function"
        ) {

            await window.StoreSenseAuth.logout();

            return;

        }


        /*
         * Fallback.
         */

        const token =
            localStorage.getItem(
                TOKEN_KEY
            );


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

        }

        catch (error) {

            console.warn(
                "Logout request failed:",
                error
            );

        }


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


    /* =========================================================
       MOBILE SIDEBAR
       ========================================================= */

    function setupMobileSidebar() {

        const sidebar =
            document.getElementById(
                "sharedSidebar"
            );


        if (!sidebar) {
            return;
        }


        /*
         * Common menu buttons.
         */

        const menuButtons =
            document.querySelectorAll(
                "[data-sidebar-toggle], #sidebarToggle, .sidebar-toggle, .menu-toggle"
            );


        menuButtons.forEach(
            button => {

                button.addEventListener(
                    "click",
                    function (event) {

                        event.preventDefault();

                        toggleSidebar();

                    }
                );

            }
        );


        /*
         * Overlay.
         */

        let overlay =
            document.getElementById(
                "sidebarOverlay"
            );


        if (!overlay) {

            overlay =
                document.createElement(
                    "div"
                );

            overlay.id =
                "sidebarOverlay";

            overlay.className =
                "sidebar-overlay";


            document.body.appendChild(
                overlay
            );

        }


        overlay.addEventListener(
            "click",
            function () {

                closeSidebar();

            }
        );


        /*
         * Close button inside sidebar.
         */

        const closeButtons =
            sidebar.querySelectorAll(
                "[data-sidebar-close], .sidebar-close"
            );


        closeButtons.forEach(
            button => {

                button.addEventListener(
                    "click",
                    function (event) {

                        event.preventDefault();

                        closeSidebar();

                    }
                );

            }
        );


        /*
         * Close sidebar after clicking navigation
         * on small screens.
         */

        const links =
            sidebar.querySelectorAll(
                "a"
            );


        links.forEach(
            link => {

                link.addEventListener(
                    "click",
                    function () {

                        if (
                            window.innerWidth <=
                            900
                        ) {

                            closeSidebar();

                        }

                    }
                );

            }
        );

    }


    /* =========================================================
       OPEN SIDEBAR
       ========================================================= */

    function openSidebar() {

        const sidebar =
            document.getElementById(
                "sharedSidebar"
            );


        const overlay =
            document.getElementById(
                "sidebarOverlay"
            );


        if (sidebar) {

            sidebar.classList.add(
                "open"
            );

        }


        if (overlay) {

            overlay.classList.add(
                "visible"
            );

        }


        document.body.classList.add(
            "sidebar-open"
        );

    }


    /* =========================================================
       CLOSE SIDEBAR
       ========================================================= */

    function closeSidebar() {

        const sidebar =
            document.getElementById(
                "sharedSidebar"
            );


        const overlay =
            document.getElementById(
                "sidebarOverlay"
            );


        if (sidebar) {

            sidebar.classList.remove(
                "open"
            );

        }


        if (overlay) {

            overlay.classList.remove(
                "visible"
            );

        }


        document.body.classList.remove(
            "sidebar-open"
        );

    }


    /* =========================================================
       TOGGLE SIDEBAR
       ========================================================= */

    function toggleSidebar() {

        const sidebar =
            document.getElementById(
                "sharedSidebar"
            );


        if (!sidebar) {
            return;
        }


        if (
            sidebar.classList.contains(
                "open"
            )
        ) {

            closeSidebar();

        }

        else {

            openSidebar();

        }

    }


    /* =========================================================
       AUTHENTICATION EVENT
       ========================================================= */

    window.addEventListener(
        "storesense-authenticated",
        function () {

            updateUserInformation();

            setupLogout();

        }
    );


    /* =========================================================
       WINDOW RESIZE
       ========================================================= */

    window.addEventListener(
        "resize",
        function () {

            if (
                window.innerWidth >
                900
            ) {

                closeSidebar();

            }

        }
    );
    document.addEventListener("DOMContentLoaded", () => {

    // =========================================================
    // LOAD LOGGED-IN USER
    // =========================================================

    const userNameElement = document.getElementById("sidebarUserName");
    const userRoleElement = document.getElementById("sidebarUserRole");
    const userAvatarElement = document.getElementById("sidebarUserAvatar");

    try {

        const storedUser = localStorage.getItem("storesense_user");

        if (storedUser) {

            const user = JSON.parse(storedUser);

            const name =
                user.full_name ||
                user.name ||
                user.username ||
                user.email ||
                "User";

            const role =
                user.role ||
                "Retail Manager";

            userNameElement.textContent = name;
            userRoleElement.textContent = role;

            // First letter of username
            userAvatarElement.textContent =
                name.charAt(0).toUpperCase();

        }

    } catch (error) {

        console.error(
            "Unable to load sidebar user:",
            error
        );

    }


    // =========================================================
    // LOGOUT
    // =========================================================

    const logoutButton =
        document.getElementById("sidebarLogoutButton");

    if (logoutButton) {

        logoutButton.addEventListener(
            "click",
            async () => {

                const token =
                    localStorage.getItem(
                        "storesense_access_token"
                    );

                try {

                    // Tell backend to invalidate/logout
                    if (token) {

                        await fetch(
                            "/api/auth/logout",
                            {
                                method: "POST",
                                headers: {
                                    "Authorization":
                                        `Bearer ${token}`
                                }
                            }
                        );

                    }

                } catch (error) {

                    console.warn(
                        "Logout API request failed:",
                        error
                    );

                } finally {

                    // Always clear local session
                    localStorage.removeItem(
                        "storesense_access_token"
                    );

                    localStorage.removeItem(
                        "storesense_user"
                    );

                    // Prevent going back into protected pages
                    window.location.replace("/login");

                }

            }
        );

    }

});
    /* =========================================================
       ESC KEY
       ========================================================= */

    document.addEventListener(
        "keydown",
        function (event) {

            if (
                event.key ===
                "Escape"
            ) {

                closeSidebar();

            }

        }
    );


    /* =========================================================
       PUBLIC API
       ========================================================= */

    window.initializeSidebar =
        initializeSidebar;


    window.updateSidebarUser =
        updateUserInformation;


    window.openSidebar =
        openSidebar;


    window.closeSidebar =
        closeSidebar;


    window.toggleSidebar =
        toggleSidebar;


    window.StoreSenseSidebar = {

        initialize:
            initializeSidebar,

        updateUser:
            updateUserInformation,

        open:
            openSidebar,

        close:
            closeSidebar,

        toggle:
            toggleSidebar,

        logout:
            logout

    };


    /* =========================================================
       AUTO INITIALIZATION
       ========================================================= */

    document.addEventListener(
        "DOMContentLoaded",
        function () {

            /*
             * If sidebar HTML already exists,
             * initialize immediately.
             */

            if (
                document.getElementById(
                    "sharedSidebar"
                )
            ) {

                initializeSidebar();

            }

        }
    );

})();