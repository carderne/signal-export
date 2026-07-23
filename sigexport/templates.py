"""HTML templates.

These are used with str.format(), so any literal braces would need doubling.
That is why the CSS and JS live in their own files (style.css, chat.js).
"""

html = """
<!doctype html>
<html lang='en'>
<head>
    <meta charset='utf-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1'>
    <title>{name}</title>
    <link rel=stylesheet href='../style.css'>
    <script src='../chat.js'></script>
</head>
<body data-last-page='{last_page}'>
    <header class=topbar>
        <h1 class=chat-title>{name}</h1>
        <div class=theme-switch role=group aria-label='Colour theme'>
            <button type=button data-theme-choice=auto aria-pressed=true>Auto</button>
            <button type=button data-theme-choice=light aria-pressed=false>Light</button>
            <button type=button data-theme-choice=dark aria-pressed=false>Dark</button>
        </div>
    </header>
    <main>
    {content}
    </main>
</body>
</html>
"""

page = """
<div class=page id=pg{page_num}>
    {pager}
    {content}
</div>
"""

pager = """
<nav class=pager aria-label='Pagination'>
    {first}
    {prev}
    <span class=pageno>
        <input class=pagejump type=number inputmode=numeric min=1 max={total_pages}
            value={page_num} readonly aria-label='Jump to page'>
        <span class=pagetotal>/ {total_pages}</span>
    </span>
    {next}
    {last}
</nav>
"""

pager_link = "<a href=#pg{page_num} title='{label}' aria-label='{label}'>{symbol}</a>"

pager_disabled = "<span class=step aria-hidden=true>{symbol}</span>"

day = "<div class=day>{date}</div>"

message = """
<div class='{cl}'>
    {meta}
    {quote}
    <div class=body>{body}</div>
    {reactions}
</div>
"""

meta = """
<div class=meta>
    <span class=sender>{sender}</span>
    <time class=time datetime='{iso}' title='{date}'>{time}</time>
</div>
"""

quote = "<div class=quote>{text}</div>"

reactions = "<div class=reactions>{chips}</div>"

reaction = "<span class=reaction>{emoji}<span class=who>{name}</span></span>"

audio = """
<audio controls preload=metadata src="{src}"></audio>
"""

figure = """
<figure>
    <label for="{fid}">
        <img loading="lazy" src="{src}" alt="{alt}">
    </label>
    <input class="modal-state" id="{fid}" type="checkbox">
    <div class="modal">
        <label for="{fid}" class="modal-content">
            <img class="modal-photo" loading="lazy" src="{src}" alt="{alt}">
        </label>
    </div>
</figure>
"""

video = """
<video controls preload=metadata playsinline src="{src}"></video>
"""

file_link = """
<a class=file href="{src}" target="_blank" rel="noopener">
    <span aria-hidden=true>&#128206;</span>
    <span>{name}</span>
</a>
"""
