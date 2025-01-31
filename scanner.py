import pytesseract
from PIL import Image
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

class BetSlipScanner:
    def __init__(self):
        if os.name == 'nt':
            pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

    def clean_text(self, text: str) -> str:
        # Remove special characters but keep essential ones
        text = re.sub(r'[^A-Z0-9\s+\-\.@]', '', text.upper())
        return ' '.join(text.split())

    def clean_player_name(self, text: str) -> str:
        # Remove common OCR artifacts and team indicators
        text = re.sub(r'^[&@iG\s]+', '', text)  # Remove leading artifacts
        text = re.sub(r'^\d+\s*', '', text)     # Remove leading numbers
        text = re.sub(r'[^A-Za-z\s]', '', text) # Keep only letters and spaces
        return text.strip()

    def extract_wager_and_payout(self, text: str) -> Tuple[float, float]:
        wager = 0.0
        payout = 0.0
        
        words = text.split()
        dollar_amounts = []
        
        print("\nDEBUG - Processing text word by word:")
        for i, word in enumerate(words):
            print(f"Word {i}: '{word}'")
            match = re.match(r'\$(\d+\.\d+)', word)
            if match:
                amount = float(match.group(1))
                dollar_amounts.append(amount)
                print(f"Found dollar amount: ${amount}")

        print("\nDEBUG - All dollar amounts found:", dollar_amounts)
        
        print("\nDEBUG - Looking for TOTAL WAGER/PAYOUT:")
        amount_index = 0
        for i, word in enumerate(words):
            if amount_index < len(dollar_amounts):
                if word.upper() == "TOTAL":
                    next_word = words[i + 1].upper() if i + 1 < len(words) else ""
                    print(f"Found TOTAL followed by: '{next_word}'")
                    
                    if next_word == "WAGER":
                        wager = dollar_amounts[amount_index]
                        print(f"Setting wager to: ${wager}")
                        amount_index += 1
                    elif next_word == "PAYOUT":
                        payout = dollar_amounts[amount_index]
                        print(f"Setting payout to: ${payout}")
                        amount_index += 1

        print(f"\nDEBUG - Final values: Wager=${wager}, Payout=${payout}")
        return wager, payout






    
    def extract_made_threes_leg(self, text: str) -> List[str]:
        legs = []
        lines = text.split('\n')
        current_player = None
        
        for i, line in enumerate(lines):
            clean_line = line.strip()
            upper_line = clean_line.upper()
            
            if 'MADE THREES' in upper_line:
                if current_player:
                    threshold_match = re.search(r'(\d+)\+?\s*MADE THREES', upper_line)
                    if threshold_match:
                        clean_player = self.clean_player_name(current_player)
                        legs.append(f"{clean_player} {threshold_match.group(1)}+ MADE THREES")
                current_player = None
            elif clean_line and not any(x in upper_line for x in ['MADE', 'SCORE', 'RECORD', 'TOTAL', 'WAGER', 'PAYOUT', 'GAME']):
                current_player = clean_line

        return legs

    def extract_to_score_leg(self, text: str) -> List[str]:
        legs = []
        lines = text.split('\n')
        current_player = None
        
        for i, line in enumerate(lines):
            clean_line = line.strip()
            upper_line = clean_line.upper()
            
            if 'TO SCORE' in upper_line:
                if current_player:
                    points_match = re.search(r'TO SCORE (\d+)\+? POINTS', upper_line)
                    if points_match:
                        clean_player = self.clean_player_name(current_player)
                        legs.append(f"{clean_player} TO SCORE {points_match.group(1)}+ POINTS")
                current_player = None
            elif clean_line and not any(x in upper_line for x in ['MADE', 'SCORE', 'RECORD', 'TOTAL', 'WAGER', 'PAYOUT', 'GAME']):
                current_player = clean_line

        return legs

    def extract_assists_leg(self, text: str) -> List[str]:
        legs = []
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            if 'RECORD' in line.upper() and 'ASSISTS' in line.upper():
                if i > 0:
                    player_line = lines[i-1].strip()
                    if player_line:
                        clean_player = self.clean_player_name(player_line)
                        clean_line = self.clean_text(line)
                        legs.append(f"{clean_player} {clean_line}")
        
        return legs

    def extract_moneyline_details(self, text: str) -> Dict:
        lines = text.split('\n')
        matchup = None
        event_time = None
        odds = None
        
        for line in lines:
            if 'v' in line and not any(x in line.upper() for x in ['ALT', 'MADE', 'SCORE']):
                matchup = line.strip()
            elif any(x in line for x in ['ET', 'PM', 'AM']) and re.search(r'\d{1,2}:\d{2}', line):
                event_time = line.strip()
            # Look for odds at start of lines
            elif re.match(r'^[+-]\d+\s*$', line.strip()):
                odds = line.strip()
        
        return {
            'matchup': matchup,
            'event_time': event_time,
            'odds': odds
        }

    def extract_legs(self, text: str) -> Dict:
        wager, payout = self.extract_wager_and_payout(text)
        lines = text.split('\n')
        
        # Determine bet type
        is_parlay = 'PARLAY' in text.upper()
        bet_type = 'parlay' if is_parlay else 'straight'
        
        # For straight bets
        if not is_parlay:
            position = None
            # Look for Super Boost
            for i, line in enumerate(lines):
                if 'SUPER BOOST' in line.upper():
                    position_lines = []
                    j = i
                    while j < len(lines) and not any(x in lines[j].upper() for x in ['TOTAL WAGER', 'TOTAL PAYOUT']):
                        clean_line = lines[j].strip()
                        if clean_line and not any(x in clean_line.upper() for x in ['+', 'ET', 'PM']):
                            position_lines.append(clean_line)
                        j += 1
                    position = ' '.join(position_lines)
                    break
            
            # For other straight bets
            if not position:
                for line in lines:
                    if ' - ALT ' in line.upper():
                        position = line.strip()
                        break
            
            positions = [position] if position else []
            return {
                'bet_type': bet_type,
                'expected_legs': 1,
                'found_legs': 1 if position else 0,
                'positions': positions,
                'total_wager': wager,
                'total_payout': payout,
                'formatted_output': [f"Position: {position}"] if position else [],
                'games': [{'game': 'Straight Bet', 'positions': positions}] if position else []
            }
        
        # For parlays
        legs = []
        games = []
        current_game = None
        current_legs = []
        current_positions = []
        
        for i, line in enumerate(lines):
            clean_line = line.strip()
            upper_line = clean_line.upper()
            
            # Handle new SGP section
            if 'SAME GAME PARLAY' in upper_line and '@' in ''.join(lines[i:i+3]):
                if current_game and current_positions:
                    games.append({
                        'game': current_game,
                        'positions': current_positions.copy()
                    })
                    current_positions = []
                
                # Look ahead for game header
                for j in range(i+1, min(i+3, len(lines))):
                    if '@' in lines[j] and not any(x in lines[j].upper() for x in ['ALT', 'SCORE', 'RECORD']):
                        current_game = lines[j].strip()
                        break
            
            # Process positions (former ALT lines)
            elif ' - ALT ' in upper_line:
                position = self.clean_text(line)
                if position and not any(position in pos for pos in current_positions):
                    current_positions.append(position)
                    legs.append(position)
        
        # Add final game section
        if current_game and current_positions:
            games.append({
                'game': current_game,
                'positions': current_positions.copy()
            })
        
        # Count expected legs
        parlay_match = re.search(r'(\d+)\s*leg.*Parlay', text, re.IGNORECASE)
        expected_legs = int(parlay_match.group(1)) if parlay_match else len(legs)
        
        # Create formatted output
        formatted_output = []
        for game_idx, game in enumerate(games, 1):
            formatted_output.append(f"\nGame {game_idx}: {game['game']}")
            for pos_idx, position in enumerate(game['positions'], 1):
                formatted_output.append(f"Leg {pos_idx} Position: {position}")
        
        return {
            'bet_type': bet_type,
            'expected_legs': expected_legs,
            'found_legs': len(legs),
            'positions': legs,
            'games': games,
            'total_wager': wager,
            'total_payout': payout,
            'formatted_output': formatted_output
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
            print(f"Total Wager: ${result['total_wager']:.2f}")
            print(f"Total Payout: ${result['total_payout']:.2f}")
            
            print("\nFormatted Legs by Game:")
            for line in result['formatted_output']:
                print(line)
            
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
        print(f"Wager/Payout: ${result['total_wager']:.2f}/${result['total_payout']:.2f}")

if __name__ == "__main__":
    main()