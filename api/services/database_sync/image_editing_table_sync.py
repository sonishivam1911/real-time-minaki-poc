import json
import pandas as pd
from typing import Dict, Any, Tuple
from core.database import db

class ProductsService:
    """Service layer for products data operations"""
    
    @staticmethod
    def flatten_bilingual_field(field_value: Any) -> Tuple[Any, Any]:
        """
        Flattens a bilingual field {cn: "", en: ""} into separate values.
        
        Args:
            field_value: Field value that might be a dict with cn/en keys
            
        Returns:
            Tuple of (cn_value, en_value) or (None, None)
        """
        if field_value and isinstance(field_value, dict):
            return field_value.get('cn'), field_value.get('en')
        return None, None
    
    @staticmethod
    def parse_ndjson_file_to_dataframe(file_content: bytes) -> pd.DataFrame:
        """
        Parses NDJSON file content and converts to flattened DataFrame.
        
        Args:
            file_content: NDJSON file content as bytes
            
        Returns:
            Flattened pandas DataFrame
        """
        # Decode bytes to string
        ndjson_string = file_content.decode('utf-8') 
        
        # Parse each line as JSON
        data_list = []
        for line in ndjson_string.strip().split('\n'):
            if line.strip():
                try:
                    data_list.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"Warning: Skipping invalid JSON line: {line[:100]}... Error: {e}")
                    continue

        if not data_list:
            raise ValueError("No valid JSON records found in NDJSON file")
        
        flattened_data = []

        processed_data = []
        for object in data_list:
            if "data" in object:
                processed_data.extend(object["data"])


        print(f"Processed length is {len(processed_data)}")
        
        for record in processed_data:
            flat_record = {}
            
            # Simple fields
            flat_record['id'] = record.get('id')
            flat_record['spu_count'] = record.get('spuCount')
            flat_record['product_id'] = record.get('productId')
            flat_record['sku'] = record.get('sku')
            flat_record['spu'] = record.get('spu')
            flat_record['is_custom'] = record.get('isCustom')
            
            # Bilingual fields - flatten them
            flat_record['name_cn'], flat_record['name_en'] = ProductsService.flatten_bilingual_field(record.get('name'))
            flat_record['size_name_cn'], flat_record['size_name_en'] = ProductsService.flatten_bilingual_field(record.get('sizeName'))
            flat_record['alloy_name_cn'], flat_record['alloy_name_en'] = ProductsService.flatten_bilingual_field(record.get('alloyName'))
            flat_record['type_name_cn'], flat_record['type_name_en'] = ProductsService.flatten_bilingual_field(record.get('typeName'))
            flat_record['category_name_cn'], flat_record['category_name_en'] = ProductsService.flatten_bilingual_field(record.get('categoryName'))
            flat_record['plating_name_cn'], flat_record['plating_name_en'] = ProductsService.flatten_bilingual_field(record.get('platingName'))
            flat_record['paint_name_cn'], flat_record['paint_name_en'] = ProductsService.flatten_bilingual_field(record.get('paintName'))
            flat_record['material_name_cn'], flat_record['material_name_en'] = ProductsService.flatten_bilingual_field(record.get('materialName'))
            flat_record['craft_name_cn'], flat_record['craft_name_en'] = ProductsService.flatten_bilingual_field(record.get('craftName'))
            flat_record['series_name_cn'], flat_record['series_name_en'] = ProductsService.flatten_bilingual_field(record.get('seriesName'))
            flat_record['amount_name_cn'], flat_record['amount_name_en'] = ProductsService.flatten_bilingual_field(record.get('amountName'))
            flat_record['weight_name_cn'], flat_record['weight_name_en'] = ProductsService.flatten_bilingual_field(record.get('weightName'))
            flat_record['plating_group_name_cn'], flat_record['plating_group_name_en'] = ProductsService.flatten_bilingual_field(record.get('platingGroupName'))
            flat_record['stone_name_cn'], flat_record['stone_name_en'] = ProductsService.flatten_bilingual_field(record.get('stoneName'))
            
            # ID fields
            flat_record['size_id'] = record.get('sizeId')
            flat_record['alloy_id'] = record.get('alloyId')
            flat_record['type_id'] = record.get('typeId')
            flat_record['category_id'] = record.get('categoryId')
            flat_record['plating_id'] = record.get('platingId')
            flat_record['paint_id'] = record.get('paintId')
            flat_record['material_id'] = record.get('materialId')
            flat_record['craft_id'] = record.get('craftId')
            flat_record['series_id'] = record.get('seriesId')
            flat_record['amount_id'] = record.get('amountId')
            flat_record['weight_id'] = record.get('weightId')
            flat_record['plating_group_id'] = record.get('platingGroupId')
            
            # Arrays (keep as JSON strings)
            flat_record['stones'] = json.dumps(record.get('stones', [])) if record.get('stones') else None
            flat_record['stock_list'] = json.dumps(record.get('stockList', [])) if record.get('stockList') else None
            
            # Measurements
            flat_record['product_weight'] = record.get('productWeight')
            flat_record['product_stone_weight'] = record.get('productStoneWeight')
            
            # Media (comma-separated URLs)
            flat_record['images'] = record.get('images')
            flat_record['thumbs'] = record.get('thumbs')
            flat_record['pics'] = record.get('pics')
            
            # Pricing
            flat_record['retail_price'] = record.get('retailPrice')
            flat_record['wholesaler_price'] = record.get('wholesalerPrice')
            flat_record['promotion_price'] = record.get('promotionPrice')
            flat_record['client_price'] = record.get('clientPrice')
            flat_record['discount'] = record.get('discount')
            flat_record['min_price'] = record.get('minPrice')
            flat_record['max_price'] = record.get('maxPrice')
            
            # Inventory
            flat_record['min_order_amount'] = record.get('minOrderAmount')
            flat_record['min_wholesaler_amount'] = record.get('minWholesalerAmount')
            flat_record['stock_limit'] = record.get('stockLimit')
            flat_record['sold_amount'] = record.get('soldAmount')
            
            # Product attributes
            flat_record['product_brand'] = record.get('productBrand')
            flat_record['product_use'] = record.get('productUse')
            flat_record['product_level'] = record.get('productLevel')
            flat_record['product_abstract'] = record.get('productAbstract')
            flat_record['description'] = record.get('description')
            flat_record['gender'] = record.get('gender')
            flat_record['packing'] = record.get('packing')
            
            # Status and dates
            flat_record['is_promotion'] = record.get('isPromotion')
            flat_record['is_putaway'] = record.get('isPutaway')
            flat_record['is_choice_size'] = record.get('isChoiceSize')
            flat_record['promotion_start_date'] = record.get('promotionStartDate')
            flat_record['promotion_end_date'] = record.get('promotionEndDate')
            flat_record['putaway_date'] = record.get('putawayDate')
            
            # Other
            flat_record['tags'] = record.get('tags')
            flat_record['choice_size'] = record.get('choiceSize')
            flat_record['collect_num'] = record.get('collectNum')
            
            flattened_data.append(flat_record)
        
        df = pd.DataFrame(flattened_data)
        return df
    
    @staticmethod
    def import_ndjson_to_database(
        file_content: bytes,
        table_name: str = "products"
    ) -> Dict[str, Any]:
        """
        Complete import process from NDJSON file to database.
        
        Args:
            file_content: NDJSON file content as bytes
            table_name: Target table name
            
        Returns:
            Dictionary with import statistics
        """
        try:
            # Step 1: Parse NDJSON file to DataFrame
            df = ProductsService.parse_ndjson_file_to_dataframe(file_content)
            print(f"Dataframe is : {df.head()}")
            total_records = len(df)
            
            if total_records == 0:
                return {
                    'success': False,
                    'message': 'No records found in NDJSON file',
                    'total_records': 0,
                    'success_count': 0,
                    'error_count': 0
                }
            
            # Step 2: Use your existing db.create_table method
            success = db.create_table(table_name, df)
            
            if success:
                return {
                    'success': True,
                    'message': f'Successfully imported {total_records} products into table "{table_name}"',
                    'total_records': total_records,
                    'success_count': total_records,
                    'error_count': 0
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to create table in database',
                    'total_records': total_records,
                    'success_count': 0,
                    'error_count': total_records
                }
                
        except ValueError as e:
            return {
                'success': False,
                'message': f'Validation error: {str(e)}',
                'total_records': 0,
                'success_count': 0,
                'error_count': 0
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Import error: {str(e)}',
                'total_records': 0,
                'success_count': 0,
                'error_count': 0
            }