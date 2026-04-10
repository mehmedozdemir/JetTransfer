from PyQt6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QPushButton, QMessageBox, QHBoxLayout, QLabel, QFrame, QWidget
from PyQt6.QtCore import Qt
from core.crypto import CryptoManager
from core.local_db import get_connection
from core.db_adapters.postgres import PostgresAdapter
from core.db_adapters.mssql import MSSQLAdapter
from core.db_adapters.oracle import OracleAdapter

import qtawesome as qta

class AddConnectionDialog(QDialog):
    def __init__(self, parent=None, connection_id=None):
        super().__init__(parent)
        self.connection_id = connection_id
        self.is_edit = connection_id is not None
        
        title = "Bağlantıyı Düzenle" if self.is_edit else "Yeni Veritabanı Bağlantısı"
        self.setWindowTitle(title)
        self.resize(450, 480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint) # Remove ? button
        
        self.setStyleSheet("""
            QDialog { background-color: #1e1e2e; color: #cdd6f4; font-family: 'Segoe UI', Inter; }
            QLineEdit, QComboBox { 
                background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; 
                border-radius: 6px; padding: 8px; font-size: 14px;
            }
            QLineEdit:focus, QComboBox:focus { border: 1px solid #89b4fa; }
            QPushButton { 
                background-color: #89b4fa; color: #11111b; border-radius: 6px; 
                padding: 8px 16px; font-weight: bold; font-size: 14px;
            }
            QPushButton:hover { background-color: #b4befe; }
            QLabel { font-size: 14px; font-weight: 500; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header title
        header = QLabel(title)
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #89b4fa; padding-bottom: 10px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        form = QFormLayout()
        form.setSpacing(12)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Örn: Ankara Merkez SQL")
        self.type_combo = QComboBox()
        self.type_combo.addItems(["PostgreSQL", "MS SQL Server", "Oracle"])
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("192.168.1.100 veya localhost")
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("Boş bırakılırsa varsayılan")
        self.db_input = QLineEdit()
        self.db_input.setPlaceholderText("Veritabanı veya Servis Adı")
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Kullanıcı Adı")
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_input.setPlaceholderText("Parola")
        
        form.addRow("Bağlantı Adı (Alias):", self.name_input)
        form.addRow("Veritabanı Türü:", self.type_combo)
        form.addRow("Sunucu IP / Host:", self.host_input)
        form.addRow("Port:", self.port_input)
        form.addRow("Veritabanı (Şema):", self.db_input)
        form.addRow("Kullanıcı Adı:", self.user_input)
        form.addRow("Şifre:", self.pass_input)
        
        form_widget = QWidget()
        form_widget.setLayout(form)
        layout.addWidget(form_widget)
        
        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.btn_test = QPushButton("Sına")
        self.btn_test.setIcon(qta.icon('fa5s.plug', color='#11111b'))
        self.btn_test.setStyleSheet("background-color: #f9e2af; color: #11111b;")
        self.btn_test.clicked.connect(self.test_connection)
        
        self.btn_save = QPushButton("Kaydet")
        self.btn_save.setIcon(qta.icon('fa5s.save', color='#11111b'))
        self.btn_save.setStyleSheet("background-color: #a6e3a1; color: #11111b;")
        self.btn_save.clicked.connect(self.save_connection)

        self.btn_cancel = QPushButton("İptal")
        self.btn_cancel.setStyleSheet("background-color: #f38ba8; color: #11111b;")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_test)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        
        layout.addLayout(btn_layout)
        
        if self.is_edit:
            self.load_data()

    def load_data(self):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name, db_type, host, port, database, username, password_encrypted FROM connections WHERE id = ?", (self.connection_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                self.name_input.setText(row[0])
                self.type_combo.setCurrentText(row[1])
                self.host_input.setText(row[2])
                self.port_input.setText(str(row[3]) if row[3] else "")
                self.db_input.setText(row[4])
                self.user_input.setText(row[5])
                if row[6]:
                    self.pass_input.setText(CryptoManager.decrypt(row[6]))
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Bağlantı bilgileri yüklenemedi: {e}")

    def test_connection(self):
        db_type = self.type_combo.currentText()
        host = self.host_input.text().strip()
        port = self.port_input.text().strip()
        database = self.db_input.text().strip()
        username = self.user_input.text().strip()
        password = self.pass_input.text()
        
        if not host or not database or not username:
            QMessageBox.warning(self, "Uyarı", "Sınama için host, veritabanı ve kullanıcı adı zorunludur.")
            return

        adapter = None
        if db_type == "PostgreSQL":
            adapter = PostgresAdapter()
        elif db_type == "MS SQL Server":
            adapter = MSSQLAdapter()
        elif db_type == "Oracle":
            adapter = OracleAdapter()
            
        if adapter:
            self.btn_test.setText("Sınanıyor...")
            self.btn_test.setEnabled(False)
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents() # Force UI refresh
            
            try:
                adapter.connect(host, port, database, username, password)
                QMessageBox.information(self, "Başarılı", "Bağlantı başarıyla kuruldu!")
                adapter.disconnect()
            except Exception as e:
                QMessageBox.critical(self, "Bağlantı Hatası", f"Veritabanına bağlanılamadı:\n\n{str(e)}")
            finally:
                self.btn_test.setText("Sına")
                self.btn_test.setEnabled(True)

    def save_connection(self):
        name = self.name_input.text().strip()
        db_type = self.type_combo.currentText()
        host = self.host_input.text().strip()
        port = self.port_input.text().strip()
        database = self.db_input.text().strip()
        username = self.user_input.text().strip()
        password = self.pass_input.text()
        
        if not all([name, host, database, username]):
            QMessageBox.warning(self, "Hata", "Lütfen port hariç zorunlu alanları doldurun.")
            return
            
        encrypted_pass = CryptoManager.encrypt(password)
        parsed_port = int(port) if port.isdigit() else None
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            if self.is_edit:
                cursor.execute('''
                    UPDATE connections SET name=?, db_type=?, host=?, port=?, database=?, username=?, password_encrypted=?
                    WHERE id=?
                ''', (name, db_type, host, parsed_port, database, username, encrypted_pass, self.connection_id))
            else:
                cursor.execute('''
                    INSERT INTO connections (name, db_type, host, port, database, username, password_encrypted)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (name, db_type, host, parsed_port, database, username, encrypted_pass))
                
            conn.commit()
            conn.close()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "DB Hatası", f"Kayıt işlemi başarısız: {str(e)}")
