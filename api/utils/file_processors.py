import pandas as pd
import io
from datetime import datetime
from fastapi import HTTPException

def preprocess_excel_file(file_content: bytes) -> pd.DataFrame:
    """Preprocess Excel file similar to Streamlit logic."""
    try:
        # Read Excel file with skiprows=7
        taj_sales_df = pd.read_excel(io.BytesIO(file_content), sheet_name="Sheet1", skiprows=7)
        
        # Get the first column name
        first_col = taj_sales_df.columns[0]
        
        # Filter rows where first column doesn't contain 'Total' and is not null
        taj_sales_df = taj_sales_df[
            taj_sales_df[first_col].apply(lambda x: "Total" not in str(x) and pd.notna(x))
        ]
        
        return taj_sales_df
        
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error processing Excel file: {str(e)}"
        )

def validate_required_columns(df: pd.DataFrame) -> None:
    """Validate that required columns are present in the DataFrame."""
    required_columns = ['Style', 'Branch Name', 'Qty', 'Total', 'PrintName']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {', '.join(missing_columns)}"
        )

def parse_date(date_string: str) -> datetime:
    """Parse date string to datetime object."""
    try:
        # Try different date formats
        for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d/%m/%Y'):
            try:
                return datetime.strptime(date_string, fmt)
            except ValueError:
                continue
        
        # If none of the formats work, raise an error
        raise ValueError("Invalid date format")
        
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format. Please use YYYY-MM-DD format. Error: {str(e)}"
        )
