from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json
from .product import ShopifyProductService

@dataclass
class ProductFilterCriteria:
    """
    Filter criteria based on CSV columns mapping to Shopify metafields
    
    CSV Columns from Google Sheet:
    - Column P: Gender -> addfea.gender
    - Column Q: Category -> addfea.group (e.g., "Jewelry Sets", "Bracelets", "Earrings")
    - Column R: Line -> Line/Collection names (e.g., "American Diamonds", "Kundan & Polki")
    - Column S: Style -> addfea.style (e.g., "Collar", "Choker", "Temple")
    """
    gender: Optional[str] = None  # Column P: maps to addfea.gender
    category: Optional[str] = None  # Column Q: maps to addfea.group
    line: Optional[str] = None  # Column R: Line/Collection name
    style: Optional[str] = None  # Column S: maps to addfea.style


class ProductFilterService:
    """
    Service to filter Shopify products based on metafield criteria
    """

    def __init__(self, shopify_product_service: ShopifyProductService):
        """
        Initialize with ShopifyProductService instance
        
        Args:
            shopify_product_service: Instance of ShopifyProductService
        """
        self.shopify_service = shopify_product_service
    
    def _partial_match(self, value: str, target: str):
        """
        Check if value partially matches target (case-insensitive)
        
        Args:
            value: Value to search for
            target: Target string to search in
            
        Returns:
            True if value is found in target
        """
        if not value or not target:
            return False
        return value.lower() in target.lower()
    
    def _list_partial_match(self, values: List, target_list: List):
        """
        Check if any value in values partially matches any item in target_list
        
        Args:
            values: List of values to search for
            target_list: List of target strings
            
        Returns:
            True if any value matches any target
        """
        if not values or not target_list:
            return False
        
        for value in values:
            for target in target_list:
                if self._partial_match(value, target):
                    return True
        return False
    
    def _get_metafield_value(self, metafields: Dict, namespace: str, key: str):
        """
        Extract metafield value from product metafields structure
        
        Args:
            metafields: Product metafields dict with edges structure
            namespace: Metafield namespace
            key: Metafield key
            
        Returns:
            Metafield value or None
        """
        edges = metafields.get('edges', [])
        
        for edge in edges:
            node = edge.get('node', {})
            if node.get('namespace') == namespace and node.get('key') == key:
                value = node.get('value')
                print(f"Metafield found: {namespace}.{key} = {value}")
                
                # Handle list types (JSON arrays)
                if isinstance(value, str) and value.startswith('['):
                    try:
                        return json.loads(value)
                    except:
                        return value
                
                return value
        
        return None
    
    def _matches_criteria(self, product: Dict, criteria: ProductFilterCriteria):
        """
        Check if a product matches the filter criteria
        
        Args:
            product: Product data dict
            criteria: Filter criteria
            
        Returns:
            True if product matches all criteria
        """
        metafields = product.get('metafields', {})
        tags = product.get('tags', [])
        
        # Gender check (Column P -> addfea.gender)
        if criteria.gender:
            gender = self._get_metafield_value(metafields, 'addfea', 'gender')
            if not gender or not self._partial_match(criteria.gender, gender):
                return False
        
        # Category check (Column Q -> addfea.group)
        # Examples: "Jewelry Sets", "Bracelets", "Earrings", "Charms & Pendants"
        if criteria.category:
            group = self._get_metafield_value(metafields, 'addfea', 'group')
            if not group or not self._partial_match(criteria.category, group):
                return False
        
        # Line check (Column R -> Check in multiple places)
        # Examples: "American Diamonds", "Kundan & Polki", "Temple", "Eleganza", "SS95", "Fine"
        if criteria.line:
            # Check in addfea.style first
            style_field = self._get_metafield_value(metafields, 'addfea', 'style')
            match_found = False
            
            if style_field and self._partial_match(criteria.line, style_field):
                match_found = True
            
            # Also check in tags
            if not match_found:
                for tag in tags:
                    if self._partial_match(criteria.line, tag):
                        match_found = True
                        break
            
            # Check in occasion
            if not match_found:
                occasion = self._get_metafield_value(metafields, 'addfea', 'occasion')
                if occasion:
                    if isinstance(occasion, list):
                        for occ in occasion:
                            if self._partial_match(criteria.line, occ):
                                match_found = True
                                break
                    else:
                        if self._partial_match(criteria.line, occasion):
                            match_found = True
            
            if not match_found:
                return False
        
        # Style check (Column S -> addfea.style)
        # Examples: "Collar", "Choker", etc.
        if criteria.style:
            style = self._get_metafield_value(metafields, 'addfea', 'style')
            if not style or not self._partial_match(criteria.style, style):
                return False
        
        return True
    
    def _extract_product_content(self, product: Dict):
        """
        Extract relevant content from product for agent input
        
        Args:
            product: Product data dict
            
        Returns:
            Dict with id, title, description, styling_tip
        """
        metafields = product.get('metafields', {})
        
        # Get description - prioritize meta.description_excerpt, then global.description_tag
        description = (
            self._get_metafield_value(metafields, 'meta', 'description_excerpt') or
            self._get_metafield_value(metafields, 'global', 'description_tag') or
            product.get('descriptionHtml', '')
        )
        
        # Get styling tip
        styling_tip = self._get_metafield_value(metafields, 'addfea', 'styling_tip') or ''
        
        return {
            'product_id': product.get('id'),
            'title': product.get('title'),
            'description': description,
            'styling_tip': styling_tip,
            'handle': product.get('handle'),
            'product_type': product.get('productType'),
            'vendor': product.get('vendor'),
            'tags': product.get('tags', [])
        }
    
    def _build_shopify_query_filter(self, criteria: ProductFilterCriteria):
        """
        Build Shopify query string for filtering products.
        
        IMPORTANT: Always gets ACTIVE products sorted by NEWEST FIRST
        
        We ONLY use Shopify's native filters for:
        - status (active)
        - created_at (sorting)
        
        ALL OTHER FILTERING (category, line, style, gender) is done via METAFIELDS in Python.
        
        Args:
            criteria: Filter criteria
            
        Returns:
            Shopify query string
        """
        query_parts = []
        
        # 🔴 CRITICAL: Always get ACTIVE products only
        query_parts.append("status:active")
        
        # 🔴 CRITICAL: Sort by created_at descending (NEWEST FIRST)
        # This ensures we get the most recently created products
        query_parts.append("created_at:>='2020-01-01'")  # All products since 2020
        
        query_string = " AND ".join(query_parts)
        
        # Add sort parameter
        query_string += " sort:created_at"
        
        return query_string
    
    def filter_products(
        self, 
        criteria_list: List[Dict[str, Any]], 
        limit_per_criteria: int = 15
    ) :
        """
        Filter products based on multiple criteria from CSV input.
        
        🔴 GUARANTEES:
        - Only ACTIVE products
        - Sorted by created_at (NEWEST FIRST)
        - Returns exactly N products per criteria (default: 15)
        
        Strategy:
        1. Use Shopify query filters where possible (product_type, tags, status, created_at)
        2. Fetch products sorted by newest first
        3. Apply metafield filtering in Python
        4. Return top N matches per criteria
        
        Args:
            criteria_list: List of filter criteria dicts (from CSV rows)
            limit_per_criteria: Max products to return per criteria (default: 15)
            
        Returns:
            List of filtered product content dicts ready for agent
        """
        # Convert dict criteria to ProductFilterCriteria objects
        criteria_objects = []
        for criteria_dict in criteria_list:
            criteria = ProductFilterCriteria(
                gender=criteria_dict.get('gender'),  # Column P
                category=criteria_dict.get('category'),  # Column Q
                line=criteria_dict.get('line'),  # Column R
                style=criteria_dict.get('style')  # Column S
            )
            criteria_objects.append(criteria)
        
        filtered_products = []
        processed_ids = set()  # Avoid duplicates across criteria
        
        # Process each criteria separately
        for idx, criteria in enumerate(criteria_objects):
            print(f"\n🔍 Criteria {idx + 1}/{len(criteria_objects)}:")
            print(f"   Gender={criteria.gender}, Category={criteria.category}")
            print(f"   Line={criteria.line}, Style={criteria.style}")
            
            # Build Shopify query filter (includes status:active and sort:created_at)
            query_string = self._build_shopify_query_filter(criteria)
            print(f"   Shopify Query: {query_string}")
            print(f"   🎯 Target: {limit_per_criteria} NEWEST ACTIVE products")
            
            # Fetch products from Shopify
            # Fetch more than needed since we'll filter by metafields
            fetch_limit = min(limit_per_criteria * 5, 250)  # Max 250 per query
            
            result = self.shopify_service.get_products(
                first=fetch_limit,
                query_filter=query_string
            )
            
            products_edges = result.get('data', {}).get('products', {}).get('edges', [])
            print(f"   📦 Shopify returned {len(products_edges)} products (active, sorted by newest)")
            
            # Now filter by metafields and get top N
            criteria_matches = []
            
            for edge in products_edges:
                product = edge['node']
                product_id = product.get('id')
                
                # Skip if already processed in another criteria
                if product_id in processed_ids:
                    continue
                
                # Verify product is active (extra safety check)
                if product.get('status') != 'ACTIVE':
                    continue
                
                # Check if matches metafield criteria (gender, style, etc.)
                if self._matches_criteria(product, criteria):
                    # Get complete metafields if needed
                    if len(product.get('metafields', {}).get('edges', [])) < 10:
                        # Fetch complete metafields
                        complete = self.shopify_service.get_complete_product_with_metafields(product_id)
                        if complete.get('data', {}).get('product'):
                            product = complete['data']['product']
                    
                    product_content = self._extract_product_content(product)
                    criteria_matches.append(product_content)
                    processed_ids.add(product_id)
                    
                    # 🔴 STOP when we have EXACTLY the limit for this criteria
                    if len(criteria_matches) >= limit_per_criteria:
                        print(f"   ✅ Reached limit: {len(criteria_matches)} products")
                        break
            
            print(f"   ✅ Final: {len(criteria_matches)} products matched after metafield filtering")
            filtered_products.extend(criteria_matches)
        
        return filtered_products
    
    def filter_products_by_single_criteria(
        self, 
        criteria: Dict[str, Any], 
        limit: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Filter products based on single criteria
        
        Args:
            criteria: Single filter criteria dict
            limit: Maximum number of products to return (default: 15)
            
        Returns:
            List of filtered product content dicts
        """
        return self.filter_products([criteria], limit_per_criteria=limit)
    
    def get_products_for_agent_input(
        self,
        csv_data: List[Dict[str, Any]],
        limit_per_criteria: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Main entry point: Get filtered products ready for Product Writer Agent
        Fetches only the most recently created products for each criteria.
        
        Args:
            csv_data: List of dicts from CSV with filter criteria
            limit_per_criteria: Max products to return per criteria (default: 15)
            
        Returns:
            List of product content dicts for agent input
        """
        print(f"🔍 Filtering products with {len(csv_data)} criteria (max {limit_per_criteria} per criteria)...")
        
        filtered = self.filter_products(csv_data, limit_per_criteria=limit_per_criteria)
        
        print(f"✅ Found {len(filtered)} total matching products")
        
        return filtered

