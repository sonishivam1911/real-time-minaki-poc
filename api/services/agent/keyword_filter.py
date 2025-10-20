"""
KEYWORD FILTERING SYSTEM
Filters Google Keyword Planner keywords based on product category and line
Returns TOP 20-30 HIGH VOLUME keywords
INCLUDES: YoY trend + 3-month trend scoring
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple


class KeywordFilter:
    """
    Filters keywords based on product attributes
    Focus: HIGH VOLUME keywords with TRENDING data
    """
    
    # Keyword categories for kundan-polki line
    KUNDAN_POLKI_TERMS = {
        'primary': ['kundan', 'polki', 'jadau'],
        'occasions': ['bridal', 'bride', 'wedding', 'engagement', 'festive', 'ceremony'],
        'types': ['jewelry set', 'jewellery set', 'necklace set', 'choker set', 'set'],
        'styles': ['traditional', 'indian', 'ethnic', 'royal', 'regal', 'temple'],
        'techniques': ['meenakari', 'antique'],
        'materials': ['gold plated', '22k', 'pearl']
    }
    
    # Terms to EXCLUDE
    EXCLUDE_TERMS = [
        'ring', 'rings',  # Unless product is ring
        'men', 'mens', 'man', 'groom',
        'boys', 'kids', 'children', 'baby',
        'diamond ring', 'engagement ring', 'solitaire',
        'gold coin', 'gold bar', 'bullion',
        'watch', 'watches',
        'chain for men', 'bracelet for men',
        'tattoo', 'piercing',
        'repair', 'cleaning', 'box', 'organizer'
    ]
    
    def __init__(self, keywords_df: pd.DataFrame):
        """
        Initialize with keywords DataFrame
        
        Args:
            keywords_df: DataFrame from Google Keyword Planner CSV
                Required columns: 
                - 'Keyword'
                - 'Avg. monthly searches'
                - 'Competition (indexed value)'
                - 'Three month change'
                - 'YoY change'
        """
        self.keywords_df = keywords_df.copy()
        
        # Clean column names
        self.keywords_df.columns = self.keywords_df.columns.str.strip()
        
        # Convert search volume to numeric
        if self.keywords_df['Avg. monthly searches'].dtype == 'object':
            self.keywords_df['Avg. monthly searches'] = pd.to_numeric(
                self.keywords_df['Avg. monthly searches'].str.replace(',', ''),
                errors='coerce'
            ).fillna(0).astype(int)
        
        # Convert trend columns to numeric (remove % signs)
        for col in ['Three month change', 'YoY change']:
            if col in self.keywords_df.columns:
                self.keywords_df[col] = self.keywords_df[col].astype(str).str.replace('%', '').str.replace(',', '')
                self.keywords_df[col] = pd.to_numeric(self.keywords_df[col], errors='coerce').fillna(0)
        
        print(f"📊 Loaded {len(self.keywords_df)} keywords from CSV")
    
    def filter_for_kundan_polki(
        self, 
        product_color: str = None,
        min_searches: int = 1000,  # HIGH VOLUME threshold
        top_n: int = 30
    ) -> pd.DataFrame:
        """
        Filter keywords for kundan-polki jewelry sets
        Returns TOP 30 HIGH VOLUME + TRENDING keywords
        
        Args:
            product_color: Product color (e.g., "green", "red", "emerald")
            min_searches: Minimum monthly searches (default: 1000 for HIGH volume)
            top_n: Number of top keywords to return (default: 30)
        
        Returns:
            DataFrame with filtered and ranked keywords
        """
        print("\n" + "="*80)
        print("FILTERING KEYWORDS FOR KUNDAN-POLKI LINE")
        print("="*80)
        
        df = self.keywords_df.copy()
        
        # STEP 1: Build relevant terms list
        relevant_terms = self._get_relevant_terms(product_color)
        print(f"\n✓ Relevant terms: {', '.join(relevant_terms[:10])}...")
        
        # STEP 2: Filter by relevance (contains ANY relevant term)
        pattern = '|'.join(relevant_terms)
        df['keyword_lower'] = df['Keyword'].str.lower()
        df = df[df['keyword_lower'].str.contains(pattern, case=False, na=False)]
        print(f"✓ After relevance filter: {len(df)} keywords")
        
        # STEP 3: Remove excluded terms
        exclude_pattern = '|'.join(self.EXCLUDE_TERMS)
        df = df[~df['keyword_lower'].str.contains(exclude_pattern, case=False, na=False)]
        print(f"✓ After exclusion filter: {len(df)} keywords")
        
        # STEP 4: Filter by HIGH search volume
        df = df[df['Avg. monthly searches'] >= min_searches]
        print(f"✓ After volume filter (>={min_searches}): {len(df)} keywords")
        
        if len(df) == 0:
            print("⚠️  No keywords found! Trying lower threshold...")
            # Fallback to medium volume if no high volume keywords
            df = self.keywords_df.copy()
            df['keyword_lower'] = df['Keyword'].str.lower()
            df = df[df['keyword_lower'].str.contains(pattern, case=False, na=False)]
            df = df[~df['keyword_lower'].str.contains(exclude_pattern, case=False, na=False)]
            df = df[df['Avg. monthly searches'] >= 100]  # Lower threshold
            print(f"✓ With lower threshold (>=100): {len(df)} keywords")
        
        # STEP 5: Calculate relevance score WITH TRENDS
        df['relevance_score'] = df.apply(
            lambda row: self._calculate_score_with_trends(row, relevant_terms),
            axis=1
        )
        
        # STEP 6: Sort by score and get top N
        df = df.sort_values('relevance_score', ascending=False)
        top_keywords = df.head(top_n)
        
        print(f"\n✓ Returning TOP {len(top_keywords)} keywords (with trend scoring)")
        print("="*80)
        
        # Clean up and return
        result = top_keywords[[
            'Keyword', 
            'Avg. monthly searches', 
            'Three month change',
            'YoY change',
            'Competition (indexed value)',
            'relevance_score'
        ]].copy()
        
        return result
    
    def _get_relevant_terms(self, product_color: str = None) -> List[str]:
        """
        Get all relevant search terms for kundan-polki line
        """
        terms = []
        
        # Add all kundan-polki terms
        for category, term_list in self.KUNDAN_POLKI_TERMS.items():
            terms.extend(term_list)
        
        # Add color-specific terms if provided
        if product_color:
            color_lower = product_color.lower()
            
            if any(c in color_lower for c in ['green', 'emerald']):
                terms.extend(['green', 'emerald'])
            
            if any(c in color_lower for c in ['red', 'ruby']):
                terms.extend(['red', 'ruby'])
            
            if any(c in color_lower for c in ['blue', 'sapphire']):
                terms.extend(['blue', 'sapphire'])
            
            if any(c in color_lower for c in ['pink', 'rose']):
                terms.extend(['pink', 'rose'])
            
            if 'pearl' in color_lower or 'white' in color_lower:
                terms.extend(['pearl', 'white'])
        
        # Remove duplicates
        return list(set(terms))
    
    def _calculate_trend_boost(self, three_month_change: float, yoy_change: float) -> float:
        """
        Calculate trend boost score based on 3-month and YoY changes
        
        Weighting: YoY (70%) + 3-month (30%)
        
        Returns:
            Trend boost score (0 to 15,000)
        """
        # YoY trend scoring (70% weight)
        if yoy_change >= 500:  # Explosive growth
            yoy_score = 10000
        elif yoy_change >= 200:  # Very high growth
            yoy_score = 7000
        elif yoy_change >= 100:  # High growth
            yoy_score = 5000
        elif yoy_change >= 50:   # Good growth
            yoy_score = 3000
        elif yoy_change >= 10:   # Moderate growth
            yoy_score = 1500
        elif yoy_change >= 0:    # Stable
            yoy_score = 500
        elif yoy_change >= -20:  # Slight decline
            yoy_score = -500
        else:                    # Declining
            yoy_score = -2000
        
        # 3-month trend scoring (30% weight)
        if three_month_change >= 500:  # Explosive recent growth
            three_month_score = 5000
        elif three_month_change >= 200:  # Very high recent growth
            three_month_score = 3500
        elif three_month_change >= 100:  # High recent growth
            three_month_score = 2500
        elif three_month_change >= 50:   # Good recent growth
            three_month_score = 1500
        elif three_month_change >= 10:   # Moderate recent growth
            three_month_score = 700
        elif three_month_change >= 0:    # Stable
            three_month_score = 200
        elif three_month_change >= -20:  # Slight decline
            three_month_score = -300
        else:                            # Declining
            three_month_score = -1000
        
        # Combine with weights
        total_trend_boost = (yoy_score * 0.7) + (three_month_score * 0.3)
        
        return total_trend_boost
    
    def _calculate_score_with_trends(self, row: pd.Series, relevant_terms: List[str]) -> float:
        """
        Calculate relevance score with TREND FACTORS
        
        Formula:
        score = (search_volume * 0.4) +           # 40% weight
                (term_match_count * 5000 * 0.15) +  # 15% weight
                (primary_bonus * 0.15) +           # 15% weight
                (trend_boost * 0.3)                # 30% weight for TRENDS!
        
        Trends now account for 30% of the score!
        """
        keyword_lower = row['keyword_lower']
        
        # 1. Count relevant term matches
        match_count = sum(1 for term in relevant_terms if term in keyword_lower)
        
        # 2. Primary term bonus
        primary_bonus = 0
        if 'kundan' in keyword_lower:
            primary_bonus += 10000
        if 'polki' in keyword_lower:
            primary_bonus += 10000
        if 'bridal' in keyword_lower or 'bride' in keyword_lower:
            primary_bonus += 8000
        if 'wedding' in keyword_lower:
            primary_bonus += 6000
        if 'jewelry set' in keyword_lower or 'jewellery set' in keyword_lower:
            primary_bonus += 5000
        
        # 3. Search volume
        searches = row['Avg. monthly searches']
        
        # 4. TREND BOOST (NEW!)
        three_month = row.get('Three month change', 0)
        yoy = row.get('YoY change', 0)
        trend_boost = self._calculate_trend_boost(three_month, yoy)
        
        # Calculate final score with trend weighting
        score = (
            (searches * 0.4) +               # Search volume: 40%
            (match_count * 5000 * 0.15) +    # Term matches: 15%
            (primary_bonus * 0.15) +         # Primary terms: 15%
            (trend_boost * 0.3)              # TRENDS: 30%!
        )
        
        return round(score, 2)
    
    def get_keyword_summary(self, filtered_df: pd.DataFrame) -> Dict:
        """
        Get summary statistics of filtered keywords
        """
        return {
            'total_keywords': len(filtered_df),
            'avg_searches': int(filtered_df['Avg. monthly searches'].mean()),
            'total_searches': int(filtered_df['Avg. monthly searches'].sum()),
            'min_searches': int(filtered_df['Avg. monthly searches'].min()),
            'max_searches': int(filtered_df['Avg. monthly searches'].max()),
            'avg_yoy_change': round(filtered_df['YoY change'].mean(), 1),
            'avg_3month_change': round(filtered_df['Three month change'].mean(), 1),
            'top_5_keywords': filtered_df.head(5)['Keyword'].tolist()
        }
    
    def display_results(self, filtered_df: pd.DataFrame):
        """
        Display filtered keywords with trend data
        """
        print("\n" + "="*80)
        print("TOP FILTERED KEYWORDS (WITH TREND SCORING)")
        print("="*80)
        
        for i, (idx, row) in enumerate(filtered_df.head(30).iterrows(), 1):
            # Trend indicators
            yoy_emoji = "📈" if row['YoY change'] > 0 else ("📉" if row['YoY change'] < 0 else "➡️")
            three_m_emoji = "🔥" if row['Three month change'] > 50 else ("⚡" if row['Three month change'] > 0 else "❄️")
            
            print(f"\n{i}. {row['Keyword']}")
            print(f"   Searches: {row['Avg. monthly searches']:,}/month")
            print(f"   Trends: {yoy_emoji} YoY: {row['YoY change']:+.0f}% | {three_m_emoji} 3M: {row['Three month change']:+.0f}%")
            print(f"   Competition: {row['Competition (indexed value)']}/100")
            print(f"   Final Score: {row['relevance_score']:.2f}")
