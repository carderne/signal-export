/* Theme switching and keyboard navigation for signal-export HTML output.
   Loaded from <head> so the stored theme is applied before the first paint. */
(function () {
    "use strict";

    var root = document.documentElement;
    var KEY = "sigexport-theme";
    var MSG_ID = /^m\d+-\d+$/;
    var MAX_RESULTS = 60;

    root.classList.add("js");

    /* Modern browsers reveal a message's page via CSS (.page:has(:target));
       older ones need JS to show it, tracked by this flag. */
    var hasHas =
        !!(window.CSS && CSS.supports && CSS.supports("selector(:has(*))"));

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

    function flash(el) {
        el.classList.remove("flash");
        /* force a reflow so the animation restarts on a repeat jump */
        void el.offsetWidth;
        el.classList.add("flash");
    }

    /* Reveal the message named in the URL hash and scroll to it. Pages are
       hidden unless targeted; modern browsers reveal the right one via CSS,
       older ones get a .show class here. Also handles arrivals from the
       cross-chat search (index.html#m2-7). */
    function handleHash() {
        var h = location.hash.slice(1);
        var isMsg = MSG_ID.test(h);
        if (!hasHas) {
            var pages = document.querySelectorAll(".page");
            for (var i = 0; i < pages.length; i++) {
                pages[i].classList.remove("show");
            }
        }
        if (!isMsg) return;
        var el = document.getElementById(h);
        if (!el) return;
        if (!hasHas) {
            var pg = el.closest(".page");
            if (pg) pg.classList.add("show");
        }
        el.scrollIntoView({ block: "center" });
        flash(el);
    }

    function nodeText(el) {
        var bodyEl = el.querySelector(".body");
        if (bodyEl) return bodyEl.textContent || "";
        /* event line (call): the text span, not the icon or the timestamp */
        var parts = [];
        var spans = el.querySelectorAll("span");
        for (var i = 0; i < spans.length; i++) {
            if (spans[i].classList.contains("event-icon")) continue;
            parts.push(spans[i].textContent || "");
        }
        return parts.join(" ");
    }

    function buildIndex() {
        var nodes = document.querySelectorAll("main .msg[id], main .event[id]");
        var index = [];
        for (var i = 0; i < nodes.length; i++) {
            var el = nodes[i];
            var text = nodeText(el).replace(/\s+/g, " ").trim();
            if (!text) continue;
            var senderEl = el.querySelector(".sender");
            var timeEl = el.querySelector("time");
            index.push({
                id: el.id,
                text: text,
                lower: text.toLowerCase(),
                sender: senderEl ? senderEl.textContent.trim() : "",
                date: timeEl
                    ? timeEl.getAttribute("title") || timeEl.textContent.trim()
                    : ""
            });
        }
        return index;
    }

    /* A snippet around the first match, with the match wrapped in <mark>.
       Built with text nodes so message content is never treated as HTML. */
    function snippet(text, lowerQuery) {
        var pos = text.toLowerCase().indexOf(lowerQuery);
        var frag = document.createDocumentFragment();
        if (pos === -1) {
            frag.appendChild(document.createTextNode(text.slice(0, 120)));
            return frag;
        }
        var start = Math.max(0, pos - 40);
        var end = Math.min(text.length, pos + lowerQuery.length + 60);
        if (start > 0) frag.appendChild(document.createTextNode("…"));
        frag.appendChild(document.createTextNode(text.slice(start, pos)));
        var mark = document.createElement("mark");
        mark.textContent = text.slice(pos, pos + lowerQuery.length);
        frag.appendChild(mark);
        frag.appendChild(
            document.createTextNode(text.slice(pos + lowerQuery.length, end))
        );
        if (end < text.length) {
            frag.appendChild(document.createTextNode("…"));
        }
        return frag;
    }

    function resultItem(match, lowerQuery) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "searchitem";
        btn.setAttribute("role", "option");
        btn.dataset.target = match.id;
        var meta = document.createElement("span");
        meta.className = "searchitem-meta";
        meta.textContent = [match.sender, match.date]
            .filter(Boolean)
            .join(" · ");
        var snip = document.createElement("span");
        snip.className = "searchitem-text";
        snip.appendChild(snippet(match.text, lowerQuery));
        if (meta.textContent) btn.appendChild(meta);
        btn.appendChild(snip);
        return btn;
    }

    function initChatSearch() {
        var box = document.querySelector(".searchbox");
        var panel = document.querySelector(".searchresults");
        if (!box || !panel) return;

        var index = null;
        var timer = null;

        function close() {
            panel.hidden = true;
            panel.textContent = "";
        }

        function jump(id) {
            close();
            if (location.hash.slice(1) === id) {
                handleHash();
            } else {
                location.hash = id;
            }
        }

        function run() {
            var q = box.value.trim().toLowerCase();
            panel.textContent = "";
            if (q.length < 2) {
                close();
                return;
            }
            if (index === null) index = buildIndex();
            var count = 0;
            for (var i = 0; i < index.length && count < MAX_RESULTS; i++) {
                if (index[i].lower.indexOf(q) === -1) continue;
                panel.appendChild(resultItem(index[i], q));
                count++;
            }
            if (count === 0) {
                var none = document.createElement("div");
                none.className = "searchnone";
                none.textContent = "No matches";
                panel.appendChild(none);
            }
            panel.hidden = false;
        }

        box.addEventListener("input", function () {
            if (timer) clearTimeout(timer);
            timer = setTimeout(run, 120);
        });
        box.addEventListener("focus", function () {
            if (box.value.trim().length >= 2 && panel.firstChild) {
                panel.hidden = false;
            }
        });
        box.addEventListener("keydown", function (e) {
            if (e.key === "Escape") {
                close();
                box.blur();
            } else if (e.key === "ArrowDown" && !panel.hidden) {
                var first = panel.querySelector(".searchitem");
                if (first) {
                    first.focus();
                    e.preventDefault();
                }
            } else if (e.key === "Enter") {
                var hit = panel.querySelector(".searchitem");
                if (hit) {
                    jump(hit.dataset.target);
                    e.preventDefault();
                }
            }
        });

        panel.addEventListener("click", function (e) {
            var item = e.target.closest ? e.target.closest(".searchitem") : null;
            if (item) jump(item.dataset.target);
        });
        panel.addEventListener("keydown", function (e) {
            var item = e.target.closest ? e.target.closest(".searchitem") : null;
            if (!item) return;
            if (e.key === "ArrowDown") {
                var next = item.nextElementSibling;
                if (next && next.focus) next.focus();
                e.preventDefault();
            } else if (e.key === "ArrowUp") {
                var prev = item.previousElementSibling;
                if (prev && prev.focus) prev.focus();
                else box.focus();
                e.preventDefault();
            } else if (e.key === "Escape") {
                close();
                box.focus();
            }
        });

        document.addEventListener("click", function (e) {
            if (!e.target.closest || !e.target.closest(".chatsearch")) close();
        });
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

        initChatSearch();

        /* Browsers without :has() cannot show the first page unaided. */
        if (!hasHas && !location.hash) {
            location.hash = "pg0";
        }

        window.addEventListener("hashchange", handleHash);
        handleHash();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", ready);
    } else {
        ready();
    }
})();
