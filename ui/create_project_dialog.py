from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QComboBox, QPushButton, QMessageBox, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
import qtawesome as qta

from core.local_db import get_connection, create_project
from core.crypto import CryptoManager


# ─── Background bağlantı test thread'i ───────────────────────────────────────

class _ConnectionTestThread(QThread):
    result = pyqtSignal(bool, str)  # success, message

    def __init__(self, conn_id: int, parent=None):
        super().__init__(parent)
        self._conn_id = conn_id

    def run(self):
        try:
            from core.db_adapters.postgres import PostgresAdapter
            from core.db_adapters.mssql import MSSQLAdapter
            from core.db_adapters.oracle import OracleAdapter

            db_conn = get_connection()
            c = db_conn.cursor()
            c.execute(
                "SELECT db_type, host, port, database, username, password_encrypted "
                "FROM connections WHERE id = ?",
                (self._conn_id,)
            )
            row = c.fetchone()
            db_conn.close()

            if not row:
                self.result.emit(False, "Bağlantı kaydı bulunamadı.")
                return

            db_type, host, port, database, username, password_encrypted = (
                row["db_type"], row["host"], row["port"],
                row["database"], row["username"], row["password_encrypted"]
            )
            password = CryptoManager.decrypt(password_encrypted) if password_encrypted else ""

            adapters = {
                "PostgreSQL": PostgresAdapter,
                "MS SQL Server": MSSQLAdapter,
                "Oracle": OracleAdapter,
            }
            AdapterClass = adapters.get(db_type)
            if not AdapterClass:
                self.result.emit(False, f"Desteklenmeyen veritabanı tipi: {db_type}")
                return

            adapter = AdapterClass()
            adapter.connect(host, port, database, username, password)
            adapter.disconnect()
            self.result.emit(True, f"{db_type} bağlantısı başarılı.")

        except Exception as e:
            self.result.emit(False, str(e))


# ─── Yardımcı: DB tipi badge rengi ──────────────────────────────────────────

_DB_COLORS = {
    "PostgreSQL":   "#4169e1",
    "MS SQL Server": "#cc3300",
    "Oracle":       "#f08000",
}


# ─── Create / Edit Project Dialog ────────────────────────────────────────────

