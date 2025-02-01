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

    # def parse_player_prop(self, lines: List[str], start_idx: int) -> str:
    #     current_line = lines[start_idx].strip()
    #     next_line = lines[start_idx + 1].strip() if start_idx + 1 < len(lines) else ""
        
    #     # Clean up player name
    #     name = re.sub(r'^[&@iG\s£6*\d]+', '', current_line)
    #     # Clean up prop
    #     prop = re.sub(r'^[w=\\sw"]+', '', next_line)
        
    #     if name and prop and ('TO SCORE' in prop.upper() or 'TO RECORD' in prop.upper()):
    #         return f"{name} {prop}"
    #     return None

    def parse_same_game_parlay(self, lines: List[str], start_idx: int) -> Tuple[str, List[str], int]:
        positions = []
        game = None
        i = start_idx

        while i < len(lines):
            line = lines[i].strip()
            
            if not game and '@' in line:
                game = line
                i += 1
                continue

            if i < len(lines) - 1:
                prop = self.parse_player_prop(lines, i)
                if prop:
                    positions.append(prop)
                    i += 2
                    continue
                    
            if i > start_idx and 'SAME GAME PARLAY' in line.upper():
                break
                
            i += 1
        
        return game, positions, i - 1

    def parse_moneyline(self, lines: List[str]) -> str:
        for i, line in enumerate(lines):
            if 'MONEYLINE' in line.upper():
                if i > 0:  # Get player name from previous line
                    return f"MONEYLINE: {lines[i-1].strip()}"
        return None

    def parse_player_prop(self, lines: List[str], start_idx: int) -> str:
        current_line = lines[start_idx].strip()
        next_line = lines[start_idx + 1].strip() if start_idx + 1 < len(lines) else ""
        
        # Clean up player name
        name = re.sub(r'^[&@iG\s£6*\d®¢g»©]+', '', current_line)
        name = re.sub(r'[\\/"$].*$', '', name)
        
        if not next_line:
            return None
            
        # Standard formats
        prop_types = {
            'MADE THREES': lambda x: f"{x.strip()} {re.search(r'(\d+)\+?', next_line).group(1)}+ MADE THREES" if re.search(r'(\d+)\+?', next_line) else None,
            'ALT ': lambda x: f"{x.strip()} - {next_line.strip()}",
            'TO SCORE': lambda x: f"{x.strip()} {next_line.strip()}",
            'TO RECORD': lambda x: f"{x.strip()} {next_line.strip()}"
        }
        
        for key, formatter in prop_types.items():
            if key in next_line.upper():
                return formatter(name)
        
        return None

    def extract_legs(self, text: str) -> Dict:
        wager, payout = self.extract_wager_and_payout(text)
        lines = text.split('\n')
        is_parlay = 'PARLAY' in text.upper()
        bet_type = 'parlay' if is_parlay else 'straight'
        games = []
        all_positions = []
        formatted_output = []
            
        # Handle straight bets first
        if not is_parlay:
            for i, line in enumerate(lines):
                if 'MONEYLINE' in line.upper():
                    player = lines[i-1].strip() if i > 0 else ""
                    details = next((l.strip() for l in lines[i+1:] if 'v' in l and any(x in l for x in ['ET', 'PM'])), '')
                    pos = {
                        'position': f"MONEYLINE: {player}",
                        'details': details
                    }
                    return {
                        'bet_type': bet_type,
                        'expected_legs': 1,
                        'found_legs': 1,
                        'total_wager': wager,
                        'total_payout': payout,
                        'games': [{'game': 'Straight Bet', 'positions': [pos]}],
                        'formatted_output': [f"Position: {pos['position']}", f"Details: {pos['details']}"]
                    }
        
        # Handle parlay
        current_game = None
        current_positions = []
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            upper_line = line.upper()
            
            # New game section
            if '@' in line and not any(x in upper_line for x in ['ALT', 'MADE', 'SCORE']):
                if current_game and current_positions:
                    games.append({'game': current_game, 'positions': current_positions.copy()})
                    formatted_output.extend([f"\nGame: {current_game}"] + 
                        [f"Leg {idx+1} Position: {pos['position']}\nDetails: {pos['details']}" 
                        for idx, pos in enumerate(current_positions)])
                current_game = line
                current_positions = []
                i += 1
                continue
            
            # Handle player props
            if i < len(lines) - 1:
                clean_name = re.sub(r'^[&@iG\s£6*\d®¢g»©]+', '', line)
                clean_name = re.sub(r'[\\/"$].*$', '', clean_name).strip()
                
                next_line = lines[i + 1].strip()
                alt_line = None
                
                # Look for ALT line or prop details in next few lines
                for j in range(i + 1, min(i + 3, len(lines))):
                    if ' - ALT ' in lines[j].upper():
                        alt_line = lines[j].strip()
                        break
                
                if clean_name and next_line and (alt_line or 'TO SCORE' in next_line.upper() or 'TO RECORD' in next_line.upper()):
                    pos = {
                        'position': f"{clean_name} {re.sub(r'^[w=\\sw"$©]+', '', next_line).strip()}",
                        'details': alt_line or next_line
                    }
                    current_positions.append(pos)
                    all_positions.append(pos)
                    i += 2
                    continue
                    
            i += 1
        
        # Add final game section
        if current_game and current_positions:
            games.append({'game': current_game, 'positions': current_positions})
            formatted_output.extend([f"\nGame: {current_game}"] + 
                [f"Leg {idx+1} Position: {pos['position']}\nDetails: {pos['details']}" 
                for idx, pos in enumerate(current_positions)])
        
        # Get expected legs count
        parlay_match = re.search(r'(\d+)\s*leg.*Parlay', text, re.IGNORECASE)
        expected_legs = int(parlay_match.group(1)) if parlay_match else len(all_positions)
        
        return {
            'bet_type': bet_type,
            'expected_legs': expected_legs,
            'found_legs': len(all_positions),
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