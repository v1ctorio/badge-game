import badge
import time
from badge.input import Buttons

PACKET_JOIN = 1      # Badge wants to join the game
PACKET_BUTTON = 2    # Badge pressed a button (data = button number)
PACKET_WIN = 3       # Host tells badge they won
PACKET_LOSE = 4      # Host tells badge they were eliminated
PACKET_START = 5     # Host starts a new round

class App(badge.BaseApp):

    def __init__(self):
        super().__init__()
        self.participants = {}  # badge_id -> {'name': str, 'button': int or None, 'eliminated': bool}
        self.game_state = "waiting"  # "waiting", "playing", "round_end"
        self.round_timer = 0
        self.round_duration = 10.0  
        self.current_round = 0

    def on_open(self):
        self.logger.info("Badge game host started!")
        badge.display.fill(1)
        badge.display.nice_text("badge game started at "+str(badge.contacts.my_contact().badge_id), 0, 0, 18)
        badge.display.nice_text("Waiting for players...", 0, 30, 18)
        badge.display.nice_text("Players: 0", 0, 60, 18)
        badge.display.nice_text("Press SW3 to start game", 0, 150, 18)
        badge.display.show()

    def loop(self):
        if self.game_state == "waiting":
            self.handle_waiting_state()
        elif self.game_state == "playing":
            self.handle_playing_state()
        elif self.game_state == "round_end":
            self.handle_round_end_state()
            
        time.sleep(0.1)

    def handle_waiting_state(self):
        self.update_waiting_display()
        
        if badge.input.get_button(Buttons.SW3) and len(self.participants) >= 2:
            self.start_new_round()

    def handle_playing_state(self):
        elapsed = badge.time.monotonic() - self.round_timer
        remaining = max(0, self.round_duration - elapsed)
        
        if remaining <= 0:
            self.end_round()
        else:
            self.update_playing_display(remaining)

    def handle_round_end_state(self):
        if badge.time.monotonic() - self.round_timer > 3.0:
            active_players = [bid for bid, player in self.participants.items() if not player['eliminated']]
            
            if len(active_players) <= 1:
                # Game over
                self.end_game()
            else:
                # Start next round
                self.start_new_round()

    def start_new_round(self):
        self.current_round += 1
        self.game_state = "playing"
        self.round_timer = badge.time.monotonic()
        
        # Reset button choices for this round
        for player in self.participants.values():
            player['button'] = None
        
        # Send start signal to all active players via broadcast first, then individual packets
        self.send_packet_to_badge(0xFFFF, PACKET_START, bytes([self.current_round]))
        
        # Also send individual packets as backup
        for badge_id, player in self.participants.items():
            if not player['eliminated']:
                self.send_packet_to_badge(badge_id, PACKET_START, bytes([self.current_round]))
        
        self.logger.info(f"Started round {self.current_round} (broadcast + individual)")

    def end_round(self):
        self.game_state = "round_end"
        self.round_timer = badge.time.monotonic()
        
        # Count button presses
        button_counts = {}
        for player in self.participants.values():
            if not player['eliminated'] and player['button'] is not None:
                button = player['button']
                if button not in button_counts:
                    button_counts[button] = []
                button_counts[button].append(player)
        
        # Eliminate players who pressed the same button as someone else
        eliminated_this_round = []
        survivors = []
        
        for badge_id, player in self.participants.items():
            if player['eliminated']:
                continue
                
            if player['button'] is None:
                # Didn't press any button - they survive
                survivors.append(badge_id)
                self.send_packet_to_badge(badge_id, PACKET_WIN, b"No button pressed - safe!")
            else:
                button = player['button']
                if len(button_counts[button]) > 1:
                    # Multiple people pressed this button - eliminate them
                    player['eliminated'] = True
                    eliminated_this_round.append(badge_id)
                    self.send_packet_to_badge(badge_id, PACKET_LOSE, f"Button {button} eliminated!".encode())
                else:
                    # Only person to press this button - they survive
                    survivors.append(badge_id)
                    self.send_packet_to_badge(badge_id, PACKET_WIN, f"Button {button} - safe!".encode())
        
        self.logger.info(f"Round {self.current_round} ended. Eliminated: {eliminated_this_round}, Survivors: {survivors}")
        self.update_round_end_display(eliminated_this_round, survivors)

    def end_game(self):
        self.game_state = "waiting"
        winners = [bid for bid, player in self.participants.items() if not player['eliminated']]
        
        badge.display.fill(1)
        badge.display.nice_text("GAME OVER!", 0, 0, 24)
        
        if len(winners) == 1:
            winner_name = self.participants[winners[0]].get('name', f"Badge {winners[0]:04X}")
            badge.display.nice_text(f"Winner: {winner_name}", 0, 40, 18)
        elif len(winners) == 0:
            badge.display.nice_text("No survivors!", 0, 40, 18)
        else:
            badge.display.nice_text(f"{len(winners)} survivors", 0, 40, 18)
            
        badge.display.nice_text("Press SW3 for new game", 0, 150, 18)
        badge.display.show()
        
        # Reset game state
        for player in self.participants.values():
            player['eliminated'] = False
            player['button'] = None
        self.current_round = 0

    def on_packet(self, packet, _):
        packet_type = packet.data[0] if len(packet.data) > 0 else 0
        
        if packet_type == PACKET_JOIN:
            # New player wants to join
            player_name = packet.data[1:].decode() if len(packet.data) > 1 else f"Badge {packet.source:04X}"
            self.participants[packet.source] = {
                'name': player_name,
                'button': None,
                'eliminated': False
            }
            self.logger.info(f"Player {player_name} (ID: {packet.source:04X}) joined")
            
        elif packet_type == PACKET_BUTTON and packet.source in self.participants:
            # Player pressed a button
            if self.game_state == "playing" and not self.participants[packet.source]['eliminated']:
                button_num = packet.data[1] if len(packet.data) > 1 else 0
                self.participants[packet.source]['button'] = button_num
                self.logger.info(f"Player {packet.source:04X} pressed button {button_num}")

    def send_packet_to_badge(self, badge_id, packet_type, data):
        """Send a packet to a specific badge or broadcast"""
        packet_data = bytes([packet_type]) + data
        # Use broadcast if badge_id is None or for announcements
        dest_id = badge_id if badge_id is not None else 0xFFFF
        badge.radio.send_packet(dest_id, packet_data)
    
    def broadcast_game_status(self, status_type):
        """Broadcast game status to all badges"""
        status_data = bytes([status_type, self.current_round, len(self.participants)])
        badge.radio.send_packet(0xFFFF, status_data)

    def update_waiting_display(self):
        badge.display.fill(1)
        badge.display.nice_text("Badge game room "+str(badge.contacts.my_contact().badge_id), 0, 0, 18)
        badge.display.nice_text("Waiting for players...", 0, 30, 18)
        badge.display.nice_text(f"Players: {len(self.participants)}", 0, 60, 18)
        
        y_pos = 90
        for badge_id, player in list(self.participants.items())[:3]:  # Show first 3 players
            badge.display.nice_text(f"{player['name'][:12]}", 0, y_pos, 16)
            y_pos += 20
            
        if len(self.participants) >= 2:
            badge.display.nice_text("Press SW3 to start!", 0, 150, 18)
        else:
            badge.display.nice_text("Need 2+ players", 0, 150, 18)
            
        badge.display.show()

    def update_playing_display(self, remaining):
        badge.display.fill(1)
        badge.display.nice_text(f"ROUND {self.current_round}", 0, 0, 24)
        badge.display.nice_text(f"Time: {remaining:.1f}s", 0, 40, 18)
        
        active_count = sum(1 for p in self.participants.values() if not p['eliminated'])
        badge.display.nice_text(f"Active: {active_count}", 0, 70, 18)
        
        # Show who has pressed buttons
        pressed_count = sum(1 for p in self.participants.values() 
                          if not p['eliminated'] and p['button'] is not None)
        badge.display.nice_text(f"Pressed: {pressed_count}/{active_count}", 0, 100, 18)
        
        badge.display.show()

    def update_round_end_display(self, eliminated, survivors):
        badge.display.fill(1)
        badge.display.nice_text(f"ROUND {self.current_round} OVER", 0, 0, 18)
        badge.display.nice_text(f"Eliminated: {len(eliminated)}", 0, 30, 18)
        badge.display.nice_text(f"Survivors: {len(survivors)}", 0, 60, 18)
        badge.display.nice_text("Next round in 3s...", 0, 150, 18)
        badge.display.show()
