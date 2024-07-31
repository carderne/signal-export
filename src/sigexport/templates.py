"""HTML templates."""

html = """
<!doctype html>
<html lang='en'>
<head>
    <meta charset='utf-8'>
    <title>{name}</title>
    <link rel=stylesheet href='../style.css'>
</head>
<body>
    <div class=first>
        <a href=#pg0>FIRST</a>
    </div>
    <div class=last>
        <a href=#pg{last_page}>LAST</a>
    </div>
    {content}
    <script>if (!document.location.hash) document.location.hash = 'pg0'</script>
</body>
</html>
"""

message = """
<div class='{cl}'>
    <span class=date>{date}</span>
    <span class=time>{time}</span>
    <span class=sender>{sender}</span>
    {quote}
    <span class=body>{body}</span>
    <span class=reaction>{reactions}</span>
</div>
"""

audio = """
<audio controls>
    <source src="{src}" type="audio/mp4">
</audio>
"""

figure = """
<figure>
    <label for="{alt}">
        <img load="lazy" src="{src}" alt="{alt}">
    </label>
    <input class="modal-state" id="{alt}" type="checkbox">
    <div class="modal">
        <label for="{alt}">
            <div class="modal-content">
                <img class="modal-photo" loading="lazy" src="{src}" alt="{alt}">
            </div>
        </label>
    </div>
</figure>
"""

video = """
<video controls>
    <source src="{src}" type="video/mp4">
    </source>
</video>
"""
