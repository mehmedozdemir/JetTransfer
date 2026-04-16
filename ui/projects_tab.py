from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QLineEdit, QCheckBox, QAbstractItemView, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSortFilterProxyModel
from PyQt6.QtGui import QFont, QColor
import qtawesome as qta

from core.local_db import (
    get_all_projects, archive_project, delete_project
)
from ui.create_project_dialog import CreateProjectDialog

# ─── DB Tipi renkleri / badge'leri ───────────────────────────────────────────

_DB_BADGE_STYLE = {
    "PostgreSQL":    ("background:#3b5bdb; color:#edf2ff;", "#3b5bdb"),
    "MS SQL Server": ("background:#c92a2a; color:#fff5f5;", "#c92a2a"),
    "Oracle":        ("background:#e67700; color:#fff9db;", "#e67700"),
}

_STATUS_STYLE = {
    "COMPLETED": ("background:#2d6a4f; color:#d8f3dc;"),
    "RUNNING":   ("background:#1864ab; color:#e7f5ff;"),
    "FAILED":    ("background:#7d1a1a; color:#ffe3e3;"),
    "PAUSED":    ("background:#495057; color:#f1f3f5;"),
    "BEKLIYOR":  ("background:#3d3117; color:#fff3cd;"),
}


def _make_badge(text: str, style: str) -> QLabel:
    lbl = QLabel(f"  {text}  ")
    lbl.setStyleSheet(
        f"{style} border-radius:4px; font-size:11px; font-weight:bold; padding: 1px 0px;"
    )
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setFixedHeight(20)
    lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    return lbl


def _format_rows(value: int) -> str:
    if value >= 1_000_000:
        return f"{value/1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value/1_000:.1f}K"
    return str(value)


# ─── Kolon indeksleri ────────────────────────────────────────────────────────

COL_NAME    = 0
COL_SOURCE  = 1
COL_TARGET  = 2
COL_JOBS    = 3
COL_ROWS    = 4
COL_CREATED = 5
COL_UPDATED = 6
COL_ACTIONS = 7
COL_COUNT   = 8


# ─────────────────────────────────────────────────────────────────────────────
#  ProjectsTab
# ─────────────────────────────────────────────────────────────────────────────

