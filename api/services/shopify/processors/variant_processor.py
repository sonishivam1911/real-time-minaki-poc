from typing import List, Dict, Any
from ..base_connector import BaseShopifyConnector

class VariantProcessor(BaseShopifyConnector):
    """Processor for handling product variant creation and management"""
    
    def create_variants_for_product(self, product_id: str, variants_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create multiple variants for a product."""
        
        # Ensure proper GraphQL ID format
        if not product_id.startswith('gid://shopify/Product/'):
            product_id = f"gid://shopify/Product/{product_id}"
        
        created_variants = []
        errors = []
        
        for variant_data in variants_data:
            try:
                result = self.create_single_variant(product_id, variant_data)
                
                if 'errors' in result or result.get('data', {}).get('productVariantCreate', {}).get('userErrors'):
                    variant_errors = result.get('errors', []) + result.get('data', {}).get('productVariantCreate', {}).get('userErrors', [])
                    errors.append({
                        'variant_data': variant_data,
                        'errors': variant_errors
                    })
                else:
                    created_variant = result['data']['productVariantCreate']['productVariant']
                    created_variants.append(created_variant)
                    
            except Exception as e:
                errors.append({
                    'variant_data': variant_data,
                    'error': str(e)
                })
        
        return {
            'success': len(created_variants) > 0,
            'variants': created_variants,
            'variants_created': len(created_variants),
            'errors': errors,
            'total_attempted': len(variants_data)
        }
    
    def create_single_variant(self, product_id: str, variant_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a single variant for a product."""
        
        mutation = """
        mutation productVariantCreate($input: ProductVariantInput!) {
            productVariantCreate(input: $input) {
                productVariant {
                    id
                    title
                    price
                    compareAtPrice
                    sku
                    barcode
                    inventoryQuantity
                    availableForSale
                    weight
                    weightUnit
                    taxable
                    inventoryPolicy
                    fulfillmentService
                    inventoryManagement
                    selectedOptions {
                        name
                        value
                    }
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        # Prepare variant input
        variant_input = {
            'productId': product_id,
            **variant_data
        }
        
        return self.execute_mutation(mutation, {'input': variant_input})
    
    def update_variants(self, variants_updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Update multiple variants."""
        
        updated_variants = []
        errors = []
        
        for variant_update in variants_updates:
            try:
                variant_id = variant_update.get('id')
                if not variant_id:
                    errors.append({
                        'variant_data': variant_update,
                        'error': 'Variant ID is required for updates'
                    })
                    continue
                
                result = self.update_single_variant(variant_id, variant_update)
                
                if 'errors' in result or result.get('data', {}).get('productVariantUpdate', {}).get('userErrors'):
                    variant_errors = result.get('errors', []) + result.get('data', {}).get('productVariantUpdate', {}).get('userErrors', [])
                    errors.append({
                        'variant_data': variant_update,
                        'errors': variant_errors
                    })
                else:
                    updated_variant = result['data']['productVariantUpdate']['productVariant']
                    updated_variants.append(updated_variant)
                    
            except Exception as e:
                errors.append({
                    'variant_data': variant_update,
                    'error': str(e)
                })
        
        return {
            'success': len(updated_variants) > 0,
            'variants': updated_variants,
            'variants_updated': len(updated_variants),
            'errors': errors,
            'total_attempted': len(variants_updates)
        }
    
    def update_single_variant(self, variant_id: str, variant_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a single variant."""
        
        # Ensure proper GraphQL ID format
        if not variant_id.startswith('gid://shopify/ProductVariant/'):
            variant_id = f"gid://shopify/ProductVariant/{variant_id}"
        
        mutation = """
        mutation productVariantUpdate($input: ProductVariantInput!) {
            productVariantUpdate(input: $input) {
                productVariant {
                    id
                    title
                    price
                    compareAtPrice
                    sku
                    barcode
                    inventoryQuantity
                    availableForSale
                    weight
                    weightUnit
                    taxable
                    updatedAt
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        variant_input = {
            'id': variant_id,
            **variant_data
        }
        
        return self.execute_mutation(mutation, {'input': variant_input})
    
    def delete_variant(self, variant_id: str) -> Dict[str, Any]:
        """Delete a product variant."""
        
        # Ensure proper GraphQL ID format
        if not variant_id.startswith('gid://shopify/ProductVariant/'):
            variant_id = f"gid://shopify/ProductVariant/{variant_id}"
        
        mutation = """
        mutation productVariantDelete($id: ID!) {
            productVariantDelete(id: $id) {
                deletedProductVariantId
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        return self.execute_mutation(mutation, {'id': variant_id})
    
    def create_variants_with_options(self, product_id: str, options: List[Dict[str, Any]], 
                                   variants_matrix: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create variants with product options (size, color, etc.)."""
        
        try:
            # First, update the product with options
            options_result = self.update_product_options(product_id, options)
            
            if 'errors' in options_result:
                return {
                    'success': False,
                    'message': 'Failed to create product options',
                    'error': options_result.get('errors')
                }
            
            # Then create variants based on the matrix
            variants_result = self.create_variants_for_product(product_id, variants_matrix)
            
            return {
                'success': variants_result['success'],
                'message': f"Created {variants_result['variants_created']} variants with options",
                'options': options,
                'variants': variants_result['variants'],
                'variants_created': variants_result['variants_created'],
                'errors': variants_result.get('errors', [])
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error creating variants with options: {str(e)}',
                'error': str(e)
            }
    
    def update_product_options(self, product_id: str, options: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Update product options (like Size, Color, etc.)."""
        
        # Ensure proper GraphQL ID format
        if not product_id.startswith('gid://shopify/Product/'):
            product_id = f"gid://shopify/Product/{product_id}"
        
        mutation = """
        mutation productUpdate($input: ProductInput!) {
            productUpdate(input: $input) {
                product {
                    id
                    options {
                        id
                        name
                        values
                    }
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        product_input = {
            'id': product_id,
            'options': options
        }
        
        return self.execute_mutation(mutation, {'input': product_input})
    
    def generate_variant_combinations(self, options: Dict[str, List[str]], 
                                    base_variant_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate all possible variant combinations from options."""
        
        import itertools
        
        option_names = list(options.keys())
        option_values = list(options.values())
        
        # Generate all combinations
        combinations = list(itertools.product(*option_values))
        
        variants = []
        for combo in combinations:
            variant = base_variant_data.copy()
            
            # Create the variant title
            variant['title'] = ' / '.join(combo)
            
            # Set the option values
            variant['options'] = []
            for i, value in enumerate(combo):
                variant['options'].append({
                    'name': option_names[i],
                    'value': value
                })
            
            # Generate SKU if not provided
            if 'sku' not in variant:
                sku_parts = [base_variant_data.get('basesku', 'PRODUCT')]
                sku_parts.extend([v.replace(' ', '').upper()[:3] for v in combo])
                variant['sku'] = '-'.join(sku_parts)
            
            variants.append(variant)
        
        return variants
    
    def bulk_update_inventory(self, inventory_updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Bulk update inventory for multiple variants."""
        
        updated_variants = []
        errors = []
        
        for update in inventory_updates:
            try:
                variant_id = update.get('variant_id')
                inventory_quantity = update.get('inventory_quantity')
                
                if not variant_id or inventory_quantity is None:
                    errors.append({
                        'update': update,
                        'error': 'variant_id and inventory_quantity are required'
                    })
                    continue
                
                result = self.update_single_variant(variant_id, {
                    'inventoryQuantity': inventory_quantity,
                    'inventoryManagement': 'SHOPIFY'
                })
                
                if 'errors' in result or result.get('data', {}).get('productVariantUpdate', {}).get('userErrors'):
                    variant_errors = result.get('errors', []) + result.get('data', {}).get('productVariantUpdate', {}).get('userErrors', [])
                    errors.append({
                        'update': update,
                        'errors': variant_errors
                    })
                else:
                    updated_variant = result['data']['productVariantUpdate']['productVariant']
                    updated_variants.append(updated_variant)
                    
            except Exception as e:
                errors.append({
                    'update': update,
                    'error': str(e)
                })
        
        return {
            'success': len(updated_variants) > 0,
            'message': f'Updated inventory for {len(updated_variants)} variants',
            'updated_variants': updated_variants,
            'errors': errors,
            'total_attempted': len(inventory_updates)
        }