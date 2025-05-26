import sys
import random
import string
import sqlite3
from datetime import datetime
import hashlib
import webbrowser
import requests  # para el webhook

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QListWidget, QLineEdit, QMessageBox, QComboBox, QFileDialog
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize
from PySide6.QtGui import QFont

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


# --- Clase principal de lógica RNG ---
class StivionHuzzRNG:
    def __init__(self):
        self.conn = sqlite3.connect('huzz_rng_codes.db')
        self.c = self.conn.cursor()
        self._initialize_database()

    def _initialize_database(self):
        self.c.execute('''CREATE TABLE IF NOT EXISTS codes
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          code TEXT UNIQUE,
                          creation_date TEXT,
                          used BOOLEAN DEFAULT 0,
                          used_date TEXT,
                          category TEXT,
                          metadata TEXT)''')
        self.conn.commit()

    def generate_code(self, length=12, category="general", complexity=3):
        if complexity == 1:
            chars = string.digits
        elif complexity == 2:
            chars = string.ascii_uppercase + string.digits
        else:
            chars = string.ascii_letters + string.digits + "!@#$%^&*()"

        while True:
            code = ''.join(random.choice(chars) for _ in range(length))
            self.c.execute("SELECT code FROM codes WHERE code=?", (code,))
            if not self.c.fetchone():
                break

        metadata = {
            "generator": "Stivion Huzz RNG Pro",
            "version": "1.0",
            "signature": hashlib.sha256(code.encode()).hexdigest()
        }

        creation_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.c.execute("INSERT INTO codes (code, creation_date, category, metadata) VALUES (?, ?, ?, ?)",
                      (code, creation_date, category, str(metadata)))
        self.conn.commit()
        return {
            "code": code,
            "category": category,
            "metadata": metadata,
            "creation_date": creation_date
        }

    def use_code(self, code):
        self.c.execute("UPDATE codes SET used=1, used_date=? WHERE code=? AND used=0",
                      (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), code))
        affected = self.c.rowcount
        self.conn.commit()
        return affected > 0

    def delete_code(self, code):
        self.c.execute("DELETE FROM codes WHERE code=?", (code,))
        affected = self.c.rowcount
        self.conn.commit()
        return affected > 0

    def delete_all_codes(self):
        self.c.execute("DELETE FROM codes")
        self.conn.commit()

    def list_codes(self, show_used=False):
        if show_used:
            self.c.execute("SELECT code, category, used FROM codes ORDER BY id DESC")
        else:
            self.c.execute("SELECT code, category, used FROM codes WHERE used=0 ORDER BY id DESC")
        return self.c.fetchall()

    def __del__(self):
        self.conn.close()


# --- Botón animado ---
class AnimatedButton(QPushButton):
    def __init__(self, text):
        super().__init__(text)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(self.default_style())
        self.anim = QPropertyAnimation(self, b"minimumSize")
        self.anim.setDuration(150)
        self.anim.setEasingCurve(QEasingCurve.OutQuad)

    def enterEvent(self, event):
        self.anim.stop()
        self.anim.setStartValue(self.size())
        self.anim.setEndValue(QSize(self.width() + 10, self.height() + 5))
        self.anim.start()
        self.setStyleSheet(self.hover_style())
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.anim.stop()
        self.anim.setStartValue(self.size())
        self.anim.setEndValue(QSize(self.width() - 10, self.height() - 5))
        self.anim.start()
        self.setStyleSheet(self.default_style())
        super().leaveEvent(event)

    def default_style(self):
        return """
            QPushButton {
                background-color: #8AA29E;
                border-radius: 14px;
                color: white;
                font-size: 16px;
                padding: 10px 18px;
                font-weight: 600;
                font-family: 'SF Pro Text', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                transition: all 0.3s ease;
            }
        """

    def hover_style(self):
        return """
            QPushButton {
                background-color: #718C88;
                border-radius: 14px;
                color: white;
                font-size: 16px;
                padding: 10px 18px;
                font-weight: 700;
                font-family: 'SF Pro Text', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                transition: all 0.3s ease;
            }
        """


