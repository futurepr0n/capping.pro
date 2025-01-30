import pytesseract
from PIL import Image
import os
import re
from pathlib import Path
from typing import Dict, List

class BetSlipScanner:
    def __init__(self):
        if os.name == 'nt':
            pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

    def clean_text(self, text: str) -> str:
        # Remove special characters but keep essential punctuation
        text = re.sub(r'[^A-Z0-9\s+\-\.]', '', text.upper())
        # Remove multiple spaces
        text = ' '.join(text.split())
        return text

    def extract_legs(self, text: str) -> Dict:
        legs = []
        lines = text.split('\n')
        
        # First pass: find lines with " - ALT "
        for line in lines:
            if ' - ALT ' in line.upper():
                clean_line = self.clean_text(line)
                if clean_line and not any(clean_line in leg for leg in legs):
                    legs.append(clean_line)
        
        # Determine bet type
        is_parlay = 'PARLAY' in text.upper()
        bet_type = 'parlay' if is_parlay else 'straight'
        expected_legs = len(legs) if is_parlay else 1
        
        numbered_legs = [f"Leg {i} - {leg}" for i, leg in enumerate(legs, 1)]
        
        return {
            'bet_type': bet_type,
            'expected_legs': expected_legs,
            'found_legs': len(legs),
            'legs': numbered_legs
        }

    def scan_image(self, image_path: Path) -> Dict:
        try:
            print(f"\nProcessing: {image_path.name}")
            print("="*50)
            
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image)
            
            print("Raw Extracted Text:")
            print(text)
            
            result = self.extract_legs(text)
            
            print(f"\nBet Details:")
            print(f"Type: {result['bet_type'].title()}")
            print(f"Expected legs: {result['expected_legs']}")
            print(f"Found legs: {result['found_legs']}")
            
            print("\nFormatted Legs:")
            for leg in result['legs']:
                print(f"{leg}")
            
            return result
            
        except Exception as e:
            print(f"Error processing {image_path.name}: {str(e)}")
            return None

    def process_directory(self, directory: Path) -> List[Dict]:
        results = []
        for ext in ('*.jpg', '*.png'):
            for image_path in directory.glob(ext):
                result = self.scan_image(image_path)
                if result:
                    results.append({'file': image_path.name, **result})
        return results

def main():
    scanner = BetSlipScanner()
    current_dir = Path(__file__).parent.parent
    images_dir = current_dir / "images"
    results = scanner.process_directory(images_dir)
    
    print("\nSummary:")
    print("="*50)
    for result in results:
        print(f"\nFile: {result['file']}")
        print(f"Type: {result['bet_type']}")
        print(f"Expected/Found Legs: {result['expected_legs']}/{result['found_legs']}")

if __name__ == "__main__":
    main()