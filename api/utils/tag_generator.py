"""
Enhanced Tag Generation System for MINAKI Products
Generates comprehensive and SEO-optimized tags for jewelry products
"""

from typing import List, Dict, Any, Set
import re


class TagGenerator:
    """
    Advanced tag generation system for jewelry products
    Creates relevant, SEO-friendly tags based on product attributes
    """
    
    def __init__(self):
        # Price range mappings
        self.price_ranges = {
            "₹0-₹999": lambda p: p < 1000,
            "₹1000-₹2999": lambda p: 1000 <= p < 3000,
            "₹3000-₹4999": lambda p: 3000 <= p < 5000,
            "₹5000-₹9999": lambda p: 5000 <= p < 10000,
            "₹10000-₹19999": lambda p: 10000 <= p < 20000,
            "₹20000+": lambda p: p >= 20000
        }
        
        # Category to tag mappings
        self.category_mappings = {
            "Earrings": ["earrings", "ear jewelry", "studs", "hoops", "danglers"],
            "Necklace": ["necklace", "chains", "pendants", "chokers", "collar"],
            "Bracelet": ["bracelets", "bangles", "arm jewelry", "wrist wear"],
            "Ring": ["rings", "finger rings", "band rings"],
            "Set": ["jewelry sets", "sets", "matching sets", "bridal sets"],
            "Bangles": ["bangles", "kada", "arm bands"],
            "Anklet": ["anklets", "payal", "foot jewelry"],
            "Maang Tikka": ["maang tikka", "hair jewelry", "forehead jewelry"],
            "Nose Ring": ["nose rings", "nath", "nose jewelry"],
            "Toe Ring": ["toe rings", "foot jewelry"]
        }
        
        # Style to tag mappings
        self.style_mappings = {
            "Temple": ["temple jewelry", "traditional", "south indian", "antique"],
            "Modern": ["modern jewelry", "contemporary", "trendy", "fashion"],
            "Kundan": ["kundan", "royal", "mughal", "traditional"],
            "Polki": ["polki", "uncut diamonds", "traditional", "royal"],
            "Crystal": ["crystal jewelry", "sparkle", "glamour", "party wear"],
            "Pearl": ["pearl jewelry", "pearls", "classic", "elegant"],
            "Diamond": ["diamond jewelry", "precious", "luxury", "bridal"],
            "Gold": ["gold jewelry", "precious metal", "luxury"],
            "Silver": ["silver jewelry", "sterling silver", "oxidized"]
        }
        
        # Color to standardized color tags
        self.color_mappings = {
            "Gold": ["color-Gold", "Golden", "Yellow Gold"],
            "Silver": ["color-Silver", "White", "Platinum Look"],
            "Rose Gold": ["color-Rose Gold", "Pink Gold", "Copper"],
            "Black": ["color-Black", "Dark", "Oxidized"],
            "White": ["color-White", "Pearl White", "Crystal"],
            "Red": ["color-Red", "Ruby Red", "Maroon"],
            "Blue": ["color-Blue", "Sapphire Blue", "Navy"],
            "Green": ["color-Green", "Emerald Green", "Mint"],
            "Pink": ["color-Pink", "Rose", "Blush"],
            "Purple": ["color-Purple", "Violet", "Lavender"],
            "Yellow": ["color-Yellow", "Amber", "Citrine"],
            "Orange": ["color-Orange", "Coral", "Sunset"],
            "Multi": ["color-Multi", "Rainbow", "Multicolored"]
        }
        
        # Finish to tag mappings
        self.finish_mappings = {
            "Gold Plated": ["Finish:Gold Plated", "plated", "affordable luxury"],
            "Silver Plated": ["Finish:Silver Plated", "plated", "budget friendly"],
            "Rose Gold Plated": ["Finish:Rose Gold Plated", "trendy", "modern"],
            "Oxidized": ["Finish:Oxidized", "antique look", "vintage"],
            "Matte": ["Finish:Matte", "brushed", "contemporary"],
            "Polished": ["Finish:Polished", "shiny", "lustrous"],
            "Antique": ["Finish:Antique", "vintage", "traditional"],
            "Rhodium": ["Finish:Rhodium", "white gold look", "premium"]
        }
        
        # Occasion mappings
        self.occasion_mappings = {
            "Wedding": ["wedding", "bridal", "marriage", "ceremony"],
            "Party": ["party wear", "celebration", "festive", "special occasion"],
            "Daily": ["daily wear", "everyday", "casual", "office wear"],
            "Festival": ["festival", "festive", "traditional", "celebration"],
            "Engagement": ["engagement", "proposal", "romantic", "love"],
            "Office": ["office wear", "professional", "formal", "work"],
            "Anniversary": ["anniversary", "milestone", "celebration"],
            "Birthday": ["birthday", "gift", "special day"],
            "Religious": ["religious", "spiritual", "temple", "prayer"]
        }
        
        # Gender mappings
        self.gender_mappings = {
            "Woman": ["women", "feminine", "ladies", "female"],
            "Man": ["men", "masculine", "gents", "male"],
            "Unisex": ["unisex", "universal", "both"]
        }
        
        # Core business tags (always included)
        self.core_tags = [
            "jewellery",
            "Vendor  MINAKI",
            "Ready to Ship"
        ]
        
        # SEO and marketing tags
        self.marketing_tags = [
            "best seller",
            "trending",
            "new arrival",
            "premium quality",
            "handcrafted",
            "designer jewelry"
        ]

    def generate_comprehensive_tags(
        self,
        product_data: Dict[str, Any],
        ai_generated_content: Dict[str, Any] = None,
        price: float = None,
        availability_days: int = None
    ) -> List[str]:
        """
        Generate comprehensive tags for a jewelry product
        
        Args:
            product_data: Product information from CSV
            ai_generated_content: AI-generated content with keywords
            price: Product price for price range tags
            availability_days: Days for shipping/availability
            
        Returns:
            List of unique, relevant tags
        """
        tags = set()
        
        # 1. Add core business tags
        tags.update(self.core_tags)
        
        # 2. Category-based tags
        category = product_data.get('category', '').strip()
        if category:
            tags.add(category)
            tags.add(category.lower())
            # Add category-specific tags
            for cat, tag_list in self.category_mappings.items():
                if category.lower() in cat.lower() or cat.lower() in category.lower():
                    tags.update(tag_list)
        
        # 3. Style-based tags
        style = product_data.get('style', '').strip()
        if style:
            tags.add(style)
            tags.add(f"{style} Jewellery")
            # Add style-specific tags
            for style_key, tag_list in self.style_mappings.items():
                if style.lower() in style_key.lower() or style_key.lower() in style.lower():
                    tags.update(tag_list)
        
        # 4. Color-based tags
        primary_color = product_data.get('primary_color', '').strip()
        secondary_color = product_data.get('secondary_color', '').strip()
        
        for color in [primary_color, secondary_color]:
            if color:
                tags.add(color)
                # Add standardized color tags
                for color_key, tag_list in self.color_mappings.items():
                    if color.lower() in color_key.lower() or color_key.lower() in color.lower():
                        tags.update(tag_list)
        
        # 5. Finish-based tags
        finish = product_data.get('finish', '').strip()
        if finish:
            tags.add(f"Finish:{finish}")
            # Add finish-specific tags
            for finish_key, tag_list in self.finish_mappings.items():
                if finish.lower() in finish_key.lower() or finish_key.lower() in finish.lower():
                    tags.update(tag_list)
        
        # 6. Components tags
        components = product_data.get('components', '').strip()
        if components:
            component_list = [comp.strip() for comp in components.split(',') if comp.strip()]
            for component in component_list:
                tags.add(f"Component:{component}")
                tags.add(component.lower())
        
        # 7. Finding/Work tags (Stone Settings)
        finding = product_data.get('finding', '').strip()
        work = product_data.get('work', '').strip()
        
        for stone_work in [finding, work]:
            if stone_work:
                tags.add(f"Stone Setting:{stone_work}")
                tags.add(stone_work)
        
        # 8. Gender tags
        gender = product_data.get('gender', '').strip()
        if gender:
            tags.add(f"Gender:{gender}")
            # Add gender-specific tags
            for gender_key, tag_list in self.gender_mappings.items():
                if gender.lower() in gender_key.lower():
                    tags.update(tag_list)
        
        # 9. Occasion tags
        occasions = product_data.get('occasions', '').strip()
        if occasions:
            occasion_list = [occ.strip() for occ in occasions.split(',') if occ.strip()]
            for occasion in occasion_list:
                tags.add(occasion)
                # Add occasion-specific tags
                for occ_key, tag_list in self.occasion_mappings.items():
                    if occasion.lower() in occ_key.lower() or occ_key.lower() in occasion.lower():
                        tags.update(tag_list)
        
        # 10. Price range tags
        if price is not None and price > 0:
            for price_tag, price_check in self.price_ranges.items():
                if price_check(price):
                    tags.add(price_tag)
                    break
        
        # 11. Availability tags
        if availability_days is not None:
            if availability_days <= 3:
                tags.update(["3days", f"availability-{availability_days} Days", "Quick Delivery"])
            elif availability_days <= 7:
                tags.update(["7days", f"availability-{availability_days} Days", "Fast Shipping"])
            elif availability_days <= 21:
                tags.update([f"{availability_days} Days", f"availability-{availability_days} Days"])
            else:
                tags.add("Custom Order")
        
        # 12. AI-generated keyword tags
        if ai_generated_content:
            self._add_ai_keywords_as_tags(tags, ai_generated_content)
        
        # 13. Add some marketing tags based on product characteristics
        self._add_marketing_tags(tags, product_data)
        
        # 14. Add care and shipping info tags
        tags.update([
            "tabt4_Care",
            "tabt4_Payments & Shipping"
        ])
        
        # Clean and return tags
        return self._clean_and_validate_tags(list(tags))
    
    def _add_ai_keywords_as_tags(self, tags: Set[str], ai_content: Dict[str, Any]) -> None:
        """Extract relevant keywords from AI-generated content to use as tags"""
        
        # Extract keywords from title
        title = ai_content.get('title', '')
        if title:
            # Extract meaningful words (more than 2 characters, not common words)
            words = re.findall(r'\b[A-Za-z]{3,}\b', title)
            common_words = {'the', 'and', 'for', 'with', 'you', 'your', 'this', 'that', 'from', 'are', 'was', 'will', 'can'}
            meaningful_words = [word.lower() for word in words if word.lower() not in common_words]
            tags.update(meaningful_words[:5])  # Add top 5 meaningful words
        
        # Extract keywords from description
        description = ai_content.get('description', '')
        if description:
            # Look for jewelry-specific terms
            jewelry_terms = re.findall(
                r'\b(?:elegant|stunning|beautiful|exquisite|crafted|delicate|intricate|sophisticated|glamorous|timeless|classic|modern|traditional|luxury|premium)\b',
                description,
                re.IGNORECASE
            )
            tags.update([term.lower() for term in jewelry_terms[:3]])
    
    def _add_marketing_tags(self, tags: Set[str], product_data: Dict[str, Any]) -> None:
        """Add marketing tags based on product characteristics"""
        
        # Add best seller tag for certain styles
        style = product_data.get('style', '').lower()
        if any(popular_style in style for popular_style in ['temple', 'kundan', 'modern', 'crystal']):
            tags.add("best seller")
        
        # Add collections tag for sets
        if product_data.get('category', '').lower() == 'set':
            tags.add("collections")
        
        # Add handcrafted for traditional styles
        if any(traditional in style for traditional in ['temple', 'kundan', 'antique']):
            tags.add("handcrafted")
        
        # Add trending for modern styles
        if any(modern in style for modern in ['modern', 'contemporary', 'crystal']):
            tags.add("trending")
    
    def _clean_and_validate_tags(self, tags: List[str]) -> List[str]:
        """Clean, validate and optimize tags list"""
        
        # Remove empty tags and clean whitespace
        clean_tags = []
        for tag in tags:
            if tag and isinstance(tag, str):
                cleaned_tag = tag.strip()
                if cleaned_tag and len(cleaned_tag) > 1:  # Minimum 2 characters
                    clean_tags.append(cleaned_tag)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_tags = []
        for tag in clean_tags:
            if tag.lower() not in seen:
                seen.add(tag.lower())
                unique_tags.append(tag)
        
        # Limit to reasonable number of tags (Shopify recommends max 250 chars total)
        # Prioritize important tags
        priority_keywords = [
            'jewellery', 'vendor', 'minaki', 'finish:', 'component:', 'stone setting:',
            'gender:', 'color-', 'wedding', 'bridal', 'best seller'
        ]
        
        priority_tags = []
        other_tags = []
        
        for tag in unique_tags:
            if any(keyword in tag.lower() for keyword in priority_keywords):
                priority_tags.append(tag)
            else:
                other_tags.append(tag)
        
        # Combine priority tags first, then others (max ~40 tags to stay under char limit)
        final_tags = priority_tags + other_tags[:40-len(priority_tags)]
        
        return final_tags[:40]  # Hard limit of 40 tags
    
    def generate_simple_tags(self, product_data: Dict[str, Any]) -> List[str]:
        """
        Generate a simpler tag set for basic use cases
        """
        tags = set()
        
        # Core tags
        tags.update(["jewellery", "Vendor  MINAKI"])
        
        # Category
        if product_data.get('category'):
            tags.add(product_data['category'].lower())
        
        # Style
        if product_data.get('style'):
            tags.add(product_data['style'])
        
        # Colors
        if product_data.get('primary_color'):
            tags.add(f"color-{product_data['primary_color']}")
        
        # Gender
        if product_data.get('gender'):
            tags.add(product_data['gender'].lower())
        
        # Basic marketing tags
        tags.update(["wedding", "tabt4_Care"])
        
        return list(tags)


# Convenience function for easy import
def generate_product_tags(
    product_data: Dict[str, Any],
    ai_content: Dict[str, Any] = None,
    price: float = None,
    availability_days: int = None
) -> List[str]:
    """
    Generate comprehensive tags for a product
    
    Usage:
        tags = generate_product_tags(
            product_data={'category': 'Earrings', 'style': 'Temple', ...},
            ai_content={'title': 'Beautiful Temple Earrings', ...},
            price=2500,
            availability_days=3
        )
    """
    generator = TagGenerator()
    return generator.generate_comprehensive_tags(product_data, ai_content, price, availability_days)