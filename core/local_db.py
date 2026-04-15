import sqlite3
import os

DB_PATH = "jettransfer_state.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # connections table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            db_type TEXT NOT NULL,
            host TEXT NOT NULL,
            port INTEGER,
            database TEXT,
            username TEXT,
            password_encrypted TEXT
        )
    ''')
    
    # jobs table for pause/resume tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transfer_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_conn_id INTEGER,
            target_conn_id INTEGER,
            source_schema TEXT,
            target_schema TEXT,
            source_table TEXT,
            target_table TEXT,
            status TEXT, -- 'RUNNING', 'PAUSED', 'FAILED', 'COMPLETED', 'BEKLIYOR'
            last_pk_transferred TEXT,
            rows_transferred INTEGER DEFAULT 0,
            total_rows INTEGER DEFAULT 0,
            column_mapping TEXT,
            custom_ddl TEXT,
            custom_source_sql TEXT,
            max_rows_limit INTEGER DEFAULT 0,
            FOREIGN KEY(source_conn_id) REFERENCES connections(id),
            FOREIGN KEY(target_conn_id) REFERENCES connections(id)
        )
    ''')
    
    # Migrations for existing databases
    try:
        cursor.execute("ALTER TABLE transfer_jobs ADD COLUMN custom_source_sql TEXT")
    except sqlite3.OperationalError:
        pass # Column already exists
        
    try:
        cursor.execute("ALTER TABLE transfer_jobs ADD COLUMN max_rows_limit INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass # Column already exists
        
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
