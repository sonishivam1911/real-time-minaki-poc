"""
Inventory Upload Service
Handles CSV upload and populates billing_system_* tables
"""

import pandas as pd
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Tuple

from core.database import db


class InventoryUploadService:
    """Service to handle inventory CSV upload"""
    
    def __init__(self):
        self.db = db
    
    def parse_serial_numbers(self, notes) -> List[str]:
        """Extract serial numbers from notes field"""
        # Handle NaN values from pandas
        if not notes or not isinstance(notes, str) or 'Serial:' not in notes:
            return []
        serial_part = notes.split('Serial:')[1].strip()
        return [s.strip() for s in serial_part.split(',') if s.strip()]
    
    def calculate_prices(self, row: Dict) -> Dict:
        """Calculate all prices"""
        metal_cost = Decimal(str(row['net_weight_g'])) * Decimal(str(row['metal_rate_per_g']))
        stone_cost = Decimal(str(row['stone_carats'])) * Decimal(str(row['stone_rate_per_carat']))
        
        making_gram = Decimal(str(row['net_weight_g'])) * Decimal(str(row['making_rate_per_g']))
        making_percent = (metal_cost + stone_cost) * (Decimal(str(row['making_percentage'])) / 100)
        total_making = making_gram + making_percent
        
        selling_price = metal_cost + stone_cost + total_making
        gst = selling_price * Decimal('0.03')
        final_price = selling_price + gst
        
        return {
            'metal_cost': float(metal_cost),
            'stone_cost': float(stone_cost),
            'making_charges': float(total_making),
            'selling_price': float(selling_price),
            'gst_amount': float(gst),
            'final_price': float(final_price)
        }
    
    def process_row(self, row: Dict) -> Tuple[bool, str, Dict]:
        """Process single CSV row"""
        try:
            product_id = str(uuid.uuid4())
            variant_id = str(uuid.uuid4())
            lot_id = str(uuid.uuid4())
            
            prices = self.calculate_prices(row)
            serials = self.parse_serial_numbers(row.get('notes', ''))
            
            # Product
            product = {
                'id': product_id,
                'handle': row['sku'].lower().replace(' ', '-'),
                'title': row.get('product_title') or f"{row.get('design_code', '')} - {row['metal_type']} {row['purity_k']}K",
                'description': row.get('design_code', ''),
                'vendor': 'IVEE GEMS AND JEWELLERY',
                'product_type': row['product_type'],
                'tags': ['imported'],
                'is_active': True,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            
            # Variant
            variant = {
                'id': variant_id,
                'product_id': product_id,
                'sku': row['sku'],
                'barcode': None,
                'sku_name': row.get('design_code', ''),
                'status': 'active',
                'price': prices['selling_price'],
                'base_cost': prices['metal_cost'] + prices['stone_cost'] + prices['making_charges'],
                'weight_g': float(row['gross_weight_g']),
                'net_weight_g': float(row['net_weight_g']),
                'purity_k': float(row['purity_k']),
                'track_serials': len(serials) > 0,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            
            # Metal
            metal = {
                'id': str(uuid.uuid4()),
                'variant_id': variant_id,
                'metal_type': row['metal_type'],
                'purity_k': float(row['purity_k']),
                'weight_g': float(row['net_weight_g']),
                'rate_per_g': float(row['metal_rate_per_g']),
                'metal_cost': prices['metal_cost'],
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            
            # Diamond
            diamond = {
                'id': str(uuid.uuid4()),
                'variant_id': variant_id,
                'stone_type': row['stone_type'],
                'quantity': int(row['stone_quantity']),
                'carat_weight': float(row['stone_carats']),
                'clarity': row['stone_clarity'],
                'color': row['stone_color'],
                'cut_grade': None,
                'shape': row['stone_shape'],
                'certificate_no': None,
                'rate_per_carat': float(row['stone_rate_per_carat']),
                'stone_cost': prices['stone_cost'],
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            
            # Pricing
            pricing = {
                'id': str(uuid.uuid4()),
                'variant_id': variant_id,
                'metal_cost': prices['metal_cost'],
                'stone_cost': prices['stone_cost'],
                'making_charges': prices['making_charges'],
                'wastage_charges': 0,
                'other_charges': 0,
                'total_cost': prices['metal_cost'] + prices['stone_cost'] + prices['making_charges'],
                'margin_percent': 0,
                'margin_amount': 0,
                'selling_price': prices['selling_price'],
                'gst_rate_percent': 3.0,
                'gst_amount': prices['gst_amount'],
                'final_price': prices['final_price'],
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            
            # Inventory
            inventory = {
                'id': lot_id,
                'variant_id': variant_id,
                'lot_number': f"LOT-{row['sku']}-{datetime.now().strftime('%Y%m')}",
                'location': row.get('location', 'main_warehouse'),
                'quantity_available': len(serials) if serials else 1,
                'quantity_reserved': 0,
                'quantity_sold': 0,
                'purchase_date': datetime.now().date(),
                'purchase_cost_per_unit': prices['metal_cost'] + prices['stone_cost'] + prices['making_charges'],
                'supplier': 'IVEE GEMS AND JEWELLERY',
                'notes': None,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            
            # Serials
            serials_data = []
            for sn in serials:
                serials_data.append({
                    'id': str(uuid.uuid4()),
                    'lot_id': lot_id,
                    'variant_id': variant_id,
                    'serial_no': sn,
                    'status': 'available',
                    'reserved_by': None,
                    'sold_invoice_id': None,
                    'sold_date': None,
                    'notes': None,
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                })
            
            return True, "", {
                'product': product,
                'variant': variant,
                'metal': metal,
                'diamond': diamond,
                'pricing': pricing,
                'inventory': inventory,
                'serials': serials_data
            }
            
        except Exception as e:
            return False, str(e), {}
    
    def upload_csv(self, file_content: bytes) -> Dict:
        """Upload CSV and populate all tables"""
        try:
            df = pd.read_csv(pd.io.common.BytesIO(file_content))
            
            total = len(df)
            processed = 0
            failed = 0
            errors = []
            
            for idx, row in df.iterrows():
                success, error, data = self.process_row(row.to_dict())
                
                if not success:
                    failed += 1
                    errors.append({'row': idx + 2, 'sku': row.get('sku', 'Unknown'), 'error': error})
                    continue
                
                # Process each record in its own transaction
                try:
                    self.db.begin_transaction()
                    
                    # Check if product with this handle already exists
                    existing_check = self.db.execute_query(
                        f"SELECT id FROM billing_system_products WHERE handle = '{data['product']['handle']}'",
                        return_data=True
                    )
                    
                    if not existing_check.empty:
                        # Product already exists, skip this record
                        self.db.rollback_transaction()
                        failed += 1
                        errors.append({
                            'row': idx + 2, 
                            'sku': row.get('sku', 'Unknown'), 
                            'error': f"Product with handle '{data['product']['handle']}' already exists"
                        })
                        continue
                    
                    self.db.insert('billing_system_products', data['product'])
                    self.db.insert('billing_system_product_variants', data['variant'])
                    self.db.insert('billing_system_metal_components', data['metal'])
                    self.db.insert('billing_system_diamond_components', data['diamond'])
                    self.db.insert('billing_system_product_pricing', data['pricing'])
                    self.db.insert('billing_system_inventory_lots', data['inventory'])
                    
                    for serial in data['serials']:
                        self.db.insert('billing_system_stock_serials', serial)
                    
                    self.db.commit_transaction()
                    processed += 1
                    
                except Exception as e:
                    self.db.rollback_transaction()
                    failed += 1
                    errors.append({'row': idx + 2, 'sku': row.get('sku', 'Unknown'), 'error': str(e)})
                
            return {
                'success': True,
                'message': f'Processed {processed}/{total} rows',
                'total_rows': total,
                'processed': processed,
                'failed': failed,
                'errors': errors,
                'summary': {
                    'products': processed,
                    'variants': processed,
                    'serials': sum(len(self.parse_serial_numbers(row.get('notes', ''))) for _, row in df.iterrows())
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': str(e),
                'total_rows': 0,
                'processed': 0,
                'failed': 0,
                'errors': [],
                'summary': {}
            }