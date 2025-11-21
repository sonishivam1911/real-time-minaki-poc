"""
Metafield Value Mapper
Maps CSV values to valid Shopify metafield choices
"""

class MetafieldValueMapper:
    """Maps product CSV values to valid Shopify metafield enumeration values"""
    
    # Gender mapping - CSV "Female"/"Male" -> Shopify "Women"/"Men"
    GENDER_MAPPING = {
        'female': 'Women',
        'male': 'Men',
        'women': 'Women',
        'men': 'Men',
        'unisex': 'Women',  # Default to Women for unisex
    }
    
    # Components mapping - map jewelry types to valid options
    COMPONENTS_MAPPING = {
        # Necklaces
        'necklace': 'Choker Necklace',
        'choker': 'Choker Necklace',
        'collar': 'Collar Necklace',
        'long necklace': 'Long Necklace',
        'pendant': 'Choker Necklace',
        'chain': 'Choker Necklace',
        
        # Earrings
        'earrings': 'Stud Earrings',
        'studs': 'Stud Earrings',
        'dangle': 'Dangler Earrings',
        'dangler': 'Dangler Earrings',
        'hoop': 'Hoop Earrings',
        'jhumka': 'Jhumka Earrings',
        'chaand baali': 'Chaand Baali Earrings',
        'chandbali': 'Chaand Baali Earrings',
        'drop': 'Dangler Earrings',
        
        # Head accessories
        'maang': 'Maang Teeka',
        'maang tikka': 'Maang Teeka',
        'matha patti': 'Matha Patti',
        'sheeshphool': 'Sheeshphool',
        
        # Bracelets and bangles
        'bracelet': 'Bracelet',
        'bangle': 'Bangle',
        'kada': 'Kada',
        
        # Rings and hand jewelry
        'ring': 'Ring',
        'haath phool': 'Haath Phool',
        
        # Nose and forehead
        'nath': 'Nath',
        'nose ring': 'Nath',
        'borla': 'Borla',
        'passa': 'Passa',
        
        # Accessories
        'belt': 'Belt',
    }
    
    # Finish mapping
    FINISH_MAPPING = {
        '22k gold': '22K Gold Plated',
        '22k gold plated': '22K Gold Plated',
        '18k gold': '18K Gold Plated',
        '18k gold plated': '18K Gold Plated',
        'rose gold': 'Rose Gold Plated',
        'rose gold plated': 'Rose Gold Plated',
        'white gold': 'White Gold Plated',
        'white gold plated': 'White Gold Plated',
        'black rhodium': 'Black Rhodium Polish',
        'black rhodium polish': 'Black Rhodium Polish',
        'zircon': 'Zircon Setting',
        'zircon setting': 'Zircon Setting',
        'enamel': 'Enameling',
        'enameling': 'Enameling',
        'silver': 'White Gold Plated',  # Default to white gold
        'gold': '22K Gold Plated',  # Default to 22K
        'plated': '22K Gold Plated',  # Generic plated -> 22K
    }
    
    @staticmethod
    def map_gender(value: str) -> str:
        """
        Map CSV gender value to Shopify metafield choice
        
        Args:
            value: CSV value (e.g., "Female", "Male")
            
        Returns:
            Valid Shopify metafield value or original if no mapping found
        """
        if not value:
            return None
        
        normalized = str(value).strip().lower()
        return MetafieldValueMapper.GENDER_MAPPING.get(normalized, 'Women')
    
    @staticmethod
    def map_component(value: str) -> str:
        """
        Map CSV component value to Shopify metafield choice
        
        Args:
            value: CSV value (e.g., "Earrings", "Necklace")
            
        Returns:
            Valid Shopify metafield value or original if no mapping found
        """
        if not value:
            return None
        
        normalized = str(value).strip().lower()
        return MetafieldValueMapper.COMPONENTS_MAPPING.get(normalized, 'Bracelet')
    
    @staticmethod
    def map_finish(value: str) -> str:
        """
        Map CSV finish value to Shopify metafield choice
        
        Args:
            value: CSV value (e.g., "Rose gold-plated")
            
        Returns:
            Valid Shopify metafield value or original if no mapping found
        """
        if not value:
            return None
        
        normalized = str(value).strip().lower()
        
        # Try exact match first
        if normalized in MetafieldValueMapper.FINISH_MAPPING:
            return MetafieldValueMapper.FINISH_MAPPING[normalized]
        
        # Try partial matches
        for key, mapped_value in MetafieldValueMapper.FINISH_MAPPING.items():
            if key in normalized or normalized in key:
                return mapped_value
        
        return '22K Gold Plated'  # Safe default
    
    @staticmethod
    def map_components_list(csv_value: str) -> list:
        """
        Map CSV components string (comma-separated) to list of valid Shopify values
        
        Args:
            csv_value: Comma-separated components (e.g., "Earrings, Necklaces")
            
        Returns:
            List of valid Shopify metafield values
        """
        if not csv_value:
            return []
        
        components = [c.strip() for c in str(csv_value).split(',')]
        mapped_components = []
        
        for component in components:
            mapped = MetafieldValueMapper.map_component(component)
            if mapped and mapped not in mapped_components:
                mapped_components.append(mapped)
        
        return mapped_components if mapped_components else ['Bracelet']
