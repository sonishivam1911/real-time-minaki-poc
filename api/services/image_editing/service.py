import os
import shutil
import zipfile
from collections import defaultdict
from typing import Dict, List, Tuple, Any
from PIL import Image
import cv2
import numpy as np
from core.database import db

class ImageProcessingService:
    """Service layer for image processing operations"""
    
    @staticmethod
    def extract_sku_and_number(filename: str) -> Tuple[str, str]:
        """
        Extracts SKU and image number from filename.
        
        Expected format: SKU_NUMBER.jpg (e.g., X000930496_1.jpg)
        
        Args:
            filename: Image filename
            
        Returns:
            Tuple of (sku, image_number) or (None, None) if invalid
        """
        try:
            # Remove extension
            name_without_ext = os.path.splitext(filename)[0]
            
            # Split by underscore
            if '_' not in name_without_ext:
                return None, None
            
            parts = name_without_ext.split('_')
            
            if len(parts) < 2:
                return None, None
            
            sku = parts[0]
            image_number = parts[1]
            
            return sku, image_number
        
        except Exception as e:
            print(f"Error parsing filename {filename}: {e}")
            return None, None
    
    @staticmethod
    def validate_skus_in_database(sku_list: List[str], table_name: str = "products") -> Dict[str, List[str]]:
        """
        Validates if SKUs exist in the database.
        
        Args:
            sku_list: List of SKUs to validate
            table_name: Table name to check
            
        Returns:
            Dictionary with 'valid' and 'invalid' SKU lists
        """
        try:
            # Query database for SKUs
            sku_str = "', '".join(sku_list)
            query = f"SELECT sku FROM {table_name} WHERE sku IN ('{sku_str}')"
            
            df = db.execute_query(query, return_data=True)
            
            if df.empty:
                return {'valid': [], 'invalid': sku_list}
            
            valid_skus = df['sku'].tolist()
            invalid_skus = [sku for sku in sku_list if sku not in valid_skus]
            
            return {'valid': valid_skus, 'invalid': invalid_skus}
        
        except Exception as e:
            print(f"Error validating SKUs: {e}")
            return {'valid': [], 'invalid': sku_list}
    
    @staticmethod
    def remove_watermark(image_path: str, output_dir: str, sku: str, image_number: str) -> str:
        """
        Removes watermark from the image and saves it in the corresponding SKU folder.

        Args:
            image_path: Path to the input image
            output_dir: Directory where processed images will be saved
            sku: SKU identifier for the product
            image_number: Image number (e.g., "1", "2", "3")

        Returns:
            Path to the saved processed image or None if failed
        """
        try:
            # Load the image
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Unable to load image: {image_path}")

            # Get image dimensions
            height, width, _ = image.shape

            # Define watermark regions
            watermark_regions = [
                (0, 3, 260, 189),      # Top-left region for "Xuping"
                (454, 837, 900, 897)   # Bottom-right region for website URL
            ]

            mask = np.zeros((height, width), dtype=np.uint8)

            for x1, y1, x2, y2 in watermark_regions:
                # Ensure coords are in valid range
                x1 = max(0, x1); y1 = max(0, y1)
                x2 = min(width, x2); y2 = min(height, y2)
                mask[y1:y2, x1:x2] = 255

            # Inpaint to remove watermark
            inpainted_image = cv2.inpaint(image, mask, inpaintRadius=5, flags=cv2.INPAINT_NS)

            # Create output folder for SKU if it doesn't exist
            sku_folder = os.path.join(output_dir, sku)
            os.makedirs(sku_folder, exist_ok=True)

            # Save with just the image number as filename
            output_path = os.path.join(sku_folder, f"{image_number}.jpg")
            cv2.imwrite(output_path, inpainted_image)

            return output_path

        except Exception as e:
            print(f"Error processing {image_path}: {e}")
            return None
    
    @staticmethod
    def get_all_image_files(directory: str) -> List[str]:
        """
        Recursively gets all image files from a directory.
        
        Args:
            directory: Root directory to search
            
        Returns:
            List of image file paths
        """
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif'}
        image_files = []
        
        for root, _, files in os.walk(directory):
            for file in files:
                if os.path.splitext(file)[1].lower() in image_extensions:
                    image_files.append(os.path.join(root, file))
        
        return image_files
    
    @staticmethod
    def group_images_by_sku(image_paths: List[str]) -> Dict[str, List[Tuple[str, str]]]:
        """
        Groups image paths by their SKU.
        
        Args:
            image_paths: List of image file paths
            
        Returns:
            Dictionary with SKU as key and list of (image_path, image_number) tuples as value
        """
        grouped = defaultdict(list)
        invalid_files = []
        
        for image_path in image_paths:
            filename = os.path.basename(image_path)
            sku, image_number = ImageProcessingService.extract_sku_and_number(filename)
            
            if sku is None or image_number is None:
                invalid_files.append(filename)
                continue
            
            grouped[sku].append((image_path, image_number))
        
        if invalid_files:
            print(f"Warning: {len(invalid_files)} files have invalid naming format")
            for f in invalid_files[:10]:  # Show first 10
                print(f"  - {f}")
            if len(invalid_files) > 10:
                print(f"  ... and {len(invalid_files) - 10} more")
        
        return dict(grouped)
    
    @staticmethod
    def extract_zip_files(zip_files: List[bytes], zip_names: List[str], extract_dir: str) -> List[str]:
        """
        Extracts multiple ZIP files to a directory.
        
        Args:
            zip_files: List of ZIP file contents as bytes
            zip_names: List of ZIP filenames
            extract_dir: Directory to extract files to
            
        Returns:
            List of extracted image paths
        """
        os.makedirs(extract_dir, exist_ok=True)
        all_images = []
        
        for idx, (zip_content, zip_name) in enumerate(zip(zip_files, zip_names)):
            # Save ZIP temporarily
            zip_path = os.path.join(extract_dir, f"temp_{idx}_{zip_name}")
            with open(zip_path, 'wb') as f:
                f.write(zip_content)
            
            # Extract ZIP
            extract_subdir = os.path.join(extract_dir, f"zip_{idx}")
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_subdir)
                
                # Get all images from extracted directory
                images = ImageProcessingService.get_all_image_files(extract_subdir)
                all_images.extend(images)
                
            except zipfile.BadZipFile:
                print(f"Warning: {zip_name} is not a valid ZIP file")
            finally:
                # Remove temporary ZIP file
                if os.path.exists(zip_path):
                    os.remove(zip_path)
        
        return all_images
    
    @staticmethod
    def process_images_batch(
        zip_files: List[bytes],
        zip_names: List[str],
        output_dir: str = "processed_images",
        validate_db: bool = True,
        table_name: str = "products"
    ) -> Dict[str, Any]:
        """
        Complete batch processing of images from ZIP files.
        
        Args:
            zip_files: List of ZIP file contents
            zip_names: List of ZIP filenames
            output_dir: Output directory for processed images
            validate_db: Whether to validate SKUs against database
            table_name: Database table name for validation
            
        Returns:
            Dictionary with processing statistics
        """
        temp_extract_dir = "temp_extracted"
        
        try:
            # Step 1: Extract all ZIP files
            print("Extracting ZIP files...")
            all_image_paths = ImageProcessingService.extract_zip_files(
                zip_files, zip_names, temp_extract_dir
            )
            
            if not all_image_paths:
                return {
                    'success': False,
                    'message': 'No images found in uploaded ZIP files',
                    'total_zips': len(zip_files),
                    'total_images': 0,
                    'total_skus': 0,
                    'processed_images': 0,
                    'failed_images': 0,
                    'invalid_skus': [],
                    'sku_details': []
                }
            
            print(f"Found {len(all_image_paths)} images")
            
            # Step 2: Group images by SKU
            print("Grouping images by SKU...")
            grouped_images = ImageProcessingService.group_images_by_sku(all_image_paths)
            
            print(f"Found {len(grouped_images)} unique SKUs")
            
            # Step 3: Validate SKUs in database (optional)
            invalid_skus = []
            if validate_db:
                print("Validating SKUs in database...")
                validation = ImageProcessingService.validate_skus_in_database(
                    list(grouped_images.keys()), 
                    table_name
                )
                invalid_skus = validation['invalid']
                
                if invalid_skus:
                    print(f"Warning: {len(invalid_skus)} SKUs not found in database")
            
            # Step 4: Process images
            print("Processing images (removing watermarks)...")
            os.makedirs(output_dir, exist_ok=True)
            
            stats = {
                'total_zips': len(zip_files),
                'total_images': len(all_image_paths),
                'total_skus': len(grouped_images),
                'processed_images': 0,
                'failed_images': 0,
                'invalid_skus': invalid_skus,
                'sku_details': []
            }
            
            for sku, image_list in grouped_images.items():
                sku_success = 0
                sku_failed = 0
                
                for image_path, image_number in image_list:
                    result = ImageProcessingService.remove_watermark(
                        image_path, output_dir, sku, image_number
                    )
                    
                    if result:
                        sku_success += 1
                        stats['processed_images'] += 1
                    else:
                        sku_failed += 1
                        stats['failed_images'] += 1
                
                stats['sku_details'].append({
                    'sku': sku,
                    'total': len(image_list),
                    'success': sku_success,
                    'failed': sku_failed,
                    'in_database': sku not in invalid_skus
                })
                
                print(f"  {sku}: {sku_success} processed, {sku_failed} failed")
            
            return {
                'success': True,
                'message': f'Successfully processed {stats["processed_images"]} images',
                **stats
            }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'Processing error: {str(e)}',
                'total_zips': len(zip_files),
                'total_images': 0,
                'total_skus': 0,
                'processed_images': 0,
                'failed_images': 0,
                'invalid_skus': [],
                'sku_details': []
            }
        
        finally:
            # Cleanup temporary extraction directory
            if os.path.exists(temp_extract_dir):
                shutil.rmtree(temp_extract_dir)