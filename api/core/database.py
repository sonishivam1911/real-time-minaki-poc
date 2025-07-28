import pandas as pd
from sqlalchemy import create_engine, text
import json
from core.config import settings

class PostgresCRUD:
    def __init__(self, db_uri):
        self.engine = create_engine(db_uri)
    
    def create_table(self, table_name, dataframe):
        """Create a table in PostgreSQL from a pandas DataFrame."""
        # Handle JSON columns
        for col in dataframe.columns:
            if dataframe[col].apply(lambda x: isinstance(x, (dict, list))).any():
                dataframe[col] = dataframe[col].apply(lambda x: json.dumps(x) if x else None)
                
        try:
            dataframe.to_sql(table_name, con=self.engine, if_exists='replace', index=False)
            return True
        except Exception as e:
            print(f"Error creating table '{table_name}': {e}")
            return False
    
    def read_table(self, table_name):
        """Read a table from PostgreSQL into a pandas DataFrame."""
        try:
            query = f"SELECT * FROM {table_name}"
            df = pd.read_sql(query, self.engine)
            return df
        except Exception as e:
            print(f"Error reading table '{table_name}': {e}")
            return pd.DataFrame()
    
    def execute_query(self, query, return_data=False):
        """Execute a SQL query."""
        try:
            with self.engine.connect() as connection:
                if return_data:
                    cursor_result = connection.execute(text(query))
                    rows = cursor_result.fetchall()
                    columns = cursor_result.keys()
                    df = pd.DataFrame(rows, columns=columns)
                    return df
                else:
                    connection.execute(text(query))
                    return True
        except Exception as e:
            print(f"Error executing query: {e}")
            return False if not return_data else pd.DataFrame()
    
    def create_insert_statements(self, df, table_name):
        """
        Generate SQL INSERT statements for each row in a DataFrame.
        Properly handles different data types including lists and JSON.
        
        Args:
            df (pandas.DataFrame): DataFrame containing the data to insert
            table_name (str): Name of the target database table
            
        Returns:
            list: List of SQL INSERT statements
        """
        # If DataFrame is empty, return empty list
        if df.empty:
            return []
            
        insert_statements = []
        # Use double quotes for column names to handle special characters and reserved words
        columns = [f'"{col}"' for col in df.columns]
        columns_str = ", ".join(columns)
        
        for _, row in df.iterrows():
            values = []
            for value in row:

                if value is None or (isinstance(value, float) and pd.isna(value)):
                    values.append("NULL")
                
                elif isinstance(value, str):
                    safe_val = value.replace("'", "''")
                    values.append(f"'{safe_val}'")
                
                elif isinstance(value, dict):
                    try:
                        json_val = json.dumps(value).replace("'", "''")
                        values.append(f"'{json_val}'")
                    except (TypeError, ValueError):
                        # If JSON conversion fails, use string representation
                        safe_val = str(value).replace("'", "''")
                        values.append(f"'{safe_val}'")
                
                # Handle list values (convert to PostgreSQL array format)
                elif isinstance(value, list):
                    try:
                        list_elements = []
                        for item in value:
                            if item is None:
                                list_elements.append("NULL")
                            elif isinstance(item, str):
                                safe_item = item.replace("'", "''")
                                list_elements.append(f'"{safe_item}"')
                            else:
                                list_elements.append(str(item))
                        
                        array_str = "ARRAY[" + ", ".join(list_elements) + "]"
                        values.append(array_str)
                    except Exception:
                        # Fallback for complex lists
                        json_val = json.dumps(value).replace("'", "''")
                        values.append(f"'{json_val}'")
                
                # Handle boolean values
                elif isinstance(value, bool):
                    # Use PostgreSQL boolean literals
                    values.append('TRUE' if value else 'FALSE')
                
                # Handle numeric values (int, float)
                elif isinstance(value, (int, float)):
                    values.append(str(value))
                
                # Handle any other types
                else:
                    safe_val = str(value).replace("'", "''")
                    values.append(f"'{safe_val}'")
            
            values_str = ", ".join(values)
            # Create the full INSERT statement
            statement = f'INSERT INTO "{table_name}" ({columns_str}) VALUES ({values_str});'
            insert_statements.append(statement)
        
        return insert_statements
        

    def create_update_statements(self, df, table_name, id_columns):
        """
        Generate SQL UPDATE statements for each row in a DataFrame.
        
        Args:
            df (pandas.DataFrame): DataFrame containing the data to update
            table_name (str): Name of the target database table
            id_columns (list): List of column names to use in the WHERE clause
            
        Returns:
            list: List of SQL UPDATE statements
        """
        if df.empty or not id_columns:
            return []
            
        update_statements = []
        
        for _, row in df.iterrows():
            # Build SET clause
            set_items = []
            # Build WHERE clause
            where_items = []
            
            for col, value in row.items():
                # Skip NULL/None values for WHERE clause
                if col in id_columns:
                    if value is None or (isinstance(value, float) and pd.isna(value)):
                        where_items.append(f'"{col}" IS NULL')
                    elif isinstance(value, str):
                        safe_val = value.replace("'", "''")
                        where_items.append(f'"{col}" = \'{safe_val}\'')
                    elif isinstance(value, bool):
                        where_items.append(f'"{col}" = {str(value).lower()}')
                    else:
                        where_items.append(f'"{col}" = {value}')
                    continue
                
                # Handle different data types for SET clause
                if value is None or (isinstance(value, float) and pd.isna(value)):
                    set_items.append(f'"{col}" = NULL')
                
                elif isinstance(value, str):
                    safe_val = value.replace("'", "''")
                    set_items.append(f'"{col}" = \'{safe_val}\'')
                
                elif isinstance(value, dict):
                    json_val = json.dumps(value).replace("'", "''")
                    set_items.append(f'"{col}" = \'{json_val}\'')
                
                elif isinstance(value, list):
                    try:
                        # First convert list elements to strings, handling NULL values and quotes
                        list_elements = []
                        for item in value:
                            if item is None:
                                list_elements.append("NULL")
                            elif isinstance(item, str):
                                safe_item = item.replace("'", "''")
                                list_elements.append(f'"{safe_item}"')
                            else:
                                list_elements.append(str(item))
                        
                        # Format as PostgreSQL array: ARRAY['item1', 'item2', ...]
                        array_str = "ARRAY[" + ", ".join(list_elements) + "]"
                        set_items.append(f'"{col}" = {array_str}')
                    except Exception:
                        # Fallback for complex lists
                        json_val = json.dumps(value).replace("'", "''")
                        set_items.append(f'"{col}" = \'{json_val}\'')
                
                elif isinstance(value, bool):
                    set_items.append(f'"{col}" = {str(value).lower()}')
                
                elif isinstance(value, (int, float)):
                    set_items.append(f'"{col}" = {value}')
                
                else:
                    safe_val = str(value).replace("'", "''")
                    set_items.append(f'"{col}" = \'{safe_val}\'')
            
            # Skip if no SET items or no WHERE items
            if not set_items or not where_items:
                continue
                
            # Build the complete UPDATE statement
            set_clause = ", ".join(set_items)
            where_clause = " AND ".join(where_items) if len(where_items) > 1 else where_items
            
            statement = f'UPDATE "{table_name}" SET {set_clause} WHERE {where_clause};'
            update_statements.append(statement)
        
        return update_statements


    
    # Fixed function name to match what's used in invoice_service.py
    def delete_record(self, table_name, condition):
        """Delete records from a table based on a condition."""
        try:
            query = f"DELETE FROM {table_name} WHERE {condition}"
            with self.engine.connect() as connection:
                connection.execute(text(query))
            return True
        except Exception as e:
            print(f"Error deleting records from '{table_name}': {e}")
            return False

# Create an instance of the database class
db = PostgresCRUD(settings.POSTGRES_URI)