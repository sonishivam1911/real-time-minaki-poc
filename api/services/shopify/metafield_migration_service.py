import time
from typing import List, Dict, Any
from .product import ShopifyProductService

from utils.logger import logger


class MetafieldMigrationService:
    """
    Service to duplicate/migrate metafields based on CSV mapping rules.
    Reuses existing ShopifyProductService methods.
    """
    
    def __init__(self, shopify_service: ShopifyProductService):
        """
        Initialize migration service.
        
        Args:
            shopify_service: Your existing Shopify product service
        """
        self.shopify = shopify_service
    
    def run_migration(
        self, 
        mapping_rules: List[Dict[str, str]], 
        job_id: str,
        job_status: Dict[str, Any]
    ):
        """
        Run metafield migration job using your existing batch processing.
        
        Process:
        1. Iterate through all products using your get_products_batch_for_db()
        2. For each product, get all metafields using get_complete_product_with_metafields()
        3. Match metafields against CSV rules
        4. Create new metafields using add_metafield_to_product()
        
        Args:
            mapping_rules: List of CSV mapping rules
            job_id: Unique job identifier
            job_status: Shared dict to track job progress
        """
        try:
            job_status["status"] = "processing"
            job_status["start_time"] = time.time()
            job_status["errors"] = []

            logger.info(f"Job {job_id}: Starting metafield migration...")
            logger.info(f"Job {job_id}: Total mapping rules: {len(mapping_rules)}")

            # Process products in batches using YOUR existing method
            batch_number = 0
            
            for product_batch in self.shopify.get_products_batch_for_db(batch_size=10):
                batch_number += 1
                
                if batch_number == 1:
                    job_status["total_products"] = "calculating..."
                
                logger.info(f"Job {job_id}: Processing batch {batch_number} ({len(product_batch)} products)")
                
                for product in product_batch:
                    try:
                        product_id = product["id"]
                        product_title = product.get("title", "Unknown")
                        
                        # Get ALL metafields for this product using YOUR method
                        product_data = self.shopify.get_complete_product_with_metafields(product_id)
                        
                        if not product_data.get("data", {}).get("product"):
                            logger.warning(f"Job {job_id}: Skipping product {product_id} - not found")
                            job_status["skipped"] += 1
                            continue
                        
                        metafields_edges = product_data["data"]["product"]["metafields"]["edges"]
                        metafields = [edge["node"] for edge in metafields_edges]
                        logger.info(f"Job {job_id}: Product '{product_title}' has {metafields}")
                        
                        # Find matching rules and create new metafields
                        new_metafields_created = 0
                        
                        for metafield in metafields:
                            namespace = metafield["namespace"]
                            key = metafield["key"]
                            value = metafield["value"]
                            
                            # Check if any mapping rule matches
                            for rule in mapping_rules:
                                if self._matches_rule(metafield, rule):
                                    logger.info(f"Job {job_id}: MATCH FOUND!")
                                    logger.info(f"  ├─ Product ID: {product_id}")
                                    logger.info(f"  ├─ Product Name: '{product_title}'")
                                    logger.info(f"  ├─ Matched Namespace: {namespace}")
                                    logger.info(f"  ├─ Matched Key: {key}")
                                    logger.info(f"  ├─ Matched Value: {value}")
                                    logger.info(f"  ├─ Will Create: {rule['output_namespace']}.{rule['output_key']}")
                                    logger.info(f"  └─ New Value: {rule['output_value']}")

                                    try:
                                        # Create new metafield using YOUR method
                                        result=self.shopify.add_metafield_to_product(
                                            product_id=product_id,
                                            namespace=rule["output_namespace"],
                                            key=rule["output_key"],
                                            value=rule["output_value"],
                                            field_type=rule["output_type"]
                                        )
                                        
                                        new_metafields_created += 1
                                        
                                        logger.info(f"Job {job_id}: ✅ SUCCESS - Created. Result is : {result}")

                                        # logger.info(f"Job {job_id}: ✅ SUCCESS - Created {rule['output_namespace']}.{rule['output_key']} for product '{product_title}'")
                                        logger.info("=" * 80)

                                    except Exception as e:
                                        error_msg = (f"Error creating metafield for product {product_id} "
                                                   f"({rule['output_namespace']}.{rule['output_key']}): {str(e)}")
                                        print(f"Job {job_id}: ❌ FAILED - {error_msg}")
                                        print("=" * 80)
                                        job_status["errors"].append(error_msg)
                        
                        # Update job status
                        if new_metafields_created > 0:
                            job_status["updated"] += 1
                            job_status["total_metafields_created"] = job_status.get("total_metafields_created", 0) + new_metafields_created
                        else:
                            job_status["skipped"] += 1
                        
                        job_status["processed"] += 1
                        
                        # Rate limiting - respect Shopify limits
                        time.sleep(0.5)
                        
                    except Exception as e:
                        error_msg = f"Error processing product {product.get('id', 'unknown')}: {str(e)}"
                        print(error_msg)
                        job_status["errors"].append(error_msg)
                        job_status["skipped"] += 1
                
                # Log progress after each batch
                logger.info(f"Job {job_id}: Batch {batch_number} complete. "
                      f"Processed: {job_status['processed']}, "
                      f"Updated: {job_status['updated']}, "
                      f"Skipped: {job_status['skipped']}")
            
            # Mark as completed
            job_status["status"] = "completed"
            job_status["end_time"] = time.time()
            job_status["duration_seconds"] = job_status["end_time"] - job_status["start_time"]
            job_status["total_products"] = job_status["processed"]

            logger.info(f"Job {job_id}: Migration completed!")
            logger.info(f"Job {job_id}: Total products processed: {job_status['processed']}")
            logger.info(f"Job {job_id}: Products updated: {job_status['updated']}")
            logger.info(f"Job {job_id}: Products skipped: {job_status['skipped']}")
            logger.info(f"Job {job_id}: Total metafields created: {job_status.get('total_metafields_created', 0)}")

        except Exception as e:
            job_status["status"] = "failed"
            job_status["end_time"] = time.time()
            error_msg = f"Migration job failed: {str(e)}"
            job_status["errors"].append(error_msg)
            print(f"Job {job_id}: {error_msg}")
    
    def _matches_rule(self, metafield: Dict[str, Any], rule: Dict[str, str]) -> bool:
        """
        Check if a metafield matches a mapping rule.
        
        Match criteria:
        - input_namespace matches metafield namespace
        - input_key matches metafield key
        - input_value matches metafield value
        
        Args:
            metafield: Metafield node from GraphQL
            rule: Mapping rule from CSV
            
        Returns:
            True if matches, False otherwise
        """
        namespace_match = metafield["namespace"] == rule["input_namespace"]
        key_match = metafield["key"] == rule["input_key"]
        
        return namespace_match and key_match
    
    def preview_migration(
        self, 
        mapping_rules: List[Dict[str, str]],
        max_products: int = 10
    ) -> Dict[str, Any]:
        """
        Preview what the migration would do without actually creating metafields.
        Useful for testing before running full migration.
        
        Args:
            mapping_rules: List of CSV mapping rules
            max_products: Number of products to preview
            
        Returns:
            Preview statistics
        """
        preview_results = {
            "total_products_checked": 0,
            "products_with_matches": 0,
            "total_matches_found": 0,
            "matches_by_rule": {},
            "sample_matches": []
        }
        
        # Initialize rule counters
        for rule in mapping_rules:
            rule_key = f"{rule['input_namespace']}.{rule['input_key']}={rule['input_value']}"
            preview_results["matches_by_rule"][rule_key] = 0
        
        # Check first N products
        product_count = 0
        
        for product_batch in self.shopify.get_products_batch_for_db(batch_size=10):
            for product in product_batch:
                if product_count >= max_products:
                    break
                
                product_id = product["id"]
                product_title = product.get("title", "Unknown")
                
                # Get metafields
                product_data = self.shopify.get_complete_product_with_metafields(product_id)
                
                if not product_data.get("data", {}).get("product"):
                    continue
                
                metafields_edges = product_data["data"]["product"]["metafields"]["edges"]
                metafields = [edge["node"] for edge in metafields_edges]
                
                product_matches = 0
                
                # Check for matches
                for metafield in metafields:
                    for rule in mapping_rules:
                        if self._matches_rule(metafield, rule):
                            product_matches += 1
                            preview_results["total_matches_found"] += 1
                            
                            rule_key = f"{rule['input_namespace']}.{rule['input_key']}={rule['input_value']}"
                            preview_results["matches_by_rule"][rule_key] += 1
                            
                            # Store sample
                            if len(preview_results["sample_matches"]) < 20:
                                preview_results["sample_matches"].append({
                                    "product_id": product_id,
                                    "product_title": product_title,
                                    "matched_metafield": f"{metafield['namespace']}.{metafield['key']}",
                                    "matched_value": metafield['value'],
                                    "will_create": f"{rule['output_namespace']}.{rule['output_key']}",
                                    "new_value": rule['output_value']
                                })
                
                if product_matches > 0:
                    preview_results["products_with_matches"] += 1
                
                preview_results["total_products_checked"] += 1
                product_count += 1
            
            if product_count >= max_products:
                break
        
        return preview_results