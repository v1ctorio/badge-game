import badge
import time
from badge.input import Buttons

# Packet types for communication (must match host)
PACKET_JOIN = 1      # Badge wants to join the game
PACKET_BUTTON = 2    # Badge pressed a button (data = button number)
PACKET_WIN = 3       # Host tells badge they won
PACKET_LOSE = 4      # Host tells badge they were eliminated
PACKET_START = 5     # Host starts a new round

GAME_BUTTONS = [
    (Buttons.SW3, 3),
    (Buttons.SW4, 4),
    (Buttons.SW5, 5),
    (Buttons.SW6, 6),
    (Buttons.SW7, 7),
    (Buttons.SW8, 8),
    (Buttons.SW9, 9),
    (Buttons.SW10, 10),
    (Buttons.SW11, 11),
    (Buttons.SW12, 12),
    (Buttons.SW13, 13),
    (Buttons.SW14, 14),
    (Buttons.SW15, 15),
    (Buttons.SW16, 18),
    (Buttons.SW17, 17),
    (Buttons.SW18, 18),
]

class App(badge.BaseApp):

    def __init__(self):
        super().__init__()
        self.game_state = "disconnected"  # "disconnected", "waiting", "playing", "eliminated", "won"
        self.host_id = None
        self.current_round = 0
        self.button_pressed = False
        self.last_message = ""
        self.last_button_press = 0
        self.round_start_time = 0
        self.join_attempts = 0
        self.last_join_attempt = 0

    def on_open(self):
        self.logger.info("Button Elimination Player started!")
        badge.display.fill(1)
        badge.display.nice_text("BUTTON ELIMINATION", 0, 0, 18)
        badge.display.nice_text("PLAYER", 0, 25, 18)
        badge.display.nice_text("Searching for host...", 0, 60, 18)
        badge.display.nice_text("SW3-SW18: Game buttons", 0, 120, 14)
        badge.display.nice_text("Hold SW3+SW4 to find host", 0, 140, 14)
        badge.display.show()

    def loop(self):
        current_time = badge.time.monotonic()
        
        if self.game_state == "disconnected":
            self.handle_disconnected_state(current_time)
        elif self.game_state == "waiting":
            self.handle_waiting_state()
        elif self.game_state == "playing":
            self.handle_playing_state(current_time)
        elif self.game_state == "eliminated":
            self.handle_eliminated_state()
        elif self.game_state == "won":
            self.handle_won_state()
            
        time.sleep(0.1)

    def handle_disconnected_state(self, current_time):
        # Try to find and join a host
        if (badge.input.get_button(Buttons.SW3) and badge.input.get_button(Buttons.SW4)) or \
           (current_time - self.last_join_attempt > 5.0):  # Auto-retry every 5 seconds
            
            if current_time - self.last_join_attempt > 1.0:  # Rate limit join attempts
                self.attempt_join()
                self.last_join_attempt = current_time
                self.join_attempts += 1

        # Update display
        badge.display.fill(1)
        badge.display.nice_text("SEARCHING FOR HOST", 0, 0, 18)
        badge.display.nice_text(f"Attempts: {self.join_attempts}", 0, 30, 18)
        badge.display.nice_text("Hold SW3+SW4 to retry", 0, 60, 18)
        badge.display.nice_text("Or wait for auto-retry", 0, 80, 18)
        badge.display.show()

    def handle_waiting_state(self):
        badge.display.fill(1)
        badge.display.nice_text("CONNECTED TO HOST", 0, 0, 18)
        badge.display.nice_text("Waiting for game...", 0, 30, 18)
        if self.host_id:
            badge.display.nice_text(f"Host: {self.host_id:04X}", 0, 60, 18)
        badge.display.nice_text("Get ready!", 0, 120, 18)
        badge.display.show()

    def handle_playing_state(self, current_time):
        # Check for button presses if we haven't pressed one yet this round
        if not self.button_pressed:
            for button, button_num in GAME_BUTTONS:
                if badge.input.get_button(button):
                    # Debounce button press
                    if current_time - self.last_button_press > 0.3:
                        self.press_button(button_num)
                        self.last_button_press = current_time
                        break

        # Update display
        elapsed = current_time - self.round_start_time
        badge.display.fill(1)
        badge.display.nice_text(f"ROUND {self.current_round}", 0, 0, 24)
        badge.display.nice_text(f"Time: {max(0, 5.0 - elapsed):.1f}s", 0, 40, 18)
        
        if self.button_pressed:
            badge.display.nice_text("Button pressed!", 0, 80, 18)
            badge.display.nice_text("Waiting for results...", 0, 110, 18)
        else:
            badge.display.nice_text("Press a button!", 0, 80, 18)
            badge.display.nice_text("SW3-SW18", 0, 110, 18)
            badge.display.nice_text("Or press nothing", 0, 130, 18)
            
        badge.display.show()

    def handle_eliminated_state(self):
        badge.display.fill(1)
        badge.display.nice_text("ELIMINATED!", 0, 0, 24)
        badge.display.nice_text(self.last_message, 0, 40, 18)
        badge.display.nice_text("Better luck next time!", 0, 80, 18)
        badge.display.nice_text("Watching other players...", 0, 120, 18)
        badge.display.show()

    def handle_won_state(self):
        badge.display.fill(1)
        badge.display.nice_text("YOU SURVIVED!", 0, 0, 24)
        badge.display.nice_text(self.last_message, 0, 40, 18)
        badge.display.nice_text("Great job!", 0, 80, 18)
        badge.display.show()

    def attempt_join(self):
        """Try to join a game by broadcasting a join request"""
        try:
            my_contact = badge.contacts.my_contact()
            player_name = my_contact.name if my_contact else f"Badge{my_contact.badge_id if my_contact else 'Unknown'}"
            join_data = bytes([PACKET_JOIN]) + player_name.encode()[:20]  # Limit name length
            # Use broadcast address to reach any host
            badge.radio.send_packet(0xFFFF, join_data)
            self.logger.info(f"Sent join request via broadcast")
        except Exception as e:
            self.logger.error(f"Failed to send join request: {e}")

    def press_button(self, button_num):
        """Send button press to host"""
        if self.host_id and not self.button_pressed:
            try:
                button_data = bytes([PACKET_BUTTON, button_num])
                badge.radio.send_packet(self.host_id, button_data)
                self.button_pressed = True
                self.logger.info(f"Sent button {button_num} to host {self.host_id:04X}")
                
                # Play feedback sound
                badge.buzzer.tone(800, 0.1)
                
            except Exception as e:
                self.logger.error(f"Failed to send button press: {e}")

    def on_packet(self, packet, _):
        """Handle packets from the host"""
        if len(packet.data) == 0:
            return
            
        packet_type = packet.data[0]
        
        if packet_type == PACKET_START:
            # Host started a new round
            self.game_state = "playing"
            self.host_id = packet.source
            self.button_pressed = False
            self.round_start_time = badge.time.monotonic()
            
            if len(packet.data) > 1:
                self.current_round = packet.data[1]
            else:
                self.current_round += 1
                
            self.logger.info(f"Round {self.current_round} started by host {self.host_id:04X}")
            
            # Play start sound
            badge.buzzer.tone(1000, 0.2)
            
        elif packet_type == PACKET_WIN:
            # We survived this round!
            self.game_state = "won"
            self.host_id = packet.source
            
            if len(packet.data) > 1:
                try:
                    self.last_message = packet.data[1:].decode()
                except:
                    self.last_message = "You survived!"
            else:
                self.last_message = "You survived!"
                
            self.logger.info(f"Won round: {self.last_message}")
            
            # Play victory sound
            badge.buzzer.tone(1200, 0.1)
            time.sleep(0.1)
            badge.buzzer.tone(1400, 0.1)
            
            # Wait for next round or game end
            # (Host will send PACKET_START for next round or game will end)
            
        elif packet_type == PACKET_LOSE:
            # We were eliminated
            self.game_state = "eliminated"
            self.host_id = packet.source
            
            if len(packet.data) > 1:
                try:
                    self.last_message = packet.data[1:].decode()
                except:
                    self.last_message = "Eliminated!"
            else:
                self.last_message = "Eliminated!"
                
            self.logger.info(f"Eliminated: {self.last_message}")
            
            # Play elimination sound
            badge.buzzer.tone(400, 0.3)
            
        # If we receive any packet from a host, we know we're connected
        if self.game_state == "disconnected" and packet.source != badge.contacts.my_contact().badge_id:
            self.game_state = "waiting"
            self.host_id = packet.source
            self.logger.info(f"Connected to host {self.host_id:04X}")
