import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from main import PreviewBareUrlLinkifier, WINDOWS_DRIVE_PATH_PATTERN


def _linkify(html):
    linkifier = PreviewBareUrlLinkifier()
    linkifier.feed(html)
    linkifier.close()
    return linkifier.result()


def test_bare_url_keeps_query_after_ampersand():
    html = _linkify("<p>See https://example.com/search?a=1&amp;b=2 now</p>")

    assert '<a href="https://example.com/search?a=1&amp;b=2">' in html
    assert html.endswith(" now</p>")


def test_text_stays_escaped_and_code_is_not_linked():
    html = _linkify("<p>1 &lt; 2 &amp; R&amp;D</p><code>https://x.example</code>")

    assert html == "<p>1 &lt; 2 &amp; R&amp;D</p><code>https://x.example</code>"


def test_trailing_punctuation_is_not_part_of_the_link():
    html = _linkify("<p>Go to https://example.com.</p>")

    assert html == '<p>Go to <a href="https://example.com">https://example.com</a>.</p>'


def test_windows_drive_paths_are_recognised():
    assert WINDOWS_DRIVE_PATH_PATTERN.match("C:\\Users\\a.png")
    assert WINDOWS_DRIVE_PATH_PATTERN.match("C:/Users/a.png")
    assert WINDOWS_DRIVE_PATH_PATTERN.match("c:%5CUsers%5Ca.png")
    assert not WINDOWS_DRIVE_PATH_PATTERN.match("images/a.png")
    assert not WINDOWS_DRIVE_PATH_PATTERN.match("https://example.com/a.png")
