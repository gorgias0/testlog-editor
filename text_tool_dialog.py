import base64
import json
import random
import re
import uuid
from urllib.parse import quote as url_quote, unquote as url_unquote

from faker import Faker
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QFont, QIntValidator
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QTextEdit,
    QToolBar,
    QToolButton,
    QVBoxLayout,
)

TESTDATA_PROFILES = {
    "se": {
        "menu_key": "Sweden",
        "faker_locale": "sv_SE",
        "name_label": "Namn:",
        "address_label": "Adress:",
        "id_label": "Personnummer:",
        "email_label": "E-post:",
        "phone_label": "Telefon:",
        "phone_intl_label": "Telefon +46:",
        "mobile_label": "Mobil:",
        "mobile_intl_label": "Mobil +46:",
        "company_label": "Bolag:",
        "org_label": "Org.nr:",
        "vat_label": "Momsreg.nr:",
        "country_code": "+46",
        "id_generator": "_generate_personnummer",
        "landline_generator": "_generate_swedish_landline_number",
        "mobile_generator": "_generate_swedish_mobile_number",
        "org_generator": "_generate_swedish_org_number",
        "vat_generator": "_generate_swedish_vat_number",
    },
    "no": {
        "menu_key": "Norway",
        "faker_locale": "no_NO",
        "name_label": "Navn:",
        "address_label": "Adresse:",
        "id_label": "Fodselsnummer:",
        "email_label": "E-post:",
        "phone_label": "Telefon:",
        "phone_intl_label": "Telefon +47:",
        "mobile_label": "Mobil:",
        "mobile_intl_label": "Mobil +47:",
        "company_label": "Firma:",
        "org_label": "Org.nr:",
        "vat_label": "MVA-nr:",
        "country_code": "+47",
        "id_generator": "_generate_fodselsnummer",
        "landline_generator": "_generate_norwegian_landline_number",
        "mobile_generator": "_generate_norwegian_mobile_number",
        "org_generator": "_generate_norwegian_org_number",
        "vat_generator": "_generate_norwegian_vat_number",
    },
    "dk": {
        "menu_key": "Denmark",
        "faker_locale": "da_DK",
        "name_label": "Navn:",
        "address_label": "Adresse:",
        "id_label": "CPR:",
        "email_label": "E-mail:",
        "phone_label": "Telefon:",
        "phone_intl_label": "Telefon +45:",
        "mobile_label": "Mobil:",
        "mobile_intl_label": "Mobil +45:",
        "company_label": "Firma:",
        "org_label": "CVR:",
        "vat_label": "Momsnr.:",
        "country_code": "+45",
        "id_generator": "_generate_cpr_number",
        "landline_generator": "_generate_danish_landline_number",
        "mobile_generator": "_generate_danish_mobile_number",
        "org_generator": "_generate_danish_org_number",
        "vat_generator": "_generate_danish_vat_number",
    },
    "fi": {
        "menu_key": "Finland",
        "faker_locale": "fi_FI",
        "name_label": "Nimi:",
        "address_label": "Osoite:",
        "id_label": "Henkilotunnus:",
        "email_label": "Sahkoposti:",
        "phone_label": "Puhelin:",
        "phone_intl_label": "Puhelin +358:",
        "mobile_label": "Matkapuhelin:",
        "mobile_intl_label": "Matkapuhelin +358:",
        "company_label": "Yritys:",
        "org_label": "Y-tunnus:",
        "vat_label": "ALV-numero:",
        "country_code": "+358",
        "id_generator": "_generate_hetu_number",
        "landline_generator": "_generate_finnish_landline_number",
        "mobile_generator": "_generate_finnish_mobile_number",
        "org_generator": "_generate_finnish_org_number",
        "vat_generator": "_generate_finnish_vat_number",
    },
    "is": {
        "menu_key": "Iceland",
        "faker_locale": "en_US",
        "name_label": "Nafn:",
        "address_label": "Heimilisfang:",
        "id_label": "Kennitala:",
        "email_label": "Netfang:",
        "phone_label": "Simi:",
        "phone_intl_label": "Simi +354:",
        "mobile_label": "Farsimi:",
        "mobile_intl_label": "Farsimi +354:",
        "company_label": "Fyrirtaeki:",
        "org_label": "Kt.:",
        "vat_label": "VSK-nr.:",
        "country_code": "+354",
        "id_generator": "_generate_kennitala_number",
        "landline_generator": "_generate_icelandic_landline_number",
        "mobile_generator": "_generate_icelandic_mobile_number",
        "org_generator": "_generate_icelandic_org_number",
        "vat_generator": "_generate_icelandic_vat_number",
    },
    "uk": {
        "menu_key": "United Kingdom",
        "faker_locale": "en_GB",
        "name_label": "Name:",
        "address_label": "Address:",
        "id_label": "Insurance No.:",
        "email_label": "Email:",
        "phone_label": "Phone:",
        "phone_intl_label": "Phone +44:",
        "mobile_label": "Mobile:",
        "mobile_intl_label": "Mobile +44:",
        "company_label": "Company:",
        "org_label": "Company No.:",
        "vat_label": "VAT No.:",
        "country_code": "+44",
        "id_generator": "_generate_ni_number",
        "landline_generator": "_generate_uk_landline_number",
        "mobile_generator": "_generate_uk_mobile_number",
        "org_generator": "_generate_uk_company_number",
        "vat_generator": "_generate_uk_vat_number",
    },
    "us": {
        "menu_key": "United States",
        "faker_locale": "en_US",
        "name_label": "Name:",
        "address_label": "Address:",
        "id_label": "SSN:",
        "email_label": "Email:",
        "phone_label": "Phone:",
        "phone_intl_label": "Phone +1:",
        "mobile_label": "Mobile:",
        "mobile_intl_label": "Mobile +1:",
        "company_label": "Company:",
        "org_label": "EIN:",
        "vat_label": "Tax ID:",
        "country_code": "+1",
        "id_generator": "_generate_ssn",
        "landline_generator": "_generate_us_landline_number",
        "mobile_generator": "_generate_us_mobile_number",
        "org_generator": "_generate_us_ein",
        "vat_generator": "_generate_us_tax_id",
    },
}

