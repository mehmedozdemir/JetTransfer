import sqlite3
import os
from typing import Optional

DB_PATH = "jettransfer_state.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # --- connections tablosu ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS connections (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            name              TEXT UNIQUE NOT NULL,
            db_type           TEXT NOT NULL,
            host              TEXT NOT NULL,
            port              INTEGER,
            database          TEXT,
            username          TEXT,
            password_encrypted TEXT
        )
    ''')

    # --- projects tablosu (YENİ v2) ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            description     TEXT,
            source_conn_id  INTEGER NOT NULL REFERENCES connections(id),
            target_conn_id  INTEGER NOT NULL REFERENCES connections(id),
            is_archived     INTEGER DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at      TEXT DEFAULT (datetime('now', 'localtime'))
        )
    ''')

    # --- transfer_jobs tablosu ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transfer_jobs (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id          INTEGER REFERENCES projects(id),
            source_conn_id      INTEGER REFERENCES connections(id),
            target_conn_id      INTEGER REFERENCES connections(id),
            source_schema       TEXT,
            target_schema       TEXT,
            source_table        TEXT,
            target_table        TEXT,
            status              TEXT,
            last_pk_transferred TEXT,
            rows_transferred    INTEGER DEFAULT 0,
            total_rows          INTEGER DEFAULT 0,
            column_mapping      TEXT,
            custom_ddl          TEXT,
            custom_source_sql   TEXT,
            max_rows_limit      INTEGER DEFAULT 0,
            created_at          TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at          TEXT DEFAULT (datetime('now', 'localtime'))
        )
    ''')

    # --- Migrations: mevcut veritabanları için kolon eklemeleri ---
    _run_migration(cursor, "ALTER TABLE transfer_jobs ADD COLUMN custom_source_sql TEXT")
    _run_migration(cursor, "ALTER TABLE transfer_jobs ADD COLUMN max_rows_limit INTEGER DEFAULT 0")
    _run_migration(cursor, "ALTER TABLE transfer_jobs ADD COLUMN project_id INTEGER REFERENCES projects(id)")
    # NOT: SQLite'da ALTER TABLE ADD COLUMN, fonksiyon tabanlı DEFAULT desteklemiyor.
    # Bu nedenle DEFAULT NULL kullanılır; değerler INSERT/UPDATE sırasında seçici olarak set edilir.
    _run_migration(cursor, "ALTER TABLE transfer_jobs ADD COLUMN created_at TEXT DEFAULT NULL")
    _run_migration(cursor, "ALTER TABLE transfer_jobs ADD COLUMN updated_at TEXT DEFAULT NULL")

    conn.commit()

    # --- Migration: Mevcut project_id=NULL görevleri fallback projeye taşı ---
    _migrate_orphan_jobs(conn)

    conn.close()


def _run_migration(cursor: sqlite3.Cursor, sql: str):
    """Güvenli migration: kolon zaten varsa hatayı yut."""
    try:
        cursor.execute(sql)
    except sqlite3.OperationalError:
        pass


def _migrate_orphan_jobs(conn: sqlite3.Connection):
    """
    v1'den kalan transfer_jobs (project_id=NULL) kayıtlarını
    'Balıkesir -> Lokal Postgre' adlı bir fallback projeye taşır.
    Bu işlem idempotent'tir (tekrar çalıştırılırsa etkisiz kalır).
    """
    cursor = conn.cursor()

    # Orphan kayıt var mı kontrol et
    cursor.execute("SELECT COUNT(*) FROM transfer_jobs WHERE project_id IS NULL")
    orphan_count = cursor.fetchone()[0]

    if orphan_count == 0:
        return  # Yapılacak bir şey yok

    # Fallback proje zaten oluşturulmuş mu?
    cursor.execute("SELECT id FROM projects WHERE name = 'Balıkesir -> Lokal Postgre'")
    existing = cursor.fetchone()

    if existing:
        fallback_project_id = existing[0]
    else:
        # Orphan görevlerden kaynak/hedef bilgisi al
        cursor.execute("""
            SELECT source_conn_id, target_conn_id
            FROM transfer_jobs
            WHERE project_id IS NULL
              AND source_conn_id IS NOT NULL
              AND target_conn_id IS NOT NULL
            LIMIT 1
        """)
        ref_job = cursor.fetchone()

        if not ref_job:
            return  # Bağlantı bilgisi olmayan orphan'lar — taşınamaz

        cursor.execute("""
            INSERT INTO projects (name, description, source_conn_id, target_conn_id)
            VALUES (?, ?, ?, ?)
        """, (
            "Balıkesir -> Lokal Postgre",
            "v1'den taşınan mevcut aktarım görevleri.",
            ref_job[0],
            ref_job[1],
        ))
        conn.commit()
        fallback_project_id = cursor.lastrowid

    # Tüm orphan'ları bu projeye bağla
    cursor.execute(
        "UPDATE transfer_jobs SET project_id = ? WHERE project_id IS NULL",
        (fallback_project_id,)
    )
    conn.commit()


# ─────────────────────────────────────────────
#  CRUD: Projects
# ─────────────────────────────────────────────

def create_project(name: str, description: str, source_conn_id: int, target_conn_id: int) -> int:
    """Yeni proje oluşturur; oluşturulan projenin id'sini döner."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO projects (name, description, source_conn_id, target_conn_id)
        VALUES (?, ?, ?, ?)
    """, (name, description, source_conn_id, target_conn_id))
    conn.commit()
    project_id = cursor.lastrowid
    conn.close()
    return project_id


def get_all_projects(include_archived: bool = False) -> list[sqlite3.Row]:
    """
    Tüm projeleri istatistiklerle birlikte döner.
    Her satır: id, name, description, source_conn_id, target_conn_id,
                is_archived, created_at, updated_at,
                source_name, source_type, target_name, target_type,
                total_jobs, completed_jobs, failed_jobs, running_jobs, total_rows_transferred
    """
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT
            p.id,
            p.name,
            p.description,
            p.source_conn_id,
            p.target_conn_id,
            p.is_archived,
            p.created_at,
            p.updated_at,
            sc.name        AS source_name,
            sc.db_type     AS source_type,
            tc.name        AS target_name,
            tc.db_type     AS target_type,
            COUNT(j.id)                                          AS total_jobs,
            SUM(CASE WHEN j.status = 'COMPLETED' THEN 1 ELSE 0 END) AS completed_jobs,
            SUM(CASE WHEN j.status = 'FAILED'    THEN 1 ELSE 0 END) AS failed_jobs,
            SUM(CASE WHEN j.status = 'RUNNING'   THEN 1 ELSE 0 END) AS running_jobs,
            COALESCE(SUM(j.rows_transferred), 0)                 AS total_rows_transferred
        FROM projects p
        LEFT JOIN connections sc ON p.source_conn_id = sc.id
        LEFT JOIN connections tc ON p.target_conn_id = tc.id
        LEFT JOIN transfer_jobs j ON j.project_id = p.id
        WHERE p.is_archived = ?
        GROUP BY p.id
        ORDER BY p.updated_at DESC
    """
    cursor.execute(query, (1 if include_archived else 0,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_project(project_id: int) -> Optional[sqlite3.Row]:
    """Tek proje kaydını döner."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, sc.name AS source_name, sc.db_type AS source_type,
               tc.name AS target_name, tc.db_type AS target_type
        FROM projects p
        LEFT JOIN connections sc ON p.source_conn_id = sc.id
        LEFT JOIN connections tc ON p.target_conn_id = tc.id
        WHERE p.id = ?
    """, (project_id,))
    row = cursor.fetchone()
    conn.close()
    return row


def update_project(project_id: int, name: str, description: str,
                   source_conn_id: int, target_conn_id: int):
    """Proje adı, açıklaması ve bağlantılarını günceller."""
    conn = get_connection()
    conn.execute("""
        UPDATE projects
        SET name = ?, description = ?, source_conn_id = ?, target_conn_id = ?,
            updated_at = datetime('now', 'localtime')
        WHERE id = ?
    """, (name, description, source_conn_id, target_conn_id, project_id))
    conn.commit()
    conn.close()


def archive_project(project_id: int, archived: bool = True):
    """Projeyi arşivler veya arşivden çıkarır."""
    conn = get_connection()
    conn.execute("""
        UPDATE projects SET is_archived = ?, updated_at = datetime('now', 'localtime')
        WHERE id = ?
    """, (1 if archived else 0, project_id))
    conn.commit()
    conn.close()


def delete_project(project_id: int):
    """Projeyi ve bağlı tüm görevleri siler."""
    conn = get_connection()
    conn.execute("DELETE FROM transfer_jobs WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()


def touch_project(project_id: int):
    """Projenin updated_at alanını günceller (görev değişikliğinde çağrılır)."""
    conn = get_connection()
    conn.execute(
        "UPDATE projects SET updated_at = datetime('now', 'localtime') WHERE id = ?",
        (project_id,)
    )
    conn.commit()
    conn.close()


if __name__ == '__main__':
    init_db()
