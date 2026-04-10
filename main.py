import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QStackedWidget, QListWidget, QListWidgetItem, QLabel
from PyQt6.QtCore import Qt, QSize
import qtawesome as qta
from ui.connections_tab import ConnectionsTab
from ui.transfers_tab import TransfersTab
from core.local_db import init_db

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JetTransfer - Enterprise Data Migration Engine")
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Sidebar Menu
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(260)
        self.sidebar.setIconSize(QSize(22, 22))
        self.sidebar.setObjectName("sidebar")
        
        # Add Logo/Header to sidebar
        logo_item = QListWidgetItem("   JetTransfer")
        logo_item.setIcon(qta.icon('fa5s.rocket', color='#89b4fa'))
        logo_item.setFlags(Qt.ItemFlag.NoItemFlags) # Make it unselectable header
        logo_item.setSizeHint(QSize(260, 80))
        self.sidebar.addItem(logo_item)
        
        # Dashboard Tab
        item_dash = QListWidgetItem("   Gösterge Paneli")
        item_dash.setIcon(qta.icon('fa5s.chart-pie', color='#cdd6f4'))
        item_dash.setSizeHint(QSize(260, 50))
        self.sidebar.addItem(item_dash)
        
        # Connections Tab
        item_conn = QListWidgetItem("   Bağlantı Yönetimi")
        item_conn.setIcon(qta.icon('fa5s.database', color='#cdd6f4'))
        item_conn.setSizeHint(QSize(260, 50))
        self.sidebar.addItem(item_conn)
        
        self.sidebar.currentRowChanged.connect(self.switch_tab)
        
        # Main Area
        self.stack = QStackedWidget()
        
        self.transfers_tab = TransfersTab()
        self.connections_tab = ConnectionsTab()
        
        self.stack.addWidget(self.transfers_tab)
        self.stack.addWidget(self.connections_tab)
        
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack)
        
        self.sidebar.setCurrentRow(1) # Start at dash

    def switch_tab(self, row):
        if row > 0: # row 0 is the logo
            self.stack.setCurrentIndex(row - 1)

if __name__ == "__main__":
    init_db()
    app = QApplication(sys.argv)
    
    app.setStyleSheet("""
        QMainWindow { background-color: #11111b; color: #cdd6f4; }
        QWidget { background-color: #1e1e2e; color: #cdd6f4; font-family: 'Segoe UI', Inter; font-size: 10pt; }
        
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
        
        QPushButton { background-color: #89b4fa; color: #11111b; border-radius: 6px; padding: 8px 16px; font-weight: bold; font-size: 13px;}
        QPushButton:hover { background-color: #b4befe; }
        QPushButton:pressed { background-color: #74c7ec; }
        QLineEdit, QComboBox { background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 6px; padding: 8px; }
        QProgressBar { text-align: center; color: #11111b; font-weight: bold; background-color: #313244; border-radius: 5px; }
        QProgressBar::chunk { background-color: #a6e3a1; border-radius: 5px; }
        QTableWidget { background-color: #11111b; color: #cdd6f4; gridline-color: transparent; border: 1px solid #313244; border-radius: 8px; selection-background-color: #313244; }
        QTableWidget::item { border-bottom: 1px solid #313244; padding: 5px; }
        QHeaderView::section { background-color: #181825; color: #a6adc8; padding: 10px; font-weight: bold; border: none; border-bottom: 2px solid #313244; }
        QLabel { background: transparent; }
    """)

    window = MainWindow()
    window.resize(1150, 750)
    window.show()
    sys.exit(app.exec())
