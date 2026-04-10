from PyQt6.QtWidgets import QMainWindow, QTabWidget
from ui.connections_tab import ConnectionsTab
from ui.transfers_tab import TransfersTab

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JetTransfer - Enterprise Data Migration Engine")
        
        # Main Tab Widget integrating features
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Initialize Tabs
        self.transfers_tab = TransfersTab()
        self.connections_tab = ConnectionsTab()
        
        # Add to window
        self.tabs.addTab(self.transfers_tab, "Aktarım Gösterge Paneli (Dashboard)")
        self.tabs.addTab(self.connections_tab, "Sunucu Bağlantıları Yönetimi")
