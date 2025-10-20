import csv
import io

def normalize_column_name(col_name: str):
    """
    Normalize CSV column names to match our model field names
    
    Example:
        "High Resolution - 1" -> "high_resolution_1"
        "Web Format - 2" -> "web_format_2"
        "Length (cm)" -> "length_cm"
    """
    # Remove extra spaces
    col_name = col_name.strip()
    
    # Convert to lowercase
    col_name = col_name.lower()
    
    # Replace special characters with underscores
    col_name = col_name.replace(" - ", "_")
    col_name = col_name.replace(" ", "_")
    col_name = col_name.replace("(", "")
    col_name = col_name.replace(")", "")
    col_name = col_name.replace("-", "_")
    
    return col_name

def parse_csv_content(csv_content: str):
    """
    Parse CSV content and return rows and errors
    
    Returns:
        Tuple of (parsed_rows, errors)
    """
    parsed_rows = []
    errors = []
    
    try:
        # Parse CSV
        csv_file = io.StringIO(csv_content)
        reader = csv.DictReader(csv_file)
        
        for idx, row in enumerate(reader):
            try:
                # Normalize column names
                normalized_row = {}
                for key, value in row.items():
                    normalized_key = normalize_column_name(key)
                    normalized_row[normalized_key] = value if value else None
                
                parsed_rows.append(normalized_row)
                
            except Exception as e:
                errors.append({
                    "row_number": idx + 2,  # +2 because CSV has header and is 1-indexed
                    "error": str(e),
                    "raw_data": row
                })
        
    except Exception as e:
        errors.append({
            "error": f"CSV parsing error: {str(e)}"
        })
    
    return parsed_rows, errors