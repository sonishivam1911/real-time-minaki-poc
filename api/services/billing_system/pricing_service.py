"""
Pricing Service - Business logic for pricing recalculation
"""
from typing import List, Optional, Dict, Any
from datetime import datetime

from core.database import PostgresCRUD
from core.config import settings
from utils.schema.billing_system.product_schema import MetalRateUpdate


class PricingService:
    """Service for pricing-related business logic"""
    
    def __init__(self):
        self.crud = PostgresCRUD(settings.POSTGRES_URI)
    
    def recalculate_pricing(
        self,
        variant_ids: Optional[List[str]] = None,
        update_metal_rates: Optional[MetalRateUpdate] = None
    ) -> Dict[str, Any]:
        """
        Recalculate pricing for variants.
        
        Args:
            variant_ids: List of variant IDs to recalculate. If None, recalculate all.
            update_metal_rates: New metal rates to apply before recalculation
        
        Returns:
            Result dictionary with success status and count
        """
        try:
            # Step 1: Update metal rates if provided
            if update_metal_rates:
                self._update_metal_rates(variant_ids, update_metal_rates)
            
            # Step 2: Get variants to recalculate
            if variant_ids:
                variant_ids_str = "', '".join(variant_ids)
                variant_query = f"""
                    SELECT id FROM product_variants 
                    WHERE id IN ('{variant_ids_str}')
                """
            else:
                variant_query = "SELECT id FROM product_variants"
            
            variants_df = self.crud.execute_query(variant_query, return_data=True)
            
            # Step 3: Recalculate each variant
            success_count = 0
            errors = []
            
            for _, row in variants_df.iterrows():
                try:
                    self._recalculate_variant_pricing(row['id'])
                    success_count += 1
                except Exception as e:
                    errors.append(f"Variant {row['id']}: {str(e)}")
            
            return {
                'success': True,
                'variants_updated': success_count,
                'message': f'Successfully recalculated pricing for {success_count} variants',
                'errors': errors
            }
            
        except Exception as e:
            return {
                'success': False,
                'variants_updated': 0,
                'message': f'Failed to recalculate pricing: {str(e)}',
                'errors': [str(e)]
            }
    
    def _update_metal_rates(
        self,
        variant_ids: Optional[List[str]],
        metal_rates: MetalRateUpdate
    ) -> None:
        """Update metal rates for metal components"""
        # Build WHERE clause
        where_clause = ""
        if variant_ids:
            variant_ids_str = "', '".join(variant_ids)
            where_clause = f"WHERE variant_id IN ('{variant_ids_str}')"
        
        # Update gold 22k
        if metal_rates.gold_22k:
            query = f"""
                UPDATE metal_components
                SET metal_rate_per_g = {float(metal_rates.gold_22k)}
                WHERE metal_type = 'gold' AND purity_k = 22.00
                {where_clause}
            """
            self.crud.execute_query(query)
        
        # Update gold 18k
        if metal_rates.gold_18k:
            query = f"""
                UPDATE metal_components
                SET metal_rate_per_g = {float(metal_rates.gold_18k)}
                WHERE metal_type = 'gold' AND purity_k = 18.00
                {where_clause}
            """
            self.crud.execute_query(query)
        
        # Update silver
        if metal_rates.silver:
            query = f"""
                UPDATE metal_components
                SET metal_rate_per_g = {float(metal_rates.silver)}
                WHERE metal_type = 'silver'
                {where_clause}
            """
            self.crud.execute_query(query)
        
        # Update platinum
        if metal_rates.platinum:
            query = f"""
                UPDATE metal_components
                SET metal_rate_per_g = {float(metal_rates.platinum)}
                WHERE metal_type = 'platinum'
                {where_clause}
            """
            self.crud.execute_query(query)
    
    def _recalculate_variant_pricing(self, variant_id: str) -> None:
        """Recalculate pricing breakdown for a single variant"""
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
        
        # Calculate suggested retail price
        suggested_retail = final_cost * (1 + settings.DEFAULT_MARGIN_PERCENT / 100)
        
        # Update pricing breakdown
        update_query = f"""
            UPDATE variant_pricing_breakdown
            SET 
                total_metal_value = {float(total_metal_value)},
                total_stone_value = {float(total_stone_value)},
                total_making_charges = {float(total_making_charges)},
                total_wastage_charges = {float(total_wastage_charges)},
                final_cost = {float(final_cost)},
                suggested_retail_price = {float(suggested_retail)},
                last_calculated_at = CURRENT_TIMESTAMP
            WHERE variant_id = '{variant_id}'
        """
        self.crud.execute_query(update_query)
        
        # Update variant base_cost
        update_variant_query = f"""
            UPDATE product_variants
            SET base_cost = {float(final_cost)},
                updated_at = CURRENT_TIMESTAMP
            WHERE id = '{variant_id}'
        """
        self.crud.execute_query(update_variant_query)
    
    def get_current_metal_rates(self) -> Dict[str, float]:
        """Get current metal rates from database"""
        query = """
            SELECT 
                metal_type,
                purity_k,
                AVG(metal_rate_per_g) as avg_rate
            FROM metal_components
            GROUP BY metal_type, purity_k
        """
        df = self.crud.execute_query(query, return_data=True)
        
        rates = {}
        for _, row in df.iterrows():
            key = f"{row['metal_type']}_{int(row['purity_k'])}k"
            rates[key] = float(row['avg_rate'])
        
        return rates