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
    
    # Category mapping - Valid Shopify choices for addfea.group
    CATEGORY_MAPPING = {
        'jewelry': 'Jewelry',
        'jewelry sets': 'Jewelry',
        'jewelry set': 'Jewelry',
        'apparel': 'Apparel',
        'clothing': 'Apparel',
        'dress': 'Apparel',
        'outfit': 'Apparel',
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
        'teardrop': 'Dangler Earrings',
        
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
        
        # Apparel
        'anarkali': 'Anarkali',
        'lehenga': 'Lehenga',
        'blouse': 'Blouse',
        'dupatta': 'Dupatta',
        'gown dress': 'Gown Dress',
        'potli': 'Potli',
        'stole': 'Stole',
        'saree': 'Saree',
        'saree drape': 'Saree Drape',
        'cape': 'Cape',
        'sharara': 'Sharara',
        'peplum': 'Peplum',
        'kurta': 'Kurta',
        'dhoti': 'Dhoti',
        'skirt': 'Skirt',
        'jacket': 'Jacket',
        'shirt': 'Shirt',
        'salwar': 'Salwar',
        'pajami': 'Pajami',
        'churidaar': 'Churidaar',
        'top': 'Top',
        'trouser': 'Trouser',
        'blazer': 'Blazer',
        'pants': 'Pants',
        'bundi': 'Bundi',
        'sherwani': 'Sherwani',
        'tuxedo shirt': 'Tuxedo Shirt',
        
        # Accessories
        'belt': 'Belt',
    }
    
    # Color mapping - Valid Shopify color choices for addfea.color
    COLOR_MAPPING = {
        'aquamarine': 'Aquamarine',
        'black': 'Black',
        'blue': 'Blue',
        'beige': 'Beige',
        'brown': 'Brown',
        'copper': 'Copper',
        'cream': 'Cream',
        'emerald': 'Emerald',
        'fawn': 'Fawn',
        'fuschia pink': 'Fuschia Pink',
        'fuchsia pink': 'Fuschia Pink',
        'golden': 'Golden',
        'green': 'Green',
        'grey': 'Grey',
        'gray': 'Grey',
        'indigo': 'Indigo',
        'ivory': 'Ivory',
        'lemon': 'Lemon',
        'lilac': 'Lilac',
        'maroon': 'Maroon',
        'mint': 'Mint',
        'multi color': 'Multi Color',
        'multicolor': 'Multi Color',
        'mustard': 'Mustard',
        'navy blue': 'Navy Blue',
        'orange': 'Orange',
        'olive': 'Olive',
        'peach': 'Peach',
        'pink': 'Pink',
        'purple': 'Purple',
        'red': 'Red',
        'rose gold': 'Rose Gold',
        'ruby': 'Ruby',
        'sapphire': 'Sapphire',
        'silver': 'Silver',
        'sky blue': 'Sky Blue',
        'wine': 'Wine',
        'white': 'White',
        'yellow': 'Yellow',
    }
    
    # Earring design mapping
    EARRING_DESIGN_MAPPING = {
        'stud': 'Stud Earrings',
        'studs': 'Stud Earrings',
        'dangle': 'Dangler Earrings',
        'dangler': 'Dangler Earrings',
        'drop': 'Dangler Earrings',
        'teardrop': 'Dangler Earrings',
        'hoop': 'Hoop Earrings',
        'jhumka': 'Jhumka Earrings',
        'chaand baali': 'Chaand Baali Earrings',
        'chandbali': 'Chaand Baali Earrings',
        'maang teeka': 'Maang Teeka',
        'matha patti': 'Matha Patti',
        'sheeshphool': 'Sheeshphool',
    }
    
    # Necklace design mapping
    NECKLACE_DESIGN_MAPPING = {
        'choker': 'Choker Necklace',
        'collar': 'Collar Necklace',
        'long': 'Long Necklace',
        'pendant': 'Choker Necklace',
        'chain': 'Choker Necklace',
    }
    
    # Ring design mapping
    RING_DESIGN_MAPPING = {
        'ring': 'Ring',
        'cocktail ring': 'Ring',
        'statement ring': 'Ring',
    }
    
    # Bracelet design mapping
    BRACELET_DESIGN_MAPPING = {
        'bracelet': 'Bracelet',
        'bangle': 'Bangle',
        'kada': 'Kada',
        'haath phool': 'Haath Phool',
    }
    
    # Finish mapping
    FINISH_MAPPING = {
        '22k gold': '22K Gold Plated',
        '22k gold plated': '22K Gold Plated',
        '18k gold': '18K Gold Plated',
        '18k gold plated': '18K Gold Plated',
        'rose gold': 'Rose Gold Plated',
        'rose gold-plated': 'Rose Gold Plated',
        'rose gold plated': 'Rose Gold Plated',
        'white gold': 'White Gold Plated',
        'white gold-plated': 'White Gold Plated',
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
        """Map CSV gender value to Shopify metafield choice"""
        if not value:
            return None
        normalized = str(value).strip().lower()
        return MetafieldValueMapper.GENDER_MAPPING.get(normalized, value)
    
    @staticmethod
    def map_category(value: str) -> str:
        """Map CSV category value to Shopify metafield choice"""
        if not value:
            return None
        normalized = str(value).strip().lower()
        return MetafieldValueMapper.CATEGORY_MAPPING.get(normalized, value)
    
    @staticmethod
    def map_component(value: str) -> str:
        """Map CSV component value to Shopify metafield choice"""
        if not value:
            return None
        normalized = str(value).strip().lower()
        return MetafieldValueMapper.COMPONENTS_MAPPING.get(normalized, value)
    
    @staticmethod
    def map_color(value: str) -> str:
        """Map CSV color value to Shopify metafield choice"""
        if not value:
            return None
        normalized = str(value).strip().lower()
        return MetafieldValueMapper.COLOR_MAPPING.get(normalized, value)
    
    @staticmethod
    def map_earring_design(value: str) -> str:
        """Map CSV earring design to Shopify metafield choice"""
        if not value:
            return None
        normalized = str(value).strip().lower()
        return MetafieldValueMapper.EARRING_DESIGN_MAPPING.get(normalized, value)
    
    @staticmethod
    def map_necklace_design(value: str) -> str:
        """Map CSV necklace design to Shopify metafield choice"""
        if not value:
            return None
        normalized = str(value).strip().lower()
        return MetafieldValueMapper.NECKLACE_DESIGN_MAPPING.get(normalized, value)
    
    @staticmethod
    def map_ring_design(value: str) -> str:
        """Map CSV ring design to Shopify metafield choice"""
        if not value:
            return None
        normalized = str(value).strip().lower()
        return MetafieldValueMapper.RING_DESIGN_MAPPING.get(normalized, value)
    
    @staticmethod
    def map_bracelet_design(value: str) -> str:
        """Map CSV bracelet design to Shopify metafield choice"""
        if not value:
            return None
        normalized = str(value).strip().lower()
        return MetafieldValueMapper.BRACELET_DESIGN_MAPPING.get(normalized, value)
    
    @staticmethod
    def map_finish(value: str) -> str:
        """Map CSV finish value to Shopify metafield choice"""
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
        
        return value  # Return original value if no mapping found
    
    @staticmethod
    def map_components_list(csv_value: str) -> list:
        """Map CSV components string (comma-separated) to list of valid Shopify values"""
        if not csv_value:
            return []
        
        components = [c.strip() for c in str(csv_value).split(',')]
        mapped_components = []
        
        for component in components:
            mapped = MetafieldValueMapper.map_component(component)
            if mapped and mapped not in mapped_components:
                mapped_components.append(mapped)
        
        return mapped_components
