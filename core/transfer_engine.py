from PyQt6.QtCore import QThread, pyqtSignal
from typing import Dict, Any
import time

import json

class TransferEngine(QThread):
    # Signals to communicate with the main UI thread
    progress_signal = pyqtSignal(int, int, str) # transferred_rows, total_rows, status_message
    error_signal = pyqtSignal(str) # error_message
    finished_signal = pyqtSignal()

    def __init__(self, source_adapter, target_adapter, source_table: str, target_table: str, column_mapping: str = None, batch_size: int = 10000):
        super().__init__()
        self.source_adapter = source_adapter
        self.target_adapter = target_adapter
        self.source_table = source_table
        self.target_table = target_table
        self.column_mapping = column_mapping
        self.batch_size = batch_size
        
        self.is_paused = False
        self.is_cancelled = False

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        """Main transfer loop running in the background thread."""
        try:
            total_rows = self.source_adapter.count_rows(self.source_table)
            self.progress_signal.emit(0, total_rows, "Başlıyor...")
            
            offset = 0
            transferred = 0
            
            mapping = {}
            if self.column_mapping:
                mapping = json.loads(self.column_mapping)
            
            source_cols = list(mapping.keys()) if mapping else None
            target_cols = list(mapping.values()) if mapping else None
            
            while transferred < total_rows:
                # Cancel Check
                if self.is_cancelled:
                    self.progress_signal.emit(transferred, total_rows, "İptal Edildi")
                    break
                
                # Pause Check
                while self.is_paused:
                    time.sleep(0.5)
                    if self.is_cancelled:
                        break
                
                if self.is_cancelled:
                    break
                    
                # 1. Read from Source
                records, columns = self.source_adapter.read_chunk(self.source_table, self.batch_size, offset=offset, columns=source_cols)
                
                if not records:
                    break # No more data available
                
                # 2. Write to Target
                tgt_cols_to_write = target_cols if target_cols else columns
                self.target_adapter.write_chunk(self.target_table, records, tgt_cols_to_write)
                
                transferred += len(records)
                offset += self.batch_size
                
                self.progress_signal.emit(transferred, total_rows, f"Devam Ediyor ({transferred}/{total_rows})")
                
            if not self.is_cancelled:
                self.progress_signal.emit(total_rows, total_rows, "Başarıyla Tamamlandı")
                self.finished_signal.emit()
                
        except Exception as e:
            self.error_signal.emit(f"Hata oluştu: {str(e)}")
