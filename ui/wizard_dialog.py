import json
from PyQt6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout,
    QComboBox, QListWidget, QListWidgetItem, QLabel,
    QMessageBox, QApplication, QTextEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QWidget, QLineEdit, QAbstractItemView
)
from PyQt6.QtCore import Qt
import qtawesome as qta

from core.local_db import get_connection
from core.crypto import CryptoManager
from core.db_adapters.postgres import PostgresAdapter
from core.db_adapters.mssql import MSSQLAdapter
from core.db_adapters.oracle import OracleAdapter
from core.schema_validator import SchemaValidator


def get_adapter_instance(db_type: str):
    if db_type == "PostgreSQL":    return PostgresAdapter()
    if db_type == "MS SQL Server": return MSSQLAdapter()
    if db_type == "Oracle":        return OracleAdapter()
    return None


def get_creds(conn_id: int):
    """Bağlantı bilgilerini ve hazır adapter'ı döner."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT db_type, host, port, database, username, password_encrypted "
        "FROM connections WHERE id = ?",
        (conn_id,)
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    pass_clr = CryptoManager.decrypt(row["password_encrypted"]) if row["password_encrypted"] else ""
    adp = get_adapter_instance(row["db_type"])
    return adp, row["db_type"], row["host"], row["port"], row["database"], row["username"], pass_clr


# ─────────────────────────────────────────────────────────────────────────────
#  Adım 1: Tablo Eşleşme Sayfası  (ConnectionSelectionPage KALDIRILDI)
# ─────────────────────────────────────────────────────────────────────────────

class AdvancedMappingPage(QWizardPage):
    """
    Kaynak ve hedef tablo eşleştirme adımı.
    Bağlantı bilgisi artık proje düzeyinden TransferWizard'a
    source_conn_id / target_conn_id olarak iletilir.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Tablo Eşleştirme — Bulk Mapping")
        self.setSubTitle(
            "Tabloları arayın, seçin ve hızlıca hedef tablolarla ya da Auto-DDL ile eşleştirin."
        )

        self.source_adapter = None
        self.target_adapter = None
        self.source_db_type = ""
        self.target_db_type = ""
        self._all_source_tables: list[str] = []
        self._all_target_tables: list[str] = []
        self._target_tables_set: set[str] = set()

        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        top_split = QSplitter(Qt.Orientation.Horizontal)

        # ── Sol Panel (Kaynak) ────────────────────────────────────────────────
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("Kaynak Şema:"))
        self.combo_source_schema = QComboBox()
        self.combo_source_schema.currentTextChanged.connect(self._on_source_schema_changed)
        left_layout.addWidget(self.combo_source_schema)

        src_search_row = QHBoxLayout()
        self.search_source = QLineEdit()
        self.search_source.setPlaceholderText("Kaynak tablo ara…")
        self.search_source.textChanged.connect(self._filter_source_tables)

        self.btn_src_sort = QPushButton()
        self.btn_src_sort.setIcon(qta.icon("fa5s.sort-alpha-down", color="#cdd6f4"))
        self.btn_src_sort.setToolTip("Artan/Azalan Sırala")
        self.btn_src_sort.clicked.connect(self._toggle_source_sort)
        self.src_sort_asc = True

        src_search_row.addWidget(self.search_source)
        src_search_row.addWidget(self.btn_src_sort)
        left_layout.addLayout(src_search_row)

        self.list_source = QListWidget()
        self.list_source.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        left_layout.addWidget(self.list_source)

        # ── Sağ Panel (Hedef) ─────────────────────────────────────────────────
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        right_layout.addWidget(QLabel("Hedef Şema:"))
        self.combo_target_schema = QComboBox()
        self.combo_target_schema.currentTextChanged.connect(self._on_target_schema_changed)
        right_layout.addWidget(self.combo_target_schema)

        tgt_search_row = QHBoxLayout()
        self.search_target = QLineEdit()
        self.search_target.setPlaceholderText("Hedef tablo ara…")
        self.search_target.textChanged.connect(self._filter_target_tables)

        self.btn_tgt_sort = QPushButton()
        self.btn_tgt_sort.setIcon(qta.icon("fa5s.sort-alpha-down", color="#cdd6f4"))
        self.btn_tgt_sort.setToolTip("Artan/Azalan Sırala")
        self.btn_tgt_sort.clicked.connect(self._toggle_target_sort)
        self.tgt_sort_asc = True

        tgt_search_row.addWidget(self.search_target)
        tgt_search_row.addWidget(self.btn_tgt_sort)
        right_layout.addLayout(tgt_search_row)

        self.list_target = QListWidget()
        self.list_target.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        right_layout.addWidget(self.list_target)

        top_split.addWidget(left_widget)
        top_split.addWidget(right_widget)
        main_layout.addWidget(top_split, stretch=1)

        # ── Eşleştirme Butonları ──────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        self.btn_auto_map = QPushButton("İsimden Eşle (Name Match)")
        self.btn_auto_map.clicked.connect(self._auto_map_by_name)
        self.btn_auto_ddl = QPushButton("Hedefte Yoksa Auto-DDL ile Eşle")
        self.btn_auto_ddl.clicked.connect(self._auto_map_ddl)
        self.btn_clear = QPushButton("Eşleşmeleri Temizle")
        self.btn_clear.clicked.connect(self._clear_mappings)
        btn_layout.addWidget(self.btn_auto_map)
        btn_layout.addWidget(self.btn_auto_ddl)
        btn_layout.addWidget(self.btn_clear)
        main_layout.addLayout(btn_layout)

        # ── Eşleşme Tablosu ───────────────────────────────────────────────────
        main_layout.addWidget(QLabel("Onaylanan Tablo Eşleşmeleri:"))
        self.table_mappings = QTableWidget()
        self.table_mappings.setColumnCount(3)
        self.table_mappings.setHorizontalHeaderLabels(
            ["Kaynak Tablo", "Hedef Tablo", "İşlem / Durum"]
        )
        self.table_mappings.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_mappings.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_mappings.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        main_layout.addWidget(self.table_mappings, stretch=1)

    # ── Sayfa başlatma ────────────────────────────────────────────────────────

    def initializePage(self):
        self.combo_source_schema.clear()
        self.combo_target_schema.clear()
        self.table_mappings.setRowCount(0)
        self.wizard().transfer_mappings = []

        src_id = self.wizard().source_conn_id
        tgt_id = self.wizard().target_conn_id

        s_creds = get_creds(src_id)
        t_creds = get_creds(tgt_id)

        if not s_creds or not t_creds:
            QMessageBox.critical(self, "Hata", "Proje bağlantı bilgileri alınamadı.")
            return

        adp, db_type, host, port, db, user, pwd = s_creds
        tadp, t_db_type, t_host, t_port, t_db, t_user, t_pwd = t_creds

        self.source_adapter = adp
        self.source_db_type = db_type
        self.target_adapter = tadp
        self.target_db_type = t_db_type

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.wizard().source_url = adp.get_sqlalchemy_url(host, port, db, user, pwd)
            self.wizard().target_url = tadp.get_sqlalchemy_url(t_host, t_port, t_db, t_user, t_pwd)

            adp.connect(host, port, db, user, pwd)
            for sch in adp.get_schemas():
                self.combo_source_schema.addItem(sch)

            tadp.connect(t_host, t_port, t_db, t_user, t_pwd)
            for tsch in tadp.get_schemas():
                self.combo_target_schema.addItem(tsch)

            # Varsayılan şema seçimi
            _defaults = {"PostgreSQL": "public", "MS SQL Server": "dbo"}
            self.combo_source_schema.setCurrentText(
                _defaults.get(db_type, user.upper())
            )
            self.combo_target_schema.setCurrentText(
                _defaults.get(t_db_type, t_user.upper())
            )

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Şemalar yüklenemedi:\n{e}")
        finally:
            QApplication.restoreOverrideCursor()

    # ── Şema / Tablo Değişimleri ──────────────────────────────────────────────

    def _on_source_schema_changed(self, schema_name: str):
        if not schema_name:
            return
        self.list_source.clear()
        self._all_source_tables = []
        try:
            tables = self.source_adapter.get_tables(schema_name)
            self._all_source_tables = tables
            for t in tables:
                self.list_source.addItem(t)
        except Exception as e:
            print("Source schema error:", e)

    def _on_target_schema_changed(self, schema_name: str):
        if not schema_name:
            return
        self.list_target.clear()
        self._all_target_tables = []
        self._target_tables_set.clear()
        try:
            tables = self.target_adapter.get_tables(schema_name)
            self._all_target_tables = tables
            for tt in tables:
                self.list_target.addItem(tt)
                self._target_tables_set.add(tt.lower())
            # Listeyi sıralı aç
            self.src_sort_asc = False
            self.tgt_sort_asc = False
            self._toggle_source_sort()
            self._toggle_target_sort()
        except Exception as e:
            print("Target schema error:", e)

    def _filter_source_tables(self, text: str):
        self.list_source.clear()
        txt = text.lower()
        for t in self._all_source_tables:
            if txt in t.lower():
                self.list_source.addItem(t)
        order = Qt.SortOrder.AscendingOrder if self.src_sort_asc else Qt.SortOrder.DescendingOrder
        self.list_source.sortItems(order)

    def _filter_target_tables(self, text: str):
        self.list_target.clear()
        txt = text.lower()
        for t in self._all_target_tables:
            if txt in t.lower():
                self.list_target.addItem(t)
        order = Qt.SortOrder.AscendingOrder if self.tgt_sort_asc else Qt.SortOrder.DescendingOrder
        self.list_target.sortItems(order)

    def _toggle_source_sort(self):
        if self.list_source.count() == 0:
            return
        self.src_sort_asc = not self.src_sort_asc
        icon_name = "fa5s.sort-alpha-down" if self.src_sort_asc else "fa5s.sort-alpha-up"
        self.btn_src_sort.setIcon(qta.icon(icon_name, color="#cdd6f4"))
        order = Qt.SortOrder.AscendingOrder if self.src_sort_asc else Qt.SortOrder.DescendingOrder
        self.list_source.sortItems(order)

    def _toggle_target_sort(self):
        if self.list_target.count() == 0:
            return
        self.tgt_sort_asc = not self.tgt_sort_asc
        icon_name = "fa5s.sort-alpha-down" if self.tgt_sort_asc else "fa5s.sort-alpha-up"
        self.btn_tgt_sort.setIcon(qta.icon(icon_name, color="#cdd6f4"))
        order = Qt.SortOrder.AscendingOrder if self.tgt_sort_asc else Qt.SortOrder.DescendingOrder
        self.list_target.sortItems(order)

    # ── Eşleştirme İşlemleri ─────────────────────────────────────────────────

    def _add_mapping_to_table(self, src_table: str, tgt_table: str, status: str):
        """Aynı kaynak tablo zaten ekli ise atla."""
        for i in range(self.table_mappings.rowCount()):
            if self.table_mappings.item(i, 0).text() == src_table:
                return
        row = self.table_mappings.rowCount()
        self.table_mappings.insertRow(row)
        self.table_mappings.setItem(row, 0, QTableWidgetItem(src_table))
        self.table_mappings.setItem(row, 1, QTableWidgetItem(tgt_table))
        self.table_mappings.setItem(row, 2, QTableWidgetItem(status))

    def _auto_map_by_name(self):
        items = self.list_source.selectedItems()
        if not items:
            QMessageBox.warning(self, "Uyarı", "Lütfen sol panelden kaynak tablo(lar) seçin.")
            return
        for item in items:
            src_tbl = item.text()
            if src_tbl.lower() in self._target_tables_set:
                tgt_exact = next(
                    (t for t in self._all_target_tables if t.lower() == src_tbl.lower()),
                    src_tbl
                )
                self._add_mapping_to_table(src_tbl, tgt_exact, "İsimden Eşleşti (Varolan Tablo)")

    def _auto_map_ddl(self):
        items = self.list_source.selectedItems()
        if not items:
            QMessageBox.warning(self, "Uyarı", "Lütfen sol panelden kaynak tablo(lar) seçin.")
            return
        for item in items:
            src_tbl = item.text()
            if src_tbl.lower() in self._target_tables_set:
                tgt_exact = next(
                    (t for t in self._all_target_tables if t.lower() == src_tbl.lower()),
                    src_tbl
                )
                self._add_mapping_to_table(src_tbl, tgt_exact, "İsimden Eşleşti (Varolan Tablo)")
            else:
                self._add_mapping_to_table(
                    src_tbl, "<Yeni Tablo Yarat (Auto-DDL)>", "Auto-DDL ile Yaratılacak"
                )

    def _clear_mappings(self):
        self.table_mappings.setRowCount(0)

    # ── Doğrulama ─────────────────────────────────────────────────────────────

    def validatePage(self) -> bool:
        if self.table_mappings.rowCount() == 0:
            QMessageBox.warning(self, "Uyarı", "Hiçbir tablo eşleşmesi yok. Lütfen eşleştirme yapın.")
            return False

        mappings = []
        s_schema = self.combo_source_schema.currentText() or None
        t_schema = self.combo_target_schema.currentText() or None

        self.wizard().source_schema = s_schema
        self.wizard().target_schema = t_schema

        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

            for i in range(self.table_mappings.rowCount()):
                src_tbl = self.table_mappings.item(i, 0).text()
                tgt_tbl = self.table_mappings.item(i, 1).text()

                src_schema_info = SchemaValidator.get_table_schema(
                    self.wizard().source_url, src_tbl, schema=s_schema
                )
                mapped_columns: dict[str, str] = {}
                custom_ddl_query = ""

                if tgt_tbl == "<Yeni Tablo Yarat (Auto-DDL)>":
                    actual_tgt_tbl = src_tbl
                    for sc in src_schema_info:
                        mapped_columns[sc["name"]] = sc["name"]
                    custom_ddl_query = SchemaValidator.generate_target_ddl(
                        self.wizard().source_url,
                        self.wizard().target_url,
                        src_tbl,
                        actual_tgt_tbl,
                        s_schema,
                        t_schema,
                    )
                else:
                    actual_tgt_tbl = tgt_tbl
                    tgt_schema_info = SchemaValidator.get_table_schema(
                        self.wizard().target_url, actual_tgt_tbl, schema=t_schema
                    )
                    tgt_cols_lower = {c["name"].lower(): c["name"] for c in tgt_schema_info}
                    for sc in src_schema_info:
                        src_col = sc["name"]
                        if src_col.lower() in tgt_cols_lower:
                            mapped_columns[src_col] = tgt_cols_lower[src_col.lower()]

                if not mapped_columns:
                    print(f"[{src_tbl}] ↔ [{actual_tgt_tbl}] için kesişen kolon yok. Atlandı.")
                    continue

                mappings.append({
                    "src_table":      src_tbl,
                    "tgt_table":      actual_tgt_tbl,
                    "custom_ddl":     custom_ddl_query,
                    "column_mapping": json.dumps(mapped_columns),
                })

            if not mappings:
                QApplication.restoreOverrideCursor()
                QMessageBox.critical(self, "Hata", "Geçerli bir eşleşme kurulamadı (kesişen kolon yok).")
                return False

            self.wizard().transfer_mappings = mappings

        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Hata", f"Analiz sırasında hata:\n{e}")
            return False
        finally:
            QApplication.restoreOverrideCursor()

        return True


