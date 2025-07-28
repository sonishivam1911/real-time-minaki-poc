import tempfile
import os 
from datetime import datetime
import re
import pandas as pd
import pdfplumber
from utils.zakya_helpers import post_record_to_zakya, fetch_records_from_zakya, extract_record_list


fields = {
    "PO No": None,
    "PO Date": None,
    "PO Delivery Date": None,
    "Order Source": None,
    "SKU": None,
    "Order Ref No": None,
    "Partner SKU": None,
    "Description": None,
    "Quantity": None,
    "Unit Price": None,
    "Other Costs": None,
    "Total": None,
    "Size": None,
    "Product Link": None,
    "OPC": None,
    "Pricebook_id": None,
    "Vendor": None,
    "Price List": None
}

def pdf_extract__po_details_ppus(lines):
    fields = {}
    i = 0
    fields["Pricebook_id"] = "1923531000000090263"
    fields["Vendor"] = "1923531000000176206"
    fields["OPC"] = 0
    fields["Price List"] = 0.5
    while i < len(lines):
        line = lines[i].strip()
        if "PO No" in line and i + 1 < len(lines):
            fields["PO No"] = lines[i + 1].strip().split()[0]
        elif "PO Date" in line:
            fields["PO Date"] = line.split("PO Date")[-1].strip()
        elif "PO Delivery Date" in line:
            fields["PO Delivery Date"] = line.split("PO Delivery Date")[-1].strip()
        elif "Order Source" in line:
            fields["Order Source"] = line.split("Order Source")[-1].strip()
        elif "Vendor Code" in line:
            fields["SKU"] = line.split("Vendor Code")[-1].strip()
        elif "Order Ref No" in line:
            fields["Order Ref No"] = line.split("Order Ref No")[-1].strip()
        elif "SKU Code" in line:
            sku_code = line.split("SKU Code")[-1].strip()
            fields["Partner SKU"] = sku_code
            fields["Product Link"] = f"https://dimension-six.perniaspopupshop.com/skuDetail.php?sku={sku_code}"
        elif "Description" in line:
            desc = ""
            for j in range(i + 1, len(lines)):  # Start from the next line of SKU
                if "Quantity" in lines[j]:  # Stop when reaching "Quantity"
                    break
                if lines[j].strip():  # Append non-empty lines to description
                    desc += " " + lines[j].strip()
            fields["Description"] = desc.strip()
        elif "Quantity" in line:
            fields["Quantity"] = line.split("Quantity")[-1].strip()
        elif "Unit Price" in line:
            fields["Unit Price"] = line.split("Unit Price")[-1].strip()
        elif "Other Costs" in line:
            fields["Other Costs"] = line.split("Other Costs")[-1].strip()
        elif "Total" in line:
            fields["Total"] = line.split("Total")[-1].strip()
        elif "Size" in line:
            fields["Size"] = line.split("Size", 1)[1]
        elif "GST No :" in line:
            gstin = line.split()[1].split()[0]
            if gstin.startswith("07"):
                fields["Vendor"] = 1923531000000176206
        i += 1  # Move to the next line
    return fields

def pdf_extract__po_details_aza(lines):
    fields = {}
    i = 0
    fields["Price List"] = 0.55
    if "AZA FASHION PVT LTD DTDC E-fulfilment" in lines[7]:
        fields["Vendor"] = 1923531000000809250
    else:
        fields["Vendor"] = 1923531000000176011
    while i < len(lines):
        line = lines[i].strip()
        fields["Pricebook_id"] = "1923531000000287311"

        # Extract PO Details
        if "PO Number:" in line:
            fields["PO No"] = line.split("PO Number:")[-1].strip()
        elif "GST NO: " in line:
            gstin = line.split()[1].split()[0]
        elif "PO Date:" in line:
            fields["PO Date"] = line.split("PO Date:")[-1].strip()
        elif "Delivery Date:" in line:
            fields["PO Delivery Date"] = line.split("Delivery Date:")[-1].strip()
        elif line == "GST":
            detail_line = lines[i+2].split()
            designer_code = detail_line[0]
            product_id = detail_line[1]
            quantity = detail_line[2]
            cost = detail_line[3]
            customization_charges = detail_line[4]
            total_cost = detail_line[5]
            product_title = lines[i+1].rsplit(" ", 1)[0] + " " + lines[i+3].rsplit(" ", 1)[0]
            size = lines[i+1].rsplit(" ", 1)[1] + " " + lines[i+3].rsplit(" ", 1)[1]
            size = size.strip()
            fields_temp = {
                "SKU": designer_code,
                "Partner SKU": product_id,
                "Description": product_title,
                "Size": size,
                "Order Source": 'Aza Online',
                "Quantity": quantity,
                "Unit Price": cost,
                "Other Costs": customization_charges,
                "Total": total_cost,
                "Product Link": None
            }

            fields = {**fields, **fields_temp}

        # Extract Order Processing Charges (OPC)
        elif "Order Processing Charges" in line:
            opc_value = re.findall(r"\(\d+\)", line)
            fields["OPC"] = opc_value[0].replace("(", "").replace(")", "") if opc_value else None
        
        i += 1

    return fields