class ProjectsTab(QWidget):
    """
    Tüm aktarım projelerinin listelendiği, yönetildiği ana ekran.
    Sinyal: open_project(project_id, project_name, source_conn_id, target_conn_id)
    """
    open_project = pyqtSignal(int, str, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.load_projects()

    # ── UI İnşası ────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        # ─ Üst Başlık Çubuğu ─
        header = QHBoxLayout()

        title_col = QVBoxLayout()
        title_lbl = QLabel("Aktarım Projeleri")
        title_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #cdd6f4;")
        sub_lbl = QLabel("Kaynak ve hedef veritabanı çiftleri için projeler oluşturun ve yönetin.")
        sub_lbl.setStyleSheet("color: #6c7086; font-size: 11px;")
        title_col.addWidget(title_lbl)
        title_col.addWidget(sub_lbl)
        header.addLayout(title_col)
        header.addStretch()

        self.btn_new = QPushButton("  Yeni Proje")
        self.btn_new.setIcon(qta.icon("fa5s.plus", color="#11111b"))
        self.btn_new.setStyleSheet(
            "background-color: #a6e3a1; color: #11111b; font-size: 13px; "
            "padding: 9px 20px; border-radius: 7px; font-weight: bold;"
        )
        self.btn_new.clicked.connect(self.open_create_dialog)
        header.addWidget(self.btn_new)

        root.addLayout(header)

        # ─ Ayırıcı ─
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #313244;")
        root.addWidget(sep)

        # ─ Araç Çubuğu ─
        toolbar = QHBoxLayout()

        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("  🔍  Proje adı veya açıklamaya göre filtrele…")
        self.edit_search.setStyleSheet(
            "background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; "
            "border-radius: 6px; padding: 7px 12px; font-size: 12px;"
        )
        self.edit_search.setMinimumWidth(300)
        self.edit_search.textChanged.connect(self._on_search)
        toolbar.addWidget(self.edit_search)

        toolbar.addSpacing(16)

        self.chk_archived = QCheckBox("  Arşivlenenleri Göster")
        self.chk_archived.setStyleSheet("color: #a6adc8; font-size: 12px;")
        self.chk_archived.stateChanged.connect(self.load_projects)
        toolbar.addWidget(self.chk_archived)

        toolbar.addStretch()

        self.btn_refresh = QPushButton()
        self.btn_refresh.setIcon(qta.icon("fa5s.sync-alt", color="#cdd6f4"))
        self.btn_refresh.setToolTip("Yenile")
        self.btn_refresh.setStyleSheet(
            "background-color: #313244; border-radius: 6px; padding: 7px 10px;"
        )
        self.btn_refresh.clicked.connect(self.load_projects)
        toolbar.addWidget(self.btn_refresh)

        root.addLayout(toolbar)

        # ─ Tablo ─
        self.table = QTableWidget()
        self.table.setColumnCount(COL_COUNT)
        self.table.setHorizontalHeaderLabels([
            "Proje Adı", "Kaynak DB", "Hedef DB",
            "Görevler", "Aktarılan Satır",
            "Oluşturulma", "Son Aktivite", "İşlemler"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setStyleSheet("""
            QTableWidget {
                font-size: 12px;
                alternate-background-color: #181825;
                background-color: #1e1e2e;
                border: 1px solid #313244;
                border-radius: 8px;
            }
            QTableWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #2a2a3d;
            }
            QTableWidget::item:selected {
                background-color: #313244;
                color: #cdd6f4;
            }
            QHeaderView::section {
                background-color: #181825;
                color: #a6adc8;
                padding: 10px 8px;
                font-weight: bold;
                font-size: 12px;
                border: none;
                border-bottom: 2px solid #313244;
            }
        """)

        # Kolon genişlikleri — Fixed modda elle tanımlandı
        # (ResizeToContents setCellWidget ile uyumlu çalışmaz)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(COL_SOURCE,  140)
        self.table.setColumnWidth(COL_TARGET,  140)
        self.table.setColumnWidth(COL_JOBS,    160)
        self.table.setColumnWidth(COL_ROWS,    100)
        self.table.setColumnWidth(COL_CREATED, 130)
        self.table.setColumnWidth(COL_UPDATED, 130)
        self.table.setColumnWidth(COL_ACTIONS, 148)
        hdr.setMinimumSectionSize(80)

        # NOT: setSortingEnabled(True) ile setCellWidget birlikte
        # kullanılamaz — Qt widget'ları render etmeyi bozar.
        self.table.setSortingEnabled(False)

        # Çift tıklama ile projeyi aç
        self.table.cellDoubleClicked.connect(self._on_double_click)

        root.addWidget(self.table)

        # ─ Alt Özet Çubuğu ─
        self.lbl_summary = QLabel("")
        self.lbl_summary.setStyleSheet("color: #6c7086; font-size: 11px;")
        root.addWidget(self.lbl_summary)

    # ── Veri Yükleme ─────────────────────────────────────────────────────────

    def load_projects(self):
        show_archived = self.chk_archived.isChecked()
        rows = get_all_projects(include_archived=show_archived)
        self._all_rows = rows  # arama filtresi için sakla
        self._render_rows(rows)
        self._update_summary(rows)

    def _render_rows(self, rows):
        self.table.setRowCount(len(rows))
        ROW_H = 62  # Widget'ların nefes alacağı sabit yükseklik

        for r_idx, row in enumerate(rows):
            self.table.setRowHeight(r_idx, ROW_H)

            # ─ Proje Adı ─
            name_widget = self._make_name_cell(row, r_idx)
            self.table.setCellWidget(r_idx, COL_NAME, name_widget)
            # Çift tık navigasyonu için gizli item — metin boş, widget gösterimi yönetir
            _sort_item(self.table, r_idx, COL_NAME, "",
                       project_id=row["id"], project_name=row["name"],
                       src_id=row["source_conn_id"], tgt_id=row["target_conn_id"])


            # ─ Kaynak DB Badge ─
            self.table.setCellWidget(
                r_idx, COL_SOURCE,
                self._make_db_badge_cell(row["source_name"] or "—", row["source_type"] or "")
            )

            # ─ Hedef DB Badge ─
            self.table.setCellWidget(
                r_idx, COL_TARGET,
                self._make_db_badge_cell(row["target_name"] or "—", row["target_type"] or "")
            )

            # ─ Görev Özet Badge'leri ─
            self.table.setCellWidget(r_idx, COL_JOBS, self._make_jobs_summary_cell(row))

            # ─ Aktarılan Satır ─
            rows_item = QTableWidgetItem(_format_rows(row["total_rows_transferred"] or 0))
            rows_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            rows_item.setForeground(QColor("#a6e3a1"))
            self.table.setItem(r_idx, COL_ROWS, rows_item)

            # ─ Oluşturulma ─
            created_str = (row["created_at"] or "")[:16].replace("T", " ")
            item_created = QTableWidgetItem(created_str)
            item_created.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_created.setForeground(QColor("#6c7086"))
            self.table.setItem(r_idx, COL_CREATED, item_created)

            # ─ Son Aktivite ─
            updated_str = (row["updated_at"] or "")[:16].replace("T", " ")
            item_updated = QTableWidgetItem(updated_str)
            item_updated.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_updated.setForeground(QColor("#89b4fa"))
            self.table.setItem(r_idx, COL_UPDATED, item_updated)

            # ─ İşlem Butonları ─
            self.table.setCellWidget(
                r_idx, COL_ACTIONS,
                self._make_action_buttons(
                    project_id=row["id"],
                    project_name=row["name"],
                    source_conn_id=row["source_conn_id"],
                    target_conn_id=row["target_conn_id"],
                    is_archived=bool(row["is_archived"])
                )
            )

    # ── Hücre Widget Fabrikaları ──────────────────────────────────────────────

    def _make_name_cell(self, row, row_idx: int = 0) -> QWidget:
        # Arka plan opak olmalı — transparent yapınca alttaki item metni sızıyor
        # Alternatif satır renkleriyle uyumlu
        bg_color = "#181825" if row_idx % 2 == 1 else "#1e1e2e"
        w = QWidget()
        w.setAutoFillBackground(True)
        w.setStyleSheet(f"QWidget {{ background-color: {bg_color}; }}")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.setSpacing(3)

        name_lbl = QLabel(row["name"])
        name_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        name_lbl.setStyleSheet("color: #cdd6f4; background: transparent;")
        layout.addWidget(name_lbl)

        desc = row["description"] or ""
        if desc:
            desc_lbl = QLabel(desc[:90] + ("…" if len(desc) > 90 else ""))
            desc_lbl.setStyleSheet("color: #6c7086; font-size: 10px; background: transparent;")
            layout.addWidget(desc_lbl)

        return w

    @staticmethod
    def _make_db_badge_cell(conn_name: str, db_type: str) -> QWidget:
        """DB tipi badge + bağlantı adını tek satırda gösterir."""
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(3)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        style_str, _ = _DB_BADGE_STYLE.get(
            db_type, ("background:#45475a; color:#cdd6f4;", "#45475a")
        )
        badge = _make_badge(db_type or "?", style_str)
        badge.setMaximumWidth(120)
        layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignCenter)

        name_lbl = QLabel(conn_name)
        name_lbl.setStyleSheet("color: #a6adc8; font-size: 10px; background: transparent;")
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setMaximumWidth(130)
        # Uzun isimleri ... ile kes
        name_lbl.setWordWrap(False)
        metrics = name_lbl.fontMetrics()
        elided = metrics.elidedText(conn_name, Qt.TextElideMode.ElideRight, 128)
        name_lbl.setText(elided)
        layout.addWidget(name_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        return w

    @staticmethod
    def _make_jobs_summary_cell(row) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        total      = row["total_jobs"] or 0
        completed  = row["completed_jobs"] or 0
        failed     = row["failed_jobs"] or 0
        running    = row["running_jobs"] or 0
        waiting    = total - completed - failed - running

        if total == 0:
            lbl = QLabel("Görev yok")
            lbl.setStyleSheet("color: #585b70; font-size: 11px; background: transparent;")
            layout.addWidget(lbl)
            return w

        if completed:
            layout.addWidget(_make_badge(f"✓ {completed}", "background:#2d6a4f; color:#d8f3dc;"))
        if running:
            layout.addWidget(_make_badge(f"▶ {running}", "background:#1864ab; color:#e7f5ff;"))
        if failed:
            layout.addWidget(_make_badge(f"✗ {failed}", "background:#7d1a1a; color:#ffe3e3;"))
        if waiting:
            layout.addWidget(_make_badge(f"⏳ {waiting}", "background:#3d3117; color:#fff3cd;"))

        return w

    def _make_action_buttons(
        self, project_id: int, project_name: str,
        source_conn_id: int, target_conn_id: int,
        is_archived: bool
    ) -> QWidget:
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
                "QPushButton { background: transparent; border: none; border-radius: 4px; }"
                "QPushButton:hover { background-color: #313244; }"
            )
            return btn

        # Aç
        btn_open = icon_btn("fa5s.folder-open", "#89b4fa", "Projeyi Aç")
        btn_open.clicked.connect(
            lambda: self.open_project.emit(project_id, project_name, source_conn_id, target_conn_id)
        )
        layout.addWidget(btn_open)

        # Düzenle
        btn_edit = icon_btn("fa5s.edit", "#f9e2af", "Düzenle")
        btn_edit.clicked.connect(lambda: self._on_edit(project_id))
        layout.addWidget(btn_edit)

        # Arşivle / Geri Al
        if is_archived:
            btn_archive = icon_btn("fa5s.box-open", "#a6e3a1", "Arşivden Çıkar")
            btn_archive.clicked.connect(lambda: self._on_unarchive(project_id))
        else:
            btn_archive = icon_btn("fa5s.archive", "#a6adc8", "Arşivle")
            btn_archive.clicked.connect(lambda: self._on_archive(project_id))
        layout.addWidget(btn_archive)

        # Sil
        btn_del = icon_btn("fa5s.trash-alt", "#f38ba8", "Sil")
        btn_del.clicked.connect(lambda: self._on_delete(project_id, project_name))
        layout.addWidget(btn_del)

        return w

    # ── Özet Çubuğu ──────────────────────────────────────────────────────────

    def _update_summary(self, rows):
        total = len(rows)
        active = sum(1 for r in rows if not r["is_archived"])
        archived = total - active
        total_jobs = sum(r["total_jobs"] or 0 for r in rows)
        total_rows = sum(r["total_rows_transferred"] or 0 for r in rows)
        self.lbl_summary.setText(
            f"Toplam {active} aktif proje"
            + (f"  •  {archived} arşivlenmiş" if archived else "")
            + f"  •  {total_jobs} görev"
            + f"  •  {_format_rows(total_rows)} satır aktarıldı"
        )

    # ── Filtre ───────────────────────────────────────────────────────────────

    def _on_search(self, text: str):
        if not hasattr(self, "_all_rows"):
            return
        text = text.strip().lower()
        if not text:
            self._render_rows(self._all_rows)
            return
        filtered = [
            r for r in self._all_rows
            if text in (r["name"] or "").lower()
            or text in (r["description"] or "").lower()
            or text in (r["source_name"] or "").lower()
            or text in (r["target_name"] or "").lower()
        ]
        self._render_rows(filtered)

    # ── Eylemler ─────────────────────────────────────────────────────────────

    def open_create_dialog(self):
        dlg = CreateProjectDialog(self)
        if dlg.exec():
            self.load_projects()

    def _on_edit(self, project_id: int):
        dlg = CreateProjectDialog(self, project_id=project_id)
        if dlg.exec():
            self.load_projects()

    def _on_archive(self, project_id: int):
        reply = QMessageBox.question(
            self, "Arşivle",
            "Bu proje arşivlensin mi? Arşivlenen projeler listelenmez fakat kalıcı olarak silinmez.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            archive_project(project_id, True)
            self.load_projects()

    def _on_unarchive(self, project_id: int):
        archive_project(project_id, False)
        self.load_projects()

    def _on_delete(self, project_id: int, project_name: str):
        reply = QMessageBox.warning(
            self, "Projeyi Sil",
            f"<b>'{project_name}'</b> projesi ve bağlı tüm aktarım görevleri <b>kalıcı olarak</b> silinecek.\n\nDevam etmek istiyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_project(project_id)
            self.load_projects()

    def _on_double_click(self, row: int, _col: int):
        """Çift tıklama = projeyi aç."""
        # COL_ACTIONS hariç tüm satırda çalışır
        if _col == COL_ACTIONS:
            return
        if not hasattr(self, "_all_rows"):
            return
        # Tablo sıralı olabileceğinden project_id'yi sort item'dan okuyalım
        sort_item = self.table.item(row, COL_NAME)
        if not sort_item:
            return
        project_name = sort_item.data(Qt.ItemDataRole.UserRole + 1)
        project_id   = sort_item.data(Qt.ItemDataRole.UserRole + 2)
        src_id        = sort_item.data(Qt.ItemDataRole.UserRole + 3)
        tgt_id        = sort_item.data(Qt.ItemDataRole.UserRole + 4)
        if project_id:
            self.open_project.emit(project_id, project_name, src_id, tgt_id)


# ─── Yardımcı: Sıralama item'ı ───────────────────────────────────────────────

def _sort_item(table: QTableWidget, row: int, col: int, sort_text: str,
               project_id: int | None = None, project_name: str | None = None,
               src_id: int | None = None, tgt_id: int | None = None):
    """
    Görsel olarak widget kullanılan hücrelerde sıralama için
    gizli bir QTableWidgetItem oluşturur. COL_NAME item'ına da
    navigasyon verisini UserRole ile depolar.
    """
    item = QTableWidgetItem(sort_text)
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    # COL_NAME'e proje metadata'sını göm
    if col == COL_NAME and project_id is not None:
        item.setData(Qt.ItemDataRole.UserRole + 1, project_name)
        item.setData(Qt.ItemDataRole.UserRole + 2, project_id)
        item.setData(Qt.ItemDataRole.UserRole + 3, src_id)
        item.setData(Qt.ItemDataRole.UserRole + 4, tgt_id)
    table.setItem(row, col, item)