# ─────────────────────────────────────────────────────────────────────────────
#  TransferWizard
# ─────────────────────────────────────────────────────────────────────────────

class TransferWizard(QWizard):
    """
    Proje içi yeni aktarım ekleme sihirbazı.

    Args:
        source_conn_id: Projenin kaynak bağlantı ID'si.
        target_conn_id: Projenin hedef bağlantı ID'si.
    """

    def __init__(self, source_conn_id: int, target_conn_id: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Yeni Aktarım — Tablo Eşleştirme")
        self.resize(960, 740)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )

        self.setStyleSheet("""
            QWizard       { background-color: #1e1e2e; color: #cdd6f4; font-size:14px; }
            QLabel        { color: #89b4fa; font-weight: bold; }
            QComboBox, QListWidget, QLineEdit, QTextEdit {
                background-color: #313244; color: #cdd6f4;
                border: 1px solid #45475a; border-radius: 4px; padding: 5px;
            }
            QPushButton   { background-color: #89b4fa; color: #11111b; font-weight: bold; padding: 6px; border-radius:4px; }
            QPushButton:hover { background-color: #b4befe; }
            QTableWidget  { background-color: #313244; color: #cdd6f4; gridline-color: #45475a; font-size: 13px; }
            QHeaderView::section { background-color: #181825; color: #cdd6f4; font-weight: bold; padding: 6px; }
        """)

        # Proje düzeyinde sabit bağlantı ID'leri
        self.source_conn_id: int = source_conn_id
        self.target_conn_id: int = target_conn_id

        # Wizard boyunca taşınan veriler
        self.source_url: str = ""
        self.target_url: str = ""
        self.source_schema: str | None = None
        self.target_schema: str | None = None
        self.transfer_mappings: list[dict] = []

        self.addPage(AdvancedMappingPage(self))