def format_date_for_api(date_str):
    try:
        # Try to parse the date from the PDF - adjust formats as needed
        # Common formats might include "DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"
        for fmt in ["%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"]:
            try:
                parsed_date = datetime.strptime(date_str.strip(), fmt)
                # Convert to the API-required format (ISO format)
                return parsed_date.strftime("%Y-%m-%d")
            except ValueError:
                continue
        # If none of the formats worked, try a more relaxed approach
        return date_str.strip()
    except Exception as e:
        print(f"Error formatting date {date_str}: {e}")
        return date_str

def process_sales_order(fields, settings_obj):
    """Checks if a Sales Order exists for the given reference number and creates one if not."""
    try:
        access_token = settings_obj.get_access_token()
        if not access_token:
            raise Exception("Failed to get access token")

        sales_order_data = fetch_records_from_zakya(
            settings_obj.API_DOMAIN,
            access_token,
            settings_obj.ORGANIZATION_ID,
            '/salesorders'                  
        )
        mapping_order = extract_record_list(sales_order_data, "salesorders")
        
        item_data = fetch_records_from_zakya(
            settings_obj.API_DOMAIN,
            access_token,
            settings_obj.ORGANIZATION_ID,
            '/items'                  
        )
        mapping_product = extract_record_list(item_data, "items")
        mapping_product = pd.DataFrame(mapping_product)
        
        item_id = None
        item_name = None
        mrp_rate = None
        
        filtered_products = mapping_product[mapping_product["sku"] == fields["SKU"]]
        if not filtered_products.empty:
            item_id = filtered_products["item_id"].iloc[0]
            mrp_rate = filtered_products["rate"].iloc[0]
            item_name = filtered_products["name"].iloc[0]
        else:
            # Handle the case where no matching SKU was found
            print(f"No product found with SKU: {fields['SKU']}")       

        reference_number = fields.get("PO No")
        os_value = fields.get("Order Source")
        if not reference_number:
            raise Exception("Reference number is missing!")

        existing_orders = pd.DataFrame(mapping_order)
        for _, order in existing_orders.iterrows():
            print(f"order is {order}")
            po_refnum = order.get("reference_number")
            po_refnum = re.sub(r"PO:\s*", "", po_refnum) 
            if po_refnum == reference_number:
                raise Exception(f"Sales Order with reference number {reference_number} already exists.")

        terms_and_conditions = """
            All orders are final. Returns or exchanges are not accepted unless the item is damaged or defective upon receipt.
            Custom and made-to-order items cannot be cancelled or refunded once confirmed.
            Standard dispatch within 7–14 business days. Any delays will be duly communicated.
            Minor variations in color or finish are inherent to the handcrafted nature of our products and do not constitute defects.
            """
        
        mulx = fields["Price List"]
        desc = fields.get("Description", "")
        sku = fields.get("SKU", "")
        
        salesorder_payload = {
            "customer_id": fields["Vendor"],
            "date": format_date_for_api(fields["PO Date"]),
            "shipment_date": format_date_for_api(fields["PO Delivery Date"]),
            "reference_number": "PO: " + reference_number,
            "custom_fields": [
                {
                    "index": 1,
                    "label": "Status",
                    "api_name": "cf_status",
                    "placeholder": "cf_status",
                    "value": "Created"
                },
                {
                    "index": 2,
                    "label": "Order Type",
                    "api_name": "cf_order_type",
                    "placeholder": "cf_order_type",
                    "value": 'eCommerce Order'
                },
                {
                    "index": 3,
                    "label": "OPC",
                    "api_name": "cf_opc",
                    "placeholder": "cf_opc",
                    "value": fields["OPC"]
                }
            ],
            "line_items": [
                {
                    "name": item_name if item_name else None,
                    "item_id": int(item_id) if item_id else None,
                    "description": f"PO: {reference_number}" if item_id else f"SKU: {sku} PO: {reference_number} {desc}",
                    "quantity": int(fields["Quantity"]),
                    "warehouse_id": "1923531000001452123"
                }
            ],
            "is_inclusive_tax": True,
            "is_discount_before_tax": True,
            "discount_type": "entity_level",
            "discount": (round(((mrp_rate * mulx) - float(fields["Total"])) / 1.03, 2)
                if mrp_rate and fields.get("Total") else 0),
            "pricebook_id": fields["Pricebook_id"],
            "notes": f"Order Source : {os_value}",
            "terms": terms_and_conditions
        }
        
        print(f"Creating a new Sales Order with reference number {reference_number}...")
        result = post_record_to_zakya(
            settings_obj.API_DOMAIN,
            access_token,  
            settings_obj.ORGANIZATION_ID,
            'salesorders',
            salesorder_payload
        )    
        return result
        
    except Exception as e:
        print(f"Error in process_sales_order: {e}")
        raise e

