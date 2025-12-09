"""
Product Service - Business logic for product operations
"""
from typing import List, Optional, Dict, Any, Union
from uuid import uuid4
from datetime import datetime
from decimal import Decimal
import math

from core.database import db
from core.config import settings
from utils.schema.billing_system.product_schema import (
    ProductCreate,
    VariantCreate,
    MetalComponentCreate,
    DiamondComponentCreate
)
from services.shopify_service import ShopifyGraphQLConnector


class WhereClauseBuilder:
    """
    Comprehensive where clause builder for PostgreSQL queries.
    Builds safe SQL with properly escaped values (compatible with existing PostgresCRUD).
    """
    
    def __init__(self):
        self.conditions = []
    
    def _escape_string(self, value: str) -> str:
        """Safely escape string values for SQL"""
        if value is None:
            return "NULL"
        return value.replace("'", "''")
    
    def _format_value(self, value: Any) -> str:
        """Format value for SQL based on its type"""
        if value is None:
            return "NULL"
        elif isinstance(value, str):
            return f"'{self._escape_string(value)}'"
        elif isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        elif isinstance(value, (int, float)):
            return str(value)
        else:
            return f"'{self._escape_string(str(value))}'"
    
    def like(self, field: str, value: Optional[str], fields: Optional[List[str]] = None) -> 'WhereClauseBuilder':
        """
        Add ILIKE condition for text search (case-insensitive).
        
        Args:
            field: Single field name for search
            value: Search value
            fields: List of fields to search across (OR condition between fields)
        
        Returns:
            Self for method chaining
        """
        if not value or not value.strip():
            return self
        
        search_value = f"%{self._escape_string(value.strip())}%"
        
        if fields:
            # Multiple fields with OR
            field_conditions = []
            for f in fields:
                field_conditions.append(f"{f} ILIKE '{search_value}'")
            condition = f"({' OR '.join(field_conditions)})"
        else:
            # Single field
            condition = f"{field} ILIKE '{search_value}'"
        
        self.conditions.append(condition)
        return self
    
    def equals(self, field: str, value: Optional[Union[str, int, float]]) -> 'WhereClauseBuilder':
        """
        Add exact match condition.
        
        Args:
            field: Field name
            value: Exact value to match
        
        Returns:
            Self for method chaining
        """
        if value is None:
            return self
        
        formatted_value = self._format_value(value)
        self.conditions.append(f"{field} = {formatted_value}")
        return self
    
    def in_list(self, field: str, values: Optional[List[Union[str, int]]]) -> 'WhereClauseBuilder':
        """
        Add IN condition for list of values.
        
        Args:
            field: Field name
            values: List of values
        
        Returns:
            Self for method chaining
        """
        if not values or len(values) == 0:
            return self
        
        # Filter out None values
        clean_values = [v for v in values if v is not None]
        if not clean_values:
            return self
        
        formatted_values = [self._format_value(v) for v in clean_values]
        values_str = ", ".join(formatted_values)
        self.conditions.append(f"{field} IN ({values_str})")
        return self
    
    def range_filter(self, field: str, min_value: Optional[Union[int, float]] = None, 
                    max_value: Optional[Union[int, float]] = None) -> 'WhereClauseBuilder':
        """
        Add range condition (between min and max values).
        
        Args:
            field: Field name
            min_value: Minimum value (inclusive)
            max_value: Maximum value (inclusive)
        
        Returns:
            Self for method chaining
        """
        if min_value is not None:
            self.conditions.append(f"{field} >= {self._format_value(min_value)}")
        
        if max_value is not None:
            self.conditions.append(f"{field} <= {self._format_value(max_value)}")
        
        return self
    
    def date_range(self, field: str, start_date: Optional[Union[str, datetime]] = None,
                  end_date: Optional[Union[str, datetime]] = None) -> 'WhereClauseBuilder':
        """
        Add date range condition.
        
        Args:
            field: Field name (should be date/timestamp field)
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
        
        Returns:
            Self for method chaining
        """
        if start_date is not None:
            formatted_date = self._format_value(str(start_date))
            self.conditions.append(f"{field}::date >= {formatted_date}")
        
        if end_date is not None:
            formatted_date = self._format_value(str(end_date))
            self.conditions.append(f"{field}::date <= {formatted_date}")
        
        return self
    
    def greater_than(self, field: str, value: Optional[Union[int, float]]) -> 'WhereClauseBuilder':
        """Add greater than condition"""
        if value is None:
            return self
        
        self.conditions.append(f"{field} > {self._format_value(value)}")
        return self
    
    def less_than(self, field: str, value: Optional[Union[int, float]]) -> 'WhereClauseBuilder':
        """Add less than condition"""
        if value is None:
            return self
        
        self.conditions.append(f"{field} < {self._format_value(value)}")
        return self
    
    def not_null(self, field: str) -> 'WhereClauseBuilder':
        """Add IS NOT NULL condition"""
        self.conditions.append(f"{field} IS NOT NULL")
        return self
    
    def is_null(self, field: str) -> 'WhereClauseBuilder':
        """Add IS NULL condition"""
        self.conditions.append(f"{field} IS NULL")
        return self
    
    def custom_condition(self, condition: str) -> 'WhereClauseBuilder':
        """
        Add custom SQL condition.
        
        Args:
            condition: Raw SQL condition string
        
        Returns:
            Self for method chaining
        """
        self.conditions.append(condition)
        return self
    
    def build(self) -> str:
        """
        Build the final WHERE clause.
        
        Returns:
            Complete WHERE clause string (empty string if no conditions)
        """
        if not self.conditions:
            return ""
        
        return "WHERE " + " AND ".join(self.conditions)
    
    def build_having(self) -> str:
        """
        Build as HAVING clause instead of WHERE.
        
        Returns:
            Complete HAVING clause string (empty string if no conditions)
        """
        if not self.conditions:
            return ""
        
        return "HAVING " + " AND ".join(self.conditions)
    
    @classmethod
    def create(cls) -> 'WhereClauseBuilder':
        """Factory method to create new builder instance"""
        return cls()


