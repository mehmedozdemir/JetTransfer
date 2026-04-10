import pyodbc
from typing import List, Tuple, Any, Optional
from core.db_adapters.base import BaseDBAdapter

class MSSQLAdapter(BaseDBAdapter):
    def connect(self, host, port, database, username, password):
        # Build standard ODBC connection string
        # Assuming ODBC Driver 17 is installed. Will fallback or make customizable in future.
        port_str = f",{port}" if port else "" # MS SQL uses comma for port in host string
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={host}{port_str};"
            f"DATABASE={database};"
            f"UID={username};"
            f"PWD={password};"
        )
        self.connection = pyodbc.connect(conn_str)
        return self.connection

    def disconnect(self):
        if self.connection:
            self.connection.close()

    def get_schemas(self) -> List[str]:
        cursor = self.connection.cursor()
        cursor.execute("SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA")
        schemas = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return schemas

    def get_tables(self, schema: Optional[str] = None) -> List[str]:
        target_schema = schema if schema else 'dbo'
        cursor = self.connection.cursor()
        cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = ?", (target_schema,))
        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return tables

    def read_chunk(self, table_name: str, batch_size: int, offset: int = 0, pk_column: Optional[str] = None, last_pk: Optional[Any] = None, columns: Optional[List[str]] = None) -> Tuple[List[tuple], List[str]]:
        cursor = self.connection.cursor()
        
        cols_sql = "*"
        if columns:
            cols_sql = ",".join([f'[{c}]' for c in columns])
            
        if pk_column and last_pk is not None:
             query = f"SELECT TOP {batch_size} {cols_sql} FROM {table_name} WHERE {pk_column} > ? ORDER BY {pk_column}"
             cursor.execute(query, (last_pk,))
        else:
             # Offset requires ORDER BY in SQL Server
             query = f"SELECT {cols_sql} FROM {table_name} ORDER BY (SELECT NULL) OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
             cursor.execute(query, (offset, batch_size))
             
        records = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        cursor.close()
        
        # Convert pyodbc.Row to standard tuples
        records = [tuple(row) for row in records]
        return records, columns

    def write_chunk(self, table_name: str, records: List[tuple], columns: List[str]):
        if not records:
            return
        cursor = self.connection.cursor()
        # Ensure fast bulk inserts
        cursor.fast_executemany = True
        
        placeholders = ','.join(['?'] * len(columns))
        col_names = ','.join([f'[{col}]' for col in columns])
        insert_query = f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})"
        
        cursor.executemany(insert_query, records)
        self.connection.commit()
        cursor.close()

    def count_rows(self, table_name: str) -> int:
        cursor = self.connection.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        cursor.close()
        return count

    def get_sqlalchemy_url(self, host, port, database, username, password) -> str:
        port_str = f":{port}" if port else ""
        return f"mssql+pyodbc://{username}:{password}@{host}{port_str}/{database}?driver=ODBC+Driver+17+for+SQL+Server"
