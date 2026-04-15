from PyQt6.QtCore import QThread, pyqtSignal
from typing import Dict, Any
import time

import json

class TransferEngine(QThread):
    # Signals to communicate with the main UI thread
    progress_signal = pyqtSignal(int, int, str) # transferred_rows, total_rows, status_message
    error_signal = pyqtSignal(str) # error_message
    finished_signal = pyqtSignal()

    def __init__(self, source_adapter, target_adapter, source_table: str, target_table: str, column_mapping: str = None, batch_size: int = 10000, custom_source_sql: str = None, max_rows_limit: int = 0):
        super().__init__()
        self.source_adapter = source_adapter
        self.target_adapter = target_adapter
        self.source_table = source_table
        self.target_table = target_table
        self.column_mapping = column_mapping
        self.batch_size = batch_size
        self.custom_source_sql = custom_source_sql
        self.max_rows_limit = max_rows_limit
        
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
            total_rows = 0
            if self.custom_source_sql:
                try:
                    count_cursor = self.source_adapter.connection.cursor()
                    count_cursor.execute(f"SELECT COUNT(*) FROM ({self.custom_source_sql}) as filter_t")
                    total_rows = count_cursor.fetchone()[0]
                    count_cursor.close()
                except Exception as e:
                    # Bazı veritabanları bu wrapper yapıyı kabul etmeyebilir (Örn. Oracle raw query)
                    # Hata yutulur ve limit varsa limit atanır, yoksa bilinmeyen toplam (0) kalır.
                    total_rows = self.max_rows_limit if self.max_rows_limit > 0 else 0
            else:
                total_rows = self.source_adapter.count_rows(self.source_table)
                
            if self.max_rows_limit > 0:
                total_rows = min(total_rows, self.max_rows_limit) if total_rows > 0 else self.max_rows_limit

            self.progress_signal.emit(0, total_rows, "Başlıyor...")
            
            offset = 0
            transferred = 0
            
            mapping = {}
            if self.column_mapping:
                mapping = json.loads(self.column_mapping)
            
            source_cols = list(mapping.keys()) if mapping else None
            target_cols = list(mapping.values()) if mapping else None

            # Özelleştirilmiş SQL kullanıldıysa doğrudan Cursor Fetch döngüsü işletilir
            if self.custom_source_sql:
                cursor = self.source_adapter.connection.cursor()
                cursor.execute(self.custom_source_sql)
                
                columns = [desc[0] for desc in cursor.description]
                
                # Hedef tablo için kaydedilecek satır ve sütun haritasını hizala
                tgt_cols_to_write = []
                col_indices = []
                # DB-API column names might be upper/lower depending on dialect. Normalize them.
                col_name_map = {sc.lower(): sc for sc in (source_cols or [])}
                
                for idx, col in enumerate(columns):
                    col_key = col.lower()
                    if not source_cols or col_key in col_name_map:
                        original_src_col = col_name_map[col_key] if source_cols else col
                        tgt_cols_to_write.append(mapping.get(original_src_col, col))
                        col_indices.append(idx)
                        
                while transferred < total_rows if total_rows > 0 and not (total_rows == 0 and self.max_rows_limit == 0) else True:
                    if self.is_cancelled:
                        self.progress_signal.emit(transferred, total_rows, "İptal Edildi")
                        break
                        
                    while self.is_paused:
                        time.sleep(0.5)
                        if self.is_cancelled:
                            break
                    if self.is_cancelled: break
                    
                    fetch_size = self.batch_size
                    if self.max_rows_limit > 0:
                        fetch_size = min(self.batch_size, self.max_rows_limit - transferred)
                        
                    records = cursor.fetchmany(fetch_size)
                    if not records:
                        break
                        
                    filtered_records = []
                    for row in records:
                        filtered_records.append(tuple(row[i] for i in col_indices))
                        
                    self.target_adapter.write_chunk(self.target_table, filtered_records, tgt_cols_to_write)
                    transferred += len(filtered_records)
                    self.progress_signal.emit(transferred, total_rows, f"Filtreli Aktarım ({transferred}/{total_rows})")
                    
                    if self.max_rows_limit > 0 and transferred >= self.max_rows_limit:
                        break
                        
                cursor.close()

            # Standart Offset Limit mekanizması (Orjinal hal)
            else:
                while transferred < total_rows if total_rows > 0 else True:
                    if self.is_cancelled:
                        self.progress_signal.emit(transferred, total_rows, "İptal Edildi")
                        break
                    
                    while self.is_paused:
                        time.sleep(0.5)
                        if self.is_cancelled: break
                        
                    if self.is_cancelled: break
                    
                    batch_to_read = self.batch_size
                    if self.max_rows_limit > 0:
                         batch_to_read = min(self.batch_size, self.max_rows_limit - transferred)
                         
                    records, columns = self.source_adapter.read_chunk(self.source_table, batch_to_read, offset=offset, columns=source_cols)
                    
                    if not records:
                        break # Veri bitti
                    
                    tgt_cols_to_write = target_cols if target_cols else columns
                    self.target_adapter.write_chunk(self.target_table, records, tgt_cols_to_write)
                    
                    transferred += len(records)
                    offset += batch_to_read
                    
                    self.progress_signal.emit(transferred, total_rows, f"Toplu Aktarım ({transferred}/{total_rows})")
                    
                    if self.max_rows_limit > 0 and transferred >= self.max_rows_limit:
                        break
                
            if not self.is_cancelled:
                self.progress_signal.emit(transferred, total_rows, "Başarıyla Tamamlandı")
                self.finished_signal.emit()
                
        except Exception as e:
            self.error_signal.emit(f"Hata oluştu: {str(e)}")
