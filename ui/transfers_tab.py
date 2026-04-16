from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
                             QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
                             QProgressBar, QDialog, QTextEdit, QSpinBox, QSplitter,
                             QAbstractItemView, QApplication, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont
import qtawesome as qta

from core.local_db import get_connection, touch_project
from ui.wizard_dialog import TransferWizard
from core.transfer_engine import TransferEngine
from core.db_adapters.postgres import PostgresAdapter
from core.db_adapters.mssql import MSSQLAdapter
from core.db_adapters.oracle import OracleAdapter
from core.crypto import CryptoManager


def get_adapter(db_type: str):
    if db_type == "PostgreSQL":    return PostgresAdapter()
    if db_type == "MS SQL Server": return MSSQLAdapter()
    if db_type == "Oracle":        return OracleAdapter()
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  CustomSqlDialog  (değişmedi, sadece style güncellendi)
# ─────────────────────────────────────────────────────────────────────────────

class CustomSqlDialog(QDialog):
    def __init__(self, job_id: int, current_sql: str, current_limit: int, parent=None):
        super().__init__(parent)
        self.job_id = job_id
        self.setWindowTitle(f"Görev ID {job_id} — SQL Filtre & Canlı Önizleme")
        self.resize(860, 620)
        self.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4; font-size: 13px;")

        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Top pane
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(QLabel("Özel Veri Çekme Sorgusu"))

        self.text_sql = QTextEdit()
        self.text_sql.setStyleSheet("background-color: #313244; font-family: 'Cascadia Code', Consolas, monospace; font-size: 13px;")
        if current_sql:
            self.text_sql.setText(current_sql)
        else:
            self.text_sql.setPlaceholderText("SELECT * FROM tablo_adiniz")
        top_layout.addWidget(self.text_sql)

        limit_layout = QHBoxLayout()
        limit_layout.addWidget(QLabel("Maksimum Aktarılacak Satır (0 = Tümü):"))
        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(0, 2_000_000_000)
        self.spin_limit.setValue(current_limit if current_limit else 0)
        self.spin_limit.setStyleSheet("background-color: #313244; padding: 5px;")
        limit_layout.addWidget(self.spin_limit)
        limit_layout.addSpacing(20)
        limit_layout.addWidget(QLabel("Önizleme Satır Sayısı:"))
        self.spin_preview = QSpinBox()
        self.spin_preview.setRange(1, 5000)
        self.spin_preview.setValue(200)
        self.spin_preview.setStyleSheet("background-color: #313244; padding: 5px;")
        limit_layout.addWidget(self.spin_preview)
        limit_layout.addStretch()
        top_layout.addLayout(limit_layout)

        btn_layout = QHBoxLayout()
        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet("color: #f38ba8;")
        btn_layout.addWidget(self.lbl_error)
        btn_layout.addStretch()

        self.btn_preview = QPushButton("  Canlı Önizle")
        self.btn_preview.setIcon(qta.icon("fa5s.play", color="#11111b"))
        self.btn_preview.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold; padding: 6px 14px;")
        self.btn_preview.clicked.connect(self.preview_data)
        btn_layout.addWidget(self.btn_preview)

        self.btn_save = QPushButton("Kaydet ve Kapat")
        self.btn_save.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold; padding: 6px 14px;")
        self.btn_save.clicked.connect(self.save_and_close)
        btn_layout.addWidget(self.btn_save)
        top_layout.addLayout(btn_layout)

        # Bottom pane
        bot_widget = QWidget()
        bot_layout = QVBoxLayout(bot_widget)
        bot_layout.setContentsMargins(0, 0, 0, 0)
        self.table_preview = QTableWidget()
        self.table_preview.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_preview.setStyleSheet("background-color: #313244; color: #cdd6f4; gridline-color: #45475a;")
        bot_layout.addWidget(self.table_preview)

        splitter.addWidget(top_widget)
        splitter.addWidget(bot_widget)
        splitter.setSizes([300, 300])
        main_layout.addWidget(splitter)

    def preview_data(self):
        self.lbl_error.setText("Yükleniyor…")
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

        db_type, host, port, db, user, pass_enc = (
            row["db_type"], row["host"], row["port"],
            row["database"], row["username"], row["password_encrypted"]
        )
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
            self.lbl_error.setText(f"✓ Başarılı: {len(records)} satır getirildi.")
            self.lbl_error.setStyleSheet("color: #a6e3a1;")
        except Exception as e:
            self.lbl_error.setText(f"SQL Hatası: {str(e)}")
            self.lbl_error.setStyleSheet("color: #f38ba8;")

    def save_and_close(self):
        sql   = self.text_sql.toPlainText()
        limit = self.spin_limit.value()
        conn = get_connection()
        conn.execute(
            "UPDATE transfer_jobs SET custom_source_sql = ?, max_rows_limit = ? WHERE id = ?",
            (sql, limit, self.job_id)
        )
        conn.commit()
        conn.close()
        self.accept()


