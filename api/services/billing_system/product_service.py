"""
Product Service - Business logic for product operations
"""
from typing import List, Optional, Dict, Any
from uuid import uuid4
from datetime import datetime
from decimal import Decimal

from core.database import PostgresCRUD
from core.config import settings
from utils.schema.billing_system.product_schema import (
    ProductCreate,
    VariantCreate,
    MetalComponentCreate,
    DiamondComponentCreate
)


class ProductService:
    """Service for product-related business logic"""
    
    def __init__(self):
        self.crud = PostgresCRUD(settings.POSTGRES_URI)
    
    def create_product_with_variants(
        self, 
        product_data: ProductCreate
    ) -> Dict[str, Any]:
        """
        Create a product with all its variants and components.
        
        Args:
            product_data: Product creation data
        
        Returns:
            Created product data with IDs
        """
        try:
            # Generate product ID
            product_id = str(uuid4())
            
            # Create product record
            product_record = {
                'id': product_id,
                'handle': product_data.handle or self._generate_handle(product_data.title),
                'title': product_data.title,
                'description': product_data.description,
                'vendor': product_data.vendor,
                'product_type': product_data.product_type,
                'tags': product_data.tags,
                'is_active': product_data.is_active,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            # Insert product
            self.crud.insert_record('products', product_record)
            
            # Create variants
            variant_ids = []
            for variant_data in product_data.variants:
                variant_id = self._create_variant(product_id, variant_data)
                variant_ids.append(variant_id)
            
            return {
                'product_id': product_id,
                'variant_ids': variant_ids,
                'success': True
            }
            
        except Exception as e:
            print(f"❌ Error creating product: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _create_variant(
        self, 
        product_id: str, 
        variant_data: VariantCreate
    ) -> str:
        """Create a variant with its components"""
        variant_id = str(uuid4())
        
        # Create variant record
        variant_record = {
            'id': variant_id,
            'product_id': product_id,
            'sku': variant_data.sku,
            'barcode': variant_data.barcode,
            'sku_name': variant_data.sku_name,
            'status': variant_data.status,
            'price': float(variant_data.price),
            'base_cost': 0,  # Will be calculated
            'weight_g': float(variant_data.weight_g),
            'net_weight_g': float(variant_data.net_weight_g),
            'purity_k': float(variant_data.purity_k) if variant_data.purity_k else None,
            'track_serials': variant_data.track_serials,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        self.crud.insert_record('product_variants', variant_record)
        
        # Create metal components
        for metal_comp in variant_data.metal_components:
            self._create_metal_component(variant_id, metal_comp)
        
        # Create diamond components
        for diamond_comp in variant_data.diamond_components:
            self._create_diamond_component(variant_id, diamond_comp)
        
        # Calculate pricing breakdown
        self._calculate_pricing_breakdown(variant_id)
        
        return variant_id
    
    def _create_metal_component(
        self, 
        variant_id: str, 
        metal_data: MetalComponentCreate
    ) -> str:
        """Create a metal component"""
        metal_id = str(uuid4())
        
        metal_record = {
            'id': metal_id,
            'variant_id': variant_id,
            'metal_type': metal_data.metal_type,
            'purity_k': float(metal_data.purity_k),
            'gross_weight_g': float(metal_data.gross_weight_g),
            'net_weight_g': float(metal_data.net_weight_g),
            'wastage_percent': float(metal_data.wastage_percent),
            'making_charge_per_g': float(metal_data.making_charge_per_g),
            'making_charge_flat': float(metal_data.making_charge_flat),
            'metal_rate_per_g': float(metal_data.metal_rate_per_g),
            'notes': metal_data.notes,
            'created_at': datetime.utcnow()
        }
        
        self.crud.insert_record('metal_components', metal_record)
        return metal_id
    
    def _create_diamond_component(
        self, 
        variant_id: str, 
        diamond_data: DiamondComponentCreate
    ) -> str:
        """Create a diamond component"""
        diamond_id = str(uuid4())
        
        diamond_record = {
            'id': diamond_id,
            'variant_id': variant_id,
            'cert_no': diamond_data.cert_no,
            'shape': diamond_data.shape,
            'carat': float(diamond_data.carat),
            'cut': diamond_data.cut,
            'clarity': diamond_data.clarity,
            'color_grade': diamond_data.color_grade,
            'stone_price_per_carat': float(diamond_data.stone_price_per_carat),
            'origin': diamond_data.origin,
            'notes': diamond_data.notes,
            'created_at': datetime.utcnow()
        }
        
        self.crud.insert_record('diamond_components', diamond_record)
        return diamond_id
    
    def _calculate_pricing_breakdown(self, variant_id: str) -> None:
        """Calculate and store pricing breakdown for a variant"""
        # Get metal components
        metal_query = f"""
            SELECT 
                net_weight_g,
                metal_rate_per_g,
                making_charge_per_g,
                making_charge_flat,
                gross_weight_g,
                wastage_percent
            FROM metal_components
            WHERE variant_id = '{variant_id}'
        """
        metal_df = self.crud.execute_query(metal_query, return_data=True)
        
        # Calculate metal totals
        total_metal_value = 0
        total_making_charges = 0
        total_wastage_charges = 0
        
        for _, row in metal_df.iterrows():
            # Metal value
            metal_value = row['net_weight_g'] * row['metal_rate_per_g']
            total_metal_value += metal_value
            
            # Making charges
            making = (row['net_weight_g'] * row['making_charge_per_g']) + row['making_charge_flat']
            total_making_charges += making
            
            # Wastage
            wastage_weight = row['gross_weight_g'] - row['net_weight_g']
            wastage_value = wastage_weight * row['metal_rate_per_g']
            total_wastage_charges += wastage_value
        
        # Get diamond components
        diamond_query = f"""
            SELECT carat, stone_price_per_carat
            FROM diamond_components
            WHERE variant_id = '{variant_id}'
        """
        diamond_df = self.crud.execute_query(diamond_query, return_data=True)
        
        # Calculate stone total
        total_stone_value = 0
        for _, row in diamond_df.iterrows():
            total_stone_value += row['carat'] * row['stone_price_per_carat']
        
        # Calculate final cost
        final_cost = (
            total_metal_value + 
            total_stone_value + 
            total_making_charges + 
            total_wastage_charges
        )
        
        # Calculate suggested retail price (with margin)
        suggested_retail = final_cost * (1 + settings.DEFAULT_MARGIN_PERCENT / 100)
        
        # Insert or update pricing breakdown
        pricing_record = {
            'variant_id': variant_id,
            'total_metal_value': float(total_metal_value),
            'total_stone_value': float(total_stone_value),
            'total_making_charges': float(total_making_charges),
            'total_wastage_charges': float(total_wastage_charges),
            'total_discounts': 0,
            'tax_rate_percent': 0,
            'tax_amount': 0,
            'final_cost': float(final_cost),
            'suggested_retail_price': float(suggested_retail),
            'last_calculated_at': datetime.utcnow()
        }
        
        # Check if exists
        check_query = f"""
            SELECT variant_id FROM variant_pricing_breakdown 
            WHERE variant_id = '{variant_id}'
        """
        exists = self.crud.execute_query(check_query, return_data=True)
        
        if exists.empty:
            self.crud.insert_record('variant_pricing_breakdown', pricing_record)
        else:
            # Update existing
            update_query = f"""
                UPDATE variant_pricing_breakdown
                SET total_metal_value = {pricing_record['total_metal_value']},
                    total_stone_value = {pricing_record['total_stone_value']},
                    total_making_charges = {pricing_record['total_making_charges']},
                    total_wastage_charges = {pricing_record['total_wastage_charges']},
                    final_cost = {pricing_record['final_cost']},
                    suggested_retail_price = {pricing_record['suggested_retail_price']},
                    last_calculated_at = CURRENT_TIMESTAMP
                WHERE variant_id = '{variant_id}'
            """
            self.crud.execute_query(update_query)
        
        # Update variant base_cost
        update_variant_query = f"""
            UPDATE product_variants
            SET base_cost = {final_cost}
            WHERE id = '{variant_id}'
        """
        self.crud.execute_query(update_variant_query)
    
    def _generate_handle(self, title: str) -> str:
        """Generate URL-friendly handle from title"""
        return title.lower().replace(' ', '-').replace('/', '-')
    
    def get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get product with all related data"""
        query = f"""
            SELECT * FROM products WHERE id = '{product_id}'
        """
        product_df = self.crud.execute_query(query, return_data=True)
        
        if product_df.empty:
            return None
        
        product = product_df.iloc[0].to_dict()
        
        # Get variants
        variants_query = f"""
            SELECT * FROM product_variants WHERE product_id = '{product_id}'
        """
        variants_df = self.crud.execute_query(variants_query, return_data=True)
        
        variants = []
        for _, variant_row in variants_df.iterrows():
            variant_dict = variant_row.to_dict()
            
            # Get metal components
            metal_query = f"""
                SELECT * FROM metal_components 
                WHERE variant_id = '{variant_dict['id']}'
            """
            metal_df = self.crud.execute_query(metal_query, return_data=True)
            variant_dict['metal_components'] = metal_df.to_dict('records')
            
            # Get diamond components
            diamond_query = f"""
                SELECT * FROM diamond_components 
                WHERE variant_id = '{variant_dict['id']}'
            """
            diamond_df = self.crud.execute_query(diamond_query, return_data=True)
            variant_dict['diamond_components'] = diamond_df.to_dict('records')
            
            # Get pricing breakdown
            pricing_query = f"""
                SELECT * FROM variant_pricing_breakdown 
                WHERE variant_id = '{variant_dict['id']}'
            """
            pricing_df = self.crud.execute_query(pricing_query, return_data=True)
            if not pricing_df.empty:
                variant_dict['pricing_breakdown'] = pricing_df.iloc[0].to_dict()
            
            variants.append(variant_dict)
        
        product['variants'] = variants
        return product
    
    def list_products(
        self, 
        page: int = 1, 
        page_size: int = 20
    ) -> Dict[str, Any]:
        """List products with pagination"""
        offset = (page - 1) * page_size
        
        # Get total count
        count_query = "SELECT COUNT(*) as total FROM products WHERE is_active = true"
        count_df = self.crud.execute_query(count_query, return_data=True)
        total = int(count_df.iloc[0]['total'])
        
        # Get products
        query = f"""
            SELECT * FROM products 
            WHERE is_active = true
            ORDER BY created_at DESC
            LIMIT {page_size} OFFSET {offset}
        """
        products_df = self.crud.execute_query(query, return_data=True)
        
        products = []
        for _, row in products_df.iterrows():
            product = self.get_product_by_id(row['id'])
            if product:
                products.append(product)
        
        return {
            'total': total,
            'products': products,
            'page': page,
            'page_size': page_size
        }