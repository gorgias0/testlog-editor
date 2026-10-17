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


# Elements whose end tag HTML lets authors leave out; a new one closes the open one.
HTML_IMPLIED_END_ELEMENTS = {
    "li": {"li"},
    "p": {"p"},
    "option": {"option"},
    "dt": {"dt", "dd"},
    "dd": {"dt", "dd"},
    "tr": {"tr", "td", "th"},
    "td": {"td", "th"},
    "th": {"td", "th"},
}

# Content of these elements is shown exactly as written; re-indenting it changes it.
HTML_PRESERVED_ELEMENTS = {"pre", "textarea"}


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
        self.tokens.append(("data", None, data))

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

    def unknown_decl(self, data):
        # CDATA sections, e.g. inside <svg>; dropping them loses content.
        closing = "]]>" if data.startswith("CDATA[") else "]>"
        self.tokens.append(("data", None, f"<![{data}{closing}"))


def pretty_print_html(text, indent="  "):
    parser = PrettyHTMLParser()
    parser.feed(text)
    parser.close()

    lines = []
    open_tags = []
    preserved = None
    for token_type, tag, value in parser.tokens:
        if preserved is not None:
            preserved["raw"].append(value)
            if token_type == "start" and tag == preserved["tag"]:
                preserved["nesting"] += 1
            elif token_type == "end" and tag == preserved["tag"]:
                preserved["nesting"] -= 1
                if preserved["nesting"] == 0:
                    lines.append(f"{indent * len(open_tags)}{''.join(preserved['raw'])}")
                    preserved = None
            continue

        if token_type == "data":
            if value.strip():
                lines.append(f"{indent * len(open_tags)}{value.strip()}")
            continue

        if token_type == "end":
            if tag in open_tags:
                while open_tags and open_tags[-1] != tag:
                    open_tags.pop()
                open_tags.pop()
            elif open_tags:
                open_tags.pop()
            lines.append(f"{indent * len(open_tags)}{value}")
            continue

        if token_type == "start" and tag in HTML_IMPLIED_END_ELEMENTS:
            while open_tags and open_tags[-1] in HTML_IMPLIED_END_ELEMENTS[tag]:
                open_tags.pop()

        if token_type == "start" and tag in HTML_PRESERVED_ELEMENTS:
            preserved = {"tag": tag, "nesting": 1, "raw": [value]}
            continue

        lines.append(f"{indent * len(open_tags)}{value}")
        if token_type == "start" and tag not in HTML_VOID_ELEMENTS:
            open_tags.append(tag)

    if preserved is not None:
        lines.append(f"{indent * len(open_tags)}{''.join(preserved['raw'])}")

    return "\n".join(lines)
