import oracledb
from typing import List, Tuple, Any, Optional
from core.db_adapters.base import BaseDBAdapter

class OracleAdapter(BaseDBAdapter):
    def connect(self, host, port, database, username, password):
        # Oracle thin mode DSN
        dsn = f"{host}:{port if port else 1521}/{database}"
        self.connection = oracledb.connect(user=username, password=password, dsn=dsn)
        return self.connection

    def disconnect(self):
        if self.connection:
            self.connection.close()

    def get_schemas(self) -> List[str]:
        cursor = self.connection.cursor()
        cursor.execute("SELECT username FROM all_users ORDER BY username")
        schemas = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return schemas

    def get_tables(self, schema: Optional[str] = None) -> List[str]:
        cursor = self.connection.cursor()
        if schema:
            cursor.execute("SELECT table_name FROM all_tables WHERE owner = :schema", schema=schema)
        else:
            cursor.execute("SELECT table_name FROM user_tables")
        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return tables

    def read_chunk(self, table_name: str, batch_size: int, offset: int = 0, pk_column: Optional[str] = None, last_pk: Optional[Any] = None, columns: Optional[List[str]] = None) -> Tuple[List[tuple], List[str]]:
        cursor = self.connection.cursor()
        
        cols_sql = "*"
        if columns:
             cols_sql = ",".join([f'"{c}"' for c in columns])
             
        if pk_column and last_pk is not None:
             query = f"SELECT {cols_sql} FROM {table_name} WHERE {pk_column} > :last_pk ORDER BY {pk_column} FETCH NEXT :batch_size ROWS ONLY"
             cursor.execute(query, last_pk=last_pk, batch_size=batch_size)
        else:
             # OFFSET works in Oracle 12c+
             query = f"SELECT {cols_sql} FROM {table_name} OFFSET :offset ROWS FETCH NEXT :batch_size ROWS ONLY"
             cursor.execute(query, offset=offset, batch_size=batch_size)
             
        records = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        cursor.close()
        return records, columns

    def write_chunk(self, table_name: str, records: List[tuple], columns: List[str]):
        if not records:
            return
        # Oracle handles bulk inserts incredibly well with executemany
        cursor = self.connection.cursor()
        
        placeholders = ','.join([f':{i+1}' for i in range(len(columns))])
        col_names = ','.join([f'"{col}"' for col in columns])
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
        port_str = f":{port}" if port else ":1521"
        return f"oracle+oracledb://{username}:{password}@{host}{port_str}/?service_name={database}"
