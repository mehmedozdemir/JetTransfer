from sqlalchemy import create_engine, MetaData, Table, Column
from sqlalchemy.schema import CreateTable
from sqlalchemy.types import String, Numeric, Integer, Float

class SchemaValidator:
    
    @staticmethod
    def get_table_schema(sqlalchemy_url: str, table_name: str, schema: str = None):
        """Returns a list of dictionaries with column details from a table."""
        engine = create_engine(sqlalchemy_url)
        metadata = MetaData()
        table = Table(table_name, metadata, schema=schema, autoload_with=engine)
        
        schema_info = []
        for c in table.columns:
            ctype_name = type(c.type).__name__
            schema_info.append({
                "name": c.name,
                "type": ctype_name,
                "primary_key": c.primary_key,
                "nullable": c.nullable
            })
        return schema_info

    @staticmethod
    def generate_target_ddl(source_url: str, target_url: str, source_table_name: str, target_table_name: str, source_schema: str = None, target_schema: str = None) -> str:
        """
        Reads the source table, extracts structural blueprint, genericizes the data types,
        and generates a safe CREATE TABLE SQL script compatible with the target database dialect.
        """
        src_engine = create_engine(source_url)
        tgt_engine = create_engine(target_url)
        
        src_md = MetaData()
        src_table = Table(source_table_name, src_md, schema=source_schema, autoload_with=src_engine)
        
        tgt_md = MetaData()
        columns = []
        
        for c in src_table.columns:
            try:
                if hasattr(c.type, 'as_generic'):
                    base_type_class = type(c.type.as_generic())
                else:
                    base_type_class = type(c.type)
                
                # Try to preserve lengths or precision if applicable
                kwargs = {}
                if hasattr(c.type, 'length') and c.type.length is not None:
                    # Some dialects might use MAX string lengths which are extremely large or "max" string literal
                    if isinstance(c.type.length, int):
                        kwargs['length'] = c.type.length
                
                if hasattr(c.type, 'precision') and c.type.precision is not None:
                    kwargs['precision'] = c.type.precision
                if hasattr(c.type, 'scale') and c.type.scale is not None:
                    kwargs['scale'] = c.type.scale
                    
                generic_type_instance = base_type_class(**kwargs)
                
                new_col = Column(c.name, generic_type_instance, primary_key=c.primary_key, nullable=c.nullable)
                columns.append(new_col)
            except Exception as e:
                # Fallback to simple String if translation utterly fails
                columns.append(Column(c.name, String(255), primary_key=c.primary_key, nullable=c.nullable))
            
        tgt_table = Table(target_table_name, tgt_md, *columns, schema=target_schema)
        
        # Compile against the target engine's dialect
        create_stmt = CreateTable(tgt_table).compile(tgt_engine)
        return str(create_stmt).strip()

