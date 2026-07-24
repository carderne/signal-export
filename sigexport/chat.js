/* Theme switching and keyboard navigation for signal-export HTML output.
   Loaded from <head> so the stored theme is applied before the first paint. */
(function () {
    "use strict";

    var root = document.documentElement;
    var KEY = "sigexport-theme";

    root.classList.add("js");

    function stored() {
        try {
            return localStorage.getItem(KEY);
        } catch (e) {
            /* file:// with storage disabled, or private mode */
            return null;
        }
    }

    function remember(theme) {
        try {
            if (theme === "auto") {
                localStorage.removeItem(KEY);
            } else {
                localStorage.setItem(KEY, theme);
            }
        } catch (e) {
            /* not fatal, the theme just will not stick */
        }
    }

    function apply(theme) {
        if (theme === "light" || theme === "dark") {
            root.setAttribute("data-theme", theme);
        } else {
            theme = "auto";
            root.removeAttribute("data-theme");
        }
        var buttons = document.querySelectorAll("[data-theme-choice]");
        for (var i = 0; i < buttons.length; i++) {
            buttons[i].setAttribute(
                "aria-pressed",
                buttons[i].dataset.themeChoice === theme ? "true" : "false"
            );
        }
    }

    /* Before paint: no flash of the wrong theme. */
    apply(stored());

    function currentPage() {
        var m = /^#pg(\d+)$/.exec(location.hash);
        return m ? parseInt(m[1], 10) : 0;
    }

    function closeModals() {
        var open = document.querySelectorAll(".modal-state:checked");
        for (var i = 0; i < open.length; i++) {
            open[i].checked = false;
        }
        return open.length > 0;
    }

    function isField(el) {
        if (!el) return false;
        var tag = el.tagName;
        return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
    }

    function jumpTo(input) {
        var max = parseInt(input.max, 10) || 1;
        var n = parseInt(input.value, 10);
        if (isNaN(n)) {
            input.value = currentPage() + 1;
            return;
        }
        n = Math.min(Math.max(n, 1), max);
        input.value = n;
        location.hash = "pg" + (n - 1);
    }

    function onKey(e) {
        if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
        if (e.key === "Escape") {
            if (isField(e.target) && e.target.blur) e.target.blur();
            closeModals();
            return;
        }
        /* let the page-number field handle its own keys */
        if (isField(e.target)) return;
        if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;

        var last = parseInt(document.body.dataset.lastPage, 10) || 0;
        var page = currentPage();
        var next = e.key === "ArrowLeft" ? page - 1 : page + 1;
        if (next < 0 || next > last) return;
        location.hash = "pg" + next;
        e.preventDefault();
    }

    function ready() {
        apply(stored());

        document.addEventListener("click", function (e) {
            if (!e.target || !e.target.closest) return;
            var button = e.target.closest("[data-theme-choice]");
            if (!button) return;
            var theme = button.dataset.themeChoice;
            remember(theme);
            apply(theme);
        });

        document.addEventListener("keydown", onKey);

        /* Enable the page-number jump field (readonly until JS is here). */
        var jumps = document.querySelectorAll(".pagejump");
        for (var j = 0; j < jumps.length; j++) {
            jumps[j].removeAttribute("readonly");
            jumps[j].addEventListener("change", function () {
                jumpTo(this);
            });
            jumps[j].addEventListener("keydown", function (e) {
                if (e.key === "Enter") {
                    e.preventDefault();
                    jumpTo(this);
                }
            });
        }

        /* Browsers without :has() cannot show the first page unaided. */
        var hasSupport =
            window.CSS && CSS.supports && CSS.supports("selector(:has(*))");
        if (!hasSupport && !location.hash) {
            location.hash = "pg0";
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", ready);
    } else {
        ready();
    }
})();
