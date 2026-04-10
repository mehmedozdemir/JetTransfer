from abc import ABC, abstractmethod
from typing import List, Tuple, Any, Optional

class BaseDBAdapter(ABC):
    def __init__(self):
        self.connection = None

    @abstractmethod
    def connect(self, host, port, database, username, password):
        """Establishes connection to the database"""
        pass

    @abstractmethod
    def disconnect(self):
        """Closes the connection"""
        pass

    @abstractmethod
    def get_schemas(self) -> List[str]:
        """Returns a list of schema names"""
        pass

    @abstractmethod
    def get_tables(self, schema: Optional[str] = None) -> List[str]:
        """Returns a list of table names, optionally filtered by schema"""
        pass

    @abstractmethod
    def read_chunk(self, table_name: str, batch_size: int, offset: int = 0, pk_column: Optional[str] = None, last_pk: Optional[Any] = None, columns: Optional[List[str]] = None) -> Tuple[List[tuple], List[str]]:
        """
        Reads a chunk of data.
        Returns a tuple of (List of records, List of column names).
        """
        pass

    @abstractmethod
    def write_chunk(self, table_name: str, records: List[tuple], columns: List[str]):
        """
        Writes a chunk of data to the target table using fast bulk methods (executemany).
        """
        pass

    @abstractmethod
    def count_rows(self, table_name: str) -> int:
        """Counts the total rows in a table."""
        pass

    @abstractmethod
    def get_sqlalchemy_url(self, host, port, database, username, password) -> str:
        """Returns the SQLAlchemy connection URL for DDL tasks"""
        pass