class CreateProjectDialog(QDialog):
    """
    Yeni proje oluşturma ya da mevcut projeyi düzenleme dialogu.
    `project_id` verilirse "düzenleme" modunda açılır.
    """

    def __init__(self, parent=None, project_id: int | None = None):
        super().__init__(parent)
        self._project_id = project_id
        self._test_threads: list[_ConnectionTestThread] = []

        is_edit = project_id is not None
        self.setWindowTitle("Projeyi Düzenle" if is_edit else "Yeni Aktarım Projesi Oluştur")
        self.setMinimumWidth(580)
        self.setModal(True)

        self._build_ui()
        self._load_connections()

        if is_edit:
            self._populate_for_edit(project_id)

    # ── UI inşası ────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 28, 28, 28)

        # ─ Başlık ─
        title_lbl = QLabel(
            "Projeyi Düzenle" if self._project_id else "Yeni Aktarım Projesi"
        )
        title_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #89b4fa;")
        layout.addWidget(title_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #313244;")
        layout.addWidget(sep)

        # ─ Proje Adı ─
        layout.addWidget(self._make_label("Proje Adı *"))
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("Örn: ERP → Veri Ambarı")
        layout.addWidget(self.edit_name)

        # ─ Açıklama ─
        layout.addWidget(self._make_label("Açıklama / Not"))
        self.edit_desc = QTextEdit()
        self.edit_desc.setPlaceholderText("Bu proje hakkında kısa bir açıklama ekleyin (opsiyonel).")
        self.edit_desc.setFixedHeight(72)
        layout.addWidget(self.edit_desc)

        # ─ Bağlantı Seçimleri ─
        conn_grid = QHBoxLayout()
        conn_grid.setSpacing(16)

        # Kaynak
        src_box = QVBoxLayout()
        src_box.addWidget(self._make_label("Kaynak Veritabanı *"))
        self.combo_source = QComboBox()
        src_box.addWidget(self.combo_source)
        self.btn_test_src = self._make_test_button()
        self.btn_test_src.clicked.connect(lambda: self._test_connection("source"))
        src_box.addWidget(self.btn_test_src)
        self.lbl_src_status = QLabel("")
        self.lbl_src_status.setWordWrap(True)
        src_box.addWidget(self.lbl_src_status)
        conn_grid.addLayout(src_box)

        # Hedef
        tgt_box = QVBoxLayout()
        tgt_box.addWidget(self._make_label("Hedef Veritabanı *"))
        self.combo_target = QComboBox()
        tgt_box.addWidget(self.combo_target)
        self.btn_test_tgt = self._make_test_button()
        self.btn_test_tgt.clicked.connect(lambda: self._test_connection("target"))
        tgt_box.addWidget(self.btn_test_tgt)
        self.lbl_tgt_status = QLabel("")
        self.lbl_tgt_status.setWordWrap(True)
        tgt_box.addWidget(self.lbl_tgt_status)
        conn_grid.addLayout(tgt_box)

        layout.addLayout(conn_grid)

        # ─ Butonlar ─
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("İptal")
        self.btn_cancel.setStyleSheet(
            "background-color: #313244; color: #cdd6f4; padding: 8px 20px; border-radius: 6px; font-weight: bold;"
        )
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_save = QPushButton(
            "Kaydet" if self._project_id else "Oluştur"
        )
        self.btn_save.setStyleSheet(
            "background-color: #89b4fa; color: #11111b; padding: 8px 24px; border-radius: 6px; font-weight: bold;"
        )
        self.btn_save.clicked.connect(self._on_save)
        self.btn_save.setDefault(True)

        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_save)
        layout.addLayout(btn_row)

    # ── Yardımcılar ──────────────────────────────────────────────────────────

    @staticmethod
    def _make_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #a6adc8; font-size: 11px; font-weight: 600; margin-top: 2px;")
        return lbl

    @staticmethod
    def _make_test_button() -> QPushButton:
        btn = QPushButton("  Bağlantıyı Test Et")
        btn.setIcon(qta.icon("fa5s.plug", color="#a6e3a1"))
        btn.setStyleSheet(
            "background-color: #1e1e2e; color: #a6adc8; padding: 5px 10px; "
            "border: 1px solid #45475a; border-radius: 5px; font-size: 11px;"
        )
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return btn

    def _load_connections(self):
        """Mevcut bağlantıları her iki combo'ya yükler."""
        db_conn = get_connection()
        c = db_conn.cursor()
        c.execute("SELECT id, name, db_type FROM connections ORDER BY name")
        rows = c.fetchall()
        db_conn.close()

        self.combo_source.clear()
        self.combo_target.clear()
        for row in rows:
            display = f"{row['name']}  [{row['db_type']}]"
            self.combo_source.addItem(display, row["id"])
            self.combo_target.addItem(display, row["id"])

    def _populate_for_edit(self, project_id: int):
        """Düzenleme modunda mevcut değerleri forma yükler."""
        db_conn = get_connection()
        c = db_conn.cursor()
        c.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = c.fetchone()
        db_conn.close()
        if not row:
            return
        self.edit_name.setText(row["name"])
        self.edit_desc.setPlainText(row["description"] or "")

        # Source combo
        for i in range(self.combo_source.count()):
            if self.combo_source.itemData(i) == row["source_conn_id"]:
                self.combo_source.setCurrentIndex(i)
                break
        # Target combo
        for i in range(self.combo_target.count()):
            if self.combo_target.itemData(i) == row["target_conn_id"]:
                self.combo_target.setCurrentIndex(i)
                break

    # ── Bağlantı Test ────────────────────────────────────────────────────────

    def _test_connection(self, which: str):
        combo = self.combo_source if which == "source" else self.combo_target
        btn = self.btn_test_src if which == "source" else self.btn_test_tgt
        lbl = self.lbl_src_status if which == "source" else self.lbl_tgt_status

        conn_id = combo.currentData()
        if not conn_id:
            lbl.setText("Bağlantı seçilmedi.")
            lbl.setStyleSheet("color: #f9e2af; font-size: 11px;")
            return

        btn.setEnabled(False)
        lbl.setText("Test ediliyor…")
        lbl.setStyleSheet("color: #cdd6f4; font-size: 11px;")

        thread = _ConnectionTestThread(conn_id, self)
        thread.result.connect(
            lambda ok, msg, b=btn, l=lbl: self._on_test_result(ok, msg, b, l)
        )
        self._test_threads.append(thread)
        thread.start()

    def _on_test_result(self, success: bool, message: str, btn: QPushButton, lbl: QLabel):
        btn.setEnabled(True)
        if success:
            lbl.setText(f"✓ {message}")
            lbl.setStyleSheet("color: #a6e3a1; font-size: 11px;")
        else:
            lbl.setText(f"✗ {message}")
            lbl.setStyleSheet("color: #f38ba8; font-size: 11px;")

    # ── Kaydet ───────────────────────────────────────────────────────────────

    def _on_save(self):
        name = self.edit_name.text().strip()
        desc = self.edit_desc.toPlainText().strip()
        src_id = self.combo_source.currentData()
        tgt_id = self.combo_target.currentData()

        # Validasyonlar
        if not name:
            QMessageBox.warning(self, "Hata", "Proje adı boş bırakılamaz.")
            return
        if not src_id or not tgt_id:
            QMessageBox.warning(self, "Hata", "Kaynak ve hedef bağlantı seçilmelidir.")
            return
        if src_id == tgt_id:
            QMessageBox.warning(self, "Hata", "Kaynak ve hedef bağlantı aynı olamaz.")
            return

        try:
            if self._project_id:
                from core.local_db import update_project
                update_project(self._project_id, name, desc, src_id, tgt_id)
                self.saved_project_id = self._project_id
            else:
                self.saved_project_id = create_project(name, desc, src_id, tgt_id)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Proje kaydedilemedi:\n{e}")