TESTDATA_COMPANY_SUFFIXES = {
    "se": "AB",
    "no": "AS",
    "dk": "ApS",
    "fi": "Oy",
    "is": "ehf.",
    "uk": "Ltd",
    "us": "LLC",
}

TESTDATA_EMAIL_TLDS = {
    "se": "se",
    "no": "no",
    "dk": "dk",
    "fi": "fi",
    "is": "is",
    "uk": "co.uk",
    "us": "com",
}

TESTDATA_COMPANY_WORDS = {
    "se": ["Teknik", "Konsult", "Logistik", "Bygg"],
    "no": ["Service", "Teknikk", "Drift", "Bygg"],
    "dk": ["Data", "Service", "Logistik", "Teknik"],
    "fi": ["Solutions", "Huolto", "Data", "Palvelut"],
    "is": ["Lausnir", "THjonusta", "Verkfraedi", "Honnun"],
    "uk": ["Consulting", "Services", "Logistics", "Digital"],
    "us": ["Solutions", "Consulting", "Logistics", "Systems"],
}


class TextToolDialog(QDialog):
    def __init__(self, translate, parent=None):
        super().__init__(parent)
        self._tr = translate
        self.settings = QSettings("TestLog Editor", "TestLog Editor")
        self._faker_by_locale = {}
        self.resize(700, 500)
        saved_size = self.settings.value("text_tool_size")
        if saved_size:
            self.resize(saved_size)
        self._special_character_samples = [
            (
                "XSS",
                "XSS",
                [
                    "<script>alert(1)</script>",
                    "\"><img src=x onerror=alert(1)>",
                    "<svg onload=alert(1)>",
                    "javascript:alert(1)",
                ],
            ),
            (
                "SQL injection",
                "SQL injection",
                [
                    "' OR '1'='1' --",
                    "admin'--",
                    "' UNION SELECT NULL,NULL--",
                ],
            ),
            (
                "Path traversal",
                "Path traversal",
                [
                    "../../../../etc/passwd",
                    "..\\..\\..\\windows\\win.ini",
                ],
            ),
            (
                "Command injection",
                "Command injection",
                [
                    "; whoami",
                    "&& whoami",
                    "`whoami`",
                ],
            ),
            (
                "Template injection",
                "Template injection",
                [
                    "{{7*7}}",
                    "${7*7}",
                ],
            ),
        ]

        layout = QVBoxLayout(self)
        self.menu_bar = QMenuBar(self)
        layout.setMenuBar(self.menu_bar)
        self.toolbar = QToolBar()
        self.text_area = QTextEdit()
        self.text_area.setAcceptRichText(False)
        text_area_font = QFont()
        text_area_font.setFamilies(["Cascadia Code", "Source Code Pro", "Noto Sans Mono", "monospace"])
        text_area_font.setStyleHint(QFont.StyleHint.Monospace)
        text_area_font.setPointSize(12)
        self.text_area.setFont(text_area_font)
        self.status_bar = QStatusBar()
        self.file_menu = QMenu(self)
        self.close_action = QAction(self)
        self.close_action.triggered.connect(self.close)
        self.transform_menu = QMenu(self)
        self.base64_encode_action = QAction(self)
        self.base64_encode_action.triggered.connect(self._transform_base64_encode)
        self.base64_decode_action = QAction(self)
        self.base64_decode_action.triggered.connect(self._transform_base64_decode)
        self.url_encode_action = QAction(self)
        self.url_encode_action.triggered.connect(self._transform_url_encode)
        self.url_decode_action = QAction(self)
        self.url_decode_action.triggered.connect(self._transform_url_decode)
        self.format_json_action = QAction(self)
        self.format_json_action.triggered.connect(self._transform_format_json)
        self.generate_lorem_button = QToolButton(self)
        self.generate_lorem_button.clicked.connect(lambda: self._generate_lorem_text(5))
        self.generate_lorem_menu = QMenu(self.generate_lorem_button)
        for paragraph_count in (5, 10, 20, 30, 50, 100):
            action = self.generate_lorem_menu.addAction(str(paragraph_count))
            action.triggered.connect(
                lambda checked=False, count=paragraph_count: self._generate_lorem_text(count)
            )
        self.generate_lorem_button.setMenu(self.generate_lorem_menu)
        self.generate_lorem_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.counter_string_action = QAction(self)
        self.counter_string_action.triggered.connect(self._show_counter_string_dialog)
        self.uuid_action = QAction(self)
        self.uuid_action.triggered.connect(self._show_uuid_dialog)
        self.testdata_button = QToolButton(self)
        self.testdata_button.clicked.connect(lambda checked=False: self._generate_testdata("se"))
        self.testdata_menu = QMenu(self.testdata_button)
        self.testdata_locale_actions = {}
        for locale_code in ("se", "no", "dk", "fi", "is", "uk", "us"):
            action = self.testdata_menu.addAction("")
            action.triggered.connect(
                lambda checked=False, code=locale_code: self._generate_testdata(code)
            )
            self.testdata_locale_actions[locale_code] = action
        self.testdata_button.setMenu(self.testdata_menu)
        self.testdata_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.special_characters_action = QAction(self)
        self.special_characters_action.triggered.connect(self._insert_special_character_samples)
        self.copy_all_action = QAction(self)
        self.copy_all_action.triggered.connect(self._copy_all_text)
        self.clear_action = QAction(self)
        self.clear_action.triggered.connect(self.text_area.clear)

        self.menu_bar.addMenu(self.file_menu)
        self.file_menu.addAction(self.close_action)
        self.menu_bar.addMenu(self.transform_menu)
        self.transform_menu.addAction(self.base64_encode_action)
        self.transform_menu.addAction(self.base64_decode_action)
        self.transform_menu.addSeparator()
        self.transform_menu.addAction(self.url_encode_action)
        self.transform_menu.addAction(self.url_decode_action)
        self.transform_menu.addSeparator()
        self.transform_menu.addAction(self.format_json_action)

        self.toolbar.addWidget(self.generate_lorem_button)
        self.toolbar.addAction(self.counter_string_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.uuid_action)
        self.toolbar.addWidget(self.testdata_button)
        self.toolbar.addAction(self.special_characters_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.copy_all_action)
        self.toolbar.addAction(self.clear_action)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.text_area)
        layout.addWidget(self.status_bar)

        self.text_area.textChanged.connect(self._update_counts)
        self.text_area.cursorPositionChanged.connect(self._update_counts)
        self._configure_focus_navigation()
        self.retranslate_ui()
        self._update_counts()

    def _with_mnemonic(self, text):
        return f"&{text}" if text else text

    def _configure_focus_navigation(self):
        self.menu_bar.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.toolbar.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.generate_lorem_button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.text_area.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        toolbar_widgets = [
            self.generate_lorem_button,
            self.toolbar.widgetForAction(self.counter_string_action),
            self.toolbar.widgetForAction(self.uuid_action),
            self.testdata_button,
            self.toolbar.widgetForAction(self.special_characters_action),
            self.toolbar.widgetForAction(self.copy_all_action),
            self.toolbar.widgetForAction(self.clear_action),
        ]
        focusable_widgets = [self.menu_bar] + [widget for widget in toolbar_widgets if widget is not None] + [self.text_area]
        for widget in focusable_widgets[1:-1]:
            widget.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        for current_widget, next_widget in zip(focusable_widgets, focusable_widgets[1:]):
            self.setTabOrder(current_widget, next_widget)

    def retranslate_ui(self):
        self.setWindowTitle(self._tr("Text Tool"))
        self.text_area.setPlaceholderText(self._tr("Paste text here..."))
        self.file_menu.setTitle(self._with_mnemonic(self._tr("File")))
        self.close_action.setText(self._tr("Close"))
        self.transform_menu.setTitle(self._with_mnemonic(self._tr("Transform")))
        self.base64_encode_action.setText(self._tr("To Base64"))
        self.base64_decode_action.setText(self._tr("From Base64"))
        self.url_encode_action.setText(self._tr("To URL"))
        self.url_decode_action.setText(self._tr("From URL"))
        self.format_json_action.setText(self._tr("Format JSON"))
        self.generate_lorem_button.setText(self._tr("Generate Lorem"))
        self.generate_lorem_button.setToolTip(self._tr("Generate Lorem"))
        self.counter_string_action.setText(self._tr("Counter String"))
        self.uuid_action.setText(self._tr("UUID"))
        self.testdata_button.setText(self._tr("Testdata"))
        self.testdata_button.setToolTip(self._tr("Generate Swedish Testdata"))
        for locale_code, action in self.testdata_locale_actions.items():
            action.setText(self._tr(TESTDATA_PROFILES[locale_code]["menu_key"]))
        self.special_characters_action.setText(self._tr("Special Characters"))
        self.copy_all_action.setText(self._tr("Copy All"))
        self.clear_action.setText(self._tr("Clear"))
        self._update_counts()

    def _update_counts(self):
        text = self.text_area.toPlainText()
        without_whitespace = "".join(ch for ch in text if not ch.isspace())
        cursor_pos = self.text_area.textCursor().position()
        self.status_bar.showMessage(
            self._tr("Characters: {with_ws} | Without whitespace: {without_ws} | Cursor: {cursor_pos}").format(
                with_ws=len(text),
                without_ws=len(without_whitespace),
                cursor_pos=cursor_pos,
            )
        )

    def _generate_lorem_text(self, paragraph_count=5):
        paragraphs = [
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Integer posuere erat a ante venenatis dapibus posuere velit aliquet. Sed posuere consectetur est at lobortis. Lorem ipsum dolor sit amet, consectetur adipiscing elit. Integer posuere erat a ante venenatis dapibus posuere velit aliquet. Sed posuere consectetur est at lobortis.",
            "Praesent commodo cursus magna, vel scelerisque nisl consectetur et. Donec sed odio dui. Cras justo odio, dapibus ac facilisis in, egestas eget quam. Praesent commodo cursus magna, vel scelerisque nisl consectetur et. Donec sed odio dui. Cras justo odio, dapibus ac facilisis in, egestas eget quam.",
            "Nullam id dolor id nibh ultricies vehicula ut id elit. Cras mattis consectetur purus sit amet fermentum. Vestibulum id ligula porta felis euismod semper. Nullam id dolor id nibh ultricies vehicula ut id elit. Cras mattis consectetur purus sit amet fermentum. Vestibulum id ligula porta felis euismod semper.",
            "Aenean lacinia bibendum nulla sed consectetur. Maecenas faucibus mollis interdum. Vivamus sagittis lacus vel augue laoreet rutrum faucibus dolor auctor. Aenean lacinia bibendum nulla sed consectetur. Maecenas faucibus mollis interdum. Vivamus sagittis lacus vel augue laoreet rutrum faucibus dolor auctor.",
            "Vestibulum id ligula porta felis euismod semper. Sed posuere consectetur est at lobortis. Donec ullamcorper nulla non metus auctor fringilla. Vestibulum id ligula porta felis euismod semper. Sed posuere consectetur est at lobortis. Donec ullamcorper nulla non metus auctor fringilla.",
            "Etiam porta sem malesuada magna mollis euismod. Curabitur blandit tempus porttitor. Nulla vitae elit libero, a pharetra augue. Etiam porta sem malesuada magna mollis euismod. Curabitur blandit tempus porttitor. Nulla vitae elit libero, a pharetra augue.",
            "Morbi leo risus, porta ac consectetur ac, vestibulum at eros. Sed posuere consectetur est at lobortis. Aenean lacinia bibendum nulla sed consectetur. Morbi leo risus, porta ac consectetur ac, vestibulum at eros. Sed posuere consectetur est at lobortis. Aenean lacinia bibendum nulla sed consectetur.",
            "Donec ullamcorper nulla non metus auctor fringilla. Nulla vitae elit libero, a pharetra augue. Curabitur blandit tempus porttitor. Donec ullamcorper nulla non metus auctor fringilla. Nulla vitae elit libero, a pharetra augue. Curabitur blandit tempus porttitor.",
            "Vivamus sagittis lacus vel augue laoreet rutrum faucibus dolor auctor. Integer posuere erat a ante venenatis dapibus. Maecenas faucibus mollis interdum. Vivamus sagittis lacus vel augue laoreet rutrum faucibus dolor auctor. Integer posuere erat a ante venenatis dapibus. Maecenas faucibus mollis interdum.",
            "Cras justo odio, dapibus ac facilisis in, egestas eget quam. Donec ullamcorper nulla non metus auctor fringilla. Etiam porta sem malesuada magna mollis euismod. Cras justo odio, dapibus ac facilisis in, egestas eget quam. Donec ullamcorper nulla non metus auctor fringilla. Etiam porta sem malesuada magna mollis euismod.",
        ]
        generated_paragraphs = [
            paragraphs[index % len(paragraphs)]
            for index in range(paragraph_count)
        ]
        if generated_paragraphs:
            generated_paragraphs[-1] = re.sub(r"\s*$", "", generated_paragraphs[-1])
        self.text_area.setPlainText("\n\n".join(generated_paragraphs) + "\n###")

    def _show_counter_string_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self._tr("Counter String"))

        layout = QVBoxLayout(dialog)
        form_layout = QFormLayout()
        length_input = QLineEdit(dialog)
        length_input.setValidator(QIntValidator(1, 100000, length_input))
        length_input.setPlaceholderText("100")
        length_input.returnPressed.connect(dialog.accept)
        form_layout.addRow(self._tr("Counter String Length"), length_input)
        layout.addLayout(form_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, parent=dialog)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self._tr("OK"))
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            length = int(length_input.text()) if length_input.text() else 100
            self._generate_counter_string(length)

    def _show_uuid_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self._tr("UUID"))

        layout = QVBoxLayout(dialog)
        form_layout = QFormLayout()
        count_spinbox = QSpinBox(dialog)
        count_spinbox.setRange(1, 100)
        count_spinbox.setValue(1)
        form_layout.addRow(self._tr("Count"), count_spinbox)
        layout.addLayout(form_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, parent=dialog)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self._tr("OK"))
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._generate_uuids(count_spinbox.value())

    def _generate_counter_string(self, length):
        result = ["*"] * length
        i = length
        while i > 0:
            s = str(i)
            pos = i - len(s) - 1
            if pos >= 0:
                result[pos:pos + len(s)] = list(s)
                i = pos
            else:
                break
        self.text_area.setPlainText("".join(result))

    def _generate_uuids(self, count):
        self.text_area.setPlainText("\n".join(str(uuid.uuid4()) for _ in range(count)))

    def _generate_testdata(self, locale_code="se"):
        profile = TESTDATA_PROFILES[locale_code]
        faker = self._faker(profile["faker_locale"])
        context = self._build_testdata_context(faker, locale_code)
        street = faker.street_address().replace("\n", ", ")
        postal_code = faker.postcode().replace("\n", " ")
        city = faker.city().replace("\n", " ")
        identity_value = getattr(self, profile["id_generator"])()
        landline = getattr(self, profile["landline_generator"])()
        landline_intl = self._to_international_phone(landline, profile["country_code"])
        mobile = getattr(self, profile["mobile_generator"])()
        mobile_intl = self._to_international_phone(mobile, profile["country_code"])
        org_number = getattr(self, profile["org_generator"])()
        vat_number = getattr(self, profile["vat_generator"])()
        field_width = 18
        rows = [
            (profile["name_label"], context["full_name"]),
            (profile["address_label"], f"{street}, {postal_code} {city}"),
            (profile["id_label"], identity_value),
            (profile["email_label"], context["email"]),
            (profile["phone_label"], landline),
            (profile["phone_intl_label"], landline_intl),
            (profile["mobile_label"], mobile),
            (profile["mobile_intl_label"], mobile_intl),
            ("", ""),
            (profile["company_label"], context["company_name"]),
            (profile["org_label"], org_number),
            (profile["vat_label"], vat_number),
        ]

        self.text_area.setPlainText(
            "\n".join(
                value if not label else f"{label:<{field_width}}{value}"
                for label, value in rows
            )
        )

    def _faker(self, locale_name):
        faker = self._faker_by_locale.get(locale_name)
        if faker is None:
            faker = Faker(locale_name)
            self._faker_by_locale[locale_name] = faker
        return faker

    def _build_testdata_context(self, faker, locale_code):
        first_name = faker.first_name()
        last_name = faker.last_name()
        company_name = self._build_company_name(last_name, locale_code)
        email = self._build_email_address(first_name, last_name, company_name, locale_code)
        return {
            "first_name": first_name,
            "last_name": last_name,
            "full_name": f"{first_name} {last_name}",
            "company_name": company_name,
            "email": email,
        }

    def _build_company_name(self, last_name, locale_code):
        company_word = random.choice(TESTDATA_COMPANY_WORDS[locale_code])
        company_suffix = TESTDATA_COMPANY_SUFFIXES[locale_code]
        return f"{last_name} {company_word} {company_suffix}"

    def _build_email_address(self, first_name, last_name, company_name, locale_code):
        local_part = ".".join(
            part
            for part in (
                self._normalize_email_name(first_name),
                self._normalize_email_name(last_name),
            )
            if part
        )
        if not local_part:
            local_part = "test.user"
        domain_name = self._build_company_domain(company_name, locale_code)
        return f"{local_part}@{domain_name}"

    def _build_company_domain(self, company_name, locale_code):
        domain_parts = [
            self._normalize_email_name(part)
            for part in company_name.split()
            if self._normalize_email_name(part)
            and self._normalize_email_name(part)
            not in {self._normalize_email_name(TESTDATA_COMPANY_SUFFIXES[locale_code])}
        ]
        if not domain_parts:
            domain_parts = ["example"]
        return f"{''.join(domain_parts)}.{TESTDATA_EMAIL_TLDS[locale_code]}"

    def _insert_special_character_samples(self):
        sections = []
        for _, section_label, samples in self._special_character_samples:
            body = "\n".join(samples)
            sections.append(f"=== {section_label} ===\n{body}")
        if sections:
            self._append_to_text_area("\n\n".join(sections))

    def _append_to_text_area(self, text):
        existing = self.text_area.toPlainText()
        if existing:
            self.text_area.setPlainText(existing.rstrip() + "\n\n" + text)
        else:
            self.text_area.setPlainText(text)

    def _transform_base64_encode(self):
        text = self.text_area.toPlainText()
        encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
        self.text_area.setPlainText(encoded)

    def _transform_base64_decode(self):
        text = self.text_area.toPlainText().strip()
        try:
            decoded = base64.b64decode(text, validate=True).decode("utf-8")
        except Exception:
            QMessageBox.warning(self, self._tr("Transform"), self._tr("Invalid Base64"))
            return
        self.text_area.setPlainText(decoded)

    def _transform_url_encode(self):
        self.text_area.setPlainText(url_quote(self.text_area.toPlainText()))

    def _transform_url_decode(self):
        self.text_area.setPlainText(url_unquote(self.text_area.toPlainText()))

    def _transform_format_json(self):
        text = self.text_area.toPlainText()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as error:
            QMessageBox.warning(
                self,
                self._tr("Transform"),
                self._tr("Invalid JSON: {error}").format(error=str(error)),
            )
            return
        self.text_area.setPlainText(json.dumps(parsed, indent=2, ensure_ascii=False))

    def _generate_personnummer(self):
        return f"20999999-{random.randint(9000, 9999):04d}"

    def _generate_fodselsnummer(self):
        return f"990099{random.randint(90000, 99999):05d}"

    def _generate_cpr_number(self):
        return f"991399-{random.randint(9000, 9999):04d}"

    def _generate_hetu_number(self):
        return f"990099A{random.randint(900, 999):03d}Z"

    def _generate_kennitala_number(self):
        return f"990099-{random.randint(9000, 9999):04d}"

    def _generate_ni_number(self):
        suffix = random.choice("ABCD")
        return f"ZZ00 00 00 {suffix}"

    def _generate_ssn(self):
        return f"000-00-{random.randint(9000, 9999):04d}"

    def _generate_swedish_org_number(self):
        return f"999999-{random.randint(9000, 9999):04d}"

    def _generate_swedish_vat_number(self):
        return "SE999999999999"

    def _generate_norwegian_org_number(self):
        return f"999 {random.randint(900, 999):03d} {random.randint(90, 99):02d}"

    def _generate_norwegian_vat_number(self):
        return "NO999999999MVA"

    def _generate_danish_org_number(self):
        return f"99 {random.randint(90, 99):02d} {random.randint(9000, 9999):04d}"

    def _generate_danish_vat_number(self):
        return "DK99999999"

    def _generate_finnish_org_number(self):
        return f"9999999-{random.randint(0, 9)}"

    def _generate_finnish_vat_number(self):
        return "FI99999999"

    def _generate_icelandic_org_number(self):
        return f"999999-{random.randint(9000, 9999):04d}"

    def _generate_icelandic_vat_number(self):
        return "IS999999"

    def _generate_uk_company_number(self):
        return "ZZ999999"

    def _generate_uk_vat_number(self):
        return "GB999 9999 99"

    def _generate_us_ein(self):
        return f"00-{random.randint(9000000, 9999999):07d}"

    def _generate_us_tax_id(self):
        return f"00-{random.randint(9000000, 9999999):07d}"

    def _generate_swedish_landline_number(self):
        area_code = random.choice(["08", "031", "040", "018", "019", "013"])
        middle = random.randint(100, 999)
        end_a = random.randint(10, 99)
        end_b = random.randint(10, 99)
        return f"{area_code}-{middle} {end_a:02d} {end_b:02d}"

    def _generate_swedish_mobile_number(self):
        prefix = random.choice(["070", "072", "073", "076", "079"])
        middle = random.randint(100, 999)
        end_a = random.randint(10, 99)
        end_b = random.randint(10, 99)
        return f"{prefix}-{middle} {end_a:02d} {end_b:02d}"

    def _generate_norwegian_landline_number(self):
        return f"{random.choice(['21', '22', '32', '51', '55', '61'])} {random.randint(10,99):02d} {random.randint(10,99):02d} {random.randint(10,99):02d}"

    def _generate_norwegian_mobile_number(self):
        return f"{random.choice(['40', '41', '45', '46', '47', '48', '49'])} {random.randint(10,99):02d} {random.randint(10,99):02d} {random.randint(10,99):02d}"

    def _generate_danish_landline_number(self):
        return f"{random.randint(20,89):02d} {random.randint(10,99):02d} {random.randint(10,99):02d} {random.randint(10,99):02d}"

    def _generate_danish_mobile_number(self):
        return f"{random.choice(['20', '21', '22', '23', '24', '25', '26', '27', '28', '29'])} {random.randint(10,99):02d} {random.randint(10,99):02d} {random.randint(10,99):02d}"

    def _generate_finnish_landline_number(self):
        return f"0{random.choice(['9', '13', '14', '17', '18', '19'])} {random.randint(100,999):03d} {random.randint(10,99):02d}"

    def _generate_finnish_mobile_number(self):
        return f"{random.choice(['040', '041', '044', '045', '046', '050'])} {random.randint(100,999):03d} {random.randint(10,99):02d}"

    def _generate_icelandic_landline_number(self):
        return f"{random.choice(['410', '420', '430', '440'])}-{random.randint(1000,9999):04d}"

    def _generate_icelandic_mobile_number(self):
        return f"{random.choice(['611', '621', '661', '691', '771'])}-{random.randint(1000,9999):04d}"

    def _generate_uk_landline_number(self):
        return f"0{random.choice(['20', '121', '131', '141', '161'])} {random.randint(100,999):03d} {random.randint(1000,9999):04d}"

    def _generate_uk_mobile_number(self):
        return f"07{random.randint(100,999):03d} {random.randint(100000,999999):06d}"

    def _generate_us_landline_number(self):
        area_code = random.choice(["206", "312", "415", "512", "617", "720"])
        return f"({area_code}) {random.randint(200,999):03d}-{random.randint(1000,9999):04d}"

    def _generate_us_mobile_number(self):
        area_code = random.choice(["213", "305", "404", "646", "702", "917"])
        return f"({area_code}) {random.randint(200,999):03d}-{random.randint(1000,9999):04d}"

    def _to_international_phone(self, phone_number, country_code="+46"):
        compact = re.sub(r"\s+", " ", phone_number.strip())
        if compact.startswith("0"):
            return f"{country_code} {compact[1:]}"
        if compact.startswith("("):
            digits = re.sub(r"\D", "", compact)
            if digits:
                return f"{country_code} {digits}"
        if compact.startswith(country_code):
            return compact
        return compact

    def _normalize_email_name(self, text):
        translation = str.maketrans({
            "å": "a",
            "ä": "a",
            "ö": "o",
            "Å": "a",
            "Ä": "a",
            "Ö": "o",
        })
        normalized = text.translate(translation).lower()
        return re.sub(r"[^a-z0-9]+", "", normalized)

    def _copy_all_text(self):
        QApplication.clipboard().setText(self.text_area.toPlainText())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F10:
            self.menu_bar.setFocus(Qt.FocusReason.ShortcutFocusReason)
            self.menu_bar.setActiveAction(self.file_menu.menuAction())
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        self.settings.setValue("text_tool_size", self.size())
        super().closeEvent(event)
