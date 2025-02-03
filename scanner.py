import pytesseract
from PIL import Image
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

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
            if '@' in line and not any(x in line.upper() for x in ['ALT', 'MADE', 'SCORE']):
                matchup = line.strip()
            elif any(x in line for x in ['ET', 'PM', 'AM']) and re.search(r'\d{1,2}:\d{2}', line):
                event_time = line.strip()
            elif re.match(r'^[+-]\d+\s*$', line.strip()):
                odds = line.strip()
        
        return {
            'matchup': matchup,
            'event_time': event_time,
            'odds': odds
        }

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

    def parse_structured_parlay_legs(self, text: str) -> List[Dict]:
        """Parse legs from structured parlay section with various bet types."""
        legs = []
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        current_game = None
        
        def is_game_header(line: str) -> bool:
            return '@' in line and any(x in line for x in ['ET', 'PM'])

        def is_header_line(line: str) -> bool:
            headers = [
                'TOTAL', 'SAME GAME PARLAY', 'INCLUDES:', 
                'LEG SAME', 'SELECTIONS', 'LEG PARLAY'
            ]
            return (
                any(header in line.upper() for header in headers) or
                (line.startswith('+') and line[1:].isdigit()) or  # Skip odds lines
                (line.startswith('-') and line[1:].isdigit())
            )

        def clean_player_name(line: str) -> str:
            # First, remove common OCR artifacts
            name = re.sub(r'^[#\-~@iG\s£6*\d®¢g»©AO)ae"]+', '', line)
            # Remove artifacts from the end
            name = re.sub(r'[\\/"$].*$', '', name)
            # Remove trailing odds numbers
            name = re.sub(r'-\d+$', '', name)
            # Remove any remaining artifacts
            name = re.sub(r'[®¢g»©"\[\]{}]', '', name)
            return name.strip()

        def clean_bet_details(line: str) -> str:
            # Remove leading OCR artifacts
            details = re.sub(r'^[ae"\s]+', '', line)
            # Remove any remaining artifacts
            details = re.sub(r'[®¢g»©"\[\]{}]', '', details)
            
            # Standardize bet detail format
            if 'TO SCORE' in details.upper():
                points_match = re.search(r'(\d+)\+?\s*POINTS', details.upper())
                if points_match:
                    points = points_match.group(1)
                    return f"TO SCORE {points}+ POINTS"
                    
            return details.strip()

        def is_bet_detail(line: str) -> bool:
            patterns = [
                r'TO SCORE \d+\+ POINTS',
                r'TO RECORD \d+\+ (?:REBOUNDS|ASSISTS)',
                r'\d+\+\s*MADE THREES',
                r'ANY ?TIME TOUCHDOWN SCORER',
                r'ALT (?:PASSING|RUSHING) (?:YDS|TDS)',
            ]
            # Clean the line first before checking patterns
            clean_line = clean_bet_details(line)
            return any(re.search(pattern, clean_line.upper()) for pattern in patterns)

        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Update current game if we hit a game header
            if is_game_header(line):
                current_game = line
                i += 1
                continue
                
            # Skip header lines
            if is_header_line(line):
                i += 1
                continue

            # Look ahead for bet details
            next_line = lines[i + 1] if i + 1 < len(lines) else ""
            
            # Check for player name followed by bet details pattern
            if next_line and is_bet_detail(next_line):
                player_name = clean_player_name(line)
                
                # Validate player name
                if (player_name and 
                    not player_name.isupper() and  # Skip all-caps headers
                    not '@' in player_name):       # Skip game headers
                    
                    # Handle hyphenated names (like Gilgeous-Alexander)
                    if '-' in line and '-' not in player_name:
                        parts = line.split('-')
                        if len(parts) >= 2 and not parts[-1].isdigit():
                            player_name = '-'.join(p.strip() for p in parts if not p.isdigit())
                    
                    legs.append({
                        'position': player_name,
                        'details': clean_bet_details(next_line),
                        'game': current_game
                    })
                i += 2
            else:
                i += 1
                    
        return legs

    def extract_legs(self, text: str) -> Dict:
        wager, payout = self.extract_wager_and_payout(text)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Determine bet type
        if 'SAME GAME PARLAY+' in text.upper():
            bet_type = 'Same Game Parlay+'
        elif 'SAME GAME PARLAY' in text.upper():
            bet_type = 'Same Game Parlay'
        elif 'PARLAY' in text.upper():
            bet_type = 'parlay'
        else:
            bet_type = 'straight'
        
        # Handle straight/moneyline bets
        if bet_type == 'straight':
            first_line = next((line.strip() for line in lines if line.strip()), '')
            
            for i, line in enumerate(lines):
                if 'MONEYLINE' in line.upper():
                    player = first_line
                    matchup_details = next(
                        (l.strip() for l in lines[i:] if 'v' in l and any(x in l for x in ['ET', 'PM'])),
                        ''
                    )
                    
                    pos = {
                        'position': f"MONEYLINE: {player}",
                        'details': matchup_details
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
        
        # Parse parlay legs
        all_legs = self.parse_structured_parlay_legs(text)
        
        # Get expected legs count
        parlay_match = re.search(r'(\d+)\s*leg.*Parlay', text, re.IGNORECASE)
        expected_legs = int(parlay_match.group(1)) if parlay_match else len(all_legs)
        
        # Additional bet type detection
        made_threes_legs = self.extract_made_threes_leg(text)
        to_score_legs = self.extract_to_score_leg(text)
        assists_legs = self.extract_assists_leg(text)
        
        # For regular parlays, group all legs under a single game
        if bet_type == 'parlay':
            # Filter out duplicate legs and summary lines
            clean_legs = []
            seen_positions = set()
            
            for leg in all_legs:
                position_key = f"{leg['position']}:{leg['details']}"
                if position_key not in seen_positions and ',' not in leg['position']:
                    seen_positions.add(position_key)
                    clean_legs.append(leg)
            
            games_list = [{
                'game': 'Parlay',
                'positions': clean_legs
            }]
        else:
            # Group legs by game for Same Game Parlays
            games = {}
            for leg in all_legs:
                game = leg.pop('game', None) or 'Parlay'
                if game not in games:
                    games[game] = []
                games[game].append(leg)
            
            games_list = [{'game': game, 'positions': positions} 
                        for game, positions in games.items()]
        
        # Format output
        formatted_output = []
        if bet_type == 'parlay':
            # Simple format for regular parlays
            for game_dict in games_list:
                for idx, leg in enumerate(game_dict['positions'], 1):
                    formatted_output.extend([
                        f"Leg Position {idx}: {leg['position']}",
                        f"Bet Details: {leg['details']}"
                    ])
        else:
            # More detailed format for Same Game Parlays
            for game_dict in games_list:
                formatted_output.append(f"\nGame: {game_dict['game']}")
                for idx, leg in enumerate(game_dict['positions'], 1):
                    formatted_output.extend([
                        f"Leg Position {idx}: {leg['position']}",
                        f"Bet Details: {leg['details']}"
                    ])
        
        # Validate legs count vs expected
        found_legs = len(all_legs)
        if found_legs != expected_legs:
            print(f"\nWARNING: Expected {expected_legs} legs but found {found_legs}")
            
        # Use clean_legs length for found_legs in parlay case
        if bet_type == 'parlay':
            found_legs = len(games_list[0]['positions'])
        
        return {
            'bet_type': bet_type,
            'expected_legs': expected_legs,
            'found_legs': found_legs,
            'games': games_list,
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