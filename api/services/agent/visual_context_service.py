"""
Groq Multimodal Visual Context Service for Minaki Jewelry Analysis
Uses Groq's actual multimodal vision models for real image analysis
"""

import os
import json
import base64
import requests
from typing import Dict, List, Optional
import logging
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from agent.output_parser import ActionParser
from agent.product_writer.visual_analysis_prompt import get_enhanced_visual_analysis_prompt

logger = logging.getLogger(__name__)

class MinakiVisualContextService:
    """
    Visual context service using Groq's multimodal vision models
    Analyzes actual jewelry images to provide detailed visual context
    """
    
    def __init__(self):
        self.groq_api_key = os.getenv('GROQ_API_KEY')
        
        if not self.groq_api_key:
            logger.warning("GROQ_API_KEY not set - visual analysis will be unavailable")
        
        # Initialize output parser using the existing ActionParser
        self.output_parser = ActionParser(use_json_repair=True)
        
        # Initialize with Groq's multimodal vision model
        try:
            self.llm = ChatGroq(
                model="meta-llama/llama-4-scout-17b-16e-instruct",  # Groq's multimodal vision model
                temperature=0.3,  # Lower temp for more consistent analysis
                max_tokens=500,   # Allow more tokens for detailed JSON analysis
                groq_api_key=self.groq_api_key,
                model_kwargs={"response_format": {"type": "json_object"}}  # Force JSON output
            )
            logger.info("✅ Initialized Groq multimodal vision model with JSON mode: llama-4-scout-17b-16e-instruct")
        except Exception as e:
            logger.warning(f"Failed to initialize ChatGroq vision model: {e}")
            self.llm = None
    
    def extract_image_urls_from_csv_row(self, product_row: Dict) -> List[str]:
        """
        Extract image URLs from CSV row data - only high_resolution_1
        
        Args:
            product_row: Dictionary containing product data from CSV
            
        Returns:
            List of image URLs found in the product data
        """
        image_urls = []
        
        logger.info(f"DEBUG: Product row has {len(product_row)} keys: {list(product_row.keys())}")
        logger.info(f"DEBUG: Looking for 'high_resolution_1' column...")
        
        # Only look for high_resolution_1 column
        if 'high_resolution_1' in product_row:
            value = product_row['high_resolution_1']
            logger.info(f"DEBUG: high_resolution_1 exists with value: '{value}' (type: {type(value)})")
            
            if value:
                image_url = str(value).strip()
                logger.info(f"DEBUG: After str().strip(): '{image_url}'")
                
                if image_url and image_url.lower() not in ['nan', 'null', 'none', '']:
                    image_urls.append(image_url)
                    logger.info(f"✅ Found image in high_resolution_1: {image_url[:100]}...")
                else:
                    logger.warning(f"DEBUG: Image URL is empty or invalid: '{image_url}'")
            else:
                logger.warning("DEBUG: high_resolution_1 value is falsy (None, empty, etc.)")
        else:
            logger.warning("DEBUG: 'high_resolution_1' column not found in product_row")
        
        if not image_urls:
            logger.warning("❌ No image found in high_resolution_1 column")
        
        return image_urls
    
    def _convert_google_drive_url(self, url: str) -> str:
        """
        Convert Google Drive sharing URL to direct download URL
        
        Args:
            url: Google Drive sharing URL
            
        Returns:
            Direct download URL or original URL if not a Google Drive link
        """
        if 'drive.google.com' in url:
            try:
                # Extract file ID from various Google Drive URL formats
                file_id = None
                
                if '/file/d/' in url:
                    file_id = url.split('/file/d/')[1].split('/')[0]
                elif 'id=' in url:
                    file_id = url.split('id=')[1].split('&')[0]
                elif '/open?id=' in url:
                    file_id = url.split('/open?id=')[1].split('&')[0]
                else:
                    logger.warning(f"Could not extract file ID from Google Drive URL: {url}")
                    return url
                
                if file_id:
                    # Try multiple Google Drive direct download URL formats
                    direct_urls = [
                        f"https://drive.google.com/uc?export=download&id={file_id}",
                        f"https://drive.google.com/uc?id={file_id}&export=download",
                        f"https://docs.google.com/uc?export=download&id={file_id}",
                        f"https://lh3.googleusercontent.com/d/{file_id}"
                    ]
                    
                    # Try each URL format to see which one works
                    for direct_url in direct_urls:
                        try:
                            logger.info(f"Trying Google Drive URL format: {direct_url}")
                            test_response = requests.head(direct_url, timeout=10, headers={
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                            })
                            content_type = test_response.headers.get('content-type', '')
                            
                            if content_type.startswith('image/'):
                                logger.info(f"✅ Found working Google Drive URL: {direct_url}")
                                return direct_url
                            else:
                                logger.info(f"❌ URL returned content-type: {content_type}")
                        except Exception as e:
                            logger.info(f"❌ URL failed: {e}")
                            continue
                    
                    logger.warning(f"All Google Drive URL formats failed, using original: {url}")
                    return url
                else:
                    logger.warning(f"Could not extract file ID from Google Drive URL: {url}")
                    return url
                    
            except Exception as e:
                logger.error(f"Error converting Google Drive URL: {e}")
                return url
        
        return url
    
    def _download_image_as_base64(self, image_url: str) -> Optional[str]:
        """
        Download image from URL and convert to base64
        
        Args:
            image_url: URL of the image to download
            
        Returns:
            Base64 encoded image string or None if failed
        """
        try:
            # Convert Google Drive URLs if needed
            direct_url = self._convert_google_drive_url(image_url)
            
            logger.info(f"Downloading image from: {direct_url}")
            
            # Download image with timeout and proper headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'image/*',
                'Accept-Language': 'en-US,en;q=0.9'
            }
            
            response = requests.get(direct_url, timeout=30, headers=headers, allow_redirects=True)
            response.raise_for_status()
            
            # Check if response is actually an image
            content_type = response.headers.get('content-type', '')
            logger.info(f"Response content-type: {content_type}")
            
            if not content_type.startswith('image/'):
                # If it's HTML, it might be a Google Drive permission page
                if 'text/html' in content_type and 'drive.google.com' in image_url:
                    logger.warning(f"Google Drive returned HTML - likely a permission issue or virus scan warning")
                    logger.warning(f"Original URL: {image_url}")
                    logger.warning(f"Direct URL: {direct_url}")
                    logger.warning(f"Response preview: {response.text[:200]}...")
                else:
                    logger.warning(f"Downloaded content is not an image: {content_type}")
                return None
            
            # Convert to base64
            image_data = response.content
            
            # Validate that we actually got image data
            if len(image_data) < 100:  # Very small file, probably not a real image
                logger.warning(f"Downloaded data is too small ({len(image_data)} bytes), probably not a valid image")
                return None
            
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            # Get image format
            image_format = content_type.split('/')[-1]
            if image_format == 'jpeg':
                image_format = 'jpg'
            
            logger.info(f"✅ Successfully downloaded and converted image ({len(image_data)} bytes, format: {image_format})")
            return f"data:image/{image_format};base64,{base64_image}"
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error downloading image: {e}")
            return None
        except Exception as e:
            logger.error(f"Error converting image to base64: {e}")
            return None
    
    def create_visual_context(self, image_url: str) -> Dict:
        """
        Create visual context using Groq's multimodal vision model
        
        Args:
            image_url: URL of the jewelry image to analyze
            
        Returns:
            Dictionary containing visual analysis results
        """
        if not self.groq_api_key or not self.llm:
            return {
                'error': 'Groq vision model not configured',
                'token_efficient_description': 'Visual analysis unavailable - Groq not set up.',
                'analysis': self._get_fallback_analysis()
            }
        
        try:
            # Analyze the actual image using Groq's vision model
            analysis_result = self._analyze_with_groq_vision(image_url)
            return analysis_result
            
        except Exception as e:
            logger.error(f"Visual context creation failed: {str(e)}")
            return {
                'error': f'Visual analysis failed: {str(e)}',
                'token_efficient_description': 'Visual analysis failed due to technical error.',
                'analysis': self._get_fallback_analysis()
            }
    
    def _analyze_with_groq_vision(self, image_url: str) -> Dict:
        """
        Analyze jewelry using Groq's multimodal vision capabilities
        
        Args:
            image_url: URL of the jewelry image
            
        Returns:
            Dictionary containing analysis results
        """
        
        # Use the enhanced analysis prompt from the separate file
        analysis_prompt = get_enhanced_visual_analysis_prompt()

        try:
            logger.info("Analyzing with Groq vision model...")
            
            # Download and convert image to base64 for Google Drive links
            base64_image = self._download_image_as_base64(image_url)
            
            if not base64_image:
                logger.error("Failed to download and convert image to base64")
                return self._fallback_url_analysis(image_url)
            
            # Create message with base64 image content for multimodal analysis
            message = HumanMessage(
                content=[
                    {"type": "text", "text": analysis_prompt},
                    {"type": "image_url", "image_url": {"url": base64_image}}
                ]
            )
            
            response = self.llm.invoke([message])
            analysis_text = response.content.strip()
            
            logger.info("✅ Groq vision analysis completed successfully")
            
            # Use existing ActionParser to parse JSON response
            try:
                parsed_json = self.output_parser.safe_json_parse(analysis_text)
                if parsed_json:
                    parsed_analysis = self._convert_enhanced_json_to_analysis(parsed_json)
                    logger.info("✅ Successfully parsed JSON response with ActionParser")
                else:
                    logger.warning("ActionParser returned None, using fallback analysis")
                    parsed_analysis = self._get_fallback_analysis()
            except Exception as parser_error:
                logger.warning(f"ActionParser failed: {parser_error}")
                parsed_analysis = self._get_fallback_analysis()
            
            # Create token-efficient description for LLM context
            token_efficient_desc = self._create_enhanced_token_efficient_description(parsed_analysis)
            
            return {
                'analysis': parsed_analysis,
                'token_efficient_description': token_efficient_desc,
                'raw_analysis': analysis_text,
                'provider': 'groq_vision',
                'model': 'meta-llama/llama-4-scout-17b-16e-instruct'
            }
                
        except Exception as e:
            logger.error(f"Groq vision analysis error: {str(e)}")
            # Fallback to URL-based analysis if vision fails
            return self._fallback_url_analysis(image_url)
    
    def _convert_enhanced_json_to_analysis(self, json_response: Dict) -> Dict:
        """
        Convert enhanced JSON response to internal analysis format
        
        Args:
            json_response: Parsed JSON from output parser with visual analysis fields
            
        Returns:
            Analysis dictionary in internal format
        """
        return {
            "jewelry_type": json_response.get("type", "jewelry piece"),
            "suggested_collection": json_response.get("collection_fit", "ELEGANZA"),
            "stone_type": json_response.get("stone_type", None),
            "neckline_compatibility": json_response.get("neckline_compatibility", None),
            "weight_category": json_response.get("weight_category", "medium_weight"),
            "naming_theme": json_response.get("naming_theme", "modern_minimalist"),
            "bridal_suitability": self._determine_bridal_suitability(
                json_response.get("collection_fit", "ELEGANZA"),
                json_response.get("weight_category", "medium_weight")
            )
        }
    
    def _determine_bridal_suitability(self, collection: str, weight: str) -> str:
        """
        Determine bridal suitability based on collection and weight
        
        Args:
            collection: The identified collection
            weight: The weight category
            
        Returns:
            Bridal suitability assessment
        """
        if collection == "KUNDAN" and weight in ["heavy_ornate", "bridal_heavy"]:
            return "primary_bridal_choice"
        elif collection == "CRYSTAL" and weight in ["heavy_ornate", "bridal_heavy"]:
            return "cocktail_bridal_option"
        elif collection == "TEMPLE" and weight in ["heavy_ornate", "bridal_heavy"]:
            return "traditional_bridal_option"
        elif collection == "XCLUSIVE" and weight in ["heavy_ornate", "bridal_heavy"]:
            return "special_occasion_bridal"
        else:
            return "not_typically_bridal"
    
    def _fallback_url_analysis(self, image_url: str) -> Dict:
        """
        Fallback to URL-based analysis when vision analysis fails
        
        Args:
            image_url: URL of the jewelry image
            
        Returns:
            Dictionary containing fallback analysis
        """
        logger.info("Using fallback URL-based analysis")
        
        # Basic analysis from URL patterns
        url_lower = image_url.lower()
        
        # Try to infer type from URL
        jewelry_type = "jewelry piece"
        if any(term in url_lower for term in ['necklace', 'neck']):
            jewelry_type = "necklace"
        elif any(term in url_lower for term in ['earring', 'ear']):
            jewelry_type = "earrings"
        elif any(term in url_lower for term in ['ring']):
            jewelry_type = "ring"
        elif any(term in url_lower for term in ['bracelet', 'bangle']):
            jewelry_type = "bracelet"
        elif any(term in url_lower for term in ['set']):
            jewelry_type = "jewelry set"
        
        return {
            'analysis': {
                "jewelry_type": jewelry_type,
                "suggested_collection": "ELEGANZA",
                "stone_type": None,
                "neckline_compatibility": None,
                "weight_category": "medium_weight",
                "naming_theme": "modern_minimalist",
                "bridal_suitability": "not_typically_bridal"
            },
            'token_efficient_description': f'URL-based analysis: {jewelry_type} with elegant styling. Collection: ELEGANZA. Weight: medium_weight.',
            'provider': 'url_fallback',
            'note': 'Vision analysis failed, using URL-based inference'
        }
    
    def _create_enhanced_token_efficient_description(self, analysis: Dict) -> str:
        """
        Create an enhanced concise description for LLM context (token-efficient)
        
        Args:
            analysis: Parsed analysis dictionary with enhanced fields
            
        Returns:
            Concise description string with all key information
        """
        jewelry_type = analysis.get("jewelry_type", "jewelry piece")
        collection_fit = analysis.get("suggested_collection", "ELEGANZA")
        stone_type = analysis.get("stone_type", None)
        neckline_compatibility = analysis.get("neckline_compatibility", None)
        weight_category = analysis.get("weight_category", "medium_weight")
        naming_theme = analysis.get("naming_theme", "modern_minimalist")
        bridal_suitability = analysis.get("bridal_suitability", "not_typically_bridal")
        
        description_parts = [
            f"Visual: {jewelry_type}",
            f"Collection: {collection_fit}",
            f"Weight: {weight_category}",
            f"Naming: {naming_theme} theme"
        ]
        
        if stone_type and stone_type.lower() != "null":
            description_parts.append(f"Stones: {stone_type}")
            
        if neckline_compatibility and neckline_compatibility.lower() != "null":
            description_parts.append(f"Necklines: {neckline_compatibility}")
            
        if bridal_suitability != "not_typically_bridal":
            description_parts.append(f"Bridal: {bridal_suitability}")
        
        return ". ".join(description_parts) + "."
    
    def _get_fallback_analysis(self) -> Dict:
        """
        Enhanced fallback analysis when visual analysis fails
        
        Returns:
            Default analysis dictionary with enhanced fields
        """
        return {
            "jewelry_type": "jewelry piece",
            "suggested_collection": "ELEGANZA",
            "stone_type": None,
            "neckline_compatibility": None,
            "weight_category": "medium_weight",
            "naming_theme": "modern_minimalist",
            "bridal_suitability": "not_typically_bridal"
        }
    
    def get_usage_info(self) -> Dict:
        """
        Get information about Groq vision model usage with enhanced capabilities
        
        Returns:
            Usage information dictionary
        """
        return {
            "provider": "Groq Multimodal Vision", 
            "model": "meta-llama/llama-4-scout-17b-16e-instruct",
            "cost": "Groq free tier: 30 RPM, 1K RPD, 30K TPM, 500K TPD",
            "setup_required": "GROQ_API_KEY environment variable",
            "estimated_tokens_per_analysis": "300-600 tokens",
            "collections_supported": [
                "KUNDAN (traditional Indian heritage ₹1,500-29,000)",
                "CRYSTAL (American Diamond ₹6,900-32,000)", 
                "ELEGANZA (modern/contemporary ₹1,000-3,200)",
                "XCLUSIVE (premium luxury ₹1,000-22,500)",
                "TEMPLE (traditional designs ₹1,999-14,999)",
                "MODERN (casual contemporary ₹1,500-6,500)"
            ],
            "capabilities": [
                "Actual image analysis (not just URL)",
                "Detailed jewelry visual inspection",
                "Material and gemstone identification",
                "Color accuracy verification",
                "Craftsmanship assessment",
                "All 6 Minaki collection categorization",
                "Crystal/AD jewelry type identification",
                "Weight category assessment (delicate to bridal-heavy)",
                "Bridal suitability identification",
                "Component and findings analysis",
                "5 meaningful name suggestions per piece",
                "Neckline compatibility analysis",
                "Collection-specific naming themes",
                "Color consistency to prevent hallucination"
            ],
            "naming_themes": {
                "traditional_indian": "For KUNDAN/TEMPLE (Rajwadi, Maharani, Aaravi)",
                "crystal_mystique": "For CRYSTAL (Serpentine, Aurelia, Seraphine)",
                "modern_minimalist": "For ELEGANZA/MODERN (Luna, Nova, Aria)",
                "english_royal": "For XCLUSIVE (Victoria, Elizabeth, Windsor)",
                "french_royal": "For premium pieces (Antoinette, Marguerite, Versailles)"
            },
            "bridal_identification": {
                "primary_bridal_choice": "KUNDAN heavy/ornate pieces",
                "cocktail_bridal_option": "CRYSTAL heavy sets for modern brides",
                "traditional_bridal_option": "TEMPLE heavy pieces for cultural ceremonies",
                "special_occasion_bridal": "XCLUSIVE heavy pieces for luxury events"
            },
            "rate_limits": {
                "requests_per_minute": 30,
                "requests_per_day": 1000,
                "tokens_per_minute": 30000,
                "tokens_per_day": 500000
            },
            "benefits": [
                "Real multimodal vision analysis",
                "Comprehensive jewelry insights",
                "Accurate material identification",
                "Professional naming guidance",
                "Complete Minaki collection targeting",
                "Bridal suitability assessment",
                "Component/findings identification",
                "Color accuracy enforcement",
                "Weight-based categorization",
                "Free tier availability"
            ]
        }


# Legacy alias for backward compatibility
VisualContextService = MinakiVisualContextService

