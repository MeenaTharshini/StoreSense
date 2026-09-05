"use strict";


/* =========================================================
   INITIALIZE SIDEBAR
   ========================================================= */

function initializeSidebar() {

    const sidebar =
        document.getElementById("storeSidebar");

    const collapseButton =
        document.getElementById(
            "sidebarCollapseButton"
        );

    const mobileToggle =
        document.getElementById(
            "mobileSidebarToggle"
        );

    const overlay =
        document.getElementById(
            "sidebarOverlay"
        );


    if (!sidebar) {

        console.warn(
            "StoreSense sidebar not found."
        );

        return;

    }


    /* =====================================================
       DESKTOP COLLAPSE
       ===================================================== */

    if (collapseButton) {

        collapseButton.addEventListener(
            "click",
            function () {

                const collapsed =
                    document.body.classList.toggle(
                        "sidebar-collapsed"
                    );


                collapseButton.setAttribute(
                    "aria-expanded",
                    String(!collapsed)
                );


                collapseButton.setAttribute(
                    "aria-label",
                    collapsed
                        ? "Expand sidebar"
                        : "Collapse sidebar"
                );

            }
        );

    }


    /* =====================================================
       MOBILE OPEN / CLOSE
       ===================================================== */

    if (mobileToggle) {

        mobileToggle.addEventListener(
            "click",
            function () {

                const open =
                    document.body.classList.toggle(
                        "sidebar-mobile-open"
                    );


                mobileToggle.setAttribute(
                    "aria-expanded",
                    String(open)
                );

            }
        );

    }


    /* =====================================================
       OVERLAY
       ===================================================== */

    if (overlay) {

        overlay.addEventListener(
            "click",
            closeMobileSidebar
        );

    }


    /* =====================================================
       NAVIGATION
       ===================================================== */

    sidebar
        .querySelectorAll(".sidebar-nav-item")
        .forEach(function (item) {

            item.addEventListener(
                "click",
                function () {

                    if (
                        window.innerWidth <= 760
                    ) {

                        closeMobileSidebar();

                    }

                }
            );

        });


    /* =====================================================
       ESCAPE
       ===================================================== */

    document.addEventListener(
        "keydown",
        function (event) {

            if (event.key === "Escape") {

                closeMobileSidebar();

            }

        }
    );


    /* =====================================================
       ACTIVE PAGE
       ===================================================== */

    setActiveSidebarPage();

}


/* =========================================================
   MOBILE CLOSE
   ========================================================= */

function closeMobileSidebar() {

    document.body.classList.remove(
        "sidebar-mobile-open"
    );


    const toggle =
        document.getElementById(
            "mobileSidebarToggle"
        );


    if (toggle) {

        toggle.setAttribute(
            "aria-expanded",
            "false"
        );

    }

}


/* =========================================================
   ACTIVE PAGE
   ========================================================= */

function setActiveSidebarPage() {

    const path =
        window.location.pathname;


    let currentPage =
        "dashboard";


    if (path === "/data-center") {

        currentPage =
            "data-center";

    }

    else if (path === "/inventory") {

        currentPage =
            "inventory";

    }


    document
        .querySelectorAll(".sidebar-nav-item")
        .forEach(function (item) {

            item.classList.remove(
                "active"
            );


            if (
                item.dataset.page === currentPage
            ) {

                item.classList.add(
                    "active"
                );

            }

        });

}