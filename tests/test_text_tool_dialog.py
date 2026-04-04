import text_tool_dialog
from text_tool_dialog import TextToolDialog


class StubTextArea:
    def __init__(self):
        self.value = ""

    def setPlainText(self, text):
        self.value = text


class StubFaker:
    def first_name(self):
        return "Alice"

    def last_name(self):
        return "Andersson"


def test_build_testdata_context_keeps_name_company_and_email_aligned(monkeypatch):
    dialog = TextToolDialog.__new__(TextToolDialog)
    faker = StubFaker()

    monkeypatch.setattr(text_tool_dialog.random, "choice", lambda values: "Teknik")

    context = dialog._build_testdata_context(faker, "se")

    assert context == {
        "first_name": "Alice",
        "last_name": "Andersson",
        "full_name": "Alice Andersson",
        "company_name": "Andersson Teknik AB",
        "email": "alice.andersson@anderssonteknik.se",
    }


def test_build_company_domain_omits_legal_suffix_from_email_domain():
    dialog = TextToolDialog.__new__(TextToolDialog)

    domain = dialog._build_company_domain("Morgan Consulting Ltd", "uk")

    assert domain == "morganconsulting.co.uk"


def test_generate_lorem_text_ends_last_paragraph_with_end_without_wrappers():
    dialog = TextToolDialog.__new__(TextToolDialog)
    dialog.text_area = StubTextArea()

    dialog._generate_lorem_text(2)

    assert not dialog.text_area.value.startswith("START")
    assert not dialog.text_area.value.endswith("\n\nEND")
    assert dialog.text_area.value.endswith(".\n###")