def get_customer_name_from_vendor(vendor):
    """
    Maps vendor code to customer name for Zakya.
    
    Args:
        vendor (str): The vendor name ('PPUS' or 'AZA').
        
    Returns:
        str: The corresponding customer name in Zakya.
    """
    if vendor == "PPUS":
        return "Pernia Delhi"
    elif vendor == "AZA":
        return "Aza Delhi"
    else:
        raise ValueError(f"Unknown vendor: {vendor}")

def process_single_pdf(pdf_content: bytes, vendor: str, settings_obj):
    """
    Processes a single PDF content for PO extraction and sales order creation.
    
    Args:
        pdf_content (bytes): The PDF file content in bytes.
        vendor (str): The vendor name ('PPUS' or 'AZA').
        settings_obj: The settings object for configuration.
        
    Returns:
        dict: Result of processing this specific PDF.
    """
    temp_path = None
    try:
        # Create temporary file for PDF processing
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(pdf_content)
            temp_path = temp_file.name

        # Extract text using pdfplumber
        with pdfplumber.open(temp_path) as pdf:
            text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
        
        lines = text.split("\n")
        result_extract = None
        
        # Determine format and extract data based on vendor
        if vendor.upper() == "AZA":
            result_extract = pdf_extract__po_details_aza(lines)
        elif vendor.upper() == "PPUS":
            result_extract = pdf_extract__po_details_ppus(lines)
        else:
            # Try to auto-detect if vendor format is not explicitly provided
            for line in lines:
                if "Aza " in line:
                    result_extract = pdf_extract__po_details_aza(lines)
                    break
                elif "PSL" in line:
                    result_extract = pdf_extract__po_details_ppus(lines)
                    break
        
        if not result_extract:
            raise ValueError("Could not determine PO format (AZA/PPUS) from PDF.")

        # Process the sales order
        result_order = process_sales_order(result_extract, settings_obj)
        
        return {
            "success": True,
            "message": "Sales order created successfully",
            "sales_order_id": result_order["salesorder"]["salesorder_id"],
            "po_number": result_extract.get("PO No")
        }
        
    except Exception as e:
        error_message = str(e)
        if "already exists" in error_message:
            return {
                "success": False,
                "message": error_message,
                "sales_order_id": None
            }
        else:
            return {
                "success": False,
                "message": f"Error processing PDF: {error_message}",
                "sales_order_id": None
            }
    finally:
        # Clean up the temporary file
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass