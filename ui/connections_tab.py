from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QMessageBox
from PyQt6.QtCore import Qt
import qtawesome as qta
from core.local_db import get_connection
from ui.add_connection_dialog import AddConnectionDialog

class ConnectionsTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        tools = QHBoxLayout()
        self.btn_add = QPushButton(" Yeni Bağlantı Ekle")
        self.btn_add.setIcon(qta.icon('fa5s.plus', color='#11111b'))
        self.btn_add.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-size: 14px; padding: 10px; border-radius: 6px; font-weight: bold;")
        self.btn_add.clicked.connect(self.open_add_dialog)
        
        self.btn_refresh = QPushButton(" Yenile")
        self.btn_refresh.setIcon(qta.icon('fa5s.sync', color='#cdd6f4'))
        self.btn_refresh.setStyleSheet("background-color: #313244; color: #cdd6f4; font-size: 14px; padding: 10px; border-radius: 6px; font-weight: bold;")
        self.btn_refresh.clicked.connect(self.load_data)
        
        tools.addWidget(self.btn_add)
        tools.addWidget(self.btn_refresh)
        tools.addStretch()
        layout.addLayout(tools)
        
        self.table = QTableWidget()
        self.table.setColumnCount(7) 
        self.table.setHorizontalHeaderLabels(["ID", "İsim (Alias)", "Tür", "Host / IP", "Veritabanı", "Kullanıcı", "İşlemler"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet("QTableWidget { font-size: 13px; font-weight: 500; } QHeaderView::section { font-size: 14px; background-color:#181825; padding:8px; }")
        
        layout.addWidget(self.table)
        
        self.load_data()

    def load_data(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, db_type, host, database, username FROM connections ORDER BY id DESC")
        rows = cursor.fetchall()
        
        self.table.setRowCount(len(rows))
        for row_idx, row_data in enumerate(rows):
            for col_idx, col_data in enumerate(row_data):
                item = QTableWidgetItem(str(col_data))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_idx, col_idx, item)
            
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setSpacing(10)
            
            btn_edit = QPushButton()
            btn_edit.setIcon(qta.icon('fa5s.edit', color='#f9e2af'))
            btn_edit.setToolTip("Düzenle")
            btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_edit.setStyleSheet("background: transparent; border: none;")
            conn_id = row_data[0] 
            btn_edit.clicked.connect(lambda checked, cid=conn_id: self.open_edit_dialog(cid))
            
            btn_delete = QPushButton()
            btn_delete.setIcon(qta.icon('fa5s.trash', color='#f38ba8'))
            btn_delete.setToolTip("Sil")
            btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_delete.setStyleSheet("background: transparent; border: none;")
            btn_delete.clicked.connect(lambda checked, cid=conn_id: self.delete_connection(cid))
            
            action_layout.addStretch()
            action_layout.addWidget(btn_edit)
            action_layout.addWidget(btn_delete)
            action_layout.addStretch()
            
            self.table.setCellWidget(row_idx, 6, action_widget)
                
        self.table.resizeRowsToContents()
        conn.close()

    def open_add_dialog(self):
        dialog = AddConnectionDialog(self)
        if dialog.exec():
            self.load_data()

    def open_edit_dialog(self, connection_id):
        dialog = AddConnectionDialog(self, connection_id=connection_id)
        if dialog.exec():
            self.load_data()
            
    def delete_connection(self, connection_id):
        reply = QMessageBox.question(self, "Onay", "Bu bağlantıyı silmek istediğinize emin misiniz?", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM connections WHERE id = ?", (connection_id,))
            conn.commit()
            conn.close()
            self.load_data()
