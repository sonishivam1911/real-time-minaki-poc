from typing import List, Dict, Any, Optional
from ..base_connector import BaseShopifyConnector

class ImageRepository(BaseShopifyConnector):
    """Repository for product image operations"""
    
    def upload_product_image(self, product_id: str, image_data: Dict[str, Any]) -> Dict[str, Any]:
        """Upload an image to a product."""
        
        # Ensure proper GraphQL ID format
        if not product_id.startswith('gid://shopify/Product/'):
            product_id = f"gid://shopify/Product/{product_id}"
        
        mutation = """
        mutation productImageCreate($productId: ID!, $image: ImageInput!) {
            productImageCreate(productId: $productId, image: $image) {
                image {
                    id
                    url
                    altText
                    width
                    height
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        variables = {
            'productId': product_id,
            'image': image_data
        }
        
        return self.execute_mutation(mutation, variables)
    
    def upload_multiple_images(self, product_id: str, images_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Upload multiple images to a product."""
        results = []
        
        for image_data in images_data:
            try:
                result = self.upload_product_image(product_id, image_data)
                results.append(result)
            except Exception as e:
                results.append({
                    'error': str(e),
                    'image_data': image_data
                })
        
        return results
    
    def update_product_image(self, image_id: str, image_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing product image."""
        
        # Ensure proper GraphQL ID format
        if not image_id.startswith('gid://shopify/ProductImage/'):
            image_id = f"gid://shopify/ProductImage/{image_id}"
        
        image_data['id'] = image_id
        
        mutation = """
        mutation productImageUpdate($image: ImageInput!) {
            productImageUpdate(image: $image) {
                image {
                    id
                    url
                    altText
                    width
                    height
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        return self.execute_mutation(mutation, {'image': image_data})
    
    def delete_product_image(self, image_id: str) -> Dict[str, Any]:
        """Delete a product image."""
        
        # Ensure proper GraphQL ID format
        if not image_id.startswith('gid://shopify/ProductImage/'):
            image_id = f"gid://shopify/ProductImage/{image_id}"
        
        mutation = """
        mutation productImageDelete($id: ID!) {
            productImageDelete(id: $id) {
                deletedImageId
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        return self.execute_mutation(mutation, {'id': image_id})
    
    def get_product_images(self, product_id: str) -> Dict[str, Any]:
        """Get all images for a product."""
        
        # Ensure proper GraphQL ID format
        if not product_id.startswith('gid://shopify/Product/'):
            product_id = f"gid://shopify/Product/{product_id}"
        
        query = """
        query getProductImages($id: ID!) {
            product(id: $id) {
                id
                title
                images(first: 50) {
                    edges {
                        node {
                            id
                            url
                            altText
                            width
                            height
                        }
                    }
                }
                featuredImage {
                    id
                    url
                    altText
                    width
                    height
                }
            }
        }
        """
        
        return self.execute_query(query, {'id': product_id})
    
    def set_featured_image(self, product_id: str, image_id: str) -> Dict[str, Any]:
        """Set a specific image as the featured image for a product."""
        
        # Ensure proper GraphQL ID formats
        if not product_id.startswith('gid://shopify/Product/'):
            product_id = f"gid://shopify/Product/{product_id}"
        
        if not image_id.startswith('gid://shopify/ProductImage/'):
            image_id = f"gid://shopify/ProductImage/{image_id}"
        
        mutation = """
        mutation productUpdate($input: ProductInput!) {
            productUpdate(input: $input) {
                product {
                    id
                    featuredImage {
                        id
                        url
                        altText
                    }
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        variables = {
            'input': {
                'id': product_id,
                'featuredImage': {
                    'id': image_id
                }
            }
        }
        
        return self.execute_mutation(mutation, variables)
    
    def associate_image_to_variant(self, variant_id: str, image_id: str) -> Dict[str, Any]:
        """Associate an image with a specific product variant."""
        
        # Ensure proper GraphQL ID formats
        if not variant_id.startswith('gid://shopify/ProductVariant/'):
            variant_id = f"gid://shopify/ProductVariant/{variant_id}"
        
        if not image_id.startswith('gid://shopify/ProductImage/'):
            image_id = f"gid://shopify/ProductImage/{image_id}"
        
        mutation = """
        mutation productVariantUpdate($input: ProductVariantInput!) {
            productVariantUpdate(input: $input) {
                productVariant {
                    id
                    image {
                        id
                        url
                        altText
                    }
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        variables = {
            'input': {
                'id': variant_id,
                'imageId': image_id
            }
        }
        
        return self.execute_mutation(mutation, variables)
    
    def reorder_product_images(self, product_id: str, image_ids: List[str]) -> Dict[str, Any]:
        """Reorder product images by providing ordered list of image IDs."""
        
        # Ensure proper GraphQL ID format for product
        if not product_id.startswith('gid://shopify/Product/'):
            product_id = f"gid://shopify/Product/{product_id}"
        
        # Ensure proper GraphQL ID format for images
        formatted_image_ids = []
        for img_id in image_ids:
            if not img_id.startswith('gid://shopify/ProductImage/'):
                formatted_image_ids.append(f"gid://shopify/ProductImage/{img_id}")
            else:
                formatted_image_ids.append(img_id)
        
        mutation = """
        mutation productReorderImages($id: ID!, $moves: [MoveInput!]!) {
            productReorderImages(id: $id, moves: $moves) {
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        # Create move operations based on desired order
        moves = []
        for index, image_id in enumerate(formatted_image_ids):
            moves.append({
                'id': image_id,
                'newPosition': str(index)
            })
        
        variables = {
            'id': product_id,
            'moves': moves
        }
        
        return self.execute_mutation(mutation, variables)