# --- GUI con funciones añadidas ---
class StivionHuzzGUI(QWidget):
    PRESETS = {
        "Personalizado": {"length": 12, "complexity": 3, "category": "general"},
        "Warzone": {"length": 12, "complexity": 2, "category": "warzone"},
        "Fortnite": {"length": 10, "complexity": 3, "category": "fortnite"},
        "Minecraft": {"length": 16, "complexity": 3, "category": "minecraft"},
        "Valorant": {"length": 15, "complexity": 2, "category": "valorant"},
        "Among Us": {"length": 8, "complexity": 1, "category": "amongus"},
    }

    LANGUAGES = {
        "Español": {
            "title": "Stivion Huzz RNG - Códigos ",
            "generate": "Generar Código",
            "mark_used": "Marcar como usado",
            "delete_codes": "Borrar código(s)",
            "export_csv": "Exportar CSV",
            "export_pdf": "Exportar PDF",
            "dark_mode": "Modo Oscuro",
            "discord": "Abrir Discord",
            "webhook_success": "Código enviado al webhook correctamente.",
            "webhook_error": "Error al enviar al webhook.",
            "select_code": "Selecciona un código para marcar como usado.",
            "used_success": "Código {code} marcado como usado.",
            "used_error": "El código {code} ya está marcado o no existe.",
            "length_error": "La longitud debe estar entre 4 y 50.",
            "preset_applied": "Preset '{preset}' aplicado.",
            "code_generated": "Código generado: {code} (Categoría: {category})",
            "delete_none": "No hay código seleccionado. Se borrarán todos los códigos.",
            "delete_confirm": "¿Estás seguro de que quieres borrar {count} código(s)?",
            "delete_success": "Código(s) borrado(s) correctamente.",
        },
        "English": {
            "title": "Stivion Huzz RNG -  Codes",
            "generate": "Generate Code",
            "mark_used": "Mark as Used",
            "delete_codes": "Delete Code(s)",
            "export_csv": "Export CSV",
            "export_pdf": "Export PDF",
            "dark_mode": "Dark Mode",
            "discord": "Open Discord",
            "webhook_success": "Code sent to webhook successfully.",
            "webhook_error": "Error sending to webhook.",
            "select_code": "Select a code to mark as used.",
            "used_success": "Code {code} marked as used.",
            "used_error": "Code {code} is already used or does not exist.",
            "length_error": "Length must be between 4 and 50.",
            "preset_applied": "Preset '{preset}' applied.",
            "code_generated": "Code generated: {code} (Category: {category})",
            "delete_none": "No code selected. All codes will be deleted.",
            "delete_confirm": "Are you sure you want to delete {count} code(s)?",
            "delete_success": "Code(s) deleted successfully.",
        }
    }

    DISCORD_URL = "https://discord.gg/qeE8hCGVgb"  # Cambia por tu URL real
    WEBHOOK_URL = "https://ptb.discord.com/api/webhooks/1211637693503508510/4VAK4vCIJBuTpitvQbOLECiK6_WRwEJ0x61hkB_GqmfTe6aoy0kKcfoGuoRi4iXf2ek2"  # Cambia por tu webhook real

    def __init__(self):
        super().__init__()
        self.rng = StivionHuzzRNG()
        self.dark_mode_enabled = False
        self.current_language = "Español"
        self.setWindowTitle(self.LANGUAGES[self.current_language]["title"])
        self.setMinimumSize(700, 580)
        self.setStyleSheet(self.light_style())
        self.init_ui()

    # --- Estilos claro y oscuro ---
    def light_style(self):
        return """
            QWidget {
                background-color: #F3F6F4;
                color: #2F3E46;
                font-family: 'SF Pro Text', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            QListWidget {
                background-color: white;
                border: 1px solid #B7B9B9;
            }
            QComboBox, QLineEdit {
                background-color: white;
                border: 1px solid #B7B9B9;
                border-radius: 6px;
                padding: 5px;
            }
        """

    def dark_style(self):
        return """
            QWidget {
                background-color: #2F3E46;
                color: #D9D9D9;
                font-family: 'SF Pro Text', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            QListWidget {
                background-color: #202E2E;
                border: 1px solid #D9D9D9;
            }
            QComboBox, QLineEdit {
                background-color: #202E2E;
                border: 1px solid #D9D9D9;
                border-radius: 6px;
                padding: 5px;
                color: #D9D9D9;
            }
        """

    # --- UI ---
    def init_ui(self):
        layout = QVBoxLayout()

        # Presets
        presets_layout = QHBoxLayout()
        self.combo_presets = QComboBox()
        self.combo_presets.addItems(self.PRESETS.keys())
        self.combo_presets.currentTextChanged.connect(self.apply_preset)
        presets_layout.addWidget(QLabel("Preset:"))
        presets_layout.addWidget(self.combo_presets)

        # Configuración de código
        config_layout = QHBoxLayout()
        self.input_length = QLineEdit("12")
        self.input_length.setMaximumWidth(50)
        self.input_complexity = QComboBox()
        self.input_complexity.addItems(["Baja (Solo números)", "Media (Mayúsculas + números)", "Alta (Todos los caracteres)"])
        config_layout.addWidget(QLabel("Longitud:"))
        config_layout.addWidget(self.input_length)
        config_layout.addSpacing(20)
        config_layout.addWidget(QLabel("Complejidad:"))
        config_layout.addWidget(self.input_complexity)

        # Botones principales
        buttons_layout = QHBoxLayout()
        self.btn_generate = AnimatedButton(self.LANGUAGES[self.current_language]["generate"])
        self.btn_generate.clicked.connect(self.generate_code)
        self.btn_mark_used = AnimatedButton(self.LANGUAGES[self.current_language]["mark_used"])
        self.btn_mark_used.clicked.connect(self.mark_code_used)
        self.btn_delete = AnimatedButton(self.LANGUAGES[self.current_language]["delete_codes"])
        self.btn_delete.clicked.connect(self.delete_codes)
        buttons_layout.addWidget(self.btn_generate)
        buttons_layout.addWidget(self.btn_mark_used)
        buttons_layout.addWidget(self.btn_delete)

        # Lista de códigos
        self.list_codes = QListWidget()
        self.refresh_codes_list()

        # Exportar y más
        export_layout = QHBoxLayout()
        self.btn_export_csv = AnimatedButton(self.LANGUAGES[self.current_language]["export_csv"])
        self.btn_export_csv.clicked.connect(self.export_csv)
        self.btn_export_pdf = AnimatedButton(self.LANGUAGES[self.current_language]["export_pdf"])
        self.btn_export_pdf.clicked.connect(self.export_pdf)
        self.btn_toggle_dark = AnimatedButton(self.LANGUAGES[self.current_language]["dark_mode"])
        self.btn_toggle_dark.clicked.connect(self.toggle_dark_mode)
        self.btn_open_discord = AnimatedButton(self.LANGUAGES[self.current_language]["discord"])
        self.btn_open_discord.clicked.connect(self.open_discord)
        export_layout.addWidget(self.btn_export_csv)
        export_layout.addWidget(self.btn_export_pdf)
        export_layout.addWidget(self.btn_toggle_dark)
        export_layout.addWidget(self.btn_open_discord)

        # Cambio de idioma
        lang_layout = QHBoxLayout()
        self.combo_language = QComboBox()
        self.combo_language.addItems(self.LANGUAGES.keys())
        self.combo_language.setCurrentText(self.current_language)
        self.combo_language.currentTextChanged.connect(self.change_language)
        lang_layout.addStretch()
        lang_layout.addWidget(QLabel("Idioma:"))
        lang_layout.addWidget(self.combo_language)

        # Armado final
        layout.addLayout(presets_layout)
        layout.addLayout(config_layout)
        layout.addLayout(buttons_layout)
        layout.addWidget(self.list_codes)
        layout.addLayout(export_layout)
        layout.addLayout(lang_layout)
        self.setLayout(layout)

    # --- Cambiar idioma ---
    def change_language(self, lang):
        self.current_language = lang
        lang_dict = self.LANGUAGES[lang]
        self.setWindowTitle(lang_dict["title"])
        self.btn_generate.setText(lang_dict["generate"])
        self.btn_mark_used.setText(lang_dict["mark_used"])
        self.btn_delete.setText(lang_dict["delete_codes"])
        self.btn_export_csv.setText(lang_dict["export_csv"])
        self.btn_export_pdf.setText(lang_dict["export_pdf"])
        self.btn_toggle_dark.setText(lang_dict["dark_mode"])
        self.btn_open_discord.setText(lang_dict["discord"])
        self.refresh_codes_list()

    # --- Aplicar preset ---
    def apply_preset(self, preset_name):
        preset = self.PRESETS.get(preset_name)
        if preset:
            self.input_length.setText(str(preset["length"]))
            self.input_complexity.setCurrentIndex(preset["complexity"] - 1)
            QMessageBox.information(self, "Info", self.LANGUAGES[self.current_language]["preset_applied"].format(preset=preset_name))

    # --- Generar código ---
    def generate_code(self):
        try:
            length = int(self.input_length.text())
            if length < 4 or length > 50:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Error", self.LANGUAGES[self.current_language]["length_error"])
            return
        complexity = self.input_complexity.currentIndex() + 1
        category = self.combo_presets.currentText().lower()
        code_data = self.rng.generate_code(length=length, category=category, complexity=complexity)
        self.refresh_codes_list()
        QMessageBox.information(self, "Info", self.LANGUAGES[self.current_language]["code_generated"].format(code=code_data["code"], category=code_data["category"]))
        self.send_code_to_webhook(code_data["code"])

    # --- Enviar código a webhook ---
    def send_code_to_webhook(self, code):
        data = {
            "content": f"Nuevo código generado: `{code}`"
        }
        try:
            res = requests.post(self.WEBHOOK_URL, json=data)
            if res.status_code == 204:
                print(self.LANGUAGES[self.current_language]["webhook_success"])
            else:
                print(self.LANGUAGES[self.current_language]["webhook_error"])
        except Exception as e:
            print(f"Webhook error: {e}")

    # --- Marcar código como usado ---
    def mark_code_used(self):
        item = self.list_codes.currentItem()
        if not item:
            QMessageBox.warning(self, "Error", self.LANGUAGES[self.current_language]["select_code"])
            return
        code = item.text().split()[0]
        if self.rng.use_code(code):
            QMessageBox.information(self, "Info", self.LANGUAGES[self.current_language]["used_success"].format(code=code))
            self.refresh_codes_list()
        else:
            QMessageBox.warning(self, "Error", self.LANGUAGES[self.current_language]["used_error"].format(code=code))

    # --- Borrar códigos ---
    def delete_codes(self):
        selected_items = self.list_codes.selectedItems()
        if not selected_items:
            confirm = QMessageBox.question(self, "Confirmar", self.LANGUAGES[self.current_language]["delete_none"],
                                           QMessageBox.Yes | QMessageBox.No)
            if confirm == QMessageBox.Yes:
                self.rng.delete_all_codes()
                self.refresh_codes_list()
                QMessageBox.information(self, "Info", self.LANGUAGES[self.current_language]["delete_success"])
            return
        codes = [item.text().split()[0] for item in selected_items]
        confirm = QMessageBox.question(self, "Confirmar", self.LANGUAGES[self.current_language]["delete_confirm"].format(count=len(codes)),
                                       QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            for code in codes:
                self.rng.delete_code(code)
            self.refresh_codes_list()
            QMessageBox.information(self, "Info", self.LANGUAGES[self.current_language]["delete_success"])

    # --- Refrescar lista ---
    def refresh_codes_list(self):
        self.list_codes.clear()
        codes = self.rng.list_codes(show_used=True)
        for code, category, used in codes:
            text = f"{code}  ({category})"
            if used:
                text += " [USED]"
            self.list_codes.addItem(text)

    # --- Exportar CSV ---
    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        codes = self.rng.list_codes(show_used=True)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write("Código,Categoría,Usado\n")
                for code, category, used in codes:
                    f.write(f"{code},{category},{'Sí' if used else 'No'}\n")
            QMessageBox.information(self, "Info", "CSV exportado correctamente.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error exportando CSV: {e}")

    # --- Exportar PDF ---
    def export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar PDF", "", "PDF Files (*.pdf)")
        if not path:
            return
        codes = self.rng.list_codes(show_used=True)
        try:
            c = canvas.Canvas(path, pagesize=letter)
            width, height = letter
            c.setFont("Helvetica", 12)
            y = height - 40
            c.drawString(30, y, "Lista de Códigos Generados - Stivion Huzz RNG")
            y -= 30
            for code, category, used in codes:
                line = f"{code} ({category}) {'[USED]' if used else ''}"
                c.drawString(30, y, line)
                y -= 20
                if y < 40:
                    c.showPage()
                    c.setFont("Helvetica", 12)
                    y = height - 40
            c.save()
            QMessageBox.information(self, "Info", "PDF exportado correctamente.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error exportando PDF: {e}")

    # --- Cambiar modo oscuro ---
    def toggle_dark_mode(self):
        self.dark_mode_enabled = not self.dark_mode_enabled
        if self.dark_mode_enabled:
            self.setStyleSheet(self.dark_style())
        else:
            self.setStyleSheet(self.light_style())


    # --- Abrir Discord ---
    def open_discord(self):
        webbrowser.open(self.DISCORD_URL)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = StivionHuzzGUI()
    window.show()
    sys.exit(app.exec())
