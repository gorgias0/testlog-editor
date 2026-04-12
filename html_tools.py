from html.parser import HTMLParser


HTML_VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


class PrettyHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.tokens = []

    def handle_starttag(self, tag, attrs):
        self.tokens.append(("start", tag.lower(), self.get_starttag_text()))

    def handle_startendtag(self, tag, attrs):
        self.tokens.append(("empty", tag.lower(), self.get_starttag_text()))

    def handle_endtag(self, tag):
        self.tokens.append(("end", tag.lower(), f"</{tag}>"))

    def handle_data(self, data):
        if data.strip():
            self.tokens.append(("data", None, data.strip()))

    def handle_entityref(self, name):
        self.tokens.append(("data", None, f"&{name};"))

    def handle_charref(self, name):
        self.tokens.append(("data", None, f"&#{name};"))

    def handle_comment(self, data):
        self.tokens.append(("data", None, f"<!--{data}-->"))

    def handle_decl(self, decl):
        self.tokens.append(("data", None, f"<!{decl}>"))

    def handle_pi(self, data):
        self.tokens.append(("data", None, f"<?{data}>"))


def pretty_print_html(text, indent="  "):
    parser = PrettyHTMLParser()
    parser.feed(text)
    parser.close()

    lines = []
    depth = 0
    for token_type, tag, value in parser.tokens:
        if token_type == "end":
            depth = max(0, depth - 1)
            lines.append(f"{indent * depth}{value}")
            continue

        lines.append(f"{indent * depth}{value}")
        if token_type == "start" and tag not in HTML_VOID_ELEMENTS:
            depth += 1

    return "\n".join(lines)
