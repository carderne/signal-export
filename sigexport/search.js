/* Cross-chat search for the signal-export HTML output.
   Loads the index written by sigexport (window.SIGEXPORT_SEARCH), searches it
   client-side and links each hit to that chat's page at the matching message.
   No fetch(), so it works opened straight off disk (file://). */
(function () {
    "use strict";

    var MAX_RESULTS = 200;

    var box = document.getElementById("globalsearch");
    var out = document.getElementById("globalresults");
    var hint = document.getElementById("searchhint");
    if (!box || !out) return;

    var data = window.SIGEXPORT_SEARCH;

    /* Flatten every chat's messages into one list we can scan per keystroke. */
    var items = [];
    if (data && data.chats) {
        for (var c = 0; c < data.chats.length; c++) {
            var chat = data.chats[c];
            var msgs = chat.messages || [];
            for (var m = 0; m < msgs.length; m++) {
                var msg = msgs[m];
                items.push({
                    folder: chat.folder,
                    title: chat.title || chat.folder,
                    id: msg.id,
                    sender: msg.s || "",
                    date: msg.d || "",
                    text: msg.t || "",
                    lower: (msg.t || "").toLowerCase()
                });
            }
        }
    }

    if (!items.length) {
        hint.textContent =
            "No searchable messages were found in this export.";
        box.disabled = true;
        return;
    }

    hint.textContent =
        "Searching " + items.length + " messages across " +
        data.chats.length + " chat" + (data.chats.length === 1 ? "" : "s") + ".";

    function href(item) {
        var path = String(item.folder)
            .split("/")
            .map(encodeURIComponent)
            .join("/");
        return path + "/index.html#" + item.id;
    }

    function shortDate(iso) {
        /* ISO timestamp -> "YYYY-MM-DD HH:MM" without pulling in a date lib */
        if (!iso) return "";
        return iso.replace("T", " ").slice(0, 16);
    }

    /* Snippet around the first match, match wrapped in <mark>. Text nodes only,
       so message content is never parsed as HTML. */
    function snippet(text, lowerQuery) {
        var pos = text.toLowerCase().indexOf(lowerQuery);
        var frag = document.createDocumentFragment();
        if (pos === -1) {
            frag.appendChild(document.createTextNode(text.slice(0, 160)));
            return frag;
        }
        var start = Math.max(0, pos - 50);
        var end = Math.min(text.length, pos + lowerQuery.length + 90);
        if (start > 0) frag.appendChild(document.createTextNode("…"));
        frag.appendChild(document.createTextNode(text.slice(start, pos)));
        var mark = document.createElement("mark");
        mark.textContent = text.slice(pos, pos + lowerQuery.length);
        frag.appendChild(mark);
        frag.appendChild(
            document.createTextNode(text.slice(pos + lowerQuery.length, end))
        );
        if (end < text.length) frag.appendChild(document.createTextNode("…"));
        return frag;
    }

    function resultItem(item, lowerQuery) {
        var a = document.createElement("a");
        a.className = "gresult";
        a.setAttribute("role", "option");
        a.href = href(item);

        var meta = document.createElement("span");
        meta.className = "gresult-meta";
        var chatName = document.createElement("span");
        chatName.className = "gresult-chat";
        chatName.textContent = item.title;
        meta.appendChild(chatName);
        var sub = document.createElement("span");
        sub.className = "gresult-sub";
        sub.textContent = [item.sender, shortDate(item.date)]
            .filter(Boolean)
            .join(" · ");
        meta.appendChild(sub);

        var text = document.createElement("span");
        text.className = "gresult-text";
        text.appendChild(snippet(item.text, lowerQuery));

        a.appendChild(meta);
        a.appendChild(text);
        return a;
    }

    function run() {
        var q = box.value.trim().toLowerCase();
        out.textContent = "";
        if (q.length < 2) {
            hint.hidden = false;
            return;
        }
        hint.hidden = true;
        var count = 0;
        var frag = document.createDocumentFragment();
        for (var i = 0; i < items.length; i++) {
            if (items[i].lower.indexOf(q) === -1) continue;
            if (count < MAX_RESULTS) frag.appendChild(resultItem(items[i], q));
            count++;
        }
        var head = document.createElement("div");
        head.className = "gresult-count";
        if (count === 0) {
            head.textContent = "No matches";
        } else if (count > MAX_RESULTS) {
            head.textContent =
                MAX_RESULTS + " of " + count + " matches (refine to see more)";
        } else {
            head.textContent = count + (count === 1 ? " match" : " matches");
        }
        out.appendChild(head);
        out.appendChild(frag);
    }

    var timer = null;
    box.addEventListener("input", function () {
        if (timer) clearTimeout(timer);
        timer = setTimeout(run, 150);
    });
    box.addEventListener("keydown", function (e) {
        if (e.key === "ArrowDown") {
            var first = out.querySelector(".gresult");
            if (first) {
                first.focus();
                e.preventDefault();
            }
        }
    });
    out.addEventListener("keydown", function (e) {
        var item = e.target.closest ? e.target.closest(".gresult") : null;
        if (!item) return;
        if (e.key === "ArrowDown") {
            var next = item.nextElementSibling;
            if (next && next.classList.contains("gresult")) next.focus();
            e.preventDefault();
        } else if (e.key === "ArrowUp") {
            var prev = item.previousElementSibling;
            if (prev && prev.classList.contains("gresult")) prev.focus();
            else box.focus();
            e.preventDefault();
        }
    });
})();
