import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout,
    QStackedWidget, QListWidget, QListWidgetItem, QLabel
)
from PyQt6.QtCore import Qt, QSize
import qtawesome as qta

from ui.projects_tab import ProjectsTab
from ui.transfers_tab import TransfersTab
from ui.connections_tab import ConnectionsTab
from core.local_db import init_db

# ─── Sidebar satır indeksleri ─────────────────────────────────────────────────
_ROW_LOGO        = 0
_ROW_PROJECTS    = 1
_ROW_CONNECTIONS = 2

# ─── Stack indeksleri ─────────────────────────────────────────────────────────
_STACK_PROJECTS    = 0
_STACK_TRANSFERS   = 1
_STACK_CONNECTIONS = 2


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JetTransfer — Enterprise Data Migration Engine")

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Sidebar ───────────────────────────────────────────────────────────
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(260)
        self.sidebar.setIconSize(QSize(22, 22))
        self.sidebar.setObjectName("sidebar")

        # Logo / başlık (seçilemez)
        logo_item = QListWidgetItem("   JetTransfer")
        logo_item.setIcon(qta.icon("fa5s.rocket", color="#89b4fa"))
        logo_item.setFlags(Qt.ItemFlag.NoItemFlags)
        logo_item.setSizeHint(QSize(260, 80))
        self.sidebar.addItem(logo_item)

        # Projeler
        item_projects = QListWidgetItem("   Projeler")
        item_projects.setIcon(qta.icon("fa5s.layer-group", color="#cdd6f4"))
        item_projects.setSizeHint(QSize(260, 50))
        self.sidebar.addItem(item_projects)

        # Bağlantı Yönetimi
        item_conn = QListWidgetItem("   Bağlantı Yönetimi")
        item_conn.setIcon(qta.icon("fa5s.database", color="#cdd6f4"))
        item_conn.setSizeHint(QSize(260, 50))
        self.sidebar.addItem(item_conn)

        self.sidebar.currentRowChanged.connect(self._on_sidebar_changed)

        # ── Stack ─────────────────────────────────────────────────────────────
        self.stack = QStackedWidget()

        self.projects_tab  = ProjectsTab()
        self.transfers_tab = TransfersTab()
        self.connections_tab = ConnectionsTab()

        self.stack.addWidget(self.projects_tab)    # 0
        self.stack.addWidget(self.transfers_tab)   # 1
        self.stack.addWidget(self.connections_tab) # 2

        root_layout.addWidget(self.sidebar)
        root_layout.addWidget(self.stack)

        # ── Sinyal Bağlantıları ───────────────────────────────────────────────
        # Proje listesinden "Projeyi Aç" → transfers ekranına geç
        self.projects_tab.open_project.connect(self._open_project)

        # Aktarımlar ekranından "← Projeye Dön" → projeler ekranına geri dön
        self.transfers_tab.go_back.connect(self._go_back_to_projects)

        # ── İlk Ekran ─────────────────────────────────────────────────────────
        self.sidebar.setCurrentRow(_ROW_PROJECTS)

    # ── Sidebar Navigasyonu ───────────────────────────────────────────────────

    def _on_sidebar_changed(self, row: int):
        if row == _ROW_PROJECTS:
            self.stack.setCurrentIndex(_STACK_PROJECTS)
            self.projects_tab.load_projects()          # Her girişte tazele
        elif row == _ROW_CONNECTIONS:
            self.stack.setCurrentIndex(_STACK_CONNECTIONS)
        # row == _ROW_LOGO → atla

    # ── Proje Açma ────────────────────────────────────────────────────────────

    def _open_project(
        self,
        project_id: int,
        project_name: str,
        source_conn_id: int,
        target_conn_id: int,
    ):
        """ProjectsTab'dan gelen sinyal: seçilen projeyi TransfersTab'da aç."""
        self.transfers_tab.open_project(project_id, project_name, source_conn_id, target_conn_id)
        self.stack.setCurrentIndex(_STACK_TRANSFERS)
        # Sidebar'daki seçimi görsel olarak transferlere taşıma — sidebar'ı pasif yap
        self.sidebar.blockSignals(True)
        self.sidebar.clearSelection()
        self.sidebar.blockSignals(False)

    # ── Geriye Dönüş ─────────────────────────────────────────────────────────

    def _go_back_to_projects(self):
        """TransfersTab'dan gelen sinyal: Projeler listesine dön."""
        self.projects_tab.load_projects()
        self.stack.setCurrentIndex(_STACK_PROJECTS)
        self.sidebar.blockSignals(True)
        self.sidebar.setCurrentRow(_ROW_PROJECTS)
        self.sidebar.blockSignals(False)


# ─────────────────────────────────────────────────────────────────────────────
#  Uygulama Giriş Noktası
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    app = QApplication(sys.argv)

    app.setStyleSheet("""
        QMainWindow { background-color: #11111b; color: #cdd6f4; }
        QWidget {
            background-color: #1e1e2e;
            color: #cdd6f4;
            font-family: 'Segoe UI', Inter;
            font-size: 10pt;
        }

        /* ── Sidebar ── */
        #sidebar {
            background-color: #181825;
            border-right: 1px solid #313244;
            outline: none;
        }
        #sidebar::item {
            color: #a6adc8;
            border-radius: 8px;
            margin: 4px 12px;
            font-size: 15px;
            font-weight: 500;
        }
        #sidebar::item:selected {
            background-color: #313244;
            color: #89b4fa;
            font-weight: bold;
        }
        #sidebar::item:hover:!selected {
            background-color: #1e1e2e;
            color: #cdd6f4;
        }

        /* ── Genel Elemanlar ── */
        QPushButton {
            background-color: #89b4fa; color: #11111b;
            border-radius: 6px; padding: 8px 16px;
            font-weight: bold; font-size: 13px;
        }
        QPushButton:hover   { background-color: #b4befe; }
        QPushButton:pressed { background-color: #74c7ec; }
        QPushButton:disabled { background-color: #45475a; color: #6c7086; }

        QLineEdit, QComboBox {
            background-color: #313244; color: #cdd6f4;
            border: 1px solid #45475a; border-radius: 6px; padding: 8px;
        }
        QComboBox::drop-down { border: none; }
        QComboBox QAbstractItemView {
            background-color: #313244; color: #cdd6f4;
            selection-background-color: #45475a;
        }

        QProgressBar {
            text-align: center; color: #11111b; font-weight: bold;
            background-color: #313244; border-radius: 5px;
        }
        QProgressBar::chunk { background-color: #a6e3a1; border-radius: 5px; }

        QTableWidget {
            background-color: #11111b; color: #cdd6f4;
            gridline-color: transparent;
            border: 1px solid #313244; border-radius: 8px;
            selection-background-color: #313244;
        }
        QTableWidget::item { border-bottom: 1px solid #313244; padding: 5px; }
        QHeaderView::section {
            background-color: #181825; color: #a6adc8;
            padding: 10px; font-weight: bold;
            border: none; border-bottom: 2px solid #313244;
        }

        QLabel         { background: transparent; }
        QScrollBar:vertical {
            background: #1e1e2e; width: 8px; border-radius: 4px;
        }
        QScrollBar::handle:vertical {
            background: #45475a; border-radius: 4px; min-height: 30px;
        }
        QScrollBar::handle:vertical:hover { background: #6c7086; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    """)

    window = MainWindow()
    window.resize(1200, 800)
    window.show()
    sys.exit(app.exec())
