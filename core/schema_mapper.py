from sqlalchemy import create_engine, MetaData, Table, Column

class SchemaMapper:
    @staticmethod
    def create_table_if_not_exists(source_sqlalchemy_url: str, target_sqlalchemy_url: str, table_name: str):
        """
        Reads the table definition from the source using SQLAlchemy reflection,
        and creates it on the target if it does not exist.
        """
        source_engine = create_engine(source_sqlalchemy_url)
        target_engine = create_engine(target_sqlalchemy_url)

        source_metadata = MetaData()
        target_metadata = MetaData()

        try:
            # Reflect the table from source
            source_table = Table(table_name, source_metadata, autoload_with=source_engine)

            # Replicate columns for the target table, converting to generic SQL types
            columns = []
            for col in source_table.columns:
                # Convert dialect-specific types (like MSSQL BIT) to generic (like BOOLEAN)
                generic_type = col.type.as_generic() if hasattr(col.type, 'as_generic') else col.type
                
                # Re-create the column strictly with cross-platform attributes
                new_col = Column(col.name, generic_type, primary_key=col.primary_key, nullable=col.nullable)
                columns.append(new_col)

            target_table = Table(
                table_name,
                target_metadata,
                *columns
            )

            # Create the table on target if it doesn't exist
            target_metadata.create_all(target_engine, tables=[target_table])
            return True, f"Table '{table_name}' checked/created successfully."
        except Exception as e:
            return False, f"Error creating table '{table_name}': {str(e)}"
