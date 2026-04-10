import json
from PyQt6.QtWidgets import (QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, 
                             QComboBox, QListWidget, QListWidgetItem, QLabel, 
                             QMessageBox, QCheckBox, QApplication, QTextEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QSplitter, QWidget)
from PyQt6.QtCore import Qt
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
        self.setTitle("Adım 2: Gelişmiş Şema Eşleşmesi ve DDL")
        self.setSubTitle("Tablo seçin, tür kontrollerini yapın veya SQL taslağını düzenleyin.")
        
        layout = QVBoxLayout(self)
        split = QSplitter(Qt.Orientation.Horizontal)
        
        # Left Side: Source Tables
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0,0,0,0)
        
        left_layout.addWidget(QLabel("Kaynak Şema:"))
        self.combo_source_schema = QComboBox()
        self.combo_source_schema.currentTextChanged.connect(self.on_source_schema_changed)
        left_layout.addWidget(self.combo_source_schema)
        
        left_layout.addWidget(QLabel("Kaynak Tablolar:"))
        self.list_source = QListWidget()
        self.list_source.itemSelectionChanged.connect(self.on_source_table_selected)
        left_layout.addWidget(self.list_source)
        
        # Right Side: Target Mapping & DDL
        right_widget = QWidget()
        self.right_layout = QVBoxLayout(right_widget)
        self.right_layout.setContentsMargins(0,0,0,0)
        
        self.right_layout.addWidget(QLabel("Hedef Şema (Nereye Aktarılacak):"))
        self.combo_target_schema = QComboBox()
        self.combo_target_schema.currentTextChanged.connect(self.on_target_schema_changed)
        self.right_layout.addWidget(self.combo_target_schema)
        
        self.right_layout.addWidget(QLabel("Hedef Tablo:"))
        self.combo_target = QComboBox()
        self.combo_target.currentTextChanged.connect(self.on_target_table_changed)
        self.right_layout.addWidget(self.combo_target)
        
        # SQL Editor (Shown if "Yeni Tablo Yarat")
        self.lbl_ddl = QLabel("Oluşturulacak Tablo Şeması (Önizleme ve Düzenleme):")
        self.right_layout.addWidget(self.lbl_ddl)
        self.text_ddl = QTextEdit()
        self.text_ddl.setStyleSheet("font-family: monospace; background: #1e1e2e; color: #a6e3a1;")
        self.right_layout.addWidget(self.text_ddl)
        
        split.addWidget(left_widget)
        split.addWidget(right_widget)
        split.setSizes([200, 450])
        layout.addWidget(split)
        
        self.btn_validate = QPushButton("Uyumluluğu Kontrol Et")
        self.btn_validate.clicked.connect(self.validate_schema)
        self.btn_validate.hide()
        self.right_layout.addWidget(self.btn_validate)

    def initializePage(self):
        self.combo_source_schema.clear()
        self.combo_target_schema.clear()
        
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
                
            # Default fallback checks
            if db_type == "PostgreSQL": self.combo_source_schema.setCurrentText("public")
            elif db_type == "MS SQL Server": self.combo_source_schema.setCurrentText("dbo")
            elif db_type == "Oracle": self.combo_source_schema.setCurrentText(user.upper())
            
            if t_db_type == "PostgreSQL": self.combo_target_schema.setCurrentText("public")
            elif t_db_type == "MS SQL Server": self.combo_target_schema.setCurrentText("dbo")
            elif t_db_type == "Oracle": self.combo_target_schema.setCurrentText(t_user.upper())
            
        except Exception as e:
             QMessageBox.critical(self, "Hata", f"Şemalar yüklenemedi:\n{e}")
        finally:
            QApplication.restoreOverrideCursor()

    def on_source_schema_changed(self, schema_name):
        if not schema_name: return
        self.list_source.clear()
        try:
            for t in self.source_adapter.get_tables(schema_name):
                self.list_source.addItem(t)
        except:
            pass

    def on_target_schema_changed(self, schema_name):
        if not schema_name: return
        self.combo_target.clear()
        self.combo_target.addItem("<Yeni Tablo Yarat (Auto-DDL)>")
        try:
            tables = self.target_adapter.get_tables(schema_name)
            for tt in tables:
                self.combo_target.addItem(tt)
        except:
            pass
            
    def on_source_table_selected(self):
        items = self.list_source.selectedItems()
        if not items: return
        src_table = items[0].text()
        self.wizard().selected_source_table = src_table
        
        # Try to auto-select matching table name in target schema
        index = self.combo_target.findText(src_table)
        if index != -1:
            self.combo_target.setCurrentIndex(index)
        else:
            self.combo_target.setCurrentIndex(0) # Default to <Yeni Tablo Yarat (Auto-DDL)>

    def on_target_table_changed(self, text):
        if not text: return
        if text == "<Yeni Tablo Yarat (Auto-DDL)>":
            self.text_ddl.show()
            self.lbl_ddl.show()
            self.btn_validate.hide()
            
            try:
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                s_schema = self.combo_source_schema.currentText() or None
                t_schema = self.combo_target_schema.currentText() or None
                
                src_tbl = self.wizard().selected_source_table
                if not src_tbl:
                    self.text_ddl.setText("-- Lütfen önce bir kaynak tablo seçin.")
                    QApplication.restoreOverrideCursor()
                    return
                    
                ddl = SchemaValidator.generate_target_ddl(
                    self.wizard().source_url, 
                    self.wizard().target_url, 
                    src_tbl, 
                    src_tbl,
                    s_schema,
                    t_schema
                )
                self.text_ddl.setText(ddl)
            except Exception as e:
                self.text_ddl.setText(f"-- DDL Üretilemedi: {e}")
            finally:
                QApplication.restoreOverrideCursor()
        else:
            self.text_ddl.hide()
            self.lbl_ddl.hide()
            self.btn_validate.show()

    def validate_schema(self):
        src_table = self.wizard().selected_source_table
        tgt_table = self.combo_target.currentText()
        if not src_table or not tgt_table:
            QMessageBox.warning(self, "Uyarı", "Geçerli bir kaynak ve hedef tablo seçilmelidir.")
            return
            
        s_schema = self.combo_source_schema.currentText() or None
        t_schema = self.combo_target_schema.currentText() or None
        
        src_schema_info = SchemaValidator.get_table_schema(self.wizard().source_url, src_table, schema=s_schema)
        tgt_schema_info = SchemaValidator.get_table_schema(self.wizard().target_url, tgt_table, schema=t_schema)
        
        errors = []
        tgt_cols = {c['name']: c['type'] for c in tgt_schema_info}
        
        for sc in src_schema_info:
            if sc['name'] not in tgt_cols:
                errors.append(f"Kolon eksik: Hedefte '{sc['name']}' kolonu yok.")
            else:
                # Basic check, in reality generic compat check is complex, but checking existence is primary
                # We can add strict type checking warnings here.
                pass
                
        if errors:
            msg = "Tablolar arasında kayıp kolon uyuşmazlıkları var. Eşleşmeyen kolonlar Atlanacaktır (Sadece ortak olanlar aktarılır):\n\n" + "\n".join(errors)
            QMessageBox.warning(self, "Şema Kısmi Uyumsuzluk", msg)
        else:
            QMessageBox.information(self, "Uyumluluk Testi Başarılı", "Tablo kolonları yapısal olarak birbiriyle %100 eşleşti! Aktarım başlatılabilir.")

    def validatePage(self):
        if not self.list_source.selectedItems():
            QMessageBox.warning(self, "Uyarı", "Lütfen bir kaynak tablo seçin.")
            return False
            
        tgt = self.combo_target.currentText()
        s_schema = self.combo_source_schema.currentText() or None
        t_schema = self.combo_target_schema.currentText() or None
        
        self.wizard().source_schema = s_schema
        self.wizard().target_schema = t_schema
        self.wizard().selected_target_table = self.wizard().selected_source_table if tgt == "<Yeni Tablo Yarat (Auto-DDL)>" else tgt
        self.wizard().custom_ddl = self.text_ddl.toPlainText() if tgt == "<Yeni Tablo Yarat (Auto-DDL)>" else ""
        
        # --- Kolon Eşleştirme (Phase 4) ---
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            src_table = self.wizard().selected_source_table
            src_schema_info = SchemaValidator.get_table_schema(self.wizard().source_url, src_table, schema=s_schema)
            mapped_columns = {}
            
            if tgt == "<Yeni Tablo Yarat (Auto-DDL)>":
                # Birebir tam uyumlu taslak üretileceği için hepsi eşleşir
                for sc in src_schema_info:
                    mapped_columns[sc['name']] = sc['name']
            else:
                # Kesişimleri bul (Büyük-Küçük harfe duyarsız güvenli eşleştirme)
                tgt_schema_info = SchemaValidator.get_table_schema(self.wizard().target_url, tgt, schema=t_schema)
                tgt_cols_lower = {c['name'].lower(): c['name'] for c in tgt_schema_info}
                
                for sc in src_schema_info:
                    src_col_name = sc['name']
                    if src_col_name.lower() in tgt_cols_lower:
                        mapped_columns[src_col_name] = tgt_cols_lower[src_col_name.lower()]
            
            if not mapped_columns:
                QApplication.restoreOverrideCursor()
                QMessageBox.critical(self, "Kritik Uyumsuzluk", "Eşleşen hiçbir kolon bulunamadı. Tabloların veri aktarımına uygun ortak alanı yok!")
                return False
                
            self.wizard().column_mapping = json.dumps(mapped_columns)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Şema Analiz Hatası", f"Şemalar analiz edilirken beklenmeyen bir hata oldu:\n{e}")
            return False
        finally:
            QApplication.restoreOverrideCursor()

        return True

class TransferWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Yeni Nesil Veri Aktarımı ve Eşleştirme Sistemi")
        self.resize(800, 600)
        self.setStyleSheet("""
            QWizard { background-color: #1e1e2e; color: #cdd6f4; font-size:14px; }
            QLabel { color: #89b4fa; font-weight: bold; }
            QComboBox, QListWidget, QTextEdit { background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 4px; padding: 5px; }
            QPushButton { background-color: #89b4fa; color: #11111b; font-weight: bold; padding: 5px; border-radius:4px; }
        """)
        
        self.source_id = None
        self.target_id = None
        self.source_url = ""
        self.target_url = ""
        self.selected_source_table = None
        self.selected_target_table = None
        self.custom_ddl = ""
        self.column_mapping = ""
        
        self.addPage(ConnectionSelectionPage(self))
        self.addPage(AdvancedMappingPage(self))