class ProductService:
    """Service for product-related business logic"""
    
    def __init__(self):
        self.crud = db
        # Initialize Shopify connector for image fetching
        self.shopify_connector = ShopifyGraphQLConnector()
    
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
            self.crud.insert_record('billing_system_products', product_record)
            
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
        
        self.crud.insert_record('billing_system_product_variants', variant_record)
        
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
        
        self.crud.insert_record('billing_system_metal_components', metal_record)
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
        
        self.crud.insert_record('billing_system_diamond_components', diamond_record)
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
            FROM billing_system_metal_components
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
            FROM billing_system_diamond_components
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
            SELECT variant_id FROM billing_system_variant_pricing_breakdown 
            WHERE variant_id = '{variant_id}'
        """
        exists = self.crud.execute_query(check_query, return_data=True)
        
        if exists.empty:
            self.crud.insert_record('billing_system_variant_pricing_breakdown', pricing_record)
        else:
            # Update existing
            update_query = f"""
                UPDATE billing_system_variant_pricing_breakdown
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
            UPDATE billing_system_product_variants
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
            SELECT * FROM billing_system_products WHERE id = '{product_id}'
        """
        product_df = self.crud.execute_query(query, return_data=True)
        
        if product_df.empty:
            return None
        
        product = product_df.iloc[0].to_dict()
        
        # Get variants
        variants_query = f"""
            SELECT * FROM billing_system_product_variants WHERE product_id = '{product_id}'
        """
        variants_df = self.crud.execute_query(variants_query, return_data=True)
        
        variants = []
        for _, variant_row in variants_df.iterrows():
            variant_dict = variant_row.to_dict()
            
            # Get metal components
            metal_query = f"""
                SELECT * FROM billing_system_metal_components 
                WHERE variant_id = '{variant_dict['id']}'
            """
            metal_df = self.crud.execute_query(metal_query, return_data=True)
            variant_dict['metal_components'] = metal_df.to_dict('records')
            
            # Get diamond components
            diamond_query = f"""
                SELECT * FROM billing_system_diamond_components 
                WHERE variant_id = '{variant_dict['id']}'
            """
            diamond_df = self.crud.execute_query(diamond_query, return_data=True)
            variant_dict['diamond_components'] = diamond_df.to_dict('records')
            
            # Get pricing breakdown
            pricing_query = f"""
                SELECT * FROM billing_system_variant_pricing_breakdown 
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
        count_query = "SELECT COUNT(*) as total FROM billing_system_products WHERE is_active = true"
        count_df = self.crud.execute_query(count_query, return_data=True)
        total = int(count_df.iloc[0]['total'])
        
        # Get products
        query = f"""
            SELECT * FROM billing_system_products 
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
    
    # ============================================================================
    # ZAKYA PRODUCT INTEGRATION METHODS
    # ============================================================================
    
    def get_zakya_products(
        self,
        page: int = 1,
        page_size: int = 20,
        search_query: Optional[str] = None,
        category_filter: Optional[str] = None,
        brand_filter: Optional[str] = None,
        category_list: Optional[List[str]] = None,
        brand_list: Optional[List[str]] = None,
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        stock_min: Optional[float] = None,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
        updated_after: Optional[str] = None,
        updated_before: Optional[str] = None,
        with_images: bool = True
    ) -> Dict[str, Any]:
        """
        Fetch products from zakya_products table with comprehensive filtering and optional Shopify image enrichment.
        
        Args:
            page: Page number for pagination
            page_size: Number of items per page
            search_query: Search text across name, item_name, description
            category_filter: Single category exact match
            brand_filter: Single brand exact match
            category_list: List of categories (IN clause)
            brand_list: List of brands (IN clause)
            price_min: Minimum price (rate field)
            price_max: Maximum price (rate field)
            stock_min: Minimum stock (stock_on_hand field)
            created_after: Created after date (YYYY-MM-DD)
            created_before: Created before date (YYYY-MM-DD)
            updated_after: Updated after date (YYYY-MM-DD)
            updated_before: Updated before date (YYYY-MM-DD)
            with_images: Whether to fetch images from Shopify by SKU
        
        Returns:
            Paginated zakya products with optional Shopify images
        """
        try:
            # Build WHERE clause using the builder
            builder = WhereClauseBuilder.create()
            
            # Text search across multiple fields
            builder.like(
                field=None, 
                value=search_query,
                fields=['name', 'item_name', 'description']
            )
            
            # Exact match filters
            builder.equals('category_name', category_filter)
            builder.equals('brand', brand_filter)
            
            # List filters (IN clauses)
            builder.in_list('category_name', category_list)
            builder.in_list('brand', brand_list)
            
            # Numeric range filters
            builder.range_filter('rate', min_value=price_min, max_value=price_max)
            builder.greater_than('stock_on_hand', stock_min)
            
            # Date range filters
            builder.date_range('created_time', start_date=created_after, end_date=created_before)
            builder.date_range('last_modified_time', start_date=updated_after, end_date=updated_before)
            
            # Build final WHERE clause
            where_clause = builder.build()
            
            # Get total count
            count_query = f"""
                SELECT COUNT(*) as total 
                FROM zakya_products 
                {where_clause}
            """
            
            count_df = self.crud.execute_query(count_query, return_data=True)
            total = int(count_df.iloc[0]['total'])
            
            # Calculate pagination
            offset = (page - 1) * page_size
            total_pages = math.ceil(total / page_size) if total > 0 else 0
            
            # Get products
            products_query = f"""
                SELECT 
                    item_id, name, item_name, category_name, brand, description,
                    rate, sku, stock_on_hand, available_stock, 
                    cf_collection, cf_gender, cf_work, cf_finish, cf_finding,
                    created_time, last_modified_time
                FROM zakya_products 
                {where_clause}
                ORDER BY last_modified_time DESC NULLS LAST
                LIMIT {page_size} OFFSET {offset}
            """
            
            products_df = self.crud.execute_query(products_query, return_data=True)
            products = products_df.to_dict('records')
            
            # Enrich with Shopify images if requested
            if with_images and products:
                products = self._enrich_with_shopify_images(products)
            
            return {
                'success': True,
                'total': total,
                'products': products,
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages,
                'filters': {
                    'search_query': search_query,
                    'category_filter': category_filter,
                    'brand_filter': brand_filter,
                    'category_list': category_list,
                    'brand_list': brand_list,
                    'price_range': {'min': price_min, 'max': price_max} if price_min or price_max else None,
                    'stock_min': stock_min,
                    'date_filters': {
                        'created': {'after': created_after, 'before': created_before} if created_after or created_before else None,
                        'updated': {'after': updated_after, 'before': updated_before} if updated_after or updated_before else None
                    },
                    'with_images': with_images
                },
                'sql_debug': {
                    'where_clause': where_clause,
                    'count_query': count_query,
                    'products_query': products_query
                }
            }
            
        except Exception as e:
            print(f"❌ Error fetching zakya products: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                'success': False,
                'error': str(e),
                'total': 0,
                'products': [],
                'page': page,
                'page_size': page_size,
                'total_pages': 0
            }
    
    def _enrich_with_shopify_images(self, zakya_products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enrich zakya products with images from Shopify by matching SKU.
        
        Args:
            zakya_products: List of products from zakya_products table
        
        Returns:
            Products enriched with Shopify image data
        """
        try:
            print(f"🎨 Enriching {len(zakya_products)} products with Shopify images...")
            
            enriched_products = []
            
            for product in zakya_products:
                sku = product.get('sku')
                if sku:
                    # Try to fetch image from Shopify
                    image_data = self._fetch_shopify_image_by_sku(sku)
                    product['shopify_image'] = image_data
                else:
                    product['shopify_image'] = None
                
                enriched_products.append(product)
            
            return enriched_products
            
        except Exception as e:
            print(f"⚠️ Error enriching products with images: {e}")
            # Return original products without images
            for product in zakya_products:
                product['shopify_image'] = None
            return zakya_products
    
    def _fetch_shopify_image_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        """
        Fetch product image from Shopify by SKU.
        
        Args:
            sku: Product SKU to search for
        
        Returns:
            Image data if found, None otherwise
        """
        try:
            # Search for products with matching SKU in Shopify
            search_query = f"sku:{sku}"
            result = self.shopify_connector.get_products(first=1, query_filter=search_query)
            
            products = result.get('data', {}).get('products', {}).get('edges', [])
            
            if products:
                product = products[0]['node']
                
                # Get featured image
                featured_image = product.get('featuredImage')
                if featured_image:
                    return {
                        'url': featured_image.get('url'),
                        'alt_text': featured_image.get('altText'),
                        'width': featured_image.get('width'),
                        'height': featured_image.get('height')
                    }
                
                # If no featured image, try first available image
                images = product.get('images', {}).get('edges', [])
                if images:
                    first_image = images[0]['node']
                    return {
                        'url': first_image.get('url'),
                        'alt_text': first_image.get('altText'),
                        'width': first_image.get('width'),
                        'height': first_image.get('height')
                    }
            
            return None
            
        except Exception as e:
            print(f"⚠️ Error fetching Shopify image for SKU {sku}: {e}")
            return None
    
    def get_zakya_product_by_sku(self, sku: str, with_image: bool = True) -> Dict[str, Any]:
        """
        Get a single zakya product by SKU with optional Shopify image.
        
        Args:
            sku: Product SKU
            with_image: Whether to fetch Shopify image
        
        Returns:
            Product data with optional image
        """
        try:
            query = """
                SELECT * FROM zakya_products 
                WHERE sku = '{}'
                LIMIT 1
            """.format(sku.replace("'", "''"))  # Simple SQL injection protection
            
            product_df = self.crud.execute_query(query, return_data=True)
            
            if product_df.empty:
                return {
                    'success': False,
                    'error': 'Product not found'
                }
            
            product = product_df.iloc[0].to_dict()
            
            if with_image:
                image_data = self._fetch_shopify_image_by_sku(sku)
                product['shopify_image'] = image_data
            
            return {
                'success': True,
                'product': product
            }
            
        except Exception as e:
            print(f"❌ Error fetching zakya product by SKU {sku}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_zakya_products_advanced_example(self) -> Dict[str, Any]:
        """
        Example method demonstrating various WhereClauseBuilder usage patterns.
        This is for reference and testing purposes.
        """
        try:
            # Example 1: Complex search with multiple conditions
            builder = WhereClauseBuilder.create()
            
            # Text search across multiple fields (OR between fields, AND with other conditions)
            builder.like(None, "gold ring", fields=['name', 'item_name', 'description'])
            
            # Exact matches
            builder.equals('status', 'active')
            builder.equals('is_combo_product', False)
            
            # List filters (IN clauses)
            builder.in_list('category_name', ['Rings', 'Necklaces', 'Earrings'])
            builder.in_list('brand', ['Minaki', 'Premium'])
            
            # Numeric ranges and comparisons
            builder.range_filter('rate', min_value=10000, max_value=50000)  # Price between 10k-50k
            builder.greater_than('stock_on_hand', 0)  # In stock only
            builder.less_than('available_stock', 100)  # Limited stock
            
            # Date ranges
            builder.date_range('created_time', start_date='2024-01-01', end_date='2024-12-31')
            builder.date_range('last_modified_time', start_date='2024-06-01')
            
            # Null checks
            builder.not_null('sku')  # Must have SKU
            builder.not_null('image_name')  # Must have image
            
            # Custom conditions
            builder.custom_condition("cf_cost_unformatted > rate * 0.7")  # Cost > 70% of rate
            builder.custom_condition("LENGTH(description) > 50")  # Description longer than 50 chars
            
            where_clause = builder.build()
            
            return {
                'example_where_clause': where_clause,
                'example_conditions_count': len(builder.conditions),
                'explanation': {
                    'text_search': 'ILIKE search across name, item_name, description fields',
                    'exact_matches': 'Equals conditions for status and combo product flag',
                    'list_filters': 'IN clauses for categories and brands',
                    'numeric_ranges': 'Price range and stock comparisons',
                    'date_ranges': 'Created and modified date filtering',
                    'null_checks': 'NOT NULL requirements for SKU and image',
                    'custom_conditions': 'Raw SQL for complex business logic'
                }
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def search_zakya_products_by_criteria(self, criteria: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generic search method using criteria dictionary.
        Demonstrates dynamic filter building.
        
        Args:
            criteria: Dictionary of search criteria
        
        Example criteria:
        {
            'text_search': 'gold ring',
            'categories': ['Rings', 'Necklaces'],
            'brands': ['Minaki'],
            'price_min': 10000,
            'price_max': 50000,
            'stock_min': 1,
            'created_after': '2024-01-01',
            'has_sku': True,
            'has_image': True,
            'custom_filters': [
                ('cf_gender_unformatted', 'Women'),
                ('cf_collection', 'Wedding')
            ]
        }
        """
        try:
            builder = WhereClauseBuilder.create()
            
            # Dynamic filter building based on criteria
            if criteria.get('text_search'):
                builder.like(None, criteria['text_search'], 
                           fields=['name', 'item_name', 'description'])
            
            if criteria.get('categories'):
                builder.in_list('category_name', criteria['categories'])
            
            if criteria.get('brands'):
                builder.in_list('brand', criteria['brands'])
            
            if criteria.get('price_min') or criteria.get('price_max'):
                builder.range_filter('rate', 
                                   min_value=criteria.get('price_min'),
                                   max_value=criteria.get('price_max'))
            
            if criteria.get('stock_min'):
                builder.greater_than('stock_on_hand', criteria['stock_min'])
            
            if criteria.get('created_after'):
                builder.date_range('created_time', start_date=criteria['created_after'])
            
            if criteria.get('has_sku'):
                builder.not_null('sku')
            
            if criteria.get('has_image'):
                builder.not_null('image_name')
            
            # Custom field filters
            if criteria.get('custom_filters'):
                for field, value in criteria['custom_filters']:
                    builder.equals(field, value)
            
            where_clause = builder.build()
            
            # Execute query
            query = f"""
                SELECT item_id, name, sku, rate, category_name, brand, stock_on_hand
                FROM zakya_products 
                {where_clause}
                ORDER BY last_modified_time DESC
                LIMIT 50
            """
            
            df = self.crud.execute_query(query, return_data=True)
            products = df.to_dict('records')
            
            return {
                'success': True,
                'products': products,
                'criteria': criteria,
                'sql_debug': {
                    'where_clause': where_clause,
                    'full_query': query,
                    'conditions_count': len(builder.conditions)
                }
            }
            
        except Exception as e:
            print(f"❌ Error in criteria search: {e}")
            return {
                'success': False,
                'error': str(e)
            }