# ─────────────────────────────────────────────────────────────────────────────
#  TransfersTab  — Proje İçi Aktarım Görevleri
# ─────────────────────────────────────────────────────────────────────────────

class TransfersTab(QWidget):
    """
    Belirli bir projeye ait aktarım görevlerini listeleyen ve yöneten ekran.

    Navigasyon sinyali:
      go_back  — Projeler listesine dönmek için MainWindow dinler.
    """
    go_back = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project_id: int | None = None
        self._source_conn_id: int | None = None
        self._target_conn_id: int | None = None
        self._project_name: str = ""
        self.active_workers: dict[int, TransferEngine] = {}

        self._build_ui()

    # ── UI İnşası ────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 20)
        root.setSpacing(12)

        # ─ Breadcrumb + Başlık ─
        top_row = QHBoxLayout()

        self.btn_back = QPushButton("  ← Projelere Dön")
        self.btn_back.setIcon(qta.icon("fa5s.arrow-left", color="#89b4fa"))
        self.btn_back.setStyleSheet(
            "background: transparent; color: #89b4fa; font-size: 12px; "
            "border: 1px solid #313244; border-radius: 6px; padding: 5px 12px;"
        )
        self.btn_back.clicked.connect(self.go_back.emit)
        top_row.addWidget(self.btn_back)

        top_row.addSpacing(12)

        self.lbl_breadcrumb = QLabel("")
        self.lbl_breadcrumb.setStyleSheet("color: #6c7086; font-size: 12px;")
        top_row.addWidget(self.lbl_breadcrumb)
        top_row.addStretch()

        root.addLayout(top_row)

        # ─ Proje Başlığı ─
        self.lbl_project_title = QLabel("Proje")
        self.lbl_project_title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        self.lbl_project_title.setStyleSheet("color: #cdd6f4;")
        root.addWidget(self.lbl_project_title)

        # ─ Ayırıcı ─
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #313244;")
        root.addWidget(sep)

        # ─ Araç Çubuğu ─
        tools = QHBoxLayout()

        self.btn_new_transfer = QPushButton("  Yeni Aktarım Ekle")
        self.btn_new_transfer.setIcon(qta.icon("fa5s.plus", color="#11111b"))
        self.btn_new_transfer.setStyleSheet(
            "background-color: #a6e3a1; color: #11111b; font-size: 13px; "
            "padding: 9px 18px; border-radius: 6px; font-weight: bold;"
        )
        self.btn_new_transfer.clicked.connect(self.open_wizard)

        self.btn_refresh = QPushButton("  Yenile")
        self.btn_refresh.setIcon(qta.icon("fa5s.sync-alt", color="#cdd6f4"))
        self.btn_refresh.setStyleSheet(
            "background-color: #313244; color: #cdd6f4; font-size: 13px; "
            "padding: 9px 16px; border-radius: 6px; font-weight: bold;"
        )
        self.btn_refresh.clicked.connect(self.load_jobs)

        tools.addWidget(self.btn_new_transfer)
        tools.addWidget(self.btn_refresh)
        tools.addStretch()
        root.addLayout(tools)

        # ─ Görev Tablosu ─
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Kaynak → Hedef", "Tablo", "Durum", "İlerleme", "İşlemler"]
        )
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(5, 160)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet("""
            QTableWidget {
                font-size: 12px;
                background-color: #1e1e2e;
                alternate-background-color: #181825;
                border: 1px solid #313244;
                border-radius: 8px;
            }
            QTableWidget::item { padding: 5px 8px; border-bottom: 1px solid #2a2a3d; }
            QTableWidget::item:selected { background-color: #313244; color: #cdd6f4; }
            QHeaderView::section {
                background-color: #181825; color: #a6adc8;
                padding: 9px 8px; font-weight: bold; font-size: 12px;
                border: none; border-bottom: 2px solid #313244;
            }
        """)
        self.table.setAlternatingRowColors(True)
        root.addWidget(self.table)

    # ── Proje Açma ───────────────────────────────────────────────────────────

    def open_project(self, project_id: int, project_name: str,
                     source_conn_id: int, target_conn_id: int):
        """MainWindow tarafından çağrılır; projeyi yükler ve görevleri listeler."""
        self._project_id    = project_id
        self._project_name  = project_name
        self._source_conn_id = source_conn_id
        self._target_conn_id = target_conn_id

        self.lbl_project_title.setText(f"📁  {project_name}")

        # Breadcrumb: "Projeler  /  {project_name}"
        self.lbl_breadcrumb.setText(f"Projeler  /  {project_name}")

        self.load_jobs()

    # ── Veri Yükleme ─────────────────────────────────────────────────────────

    def load_jobs(self):
        if self._project_id is None:
            return

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT j.id,
                   s.name || ' → ' || t.name AS direction,
                   COALESCE(j.source_schema || '.', '') || j.source_table AS src_table,
                   j.status,
                   j.rows_transferred,
                   j.total_rows
            FROM transfer_jobs j
            JOIN connections s ON j.source_conn_id = s.id
            JOIN connections t ON j.target_conn_id = t.id
            WHERE j.project_id = ?
            ORDER BY j.id DESC
        ''', (self._project_id,))
        rows = cursor.fetchall()
        conn.close()

        self.table.setRowCount(len(rows))
        for row_idx, row_data in enumerate(rows):
            job_id     = row_data["id"]
            direction  = row_data["direction"]
            table_name = row_data["src_table"]
            status     = row_data["status"]
            trans      = row_data["rows_transferred"] or 0
            total      = row_data["total_rows"] or 0

            self.table.setRowHeight(row_idx, 48)

            self.table.setItem(row_idx, 0, QTableWidgetItem(str(job_id)))
            self.table.setItem(row_idx, 1, QTableWidgetItem(direction))
            self.table.setItem(row_idx, 2, QTableWidgetItem(table_name))

            # Durum
            status_item = QTableWidgetItem(status)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            _STATUS_COLORS = {
                "COMPLETED": "#a6e3a1", "RUNNING": "#89b4fa",
                "FAILED": "#f38ba8",    "PAUSED": "#f9e2af",
                "BEKLIYOR": "#cba6f7",
            }
            from PyQt6.QtGui import QColor
            status_item.setForeground(QColor(_STATUS_COLORS.get(status, "#cdd6f4")))
            self.table.setItem(row_idx, 3, status_item)

            # İlerleme çubuğu
            progress = QProgressBar()
            progress.setMaximum(total if total else 100)
            progress.setValue(trans)
            pct = int((trans / total) * 100) if total else 0
            progress.setFormat(f"%v / %m  ({pct}%)")
            progress.setObjectName(f"prog_{job_id}")
            prog_container = QWidget()
            prog_layout = QHBoxLayout(prog_container)
            prog_layout.setContentsMargins(6, 6, 6, 6)
            prog_layout.addWidget(progress)
            self.table.setCellWidget(row_idx, 4, prog_container)

            # İşlem butonları
            action_widget = self._make_action_buttons(job_id)
            self.table.setCellWidget(row_idx, 5, action_widget)

        self.table.resizeRowsToContents()

    def _make_action_buttons(self, job_id: int) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        def icon_btn(icon_name: str, color: str, tooltip: str) -> QPushButton:
            btn = QPushButton()
            btn.setIcon(qta.icon(icon_name, color=color))
            btn.setToolTip(tooltip)
            btn.setFixedSize(32, 32)
            btn.setStyleSheet(
                "QPushButton { background: transparent; border: none; border-radius:4px; }"
                "QPushButton:hover { background-color: #313244; }"
            )
            return btn

        btn_play = icon_btn("fa5s.play", "#a6e3a1", "Başlat / Devam Et")
        btn_play.clicked.connect(lambda: self.start_job(job_id))

        btn_pause = icon_btn("fa5s.pause", "#f9e2af", "Duraklat")
        btn_pause.clicked.connect(lambda: self.pause_job(job_id))

        btn_sql = icon_btn("fa5s.code", "#89b4fa", "SQL / Limit Düzenle")
        btn_sql.clicked.connect(lambda: self.open_sql_editor(job_id))

        btn_del = icon_btn("fa5s.trash-alt", "#f38ba8", "Görevi Sil")
        btn_del.clicked.connect(lambda: self.delete_job(job_id))

        layout.addWidget(btn_play)
        layout.addWidget(btn_pause)
        layout.addWidget(btn_sql)
        layout.addWidget(btn_del)
        return w

    # ── Wizard ───────────────────────────────────────────────────────────────

    def open_wizard(self):
        if self._project_id is None:
            QMessageBox.warning(self, "Hata", "Aktif proje yok.")
            return

        wizard = TransferWizard(
            source_conn_id=self._source_conn_id,
            target_conn_id=self._target_conn_id,
            parent=self
        )
        if wizard.exec():
            mappings = wizard.transfer_mappings
            if not mappings:
                return
            try:
                conn = get_connection()
                cursor = conn.cursor()
                for map_data in mappings:
                    cursor.execute('''
                        INSERT INTO transfer_jobs (
                            project_id,
                            source_conn_id, target_conn_id,
                            source_schema, target_schema,
                            source_table, target_table,
                            status, custom_ddl, column_mapping
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        self._project_id,
                        self._source_conn_id,
                        self._target_conn_id,
                        wizard.source_schema,
                        wizard.target_schema,
                        map_data["src_table"],
                        map_data["tgt_table"],
                        "BEKLIYOR",
                        map_data.get("custom_ddl", ""),
                        map_data.get("column_mapping", "{}"),
                    ))
                conn.commit()
                conn.close()
                touch_project(self._project_id)
                QMessageBox.information(
                    self, "Başarılı",
                    f"{len(mappings)} tablo başarıyla eşleştirildi ve aktarım kuyruğuna eklendi."
                )
                self.load_jobs()
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Görevler oluşturulamadı:\n{e}")

    # ── SQL Editör ───────────────────────────────────────────────────────────

    def open_sql_editor(self, job_id: int):
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT j.custom_source_sql, j.max_rows_limit, j.source_schema,
                   j.source_table, j.column_mapping, s.db_type
            FROM transfer_jobs j
            JOIN connections s ON j.source_conn_id = s.id
            WHERE j.id = ?
        """, (job_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return

        sql = row["custom_source_sql"]
        if not sql:
            import json
            schema   = row["source_schema"]
            table    = row["source_table"]
            db_type  = row["db_type"]
            mapping  = json.loads(row["column_mapping"] or "{}")

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

            cols_str = ", ".join(f'"{c}"' for c in mapping.keys()) if mapping else "*"
            sql = f"SELECT {cols_str} \nFROM {full_table}"

        dialog = CustomSqlDialog(job_id, sql, row["max_rows_limit"], self)
        dialog.exec()

    # ── Görev Durumu ─────────────────────────────────────────────────────────

    def update_job_status(self, job_id: int, status: str):
        conn = get_connection()
        conn.execute(
            "UPDATE transfer_jobs SET status = ?, updated_at = datetime('now', 'localtime') WHERE id = ?",
            (status, job_id)
        )
        conn.commit()
        conn.close()
        if self._project_id:
            touch_project(self._project_id)
        self.load_jobs()

    # ── Görev Başlat ─────────────────────────────────────────────────────────

    def start_job(self, job_id: int):
        if job_id in self.active_workers and self.active_workers[job_id].isRunning():
            if self.active_workers[job_id].is_paused:
                self.active_workers[job_id].resume()
                self.update_job_status(job_id, "RUNNING")
            return

        conn = get_connection()
        cursor = conn.cursor()
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
        if not row:
            return

        s_schema, src_t_raw, t_schema, tgt_t_raw = row[0], row[1], row[2], row[3]
        s_type, s_host, s_port, s_db, s_user, s_pass_enc = row[4:10]
        t_type, t_host, t_port, t_db, t_user, t_pass_enc = row[10:16]
        custom_ddl    = row[16]
        column_mapping = row[17]
        custom_sql    = row[18]
        max_rows      = row[19]

        def fmt_table(db_type: str, schema: str, table: str) -> str:
            if not schema: return table
            if db_type == "PostgreSQL":    return f'"{schema}"."{table}"'
            if db_type == "MS SQL Server": return f'[{schema}].[{table}]'
            if db_type == "Oracle":        return f'"{schema}"."{table}"'
            return table

        src_table = fmt_table(s_type, s_schema, src_t_raw)
        tgt_table = fmt_table(t_type, t_schema, tgt_t_raw)

        source_adapter = get_adapter(s_type)
        target_adapter = get_adapter(t_type)

        try:
            source_adapter.connect(s_host, s_port, s_db, s_user, CryptoManager.decrypt(s_pass_enc))
            target_adapter.connect(t_host, t_port, t_db, t_user, CryptoManager.decrypt(t_pass_enc))

            if custom_ddl and custom_ddl.strip():
                try:
                    from sqlalchemy import create_engine, text
                    t_url = target_adapter.get_sqlalchemy_url(
                        t_host, t_port, t_db, t_user, CryptoManager.decrypt(t_pass_enc)
                    )
                    engine = create_engine(t_url)
                    with engine.begin() as sql_conn:
                        sql_conn.execute(text(custom_ddl))
                except Exception as ddl_e:
                    print(f"Custom DDL Warning: {ddl_e}")

        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Görev başlatılamadı:\n{e}")
            return

        engine = TransferEngine(
            source_adapter, target_adapter, src_table, tgt_table,
            column_mapping, custom_source_sql=custom_sql, max_rows_limit=max_rows
        )
        self.active_workers[job_id] = engine
        engine.progress_signal.connect(lambda t, tot, msg, jid=job_id: self.on_progress(jid, t, tot, msg))
        engine.finished_signal.connect(lambda jid=job_id: self.update_job_status(jid, "COMPLETED"))
        engine.error_signal.connect(lambda err, jid=job_id: self.on_error(jid, err))

        self.update_job_status(job_id, "RUNNING")
        engine.start()

    # ── Duraklat / Sil ───────────────────────────────────────────────────────

    def pause_job(self, job_id: int):
        if job_id in self.active_workers:
            self.active_workers[job_id].pause()
            self.update_job_status(job_id, "PAUSED")

    def delete_job(self, job_id: int):
        if job_id in self.active_workers:
            self.active_workers[job_id].cancel()
        conn = get_connection()
        conn.execute("DELETE FROM transfer_jobs WHERE id = ?", (job_id,))
        conn.commit()
        conn.close()
        if self._project_id:
            touch_project(self._project_id)
        self.load_jobs()

    # ── Sinyaller ────────────────────────────────────────────────────────────

    @pyqtSlot(int, int, int, str)
    def on_progress(self, job_id: int, transferred: int, total: int, message: str):
        for w in self.table.findChildren(QProgressBar):
            if w.objectName() == f"prog_{job_id}":
                w.setMaximum(total)
                w.setValue(transferred)
                w.setFormat(f"{message}  %v / %m")
                break
        if transferred % 10_000 == 0 or transferred == total:
            conn = get_connection()
            conn.execute(
                "UPDATE transfer_jobs SET rows_transferred = ?, total_rows = ?, "
                "updated_at = datetime('now', 'localtime') WHERE id = ?",
                (transferred, total, job_id)
            )
            conn.commit()
            conn.close()

    @pyqtSlot(int, str)
    def on_error(self, job_id: int, error_msg: str):
        self.update_job_status(job_id, "FAILED")
        QMessageBox.warning(self, "Aktarım Hatası", f"Görev {job_id} hatayla durdu:\n{error_msg}")
