import json
from PyQt6.QtWidgets import (QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, 
                             QComboBox, QListWidget, QListWidgetItem, QLabel, 
                             QMessageBox, QCheckBox, QApplication, QTextEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QSplitter, QWidget, QLineEdit, QAbstractItemView)
from PyQt6.QtCore import Qt
import qtawesome as qta
from core.local_db import get_connection
from core.crypto import CryptoManager
from core.db_adapters.postgres import PostgresAdapter
from core.db_adapters.mssql import MSSQLAdapter
from core.db_adapters.oracle import OracleAdapter
from core.schema_validator import SchemaValidator

def get_adapter_instance(db_type):
    if db_type == "PostgreSQL": return PostgresAdapter()
    if db_type == "MS SQL Server": return MSSQLAdapter()
    if db_type == "Oracle": return OracleAdapter()
    return None

def get_creds(conn_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT db_type, host, port, database, username, password_encrypted FROM connections WHERE id = ?", (conn_id,))
    row = c.fetchone()
    conn.close()
    if not row: return None
    pass_clr = CryptoManager.decrypt(row[5]) if row[5] else ""
    adp = get_adapter_instance(row[0])
    return adp, row[0], row[1], row[2], row[3], row[4], pass_clr

class ConnectionSelectionPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Adım 1: Kaynak ve Hedef Seçimi")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Kaynak Veritabanı:"))
        self.source_combo = QComboBox()
        layout.addWidget(self.source_combo)
        layout.addSpacing(15)
        layout.addWidget(QLabel("Hedef Veritabanı:"))
        self.target_combo = QComboBox()
        layout.addWidget(self.target_combo)
        self.registerField("source_conn", self.source_combo)
        self.registerField("target_conn", self.target_combo)
        
    def initializePage(self):
        self.source_combo.clear()
        self.target_combo.clear()
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id, name, db_type FROM connections")
        for row in c.fetchall():
            dt = f"{row[1]} [{row[2]}]"
            self.source_combo.addItem(dt, row[0])
            self.target_combo.addItem(dt, row[0])
        conn.close()

    def validatePage(self):
        src_id = self.source_combo.currentData()
        tgt_id = self.target_combo.currentData()
        if src_id == tgt_id:
            QMessageBox.warning(self, "Hata", "Kaynak ve hedef aynı olamaz.")
            return False
        self.wizard().source_id = src_id
        self.wizard().target_id = tgt_id
        return True

class AdvancedMappingPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Adım 2: Çoklu Şema Eşleşmesi (Bulk Mapping)")
        self.setSubTitle("Tabloları arayın, seçin ve hızlıca hedef tablolarla veya Auto-DDL ile eşleştirin.")
        
        main_layout = QVBoxLayout(self)
        top_split = QSplitter(Qt.Orientation.Horizontal)
        
        # --- Sol Panel (Kaynak) ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0,0,0,0)
        
        left_layout.addWidget(QLabel("Kaynak Şema:"))
        self.combo_source_schema = QComboBox()
        self.combo_source_schema.currentTextChanged.connect(self.on_source_schema_changed)
        left_layout.addWidget(self.combo_source_schema)
        
        src_search_layout = QHBoxLayout()
        self.search_source = QLineEdit()
        self.search_source.setPlaceholderText("Kaynak tablo ara...")
        self.search_source.textChanged.connect(self.filter_source_tables)
        
        self.btn_src_sort = QPushButton()
        self.btn_src_sort.setIcon(qta.icon('fa5s.sort-alpha-down', color='#cdd6f4'))
        self.btn_src_sort.setToolTip("Artan/Azalan Sırala")
        self.btn_src_sort.clicked.connect(self.toggle_source_sort)
        self.src_sort_asc = True
        
        src_search_layout.addWidget(self.search_source)
        src_search_layout.addWidget(self.btn_src_sort)
        left_layout.addLayout(src_search_layout)
        
        self.list_source = QListWidget()
        self.list_source.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        left_layout.addWidget(self.list_source)
        
        # --- Sağ Panel (Hedef) ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0,0,0,0)
        
        right_layout.addWidget(QLabel("Hedef Şema:"))
        self.combo_target_schema = QComboBox()
        self.combo_target_schema.currentTextChanged.connect(self.on_target_schema_changed)
        right_layout.addWidget(self.combo_target_schema)

        tgt_search_layout = QHBoxLayout()
        self.search_target = QLineEdit()
        self.search_target.setPlaceholderText("Hedef tablo ara...")
        self.search_target.textChanged.connect(self.filter_target_tables)
        
        self.btn_tgt_sort = QPushButton()
        self.btn_tgt_sort.setIcon(qta.icon('fa5s.sort-alpha-down', color='#cdd6f4'))
        self.btn_tgt_sort.setToolTip("Artan/Azalan Sırala")
        self.btn_tgt_sort.clicked.connect(self.toggle_target_sort)
        self.tgt_sort_asc = True
        
        tgt_search_layout.addWidget(self.search_target)
        tgt_search_layout.addWidget(self.btn_tgt_sort)
        right_layout.addLayout(tgt_search_layout)
        
        self.list_target = QListWidget()
        self.list_target.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        right_layout.addWidget(self.list_target)
        
        top_split.addWidget(left_widget)
        top_split.addWidget(right_widget)
        
        main_layout.addWidget(top_split, stretch=1)
        
        # --- Ara Panel (Butonlar) ---
        btn_layout = QHBoxLayout()
        self.btn_auto_map = QPushButton("İsimden Eşle (Mapping by Name)")
        self.btn_auto_map.clicked.connect(self.auto_map_by_name)
        self.btn_auto_ddl = QPushButton("Hedefte Yoksa Auto-DDL İle Eşle")
        self.btn_auto_ddl.clicked.connect(self.auto_map_ddl)
        self.btn_clear = QPushButton("Eşleşmeleri Temizle")
        self.btn_clear.clicked.connect(self.clear_mappings)
        
        btn_layout.addWidget(self.btn_auto_map)
        btn_layout.addWidget(self.btn_auto_ddl)
        btn_layout.addWidget(self.btn_clear)
        main_layout.addLayout(btn_layout)
        
        # --- Alt Panel (Mevcut Eşleşmeler) ---
        main_layout.addWidget(QLabel("Onaylanan Tablo Eşleşmeleri:"))
        self.table_mappings = QTableWidget()
        self.table_mappings.setColumnCount(3)
        self.table_mappings.setHorizontalHeaderLabels(["Kaynak Tablo", "Hedef Tablo", "İşlem / Durum"])
        self.table_mappings.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_mappings.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_mappings.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        main_layout.addWidget(self.table_mappings, stretch=1)

        self._all_source_tables = []
        self._all_target_tables = []
        
        # Hedef tablolara hizli bakabilmek icin set mappingi
        self._target_tables_set = set()

    def initializePage(self):
        self.combo_source_schema.clear()
        self.combo_target_schema.clear()
        self.table_mappings.setRowCount(0)
        self.wizard().transfer_mappings = []
        
        s_creds = get_creds(self.wizard().source_id)
        if not s_creds: return
        adp, db_type, host, port, db, user, pwd = s_creds
        
        self.source_adapter = adp
        self.source_db_type = db_type
        
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.wizard().source_url = adp.get_sqlalchemy_url(host, port, db, user, pwd)
        
        t_creds = get_creds(self.wizard().target_id)
        tadp, t_db_type, t_host, t_port, t_db, t_user, t_pwd = t_creds
        
        self.target_adapter = tadp
        self.target_db_type = t_db_type
        self.wizard().target_url = tadp.get_sqlalchemy_url(t_host, t_port, t_db, t_user, t_pwd)
        
        try:
            adp.connect(host, port, db, user, pwd)
            for sch in adp.get_schemas():
                self.combo_source_schema.addItem(sch)

            tadp.connect(t_host, t_port, t_db, t_user, t_pwd)
            for tsch in tadp.get_schemas():
                self.combo_target_schema.addItem(tsch)
                
            if db_type == "PostgreSQL": self.combo_source_schema.setCurrentText("public")
            elif db_type == "MS SQL Server": self.combo_source_schema.setCurrentText("dbo")
            elif db_type == "Oracle": self.combo_source_schema.setCurrentText(user.upper())
            
            if t_db_type == "PostgreSQL": self.combo_target_schema.setCurrentText("public")
            elif t_db_type == "MS SQL Server": self.combo_target_schema.setCurrentText("dbo")
            elif t_db_type == "Oracle": self.combo_target_schema.setCurrentText(t_user.upper())
            
        except Exception as e:
             QMessageBox.critical(self, "Hata", f"Dizinler yüklenemedi:\n{e}")
        finally:
            QApplication.restoreOverrideCursor()

    def on_source_schema_changed(self, schema_name):
        if not schema_name: return
        self.list_source.clear()
        self._all_source_tables = []
        try:
            tables = self.source_adapter.get_tables(schema_name)
            self._all_source_tables = tables
            for t in tables:
                self.list_source.addItem(t)
        except Exception as e:
            print("Sources error:", e)
            
    def filter_source_tables(self, text):
        self.list_source.clear()
        txt = text.lower()
        for t in self._all_source_tables:
            if txt in t.lower():
                self.list_source.addItem(t)
        # Apply sorting logic immediately after filter
        order = Qt.SortOrder.AscendingOrder if self.src_sort_asc else Qt.SortOrder.DescendingOrder
        self.list_source.sortItems(order)

    def on_target_schema_changed(self, schema_name):
        if not schema_name: return
        self.list_target.clear()
        self._all_target_tables = []
        self._target_tables_set.clear()
        try:
            tables = self.target_adapter.get_tables(schema_name)
            self._all_target_tables = tables
            for tt in tables:
                self.list_target.addItem(tt)
                self._target_tables_set.add(tt.lower())
                
            self.src_sort_asc = False
            self.tgt_sort_asc = False
            self.toggle_source_sort()
            self.toggle_target_sort()
        except Exception as e:
             print("Targets error:", e)
             
    def filter_target_tables(self, text):
        self.list_target.clear()
        txt = text.lower()
        for t in self._all_target_tables:
            if txt in t.lower():
                self.list_target.addItem(t)
        # Apply sorting logic immediately after filter
        order = Qt.SortOrder.AscendingOrder if self.tgt_sort_asc else Qt.SortOrder.DescendingOrder
        self.list_target.sortItems(order)

    def toggle_source_sort(self):
        if self.list_source.count() == 0: return
        self.src_sort_asc = not self.src_sort_asc
        icon_name = 'fa5s.sort-alpha-down' if self.src_sort_asc else 'fa5s.sort-alpha-up'
        self.btn_src_sort.setIcon(qta.icon(icon_name, color='#cdd6f4'))
        order = Qt.SortOrder.AscendingOrder if self.src_sort_asc else Qt.SortOrder.DescendingOrder
        self.list_source.sortItems(order)
        
    def toggle_target_sort(self):
        if self.list_target.count() == 0: return
        self.tgt_sort_asc = not self.tgt_sort_asc
        icon_name = 'fa5s.sort-alpha-down' if self.tgt_sort_asc else 'fa5s.sort-alpha-up'
        self.btn_tgt_sort.setIcon(qta.icon(icon_name, color='#cdd6f4'))
        order = Qt.SortOrder.AscendingOrder if self.tgt_sort_asc else Qt.SortOrder.DescendingOrder
        self.list_target.sortItems(order)

    def add_mapping_to_table(self, src_table, tgt_table, status):
        # Eger zaten eklendiyse atla
        for i in range(self.table_mappings.rowCount()):
            if self.table_mappings.item(i, 0).text() == src_table:
                return

        row = self.table_mappings.rowCount()
        self.table_mappings.insertRow(row)
        self.table_mappings.setItem(row, 0, QTableWidgetItem(src_table))
        self.table_mappings.setItem(row, 1, QTableWidgetItem(tgt_table))
        self.table_mappings.setItem(row, 2, QTableWidgetItem(status))

    def auto_map_by_name(self):
        items = self.list_source.selectedItems()
        if not items:
            QMessageBox.warning(self, "Uyarı", "Lütfen sol panelden bir veya birden fazla kaynak tablo seçin.")
            return
            
        for item in items:
            src_tbl = item.text()
            if src_tbl.lower() in self._target_tables_set:
                # Orijinal buyuk/kucuk harfini bul
                tgt_exact = next((t for t in self._all_target_tables if t.lower() == src_tbl.lower()), src_tbl)
                self.add_mapping_to_table(src_tbl, tgt_exact, "İsimden Eşleşti (Varolan Tablo)")

    def auto_map_ddl(self):
        items = self.list_source.selectedItems()
        if not items:
            QMessageBox.warning(self, "Uyarı", "Lütfen sol panelden bir veya birden fazla kaynak tablo seçin.")
            return

        for item in items:
            src_tbl = item.text()
            # Eger hedefte Varsa isimden esle, YOKSA Auto-DDL olarak sec
            if src_tbl.lower() in self._target_tables_set:
                tgt_exact = next((t for t in self._all_target_tables if t.lower() == src_tbl.lower()), src_tbl)
                self.add_mapping_to_table(src_tbl, tgt_exact, "İsimden Eşleşti (Varolan Tablo)")
            else:
                self.add_mapping_to_table(src_tbl, "<Yeni Tablo Yarat (Auto-DDL)>", "Auto-DDL ile Yaratılacak")

    def clear_mappings(self):
        self.table_mappings.setRowCount(0)

    def validatePage(self):
        if self.table_mappings.rowCount() == 0:
            QMessageBox.warning(self, "Uyarı", "Hiçbir tablo eşleşmesi bulunamadı. Lütfen eşleştirme yapın.")
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
                status = self.table_mappings.item(i, 2).text()
                
                src_schema_info = SchemaValidator.get_table_schema(self.wizard().source_url, src_tbl, schema=s_schema)
                mapped_columns = {}
                custom_ddl_query = ""
                
                if tgt_tbl == "<Yeni Tablo Yarat (Auto-DDL)>":
                    # Hepsi eşleşir, ayni tablo ismini aliriz hedefler icin
                    actual_tgt_tbl = src_tbl
                    for sc in src_schema_info:
                        mapped_columns[sc['name']] = sc['name']
                        
                    custom_ddl_query = SchemaValidator.generate_target_ddl(
                        self.wizard().source_url, 
                        self.wizard().target_url, 
                        src_tbl, 
                        actual_tgt_tbl,
                        s_schema,
                        t_schema
                    )
                else:
                    actual_tgt_tbl = tgt_tbl
                    tgt_schema_info = SchemaValidator.get_table_schema(self.wizard().target_url, actual_tgt_tbl, schema=t_schema)
                    tgt_cols_lower = {c['name'].lower(): c['name'] for c in tgt_schema_info}
                    
                    for sc in src_schema_info:
                        src_col_name = sc['name']
                        if src_col_name.lower() in tgt_cols_lower:
                            mapped_columns[src_col_name] = tgt_cols_lower[src_col_name.lower()]
                            
                # Performans acisindan en kotu senaryoda eger ortak alan yoksa atliyoruz
                if not mapped_columns:
                    print(f"[{src_tbl}] ve [{actual_tgt_tbl}] icin eslesen kolon yok. Bu atlanacak.")
                    continue
                    
                mappings.append({
                    "src_table": src_tbl,
                    "tgt_table": actual_tgt_tbl,
                    "custom_ddl": custom_ddl_query,
                    "column_mapping": json.dumps(mapped_columns)
                })
                
            if not mappings:
                QApplication.restoreOverrideCursor()
                QMessageBox.critical(self, "Hata", "Geçerli bir eşleşme kurulamadı (Kesişen kolon yok).")
                return False
                
            self.wizard().transfer_mappings = mappings
            
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Hata", f"Analiz edilirken hata oldu:\n{e}")
            return False
        finally:
            QApplication.restoreOverrideCursor()

        return True

class TransferWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Yeni Nesil Veri Aktarımı ve Çoklu Eşleştirme Sistemi")
        self.resize(900, 700)
        
        # Tam Ekran Büyütme vs için Windows flagleri eklendi
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowMinimizeButtonHint)
        
        self.setStyleSheet("""
            QWizard { background-color: #1e1e2e; color: #cdd6f4; font-size:14px; }
            QLabel { color: #89b4fa; font-weight: bold; }
            QComboBox, QListWidget, QLineEdit, QTextEdit { background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 4px; padding: 5px; }
            QPushButton { background-color: #89b4fa; color: #11111b; font-weight: bold; padding: 6px; border-radius:4px; }
            QPushButton:hover { background-color: #b4befe; }
            QTableWidget { background-color: #313244; color: #cdd6f4; gridline-color: #45475a; font-size: 13px; }
            QHeaderView::section { background-color: #181825; color: #cdd6f4; font-weight: bold; padding: 6px; }
        """)
        
        self.source_id = None
        self.target_id = None
        self.source_url = ""
        self.target_url = ""
        self.source_schema = None
        self.target_schema = None
        
        # Çoklu eşleştirmeler için yeni yapı:
        self.transfer_mappings = [] # list of dicts: [{src, tgt, ddl, cols}]
        
        self.addPage(ConnectionSelectionPage(self))
        self.addPage(AdvancedMappingPage(self))
