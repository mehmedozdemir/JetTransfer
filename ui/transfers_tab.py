from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, 
                             QProgressBar, QDialog, QTextEdit, QSpinBox, QSplitter, QAbstractItemView, QApplication)
from PyQt6.QtCore import Qt, pyqtSlot
import qtawesome as qta

from core.local_db import get_connection
from ui.wizard_dialog import TransferWizard
from core.transfer_engine import TransferEngine
from core.db_adapters.postgres import PostgresAdapter
from core.db_adapters.mssql import MSSQLAdapter
from core.db_adapters.oracle import OracleAdapter
from core.crypto import CryptoManager

def get_adapter(db_type):
    if db_type == "PostgreSQL": return PostgresAdapter()
    if db_type == "MS SQL Server": return MSSQLAdapter()
    if db_type == "Oracle": return OracleAdapter()
    return None

class CustomSqlDialog(QDialog):
    def __init__(self, job_id, current_sql, current_limit, parent=None):
        super().__init__(parent)
        self.job_id = job_id
        self.setWindowTitle(f"Görev ID {job_id} - SQL Filtre & Canlı Önizleme")
        self.resize(800, 600)
        self.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4; font-size: 13px;")
        
        main_layout = QVBoxLayout(self)
        
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # --- Top Pane ---
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0,0,0,0)
        top_layout.addWidget(QLabel("Özel Veri Çekme Sorgusu (Örn: SELECT * FROM tablo WHERE durum='aktif')"))
        
        self.text_sql = QTextEdit()
        self.text_sql.setStyleSheet("background-color: #313244; font-family: monospace;")
        if current_sql:
            self.text_sql.setText(current_sql)
        else:
            self.text_sql.setPlaceholderText("SELECT * FROM tablo_adiniz")
        top_layout.addWidget(self.text_sql)
        
        limit_layout = QHBoxLayout()
        limit_layout.addWidget(QLabel("Maksimum Aktarılacak Satır (0 = Tümü):"))
        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(0, 2000000000)
        self.spin_limit.setValue(current_limit if current_limit else 0)
        self.spin_limit.setStyleSheet("background-color: #313244; padding: 5px;")
        limit_layout.addWidget(self.spin_limit)

        limit_layout.addSpacing(20)
        limit_layout.addWidget(QLabel("Önizleme Satır Sayısı:"))
        self.spin_preview = QSpinBox()
        self.spin_preview.setRange(1, 5000)
        self.spin_preview.setValue(200) # User requested 200 as default
        self.spin_preview.setStyleSheet("background-color: #313244; padding: 5px;")
        limit_layout.addWidget(self.spin_preview)
        
        limit_layout.addStretch()
        top_layout.addLayout(limit_layout)
        
        btn_layout = QHBoxLayout()
        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet("color: #f38ba8;") # red color
        btn_layout.addWidget(self.lbl_error)
        
        btn_layout.addStretch()
        
        self.btn_preview = QPushButton(" Canlı Önizle (Test Et)")
        self.btn_preview.setIcon(qta.icon('fa5s.play', color='#11111b'))
        self.btn_preview.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold; padding: 6px;")
        self.btn_preview.clicked.connect(self.preview_data)
        btn_layout.addWidget(self.btn_preview)
        
        self.btn_save = QPushButton("Kaydet ve Kapat")
        self.btn_save.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold; padding: 6px;")
        self.btn_save.clicked.connect(self.save_and_close)
        btn_layout.addWidget(self.btn_save)
        top_layout.addLayout(btn_layout)
        
        # --- Bottom Pane ---
        bot_widget = QWidget()
        bot_layout = QVBoxLayout(bot_widget)
        bot_layout.setContentsMargins(0,0,0,0)
        
        self.table_preview = QTableWidget()
        self.table_preview.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_preview.setStyleSheet("background-color: #313244; color: #cdd6f4; gridline-color: #45475a;")
        bot_layout.addWidget(self.table_preview)
        
        splitter.addWidget(top_widget)
        splitter.addWidget(bot_widget)
        splitter.setSizes([300, 300])
        main_layout.addWidget(splitter)
        
    def preview_data(self):
        self.lbl_error.setText("Yükleniyor...")
        self.lbl_error.setStyleSheet("color: #cdd6f4;")
        self.table_preview.clear()
        self.table_preview.setRowCount(0)
        self.table_preview.setColumnCount(0)
        QApplication.processEvents()
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.db_type, s.host, s.port, s.database, s.username, s.password_encrypted
            FROM transfer_jobs j
            JOIN connections s ON j.source_conn_id = s.id
            WHERE j.id = ?
        ''', (self.job_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            self.lbl_error.setText("Kaynak bağlantı bilgisi bulunamadı.")
            self.lbl_error.setStyleSheet("color: #f38ba8;")
            return
            
        db_type, host, port, db, user, pass_enc = row
        password = CryptoManager.decrypt(pass_enc)
        adapter = get_adapter(db_type)
        if not adapter:
            self.lbl_error.setText("Sürücü desteklenmiyor.")
            self.lbl_error.setStyleSheet("color: #f38ba8;")
            return
            
        sql = self.text_sql.toPlainText().strip()
        if not sql:
            self.lbl_error.setText("Lütfen test edilecek bir sorgu yazın.")
            self.lbl_error.setStyleSheet("color: #f38ba8;")
            return
            
        try:
            adapter.connect(host, port, db, user, password)
            cur = adapter.connection.cursor()
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description]
            records = cur.fetchmany(self.spin_preview.value())
            cur.close()
            adapter.disconnect()
            
            self.table_preview.setColumnCount(len(columns))
            self.table_preview.setHorizontalHeaderLabels(columns)
            
            self.table_preview.setRowCount(len(records))
            for r_idx, record in enumerate(records):
                for c_idx, val in enumerate(record):
                    self.table_preview.setItem(r_idx, c_idx, QTableWidgetItem(str(val)))
            self.table_preview.resizeColumnsToContents()
            self.lbl_error.setText(f"Başarılı: {len(records)} satır getirildi.")
            self.lbl_error.setStyleSheet("color: #a6e3a1;")
        except Exception as e:
            self.lbl_error.setText(f"SQL Hatası: {str(e)}")
            self.lbl_error.setStyleSheet("color: #f38ba8;")

    def save_and_close(self):
        sql = self.text_sql.toPlainText()
        limit = self.spin_limit.value()
        
        conn = get_connection()
        conn.execute("UPDATE transfer_jobs SET custom_source_sql = ?, max_rows_limit = ? WHERE id = ?", (sql, limit, self.job_id))
        conn.commit()
        conn.close()
        self.accept()

class TransfersTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.active_workers = {} # job_id -> TransferEngine instance
        
        # Tools
        tools = QHBoxLayout()
        self.btn_new_transfer = QPushButton(" Yeni Veri Aktarımı Başlat")
        self.btn_new_transfer.setIcon(qta.icon('fa5s.rocket', color='#11111b'))
        self.btn_new_transfer.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-size: 14px; padding: 10px; border-radius: 6px; font-weight: bold;")
        self.btn_new_transfer.clicked.connect(self.open_wizard)
        
        self.btn_refresh = QPushButton(" Yenile / Temizle")
        self.btn_refresh.setIcon(qta.icon('fa5s.sync', color='#cdd6f4'))
        self.btn_refresh.setStyleSheet("background-color: #313244; color: #cdd6f4; font-size: 14px; padding: 10px; border-radius: 6px; font-weight: bold;")
        self.btn_refresh.clicked.connect(self.load_jobs)
        
        tools.addWidget(self.btn_new_transfer)
        tools.addWidget(self.btn_refresh)
        tools.addStretch()
        layout.addLayout(tools)
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Kaynak -> Hedef", "Tablo", "Durum", "İlerleme", "İşlemler"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setStyleSheet("QTableWidget { font-size: 13px; font-weight: 500; } QHeaderView::section { font-size: 14px; background-color:#181825; padding:8px; }")
        
        layout.addWidget(self.table)
        self.load_jobs()

    def open_wizard(self):
        wizard = TransferWizard(self)
        if wizard.exec():
            src_id = wizard.source_id
            tgt_id = wizard.target_id
            mappings = wizard.transfer_mappings
            
            if not mappings: return

            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                for map_data in mappings:
                    src_table = map_data.get("src_table")
                    tgt_table = map_data.get("tgt_table")
                    custom_ddl = map_data.get("custom_ddl", "")
                    col_map = map_data.get("column_mapping", "{}")
                    
                    cursor.execute('''
                        INSERT INTO transfer_jobs (
                            source_conn_id, target_conn_id, source_schema, target_schema, 
                            source_table, target_table, status, custom_ddl, column_mapping
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (src_id, tgt_id, wizard.source_schema, wizard.target_schema, 
                          src_table, tgt_table, 'BEKLIYOR', custom_ddl, col_map))
                
                conn.commit()
                conn.close()
                QMessageBox.information(self, "Başarılı", f"{len(mappings)} adet tablo başarıyla eşleştirildi ve aktarım kuyruğuna (BEKLIYOR) eklendi.")
                self.load_jobs()
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Görevler oluşturulamadı:\n{e}")

    def load_jobs(self):
        conn = get_connection()
        cursor = conn.cursor()
        query = '''
            SELECT j.id, 
                   s.name || ' ➔ ' || t.name, 
                   j.source_schema || '.' || j.source_table, 
                   j.status, 
                   j.rows_transferred,
                   j.total_rows
            FROM transfer_jobs j
            JOIN connections s ON j.source_conn_id = s.id
            JOIN connections t ON j.target_conn_id = t.id
            ORDER BY j.id DESC
        '''
        cursor.execute(query)
        rows = cursor.fetchall()
        
        self.table.setRowCount(len(rows))
        for row_idx, row_data in enumerate(rows):
            job_id, direction, table_name, status, trans, total = row_data
            
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(job_id)))
            self.table.setItem(row_idx, 1, QTableWidgetItem(direction))
            self.table.setItem(row_idx, 2, QTableWidgetItem(table_name))
            
            lbl_status = QTableWidgetItem(status)
            lbl_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 3, lbl_status)
            
            # Progress Bar logic
            progress = QProgressBar()
            progress.setMaximum(total if total else 100)
            progress.setValue(trans if trans else 0)
            progress.setFormat(f"%v / %m ({int((trans/total)*100) if total else 0}%)")
            
            prog_widget = QWidget()
            prog_layout = QHBoxLayout(prog_widget)
            prog_layout.setContentsMargins(5, 5, 5, 5)
            prog_layout.addWidget(progress)
            self.table.setCellWidget(row_idx, 4, prog_widget)
            
            # Store ref so we can update it
            progress.setObjectName(f"prog_{job_id}")
            
            # Action Buttons
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(0, 0, 0, 0)
            
            btn_play = QPushButton()
            btn_play.setIcon(qta.icon('fa5s.play', color='#a6e3a1'))
            btn_play.setStyleSheet("background: transparent; border: none;")
            btn_play.setToolTip("Başlat / Devam Et")
            btn_play.clicked.connect(lambda checked, jid=job_id: self.start_job(jid))
            
            btn_pause = QPushButton()
            btn_pause.setIcon(qta.icon('fa5s.pause', color='#f9e2af'))
            btn_pause.setStyleSheet("background: transparent; border: none;")
            btn_pause.setToolTip("Duraklat")
            btn_pause.clicked.connect(lambda checked, jid=job_id: self.pause_job(jid))

            btn_sql = QPushButton()
            btn_sql.setIcon(qta.icon('fa5s.code', color='#89b4fa'))
            btn_sql.setStyleSheet("background: transparent; border: none;")
            btn_sql.setToolTip("SQL / Limit Düzenle")
            btn_sql.clicked.connect(lambda checked, jid=job_id: self.open_sql_editor(jid))

            btn_del = QPushButton()
            btn_del.setIcon(qta.icon('fa5s.trash', color='#f38ba8'))
            btn_del.setStyleSheet("background: transparent; border: none;")
            btn_del.clicked.connect(lambda checked, jid=job_id: self.delete_job(jid))

            action_layout.addStretch()
            action_layout.addWidget(btn_play)
            action_layout.addWidget(btn_pause)
            action_layout.addWidget(btn_sql)
            action_layout.addWidget(btn_del)
            action_layout.addStretch()

            self.table.setCellWidget(row_idx, 5, action_widget)
            
        self.table.resizeRowsToContents()
        conn.close()

    def open_sql_editor(self, job_id):
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT j.custom_source_sql, j.max_rows_limit, j.source_schema, j.source_table, j.column_mapping, s.db_type
            FROM transfer_jobs j
            JOIN connections s ON j.source_conn_id = s.id
            WHERE j.id = ?
        """, (job_id,))
        row = c.fetchone()
        conn.close()
        if not row: return
        
        sql = row[0]
        if not sql:
            import json
            schema = row[2]
            table = row[3]
            mapping_str = row[4]
            db_type = row[5]
            
            mapping = {}
            if mapping_str:
                mapping = json.loads(mapping_str)
                
            if not schema:
                full_table = table
            elif db_type == "PostgreSQL":
                full_table = f'"{schema}"."{table}"'
            elif db_type == "MS SQL Server":
                full_table = f'[{schema}].[{table}]'
            elif db_type == "Oracle":
                full_table = f'"{schema}"."{table}"'
            else:
                full_table = f"{schema}.{table}"
                
            cols_str = "*"
            if mapping:
                cols_str = ", ".join([f'"{c}"' for c in mapping.keys()])
                
            sql = f"SELECT {cols_str} \nFROM {full_table}"
        
        dialog = CustomSqlDialog(job_id, sql, row[1], self)
        dialog.exec()

    def update_job_status(self, job_id, status):
        conn = get_connection()
        c = conn.cursor()
        c.execute("UPDATE transfer_jobs SET status = ? WHERE id = ?", (status, job_id))
        conn.commit()
        conn.close()
        self.load_jobs() # Refresh row states visually

    def start_job(self, job_id):
        # Prevent multiple spawns
        if job_id in self.active_workers and self.active_workers[job_id].isRunning():
            if self.active_workers[job_id].is_paused:
                self.active_workers[job_id].resume()
                self.update_job_status(job_id, 'RUNNING')
            return

        conn = get_connection()
        cursor = conn.cursor()
        # Fetch detailed configurations for endpoints
        cursor.execute('''
            SELECT j.source_schema, j.source_table, j.target_schema, j.target_table, 
                   s.db_type, s.host, s.port, s.database, s.username, s.password_encrypted,
                   t.db_type, t.host, t.port, t.database, t.username, t.password_encrypted,
                   j.custom_ddl, j.column_mapping, j.custom_source_sql, j.max_rows_limit
            FROM transfer_jobs j
            JOIN connections s ON j.source_conn_id = s.id
            JOIN connections t ON j.target_conn_id = t.id
            WHERE j.id = ?
        ''', (job_id,))
        row = cursor.fetchone()
        conn.close()

        if not row: return

        # Format tables correctly as [schema].[table] for the engines to consume implicitly if needed.
        s_schema, src_t_raw, t_schema, tgt_t_raw = row[0], row[1], row[2], row[3]
        s_type, s_host, s_port, s_db, s_user, s_pass_enc = row[4:10]
        t_type, t_host, t_port, t_db, t_user, t_pass_enc = row[10:16]
        custom_ddl = row[16]
        column_mapping = row[17]
        custom_sql = row[18]
        max_rows = row[19]
        
        # Dialect specific schema appending helper
        def fmt_table(t_type, schema, table):
             if not schema: return table
             if t_type == "PostgreSQL": return f'"{schema}"."{table}"'
             if t_type == "MS SQL Server": return f'[{schema}].[{table}]'
             if t_type == "Oracle": return f'"{schema}"."{table}"'
             return table
             
        src_table = fmt_table(s_type, s_schema, src_t_raw)
        tgt_table = fmt_table(t_type, t_schema, tgt_t_raw)

        source_adapter = get_adapter(s_type)
        target_adapter = get_adapter(t_type)

        try:
            source_adapter.connect(s_host, s_port, s_db, s_user, CryptoManager.decrypt(s_pass_enc))
            target_adapter.connect(t_host, t_port, t_db, t_user, CryptoManager.decrypt(t_pass_enc))
            
            # --- Custom DDL Execution ---
            if custom_ddl and custom_ddl.strip():
                try:
                    from sqlalchemy import create_engine, text
                    t_url = target_adapter.get_sqlalchemy_url(t_host, t_port, t_db, t_user, CryptoManager.decrypt(t_pass_enc))
                    engine = create_engine(t_url)
                    with engine.begin() as sql_conn:
                        sql_conn.execute(text(custom_ddl))
                except Exception as ddl_e:
                    # Ignore IF EXISTS or already exists errors gracefully, but print it
                    print(f"Custom DDL Warning (Table might exist): {ddl_e}")
            # ---------------------------

        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Görev başlatılamadı:\n{e}")
            return

        engine = TransferEngine(source_adapter, target_adapter, src_table, tgt_table, column_mapping, custom_source_sql=custom_sql, max_rows_limit=max_rows)
        self.active_workers[job_id] = engine

        # Connect signals
        engine.progress_signal.connect(lambda trans, tot, msg, jid=job_id: self.on_progress(jid, trans, tot, msg))
        engine.finished_signal.connect(lambda jid=job_id: self.update_job_status(jid, 'COMPLETED'))
        engine.error_signal.connect(lambda err, jid=job_id: self.on_error(jid, err))

        self.update_job_status(job_id, 'RUNNING')
        engine.start()

    def pause_job(self, job_id):
        if job_id in self.active_workers:
            self.active_workers[job_id].pause()
            self.update_job_status(job_id, 'PAUSED')

    def delete_job(self, job_id):
        if job_id in self.active_workers:
            self.active_workers[job_id].cancel()
        
        conn = get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM transfer_jobs WHERE id = ?", (job_id,))
        conn.commit()
        conn.close()
        self.load_jobs()

    @pyqtSlot(int, int, int, str)
    def on_progress(self, job_id, transferred, total, message):
        # Optimizing UI updates directly via objectName search to avoid heavy reload
        for w in self.table.findChildren(QProgressBar):
            if w.objectName() == f"prog_{job_id}":
                w.setMaximum(total)
                w.setValue(transferred)
                w.setFormat(f"{message} - %v / %m")
                break
        
        # We also need to lazily save state to SQLite (throttle this in a real scenario)
        if transferred % 10000 == 0 or transferred == total:
            conn = get_connection()
            conn.execute("UPDATE transfer_jobs SET rows_transferred = ?, total_rows = ? WHERE id = ?", (transferred, total, job_id))
            conn.commit()
            conn.close()

    @pyqtSlot(int, str)
    def on_error(self, job_id, error_msg):
        self.update_job_status(job_id, 'FAILED')
        QMessageBox.warning(self, "Aktarım Hatası", f"Görev {job_id} hatayla durdu:\n{error_msg}")
