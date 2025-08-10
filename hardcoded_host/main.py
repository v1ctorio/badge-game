import badge
import time
from badge.input import Buttons

# Badge IDs of the players
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
        # Check if all players have made a choice
        if len(self.choices) == len(player_ids):
            self.logger.info("All players have made a choice. Calculating results...")
            self.calculate_and_send_results()
            self.choices.clear() # Reset for the next round
            self.on_open() # Display the welcome screen again
            
        time.sleep(0.1)

    def on_packet(self, packet, _):
        player_id = packet.source
        player_choice = int.from_bytes(packet.data, 'big')
        
        # Only accept choices from registered players
        if player_id in player_ids:
            self.choices[player_id] = player_choice
            self.logger.info(f"Received choice from {player_id}: {player_choice}")
        
        # Update Adrian's display to show how many choices have been received
        badge.display.fill(1)
        badge.display.nice_text(f"Choices received: {len(self.choices)}/{len(player_ids)}", 0, 0)
        badge.display.show()

    def calculate_and_send_results(self):
        # Count how many times each choice was made
        choice_counts = {}
        for choice in self.choices.values():
            choice_counts[choice] = choice_counts.get(choice, 0) + 1
        
        # Determine the unique choice (the winning choice)
        winning_choice = None
        for choice, count in choice_counts.items():
            if count == 1:
                winning_choice = choice
                break

        # Send results to each player
        for player_id in player_ids:
            # Check if the player is in the current round's choices
            if player_id in self.choices:
                player_choice = self.choices[player_id]
                
                # If there's a winning choice and the player made it, they win. Otherwise, they lose.
                if winning_choice is not None and player_choice == winning_choice:
                    result_packet = b'\x01' # Win
                    self.logger.info(f"Sending WIN packet to {player_id}")
                else:
                    result_packet = b'\x00' # Lose
                    self.logger.info(f"Sending LOSE packet to {player_id}")
                
                badge.radio.send_packet(player_id, result_packet)