import psycopg2
from typing import List, Tuple, Any, Optional
from core.db_adapters.base import BaseDBAdapter

class PostgresAdapter(BaseDBAdapter):
    def connect(self, host, port, database, username, password):
        self.connection = psycopg2.connect(
            host=host,
            port=port if port else 5432,
            database=database,
            user=username,
            password=password
        )
        return self.connection

    def disconnect(self):
        if self.connection:
            self.connection.close()

    def get_schemas(self) -> List[str]:
        cursor = self.connection.cursor()
        cursor.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('information_schema', 'pg_catalog') AND schema_name NOT LIKE 'pg_toast%%'")
        schemas = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return schemas

    def get_tables(self, schema: Optional[str] = None) -> List[str]:
        target_schema = schema if schema else 'public'
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = %s AND table_type = 'BASE TABLE'
        """, (target_schema,))
        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return tables

    def read_chunk(self, table_name: str, batch_size: int, offset: int = 0, pk_column: Optional[str] = None, last_pk: Optional[Any] = None, columns: Optional[List[str]] = None) -> Tuple[List[tuple], List[str]]:
        cursor = self.connection.cursor()
        
        cols_sql = "*"
        if columns:
            cols_sql = ",".join([f'"{c}"' for c in columns])
            
        query = f"SELECT {cols_sql} FROM {table_name}"
        params = []
        
        if pk_column and last_pk is not None:
             query += f" WHERE {pk_column} > %s ORDER BY {pk_column} LIMIT %s"
             params.extend([last_pk, batch_size])
        else:
             query += " LIMIT %s OFFSET %s"
             params.extend([batch_size, offset])
             
        cursor.execute(query, params)
        records = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        cursor.close()
        return records, columns

    def write_chunk(self, table_name: str, records: List[tuple], columns: List[str]):
        if not records:
            return
        cursor = self.connection.cursor()
        placeholders = ','.join(['%s'] * len(columns))
        # Ensure column names are quoted exactly in case they use reserved keywords
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
        port_str = f":{port}" if port else ":5432"
        return f"postgresql+psycopg2://{username}:{password}@{host}{port_str}/{database}"
