import base64
import json
import random
import re
import uuid
from datetime import date, timedelta
from urllib.parse import quote as url_quote, unquote as url_unquote

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QFont, QIntValidator
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
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


class TextToolDialog(QDialog):
    def __init__(self, translate, parent=None):
        super().__init__(parent)
        self._tr = translate
        self.settings = QSettings("TestLog Editor", "TestLog Editor")
        self.resize(700, 500)
        saved_size = self.settings.value("text_tool_size")
        if saved_size:
            self.resize(saved_size)
        self._special_character_samples = [
            (
                "Null and control characters",
                "Null och kontrolltecken",
                ["\\x00", "\\t", "\\r\\n", "\\x1f"],
            ),
            (
                "Emoji",
                "Emoji",
                ["😀", "🔥", "💀", "🧪", "✅", "❌", "⚠️"],
            ),
            (
                "RTL text",
                "RTL-text",
                ["مرحبا", "שלום", "\u202eRTL override"],
            ),
            (
                "Long Unicode strings",
                "Långa Unicode-strängar",
                ["Zalgo: H̷̳̄ȅ̸̬j̷̞̚ ̶̫̍v̵̳͗ä̷̻̀r̵̖͝l̷̟̕d̴̰̈́", "Kombinerade tecken: A\u0301 e\u0308 o\u030a n\u0303"],
            ),
            (
                "SQL injection",
                "SQL injection",
                ["' OR '1'='1", "'; DROP TABLE users; --", "1; SELECT * FROM users"],
            ),
            (
                "XSS",
                "XSS",
                ["<script>alert('xss')</script>", "\"><img src=x onerror=alert(1)>", "javascript:alert(1)"],
            ),
            (
                "Format strings",
                "Formatsträngar",
                ["%s %d %n", "{0} {{}}", "../../../../etc/passwd"],
            ),
        ]

        layout = QVBoxLayout(self)
        self.menu_bar = QMenuBar(self)
        layout.setMenuBar(self.menu_bar)
        self.toolbar = QToolBar()
        self.text_area = QTextEdit()
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
        self.testdata_action = QAction(self)
        self.testdata_action.triggered.connect(self._generate_testdata)
        self.special_characters_action = QAction(self)
        self.special_characters_action.triggered.connect(self._show_special_characters_dialog)
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
        self.toolbar.addAction(self.testdata_action)
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
            self.toolbar.widgetForAction(self.testdata_action),
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
        self.testdata_action.setText(self._tr("Testdata"))
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
        self.text_area.setPlainText("START\n\n" + "\n\n".join(generated_paragraphs) + "\n\nEND")

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

    def _show_special_characters_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self._tr("Special Characters"))

        layout = QVBoxLayout(dialog)
        checkboxes = []
        for key, _, _ in self._special_character_samples:
            checkbox = QCheckBox(self._tr(key), dialog)
            checkbox.setChecked(True)
            layout.addWidget(checkbox)
            checkboxes.append((key, checkbox))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, parent=dialog)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self._tr("Insert Selected"))
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_keys = [key for key, checkbox in checkboxes if checkbox.isChecked()]
            self._append_special_character_sections(selected_keys)

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

    def _generate_testdata(self):
        first_name = random.choice([
            "Erik", "Anna", "Sofia", "Johan", "Lina", "Karl", "Maja", "Oskar", "Elin", "Viktor",
            "Åsa", "Älva", "Björn", "Örjan",
        ])
        last_name = random.choice([
            "Lindström", "Svensson", "Bergman", "Holm", "Nyqvist", "Dahlgren", "Sandberg", "Ekman", "Söderlund", "Lindberg",
        ])
        street = random.choice([
            "Storgatan", "Björkgatan", "Parkvägen", "Skolgatan", "Kungsgatan", "Ängsvägen", "Tallstigen", "Lindvägen",
        ])
        city, postal_code = random.choice([
            ("Göteborg", "412 56"),
            ("Stockholm", "118 62"),
            ("Malmö", "214 36"),
            ("Uppsala", "753 21"),
            ("Västerås", "722 15"),
            ("Örebro", "703 62"),
            ("Linköping", "582 24"),
            ("Lund", "223 55"),
        ])
        street_number = random.randint(3, 48)
        personal_number = self._generate_personnummer()
        email = f"{self._normalize_email_name(first_name)}.{self._normalize_email_name(last_name)}@example.com"
        landline = self._generate_landline_number()
        landline_intl = self._to_international_phone(landline)
        mobile = self._generate_mobile_number()
        mobile_intl = self._to_international_phone(mobile)
        field_width = 18
        rows = [
            ("Namn:", f"{first_name} {last_name}"),
            ("Adress:", f"{street} {street_number}, {postal_code} {city}"),
            ("Personnummer:", personal_number),
            ("E-post:", email),
            ("Telefon:", landline),
            ("Telefon +46:", landline_intl),
            ("Mobil:", mobile),
            ("Mobil +46:", mobile_intl),
        ]

        self.text_area.setPlainText(
            "\n".join(f"{label:<{field_width}}{value}" for label, value in rows)
        )

    def _append_special_character_sections(self, selected_keys):
        sections = []
        for key, section_label, samples in self._special_character_samples:
            if key not in selected_keys:
                continue
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
        start_date = date(1950, 1, 1)
        end_date = date(2005, 12, 31)
        birthday = start_date + timedelta(days=random.randint(0, (end_date - start_date).days))
        base = birthday.strftime("%y%m%d") + f"{random.randint(0, 999):03d}"
        checksum = self._luhn_checksum(base)
        return f"{birthday.strftime('%Y%m%d')}-{base[6:]}{checksum}"

    def _luhn_checksum(self, digits):
        total = 0
        for index, char in enumerate(digits):
            digit = int(char)
            if index % 2 == 0:
                digit *= 2
                if digit > 9:
                    digit -= 9
            total += digit
        return (10 - (total % 10)) % 10

    def _generate_landline_number(self):
        area_code = random.choice(["08", "031", "040", "018", "019", "013"])
        middle = random.randint(100, 999)
        end_a = random.randint(10, 99)
        end_b = random.randint(10, 99)
        return f"{area_code}-{middle} {end_a:02d} {end_b:02d}"

    def _generate_mobile_number(self):
        prefix = random.choice(["070", "072", "073", "076", "079"])
        middle = random.randint(100, 999)
        end_a = random.randint(10, 99)
        end_b = random.randint(10, 99)
        return f"{prefix}-{middle} {end_a:02d} {end_b:02d}"

    def _to_international_phone(self, phone_number):
        compact = re.sub(r"\s+", " ", phone_number.strip())
        if compact.startswith("0"):
            return f"+46 {compact[1:]}"
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
