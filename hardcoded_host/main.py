import badge
import time
from badge.input import Buttons

player_ids = [0x492a, 0x5f23, 0x182a] # Vic, Jorge, Daniel

class App(badge.BaseApp):
    def __init__(self):
        super().__init__()
        self.choices = {} # Dictionary to store choices: {badge_id: choice}
        
    def on_open(self):
        badge.display.fill(1)
        badge.display.nice_text("Adrian's Host App\nWaiting for players...", 0, 0)
        badge.display.show()

    def loop(self):
        if len(self.choices) == len(player_ids):
            self.logger.info("All players have made a choice. Calculating results...")
            self.calculate_and_send_results()
            self.choices.clear() # Reset for the next round
            self.on_open() # Display the welcome screen again
            
        time.sleep(0.1)

    def on_packet(self, packet, _):
        player_id = packet.source
        player_choice = int.from_bytes(packet.data, 'big')
        
        if player_id in player_ids:
            self.choices[player_id] = player_choice
            self.logger.info(f"Received choice from {player_id}: {player_choice}")
        
        badge.display.fill(1)
        badge.display.nice_text(f"Choices received: {len(self.choices)}/{len(player_ids)}", 0, 0)
        badge.display.show()

    def calculate_and_send_results(self):
        choice_counts = {}
        for choice in self.choices.values():
            choice_counts[choice] = choice_counts.get(choice, 0) + 1
        
        winning_choice = None
        for choice, count in choice_counts.items():
            if count == 1:
                winning_choice = choice
                break

        # Wait 2 seconds before sending results
        time.sleep(2)

        for player_id in player_ids:
            if player_id in self.choices:
                player_choice = self.choices[player_id]
                
                if winning_choice is not None and player_choice == winning_choice:
                    result_packet = b'\x01' # Win
                    self.logger.info(f"Sending WIN packet to {player_id}")
                else:
                    result_packet = b'\x00' # Lose
                    self.logger.info(f"Sending LOSE packet to {player_id}")
                
                badge.radio.send_packet(player_id, result_packet)