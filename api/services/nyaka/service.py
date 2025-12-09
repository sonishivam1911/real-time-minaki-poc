"""
Nykaa Export Service - ZAKYA-FIRST APPROACH
Fetches products from Zakya first (master inventory), then enriches with Shopify data
"""

from typing import List, Dict, Any, Optional
from services.nyaka.mapper import NykaaProductMapper
from services.shopify_service import ShopifyGraphQLConnector
from services.zakya_service import ZakyaService
import requests
from core.config import settings
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()


class NykaaExportService:
    """
    Nykaa catalog export service using ZAKYA-FIRST approach
    1. Fetch products from Zakya (master inventory) by SKUs
    2. Enrich with Shopify data (images, descriptions, metafields)
    3. Transform to Nykaa format
    """
    
    def __init__(self, shopify_connector: ShopifyGraphQLConnector):
        """
        Initialize with Shopify connector
        
        Args:
            shopify_connector: ShopifyGraphQLConnector instance
        """
        self.shopify = shopify_connector
        self.zakya = ZakyaService()
        self.mapper = NykaaProductMapper(shopify_connector)
        
        # Zakya API configuration
        self.base_url = "https://api.zakya.in/"
        self.client_id = os.getenv("ZAKYA_CLIENT_ID")
        self.client_secret = os.getenv("ZAKYA_CLIENT_SECRET")
        self.redirect_uri = os.getenv("ZAKYA_REDIRECT_URI")
        self.token_url = "https://accounts.zoho.in/oauth/v2/token"
    
    def fetch_all_products_from_zakya(self, access_token: str, organization_id: str) -> List[Dict[str, Any]]:
        """
        Fetch ALL products from Zakya API with pagination handling
        
        Args:
            access_token: OAuth access token for authentication
            organization_id: ID of the organization in Zakya
            
        Returns:
            List of all products from Zakya
        """
        endpoint = "/items"
        url = f"{self.base_url}inventory/v1{endpoint}"
        
        headers = {
            'Authorization': f"Zoho-oauthtoken {access_token}",
            'Content-Type': 'application/json'
        }
        
        params = {
            'organization_id': organization_id,
            'page': 1,
            'per_page': 200  # Maximum items per page
        }
        
        all_products = []
        
        try:
            while True:
                print(f"📦 Fetching page {params['page']} from Zakya...")
                
                response = requests.get(
                    url=url,
                    headers=headers,
                    params=params
                )
                
                response.raise_for_status()
                data = response.json()
                
                # Extract items from response
                items = data.get('items', [])
                all_products.extend(items)
                
                print(f"   Retrieved {len(items)} products from page {params['page']}")
                
                # Check pagination info
                page_context = data.get('page_context', {})
                
                if not page_context.get('has_more_page', False):
                    print(f"✅ Completed! Total products fetched: {len(all_products)}")
                    break
                    
                # Move to next page
                params['page'] = page_context.get('page', params['page']) + 1
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching products from Zakya: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response text: {e.response.text}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            
        return all_products
    
    def fetch_all_products_with_details(self, access_token: str, organization_id: str) -> List[Dict[str, Any]]:
        """
        Fetch ALL products from Zakya with full details (includes custom fields, etc.)
        
        Args:
            access_token: OAuth access token for authentication
            organization_id: ID of the organization in Zakya
            
        Returns:
            List of all products with detailed information
        """
        # First get all basic product info
        all_products = self.fetch_all_products_from_zakya(access_token, organization_id)
        
        # Optionally fetch detailed info for each product
        detailed_products = []
        
        for i, product in enumerate(all_products):
            product_id = product.get('item_id')
            if product_id:
                print(f"🔍 Fetching details for product {i+1}/{len(all_products)}: {product.get('name', 'Unknown')}")
                
                try:
                    detailed_product = self.fetch_single_product_details(
                        access_token, organization_id, product_id
                    )
                    if detailed_product:
                        detailed_products.append(detailed_product)
                    else:
                        # If detailed fetch fails, use basic product info
                        detailed_products.append(product)
                        
                except Exception as e:
                    print(f"⚠️  Error fetching details for product {product_id}: {e}")
                    # Use basic product info if detailed fetch fails
                    detailed_products.append(product)
            else:
                detailed_products.append(product)
                
        return detailed_products
    
    def fetch_single_product_details(self, access_token: str, organization_id: str, item_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed information for a single product
        
        Args:
            access_token: OAuth access token for authentication
            organization_id: ID of the organization in Zakya
            item_id: ID of the specific item to fetch
            
        Returns:
            Detailed product information or None if error
        """
        endpoint = f"/items/{item_id}"
        url = f"{self.base_url}inventory/v1{endpoint}"
        
        headers = {
            'Authorization': f"Zoho-oauthtoken {access_token}",
            'Content-Type': 'application/json'
        }
        
        params = {
            'organization_id': organization_id
        }
        
        try:
            response = requests.get(
                url=url,
                headers=headers,
                params=params
            )
            
            response.raise_for_status()
            data = response.json()
            
            return data.get('item', {})
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching product details for {item_id}: {e}")
            return None
    
    def normalize_sku(self, sku: str) -> str:
        """
        Normalize SKU by removing common variant suffixes
        
        Args:
            sku: Original SKU
            
        Returns:
            Normalized SKU without variant suffixes
        """
        if not sku:
            return ""
        
        normalized = sku.upper().strip()
        
        # Remove common variant suffixes
        suffixes_to_remove = [
            "/MC",  # Multi-color
            "/BK",  # Black
            "/WH",  # White  
            "/GD",  # Gold
            "/SL",  # Silver
            "/RG",  # Rose Gold
            "/Gy",  # Grey/Gray
            "GR",   # Green (without slash)
            "Y",    # Yellow (single letter)
        ]
        
        for suffix in suffixes_to_remove:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)]
                break
        
        return normalized

    async def fetch_zakya_products_by_skus(self, skus: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch products from Zakya by SKU list (STEP 1 - Master Data)
        
        Args:
            skus: List of SKUs to search for
        
        Returns:
            List of Zakya products that match the SKUs
        """
        zakya_products = []
        
        try:
            # Use the existing Zakya connection pattern from settings
            zakya_connection = settings.get_zakya_connection()
            access_token = zakya_connection.get('access_token')
            organization_id = zakya_connection.get('organization_id')
            
            if not access_token or not organization_id:
                print("❌ Zakya connection not properly configured")
                return []
            
            # Fetch ALL products from Zakya with pagination
            all_items = self.fetch_all_products_from_zakya(access_token, organization_id)

            # Filter items by SKUs
            sku_set = set(sku.upper().strip() for sku in skus)
            for item in all_items:
                item_sku = item.get("sku") or item.get("item_code")
                if item_sku and item_sku.upper().strip() in sku_set:
                    print(f"✅ Found Zakya item for SKU: {item_sku}")
                    zakya_products.append(item)
                    
        except Exception as e:
            print(f"❌ Error fetching Zakya products: {e}")
            # Continue without Zakya data rather than failing completely
        
        return zakya_products
    
    async def fetch_shopify_products_by_skus(self, skus: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch products from Shopify by SKU list (STEP 2 - Enrichment Data)
        
        Args:
            skus: List of SKUs to search for
        
        Returns:
            List of Shopify products that match the SKUs
        """
        if not skus:
            return []
            
        # Build query to search for products with any of these SKUs
        sku_queries = [f"sku:{sku}" for sku in skus]
        query_string = " OR ".join(sku_queries)
        
        query = """
        query getProductsBySKUs($query: String) {
            products(first: 250, query: $query) {
                edges {
                    node {
                        id
                        title
                        descriptionHtml
                        description
                        vendor
                        productType
                        handle
                        tags
                        variants(first: 10) {
                            edges {
                                node {
                                    id
                                    sku
                                    price
                                    barcode
                                    inventoryQuantity
                                    selectedOptions {
                                        name
                                        value
                                    }
                                }
                            }
                        }
                        images(first: 20) {
                            edges {
                                node {
                                    id
                                    url
                                    altText
                                }
                            }
                        }
                        metafields(first: 100) {
                            edges {
                                node {
                                    id
                                    namespace
                                    key
                                    value
                                    type
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        try:
            variables = {"query": query_string}
            result = self.shopify.execute_query(query, variables)
            edges = result.get("data", {}).get("products", {}).get("edges", [])
            products = [edge["node"] for edge in edges]
            
            # CRITICAL FIX: Deduplicate by SKU at fetch level
            # Only keep first variant that matches requested SKUs
            sku_set = set(skus)  # Convert to set for faster lookup
            unique_products = []
            seen_skus = set()
            
            for product in products:
                variants = product.get("variants", {}).get("edges", [])
                
                # Find first variant that matches our requested SKUs
                matching_variant = None
                for variant_edge in variants:
                    variant = variant_edge["node"]
                    variant_sku = variant.get("sku", "").strip()
                    
                    if variant_sku in sku_set and variant_sku not in seen_skus:
                        matching_variant = variant
                        seen_skus.add(variant_sku)
                        break
                
                # Only include product if it has a matching variant we haven't seen
                if matching_variant:
                    # Modify product to only include the matching variant
                    product["variants"]["edges"] = [{"node": matching_variant}]
                    unique_products.append(product)
            
            print(f"📦 Shopify fetch: {len(products)} products → {len(unique_products)} unique SKUs")
            return unique_products
            
        except Exception as e:
            print(f"Error fetching Shopify products: {e}")
            return []
    
    async def fetch_products_by_skus_zakya_first(self, skus: List[str]) -> List[Dict[str, Any]]:
        """
        MAIN METHOD: Fetch products using ZAKYA-FIRST approach
        
        This is the correct flow:
        1. Fetch from Zakya (master inventory) - ensures we don't miss any products
        2. Fetch from Shopify (enrichment data) - adds images, descriptions, metafields
        3. Return combined dataset with Zakya as primary source
        
        Args:
            skus: List of SKUs to search for
        
        Returns:
            List of tuples: (shopify_product_or_none, zakya_product)
        """
        print(f"🚀 Starting Zakya-first fetch for {len(skus)} SKUs...")
        
        # STEP 1: Fetch from Zakya (master inventory)
        print("📦 Step 1: Fetching from Zakya (master inventory)...")
        zakya_products = await self.fetch_zakya_products_by_skus(skus)
        print(f"   Found {len(zakya_products)} products in Zakya")
        
        # Create SKU mapping for Zakya products
        zakya_by_sku = {}
        zakya_skus = []
        for product in zakya_products:
            sku = product.get("sku") or product.get("item_code")
            if sku:
                zakya_by_sku[sku] = product
                zakya_skus.append(sku)
        
        # STEP 2: Fetch from Shopify (enrichment)
        print("🛍️  Step 2: Fetching from Shopify (enrichment data)...")
        shopify_products = await self.fetch_shopify_products_by_skus(zakya_skus)
        print(f"   Found {len(shopify_products)} products in Shopify")
        
        # Create SKU mapping for Shopify products
        shopify_by_sku = {}
        for product in shopify_products:
            variants = product.get("variants", {}).get("edges", [])
            for variant_edge in variants:
                variant = variant_edge["node"]
                sku = variant.get("sku")
                if sku:
                    shopify_by_sku[sku] = product
                    break  # Use first variant's SKU
        
        # STEP 3: Combine data with Zakya as primary source
        print("🔄 Step 3: Combining Zakya (primary) + Shopify (enrichment)...")
        combined_products = []
        
        for sku in skus:
            zakya_product = zakya_by_sku.get(sku)
            shopify_product = shopify_by_sku.get(sku)
            
            if zakya_product:
                # Zakya product found - this is our primary source
                combined_products.append((shopify_product, zakya_product))
                status = "✅ Zakya + Shopify" if shopify_product else "⚠️  Zakya only"
                print(f"   {sku}: {status}")
            else:
                # No Zakya product - check if at least Shopify has it
                if shopify_product:
                    combined_products.append((shopify_product, None))
                    print(f"   {sku}: 🟡 Shopify only (missing from Zakya)")
                else:
                    print(f"   {sku}: ❌ Not found in either system")
        
        print(f"🎯 Final result: {len(combined_products)} products ready for Nykaa export")
        return combined_products
    
    async def fetch_all_products(self, fetch_detailed: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch ALL products using ZAKYA-FIRST approach
        
        1. Fetch ALL products from Zakya (master inventory) with DETAILED information
        2. For each Zakya product, try to find matching Shopify data
        3. Return combined dataset with Zakya as primary source
        
        Args:
            fetch_detailed: Always True - we always fetch detailed information for complete data
        
        Returns:
            List of products with Zakya data + optional Shopify enrichment
        """
        # Force detailed fetching for complete product information
        fetch_detailed = True
        
        print(f"🚀 Starting Zakya-first fetch for ALL products...")
        print(f"📊 Mode: DETAILED product information (including custom fields)")
        
        # STEP 1: Fetch ALL products from Zakya (master inventory) with details
        print("📦 Step 1: Fetching ALL products from Zakya with detailed information...")
        zakya_products = await self.fetch_all_zakya_products(fetch_detailed=fetch_detailed)
        print(f"   Found {len(zakya_products)} products in Zakya")
        
        if not zakya_products:
            print("❌ No products found in Zakya")
            return []
        
        # STEP 2: Extract SKUs from Zakya products for Shopify lookup
        zakya_skus = []
        zakya_by_sku = {}
        
        for product in zakya_products:
            sku = product.get("sku") or product.get("item_code")
            if sku:
                normalized_sku = self.normalize_sku(sku).upper()
                zakya_by_sku[normalized_sku] = product
                zakya_skus.append(sku)
        
        print(f"📝 Extracted {len(zakya_skus)} unique SKUs from Zakya")
        
        # STEP 3: Fetch corresponding Shopify products
        print("🛍️  Step 2: Fetching matching products from Shopify...")
        shopify_products = []
        
        if zakya_skus:
            try:
                shopify_products = await self.fetch_shopify_products_by_skus(zakya_skus)
                print(f"   Found {len(shopify_products)} matching products in Shopify")
            except Exception as e:
                print(f"⚠️ Error fetching from Shopify: {e}")
                print("   Continuing with Zakya-only data...")
        
        # Create SKU mapping for Shopify products
        shopify_by_sku = {}
        for product in shopify_products:
            variants = product.get("variants", {}).get("edges", [])
            if variants:
                variant = variants[0]["node"]
                sku = variant.get("sku")
                if sku:
                    normalized_sku = self.normalize_sku(sku).upper()
                    shopify_by_sku[normalized_sku] = product
        
        # STEP 4: Combine data with Zakya as primary source
        print("🔄 Step 3: Combining Zakya (primary) + Shopify (enrichment)...")
        combined_products = []
        
        for sku, zakya_product in zakya_by_sku.items():
            shopify_product = shopify_by_sku.get(sku)
            
            if shopify_product:
                # Zakya + Shopify data available
                shopify_product["_zakya_data"] = zakya_product
                combined_products.append(shopify_product)
                status = "✅ Zakya + Shopify"
            else:
                # Zakya-only product - create Shopify-like structure
                fake_shopify_product = self._create_shopify_like_structure_from_zakya(zakya_product)
                combined_products.append(fake_shopify_product)
                status = "🟡 Zakya only"
            
            if len(combined_products) % 100 == 0:  # Progress logging
                print(f"   Processed {len(combined_products)} products...")
        
        print(f"🎯 Final result: {len(combined_products)} products ready")
        print(f"   Shopify+Zakya: {len([p for p in combined_products if p.get('variants', {}).get('edges')])}")
        print(f"   Zakya-only: {len([p for p in combined_products if not p.get('variants', {}).get('edges')])}")
        
        return combined_products
    
    async def fetch_all_zakya_products(self, fetch_detailed: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch ALL products from Zakya with DETAILED information including custom fields
        
        Args:
            fetch_detailed: Always True - we always fetch detailed info for complete data
        
        Returns:
            List of all Zakya products with complete details
        """
        # Always fetch detailed information for complete product data
        fetch_detailed = True
        
        try:
            # Use the existing Zakya connection pattern from settings
            zakya_connection = settings.get_zakya_connection()
            access_token = zakya_connection.get('access_token')
            organization_id = zakya_connection.get('organization_id')
            
            if not access_token or not organization_id:
                print("❌ Zakya connection not properly configured")
                return []
            
            # Always fetch ALL products with DETAILED information (includes custom fields)
            print("🔍 Fetching products with DETAILED information (including custom fields)...")
            all_items = self.fetch_all_products_with_details(access_token, organization_id)
            print(f"✅ Successfully fetched {len(all_items)} products with detailed information")
            
            return all_items
            
        except Exception as e:
            print(f"❌ Error fetching detailed products from Zakya: {e}")
            print("🔄 Falling back to basic product information...")
            
            # Fallback to basic fetch if detailed fails
            try:
                zakya_connection = settings.get_zakya_connection()
                access_token = zakya_connection.get('access_token')
                organization_id = zakya_connection.get('organization_id')
                
                basic_items = self.fetch_all_products_from_zakya(access_token, organization_id)
                print(f"⚠️ Using basic information for {len(basic_items)} products")
                return basic_items
                
            except Exception as fallback_error:
                print(f"❌ Both detailed and basic fetch failed: {fallback_error}")
                import traceback
                traceback.print_exc()
                return []
    
    def _create_shopify_like_structure_from_zakya(self, zakya_product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a Shopify-like product structure from Zakya data alone
        
        Args:
            zakya_product: Product data from Zakya
        
        Returns:
            Shopify-like product structure with Zakya data
        """
        try:
            sku = zakya_product.get("sku") or zakya_product.get("item_code", "")
            name = zakya_product.get("name", "")
            description = zakya_product.get("description", "")
            rate = zakya_product.get("rate", 0)
            stock = zakya_product.get("stock_on_hand", 0)
            
            # Create minimal Shopify-like structure
            fake_shopify = {
                "id": f"zakya_{zakya_product.get('item_id', sku)}",
                "title": name,
                "description": description,
                "descriptionHtml": f"<p>{description}</p>" if description else "",
                "vendor": "Zakya",
                "productType": zakya_product.get("category_name", ""),
                "handle": sku.lower().replace(" ", "-") if sku else "",
                "tags": [],
                "status": "active",
                "createdAt": zakya_product.get("created_time", ""),
                "updatedAt": zakya_product.get("last_modified_time", ""),
                "variants": {
                    "edges": [{
                        "node": {
                            "id": f"zakya_variant_{sku}",
                            "sku": sku,
                            "price": str(rate),
                            "inventoryQuantity": stock,
                            "availableForSale": stock > 0,
                            "title": "Default",
                            "selectedOptions": []
                        }
                    }]
                },
                "images": {"edges": []},  # No images from Zakya
                "metafields": {"edges": []},  # No metafields from Zakya
                "_zakya_data": zakya_product,
                "_source": "zakya_only"
            }
            
            return fake_shopify
            
        except Exception as e:
            print(f"⚠️ Error creating Shopify structure for Zakya product: {e}")
            # Return minimal safe structure
            return {
                "id": f"zakya_error_{zakya_product.get('item_id', 'unknown')}",
                "title": zakya_product.get("name", "Error Product"),
                "variants": {"edges": []},
                "images": {"edges": []},
                "metafields": {"edges": []},
                "_zakya_data": zakya_product,
                "_source": "zakya_only"
            }

    async def fetch_products_by_skus(self, skus: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch products from both Zakya and Shopify, then merge the data
        
        Args:
            skus: List of SKUs to search for
        
        Returns:
            List of Shopify products with Zakya data attached in _zakya_data field
        """
    
        # STEP 1: Fetch from Zakya (master inventory)
        print("📦 Step 1: Fetching from Zakya...")
        zakya_products = await self.fetch_zakya_products_by_skus(skus)
        print(f"   Found {len(zakya_products)} products in Zakya")
        
        # Create SKU mapping for Zakya products
        zakya_by_sku = {}
        for product in zakya_products:
            sku = product.get("sku") or product.get("item_code")
            if sku:
                zakya_by_sku[sku.upper().strip()] = product
        
        # STEP 2: Fetch from Shopify
        print("🛍️  Step 2: Fetching from Shopify...")
        shopify_products = await self.fetch_shopify_products_by_skus(skus)
        print(f"   Found {len(shopify_products)} products in Shopify")
        
        # STEP 3: Merge Shopify products with Zakya data
        print("🔄 Step 3: Merging Shopify + Zakya data...")
        result_products = []
        processed_skus = set()  # Track what we've already processed
        
        for shopify_product in shopify_products:
            # Get SKU from first variant
            variants = shopify_product.get("variants", {}).get("edges", [])
            if variants:
                variant = variants[0]["node"]
                original_sku = variant.get("sku", "").strip()
                normalized_sku = self.normalize_sku(original_sku).upper()
                
                # Skip if we've already processed this normalized SKU
                if normalized_sku in processed_skus:
                    print(f"🚫 Skipping variant SKU {original_sku} (normalized to {normalized_sku}) - already processed")
                    continue
                
                processed_skus.add(normalized_sku)
                
                # Find matching Zakya product using normalized SKU
                zakya_product = zakya_by_sku.get(normalized_sku)
                
                if zakya_product:
                    print(f"✅ Merged SKU {original_sku} (normalized: {normalized_sku}): Shopify + Zakya data")
                    # Attach Zakya data to Shopify product
                    shopify_product["_zakya_data"] = zakya_product
                else:
                    print(f"⚠️ SKU {original_sku} (normalized: {normalized_sku}): Shopify only (no Zakya data)")
                    shopify_product["_zakya_data"] = None
                
                result_products.append(shopify_product)
        
        # STEP 4: Handle SKUs that are only in Zakya (not in Shopify)
        shopify_skus = set()
        for product in shopify_products:
            variants = product.get("variants", {}).get("edges", [])
            if variants:
                variant = variants[0]["node"]
                sku = variant.get("sku", "").upper().strip()
                shopify_skus.add(sku)
        
        # Only add Zakya-only products (avoid duplicates with Shopify products)
        for sku in skus:
            sku_upper = sku.upper().strip()
            if sku_upper in zakya_by_sku and sku_upper not in shopify_skus:
                print(f"🟡 SKU {sku}: Creating Shopify-like structure from Zakya only")
                zakya_product = zakya_by_sku[sku_upper]
                
                # Create minimal Shopify-like structure from Zakya data
                fake_shopify = {
                    "id": f"zakya_{zakya_product.get('item_id', 'unknown')}",
                    "title": zakya_product.get("name", "Unknown Product"),
                    "description": zakya_product.get("description", ""),
                    "descriptionHtml": zakya_product.get("description", ""),
                    "vendor": "MINAKII",
                    "productType": "Jewelry",
                    "handle": zakya_product.get("sku", "unknown").lower().replace(" ", "-"),
                    "tags": [],
                    "variants": {
                        "edges": [{
                            "node": {
                                "id": f"zakya_variant_{zakya_product.get('item_id')}",
                                "sku": zakya_product.get("sku") or zakya_product.get("item_code"),
                                "price": str(zakya_product.get("rate", 0)),
                                "barcode": "",
                                "inventoryQuantity": zakya_product.get("stock_on_hand", 0),
                                "selectedOptions": []
                            }
                        }]
                    },
                    "images": {"edges": []},
                    "metafields": {"edges": []},
                    "_zakya_data": zakya_product
                }
                result_products.append(fake_shopify)
        
        # STEP 5: Final deduplication by SKU (prioritize Shopify over Zakya-only products)
        print("🔍 Final deduplication check...")
        final_products = []
        seen_skus = set()
        
        for product in result_products:
            variants = product.get("variants", {}).get("edges", [])
            if variants:
                variant = variants[0]["node"]
                original_sku = variant.get("sku", "").strip()
                normalized_sku = self.normalize_sku(original_sku).upper()
                
                if normalized_sku and normalized_sku not in seen_skus:
                    seen_skus.add(normalized_sku)
                    final_products.append(product)
                    print(f"✅ Added SKU {original_sku} (normalized: {normalized_sku})")
                elif normalized_sku:
                    print(f"⚠️ Skipped duplicate SKU {original_sku} (normalized: {normalized_sku})")
                else:
                    print(f"⚠️ Skipped product with missing/invalid SKU: {original_sku}")
        
        print(f"🎯 Final result: {len(final_products)} unique products ready for mapping")
        return final_products