import badge
import time
import json
from badge.input import Buttons
# Using simple list instead of deque for MicroPython compatibility

# Packet types for communication
PACKET_HOST_ANNOUNCE = 1    # Host announces presence (periodic broadcast)
PACKET_JOIN_REQUEST = 2     # Client wants to join
PACKET_JOIN_RESPONSE = 3    # Host accepts/rejects join
PACKET_GAME_START = 4       # Host starts new round
PACKET_BUTTON_PRESS = 5     # Client pressed button
PACKET_ROUND_END = 6        # Host announces round results
PACKET_GAME_OVER = 7        # Host announces game winner
PACKET_HEARTBEAT = 8        # Keep connection alive
PACKET_PLAYER_LIST = 9      # Host sends current players
PACKET_DISCONNECT = 10      # Clean disconnect

# Game constants
ROUND_DURATION = 5.0        # Seconds per round
HEARTBEAT_INTERVAL = 10.0   # Seconds between heartbeats
CONNECTION_TIMEOUT = 30.0   # Connection timeout
MAX_PLAYERS = 8             # Maximum players per game
DISCOVERY_INTERVAL = 3.0    # Host discovery frequency

GAME_BUTTONS = [
    (Buttons.SW4, 4), (Buttons.SW5, 5), (Buttons.SW6, 6),
    (Buttons.SW7, 7), (Buttons.SW8, 8), (Buttons.SW9, 9), (Buttons.SW10, 10),
    (Buttons.SW11, 11), (Buttons.SW12, 12), (Buttons.SW13, 13), (Buttons.SW14, 14),
    (Buttons.SW15, 15), (Buttons.SW16, 16), (Buttons.SW17, 17),
]

class GameHost:
    def __init__(self, app):
        self.app = app
        self.players = {}  # {badge_id: {"name": str, "alive": bool, "last_seen": float}}
        self.current_round = 0
        self.round_start_time = 0
        self.game_active = False
        self.last_announce = 0
        self.elimination_button = None
        self.round_results = []

    def update(self, current_time):
        # Send periodic announcements
        if current_time - self.last_announce > DISCOVERY_INTERVAL:
            self.announce_presence()
            self.last_announce = current_time

        # Check for player timeouts
        self.check_player_timeouts(current_time)

        # Handle round timing
        if self.game_active and self.round_start_time > 0:
            elapsed = current_time - self.round_start_time
            if elapsed >= ROUND_DURATION:
                self.end_round()

    def announce_presence(self):
        try:
            my_contact = badge.contacts.my_contact()
            if my_contact and my_contact.name:
                host_name = my_contact.name
                badge_id = my_contact.badge_id
            else:
                badge_id = my_contact.badge_id if my_contact else 0
                host_name = f"Host-{badge_id:04X}"

            data = {
                "host_name": host_name,
                "badge_id": badge_id,
                "players": len(self.players),
                "max_players": MAX_PLAYERS,
                "game_active": self.game_active
            }
            packet_data = bytes([PACKET_HOST_ANNOUNCE]) + json.dumps(data).encode()
            badge.radio.send_packet(0xFFFF, packet_data)
        except Exception as e:
            self.app.logger.error(f"Failed to announce: {e}")

    def handle_join_request(self, packet):
        if len(self.players) >= MAX_PLAYERS:
            self.send_join_response(packet.source, False, "Game full")
            return

        try:
            player_data = json.loads(packet.data[1:].decode())
            player_name = player_data.get("name", f"Player-{packet.source:04X}")
            player_badge_id = player_data.get("badge_id", packet.source)

            # Try to save/update contact if we have enough info
            try:
                if player_badge_id and player_name and player_name != f"Badge-{player_badge_id:04X}":
                    # Create contact object
                    contact = badge.contacts.Contact(
                        badge_id=player_badge_id,
                        name=player_name,
                        handle=player_data.get("handle"),
                        pronouns=player_data.get("pronouns")
                    )
                    badge.contacts.add_contact(contact)
                    self.app.logger.info(f"Saved contact for {player_name}")
            except Exception as contact_error:
                self.app.logger.info(f"Could not save contact: {contact_error}")

            self.players[packet.source] = {
                "name": player_name,
                "alive": True,
                "last_seen": badge.time.monotonic(),
                "badge_id": player_badge_id
            }

            self.send_join_response(packet.source, True, f"Welcome {player_name}!")
            self.broadcast_player_list()
            self.app.logger.info(f"Player {player_name} joined ({packet.source:04X})")

        except Exception as e:
            self.app.logger.error(f"Failed to handle join: {e}")
            self.send_join_response(packet.source, False, "Join failed")

    def send_join_response(self, dest, accepted, message):
        try:
            data = {"accepted": accepted, "message": message}
            packet_data = bytes([PACKET_JOIN_RESPONSE]) + json.dumps(data).encode()
            badge.radio.send_packet(dest, packet_data)
        except Exception as e:
            self.app.logger.error(f"Failed to send join response: {e}")

    def broadcast_player_list(self):
        try:
            data = {"players": [{"id": pid, "name": p["name"], "alive": p["alive"]}
                              for pid, p in self.players.items()]}
            packet_data = bytes([PACKET_PLAYER_LIST]) + json.dumps(data).encode()
            for player_id in self.players:
                badge.radio.send_packet(player_id, packet_data)
        except Exception as e:
            self.app.logger.error(f"Failed to broadcast player list: {e}")

    def start_round(self):
        if len([p for p in self.players.values() if p["alive"]]) < 2:
            self.end_game()
            return

        self.current_round += 1
        self.round_start_time = badge.time.monotonic()
        self.elimination_button = (self.current_round % 14) + 4  # SW4-SW17
        self.round_results = []

        try:
            data = {
                "round": self.current_round,
                "elimination_button": self.elimination_button,
                "duration": ROUND_DURATION
            }
            packet_data = bytes([PACKET_GAME_START]) + json.dumps(data).encode()
            for player_id in self.players:
                if self.players[player_id]["alive"]:
                    badge.radio.send_packet(player_id, packet_data)

            self.app.logger.info(f"Started round {self.current_round}, elimination button: SW{self.elimination_button}")
        except Exception as e:
            self.app.logger.error(f"Failed to start round: {e}")

    def handle_button_press(self, packet):
        if not self.game_active or packet.source not in self.players:
            return

        try:
            data = json.loads(packet.data[1:].decode())
            button = data.get("button")
            press_time = data.get("time", badge.time.monotonic())

            self.round_results.append({
                "player_id": packet.source,
                "button": button,
                "time": press_time - self.round_start_time
            })

            self.app.logger.info(f"Player {packet.source:04X} pressed SW{button}")
        except Exception as e:
            self.app.logger.error(f"Failed to handle button press: {e}")

    def end_round(self):
        # Determine eliminations
        eliminated = []
        for player_id, player in self.players.items():
            if not player["alive"]:
                continue

            # Check if player pressed elimination button
            pressed_elimination = any(r["player_id"] == player_id and r["button"] == self.elimination_button
                                    for r in self.round_results)

            if pressed_elimination:
                player["alive"] = False
                eliminated.append(player_id)

        # Send round results
        try:
            data = {
                "round": self.current_round,
                "eliminated": eliminated,
                "elimination_button": self.elimination_button,
                "survivors": len([p for p in self.players.values() if p["alive"]])
            }
            packet_data = bytes([PACKET_ROUND_END]) + json.dumps(data).encode()
            for player_id in self.players:
                badge.radio.send_packet(player_id, packet_data)

            self.app.logger.info(f"Round {self.current_round} ended, {len(eliminated)} eliminated")
        except Exception as e:
            self.app.logger.error(f"Failed to send round results: {e}")

        self.round_start_time = 0

        # Check for game end
        alive_players = [p for p in self.players.values() if p["alive"]]
        if len(alive_players) <= 1:
            self.end_game()

    def end_game(self):
        winner = None
        for player_id, player in self.players.items():
            if player["alive"]:
                winner = player_id
                break

        try:
            data = {"winner": winner, "winner_name": self.players[winner]["name"] if winner else None}
            packet_data = bytes([PACKET_GAME_OVER]) + json.dumps(data).encode()
            for player_id in self.players:
                badge.radio.send_packet(player_id, packet_data)

            self.app.logger.info(f"Game ended, winner: {self.players[winner]['name'] if winner else 'None'}")
        except Exception as e:
            self.app.logger.error(f"Failed to send game over: {e}")

        self.game_active = False
        self.current_round = 0

    def check_player_timeouts(self, current_time):
        to_remove = []
        for player_id, player in self.players.items():
            if current_time - player["last_seen"] > CONNECTION_TIMEOUT:
                to_remove.append(player_id)

        for player_id in to_remove:
            self.app.logger.info(f"Player {self.players[player_id]['name']} timed out")
            del self.players[player_id]
            self.broadcast_player_list()

class GameClient:
    def __init__(self, app):
        self.app = app
        self.state = "discovering"  # "discovering", "connected", "playing", "eliminated", "won"
        self.host_id = None
        self.discovered_hosts = {}
        self.last_discovery = 0
        self.last_heartbeat = 0
        self.connection_time = 0
        self.current_round = 0
        self.elimination_button = None
        self.round_start_time = 0
        self.button_pressed = False
        self.players = []
        self.last_message = ""
        self.round_time_left = 0

    def update(self, current_time):
        if self.state == "discovering":
            self.handle_discovery(current_time)
        elif self.state in ["connected", "playing"]:
            self.handle_connected_state(current_time)

        if self.state == "playing":
            self.handle_playing_state(current_time)

        # Send periodic heartbeats
        if self.host_id and current_time - self.last_heartbeat > HEARTBEAT_INTERVAL:
            self.send_heartbeat()
            self.last_heartbeat = current_time

    def handle_discovery(self, current_time):

        # Clean up old discovered hosts
        timeout_hosts = []
        for host_id, data in self.discovered_hosts.items():
            if current_time - data["last_seen"] > 15.0:
                timeout_hosts.append(host_id)
        for host_id in timeout_hosts:
            del self.discovered_hosts[host_id]

        # Auto-join best available host
        if self.discovered_hosts and current_time - self.last_discovery > 2.0:
            # Pick host with most players but not full
            best_host = None
            best_score = -1

            for host_id, data in self.discovered_hosts.items():
                if data["players"] < data["max_players"]:
                    score = data["players"]  # Prefer hosts with more players
                    if score > best_score:
                        best_score = score
                        best_host = host_id

            if best_host:
                self.attempt_join(best_host)
                self.last_discovery = current_time

    def attempt_join(self, host_id):
        try:
            my_contact = badge.contacts.my_contact()
            if my_contact and my_contact.name:
                player_name = my_contact.name
                badge_id = my_contact.badge_id
            else:
                # Fallback if no contact or no name set
                badge_id = my_contact.badge_id if my_contact else 0
                player_name = f"Badge-{badge_id:04X}"

            data = {
                "name": player_name,
                "badge_id": badge_id,
                "handle": my_contact.handle if my_contact and my_contact.handle else None,
                "pronouns": my_contact.pronouns if my_contact and my_contact.pronouns else None
            }
            packet_data = bytes([PACKET_JOIN_REQUEST]) + json.dumps(data).encode()
            badge.radio.send_packet(host_id, packet_data)

            self.app.logger.info(f"Sent join request to {host_id:04X} as {player_name}")
        except Exception as e:
            self.app.logger.error(f"Failed to send join request: {e}")

    def handle_connected_state(self, current_time):
        # Check for connection timeout
        if current_time - self.connection_time > CONNECTION_TIMEOUT:
            self.app.logger.info("Connection timed out")
            self.disconnect()

    def handle_playing_state(self, current_time):
        if not self.button_pressed and self.round_start_time > 0:
            # Update round timer
            elapsed = current_time - self.round_start_time
            self.round_time_left = max(0, ROUND_DURATION - elapsed)

            # Check for button presses
            for button, button_num in GAME_BUTTONS:
                if badge.input.get_button(button):
                    self.press_button(button_num, current_time)
                    break

    def press_button(self, button_num, press_time):
        if self.button_pressed or not self.host_id:
            return

        try:
            data = {"button": button_num, "time": press_time}
            packet_data = bytes([PACKET_BUTTON_PRESS]) + json.dumps(data).encode()
            badge.radio.send_packet(self.host_id, packet_data)

            self.button_pressed = True
            self.app.logger.info(f"Pressed SW{button_num}")

            # Audio feedback
            if button_num == self.elimination_button:
                badge.buzzer.tone(400, 0.2)  # Low tone for elimination button
            else:
                badge.buzzer.tone(800, 0.1)  # High tone for safe button

        except Exception as e:
            self.app.logger.error(f"Failed to send button press: {e}")

    def send_heartbeat(self):
        try:
            packet_data = bytes([PACKET_HEARTBEAT])
            badge.radio.send_packet(self.host_id, packet_data)
        except Exception as e:
            self.app.logger.error(f"Failed to send heartbeat: {e}")

    def disconnect(self):
        if self.host_id:
            try:
                packet_data = bytes([PACKET_DISCONNECT])
                badge.radio.send_packet(self.host_id, packet_data)
            except:
                pass

        self.state = "discovering"
        self.host_id = None
        self.connection_time = 0
        self.current_round = 0
        self.players = []
        self.last_message = ""

class App(badge.BaseApp):
    def __init__(self):
        super().__init__()
        self.is_host = False
        self.host = None
        self.client = None
        self.last_display_update = 0
        self.menu_selection = 0  # 0=Join Game, 1=Host Game
        self.in_menu = True
        self.button_debounce = {}
        self.packet_queue = []

    def on_open(self):
        self.logger.info("Button Elimination Game started!")
        self.show_main_menu()

    def loop(self):
        current_time = badge.time.monotonic()

        # Process queued packets first
        self.process_packet_queue(current_time)

        if self.in_menu:
            self.handle_menu_input()
        else:
            # Handle return to menu button when not in menu
            pressed = self.update_button_debounce(current_time)
            if pressed == Buttons.SW16:
                self.return_to_menu()
                return
            elif pressed == Buttons.SW6 and self.is_host and self.host:
                # Handle host start game button
                if not self.host.game_active and len(self.host.players) >= 2:
                    self.host.game_active = True
                    self.host.start_round()

            if self.is_host and self.host:
                self.host.update(current_time)
            elif not self.is_host and self.client:
                self.client.update(current_time)

        # Update display periodically
        if current_time - self.last_display_update > 0.5:
            self.update_display()
            self.last_display_update = current_time

        time.sleep(0.1)

    def update_button_debounce(self, current_time):
        for button in [Buttons.SW4, Buttons.SW5, Buttons.SW6, Buttons.SW17]:
            if button not in self.button_debounce:
                self.button_debounce[button] = 0
            if current_time - self.button_debounce[button] > 0.3:
                if badge.input.get_button(button):
                    self.button_debounce[button] = current_time
                    return button
        return None

    def handle_menu_input(self):
        pressed = self.update_button_debounce(badge.time.monotonic())

        if pressed == Buttons.SW4:  # Up
            self.menu_selection = (self.menu_selection - 1) % 2
            self.show_main_menu()
        elif pressed == Buttons.SW5:  # Down
            self.menu_selection = (self.menu_selection + 1) % 2
            self.show_main_menu()
        elif pressed == Buttons.SW6:  # Select
            if self.menu_selection == 0:
                self.start_client()
            else:
                self.start_host()

    def show_main_menu(self):
        badge.display.fill(1)
        badge.display.nice_text("BUTTON ELIMINATION", 0, 0, 24)
        badge.display.nice_text("Select mode:", 0, 40, 18)

        # Menu options
        y = 70
        options = ["Join Game", "Host Game"]
        for i, option in enumerate(options):
            prefix = "> " if i == self.menu_selection else "  "
            badge.display.nice_text(f"{prefix}{option}", 0, y, 18)
            y += 25

        badge.display.nice_text("SW4/SW5: Navigate", 0, 140, 18)
        badge.display.nice_text("SW6: Select", 0, 160, 18)
        badge.display.show()

    def start_client(self):
        self.in_menu = False
        self.is_host = False
        self.client = GameClient(self)
        self.logger.info("Started as client")

    def start_host(self):
        self.in_menu = False
        self.is_host = True
        self.host = GameHost(self)
        self.logger.info("Started as host")

    def return_to_menu(self):
        if self.client:
            self.client.disconnect()
        self.in_menu = True
        self.is_host = False
        self.host = None
        self.client = None
        self.show_main_menu()

    def update_display(self):
        if self.in_menu:
            return

        badge.display.fill(1)

        if self.is_host:
            self.draw_host_display()
        else:
            self.draw_client_display()

        badge.display.show()

    def draw_host_display(self):
        if not self.host:
            return

        badge.display.nice_text("HOST MODE", 0, 0, 24)
        badge.display.nice_text(f"Players: {len(self.host.players)}/{MAX_PLAYERS}", 0, 30, 18)

        if self.host.game_active:
            badge.display.nice_text(f"Round {self.host.current_round}", 0, 55, 18)
            if self.host.round_start_time > 0:
                elapsed = badge.time.monotonic() - self.host.round_start_time
                time_left = max(0, ROUND_DURATION - elapsed)
                badge.display.nice_text(f"Time: {time_left:.1f}s", 0, 80, 18)
                badge.display.nice_text(f"Avoid: SW{self.host.elimination_button}", 0, 105, 18)
        else:
            badge.display.nice_text("Waiting for players", 0, 55, 18)
            if len(self.host.players) >= 2:
                badge.display.nice_text("SW6: Start Game", 0, 80, 18)

        # Show players
        y = 130
        alive_players = [p for p in self.host.players.values() if p["alive"]][:3]
        for player in alive_players:
            badge.display.nice_text(f"• {player['name']}", 0, y, 18)
            y += 15



    def draw_client_display(self):
        if not self.client:
            return

        if self.client.state == "discovering":
            badge.display.nice_text("SEARCHING FOR GAMES", 0, 0, 18)
            badge.display.nice_text(f"Found: {len(self.client.discovered_hosts)}", 0, 30, 18)

            y = 60
            for host_id, data in list(self.client.discovered_hosts.items())[:4]:
                status = "FULL" if data["players"] >= data["max_players"] else f"{data['players']}/{data['max_players']}"
                # Show real name if available, otherwise show badge ID
                display_name = data["name"] if not data["name"].startswith("Host-") else f"{host_id:04X}"
                badge.display.nice_text(f"{display_name}: {status}", 0, y, 18)
                y += 20

        elif self.client.state == "connected":
            badge.display.nice_text("CONNECTED", 0, 0, 24)
            badge.display.nice_text("Waiting for game start", 0, 30, 18)
            if self.client.host_id:
                badge.display.nice_text(f"Host: {self.client.host_id:04X}", 0, 55, 18)

            # Show other players
            y = 80
            for player in self.client.players[:4]:
                status = "💀" if not player.get("alive", True) else "✓"
                badge.display.nice_text(f"{status} {player['name']}", 0, y, 18)
                y += 18

        elif self.client.state == "playing":
            badge.display.nice_text(f"ROUND {self.client.current_round}", 0, 0, 24)
            badge.display.nice_text(f"Time: {self.client.round_time_left:.1f}s", 0, 30, 18)

            if self.client.elimination_button:
                badge.display.nice_text(f"AVOID: SW{self.client.elimination_button}", 0, 60, 18)

            if self.client.button_pressed:
                badge.display.nice_text("Button pressed!", 0, 90, 18)
                badge.display.nice_text("Waiting for results...", 0, 115, 18)
            else:
                badge.display.nice_text("Press any button", 0, 90, 18)
                badge.display.nice_text("except the one above!", 0, 115, 18)

        elif self.client.state == "eliminated":
            badge.display.nice_text("ELIMINATED", 0, 0, 24)
            badge.display.nice_text(self.client.last_message, 0, 40, 18)
            badge.display.nice_text("Watching others...", 0, 80, 18)

        elif self.client.state == "won":
            badge.display.nice_text("YOU WON!", 0, 0, 32)
            badge.display.nice_text("Congratulations!", 0, 50, 18)

        badge.display.nice_text("SW17: Menu", 0, 180, 18)

    def on_packet(self, packet, _):
        # Quick and simple - just queue the packet for processing in app thread
        if len(packet.data) == 0:
            return

        # Add packet to queue with timestamp
        current_time = badge.time.monotonic()
        self.packet_queue.append((packet, current_time))

        # Keep queue size reasonable
        if len(self.packet_queue) > 50:
            self.packet_queue.pop(0)

    def process_packet_queue(self, current_time):
        # Process up to 5 packets per loop to avoid blocking
        processed = 0
        while self.packet_queue and processed < 5:
            packet, packet_time = self.packet_queue.pop(0)
            packet_type = packet.data[0]

            try:
                if self.is_host:
                    self.handle_host_packet(packet, packet_type, current_time)
                else:
                    self.handle_client_packet(packet, packet_type, current_time)
            except Exception as e:
                self.logger.error(f"Packet handling error: {e}")

            processed += 1

    def handle_host_packet(self, packet, packet_type, current_time):
        if not self.host:
            return

        if packet_type == PACKET_JOIN_REQUEST:
            self.host.handle_join_request(packet)
        elif packet_type == PACKET_BUTTON_PRESS:
            self.host.handle_button_press(packet)
        elif packet_type == PACKET_HEARTBEAT:
            if packet.source in self.host.players:
                self.host.players[packet.source]["last_seen"] = current_time
        elif packet_type == PACKET_DISCONNECT:
            if packet.source in self.host.players:
                del self.host.players[packet.source]
                self.host.broadcast_player_list()

    def handle_client_packet(self, packet, packet_type, current_time):
        if not self.client:
            return

        if packet_type == PACKET_HOST_ANNOUNCE:
            try:
                data = json.loads(packet.data[1:].decode())
                host_name = data.get("host_name", f"Host-{packet.source:04X}")
                host_badge_id = data.get("badge_id", packet.source)

                # Try to save/update host contact if we have a real name
                try:
                    if host_badge_id and host_name and not host_name.startswith("Host-"):
                        contact = badge.contacts.Contact(
                            badge_id=host_badge_id,
                            name=host_name
                        )
                        badge.contacts.add_contact(contact)
                except Exception as contact_error:
                    pass  # Don't log contact errors for announcements

                self.client.discovered_hosts[packet.source] = {
                    "name": host_name,
                    "players": data.get("players", 0),
                    "max_players": data.get("max_players", MAX_PLAYERS),
                    "game_active": data.get("game_active", False),
                    "last_seen": current_time,
                    "badge_id": host_badge_id
                }
            except:
                pass

        elif packet_type == PACKET_JOIN_RESPONSE:
            try:
                data = json.loads(packet.data[1:].decode())
                if data.get("accepted", False):
                    self.client.state = "connected"
                    self.client.host_id = packet.source
                    self.client.connection_time = current_time
                    self.client.last_message = data.get("message", "Connected!")
                    badge.buzzer.tone(1200, 0.15)
                else:
                    self.client.last_message = data.get("message", "Join rejected")
            except:
                pass

        elif packet_type == PACKET_PLAYER_LIST:
            try:
                data = json.loads(packet.data[1:].decode())
                self.client.players = data.get("players", [])
            except:
                pass

        elif packet_type == PACKET_GAME_START:
            try:
                data = json.loads(packet.data[1:].decode())
                self.client.state = "playing"
                self.client.current_round = data.get("round", 1)
                self.client.elimination_button = data.get("elimination_button", 3)
                self.client.round_start_time = current_time
                self.client.button_pressed = False
                badge.buzzer.tone(1000, 0.2)
            except:
                pass

        elif packet_type == PACKET_ROUND_END:
            try:
                data = json.loads(packet.data[1:].decode())
                eliminated = data.get("eliminated", [])
                my_id = badge.contacts.my_contact().badge_id if badge.contacts.my_contact() else 0

                if my_id in eliminated:
                    self.client.state = "eliminated"
                    self.client.last_message = f"You pressed SW{data.get('elimination_button', '?')}!"
                    badge.buzzer.tone(400, 0.5)
                else:
                    self.client.state = "connected"
                    badge.buzzer.tone(1200, 0.1)

                self.client.round_start_time = 0
                self.client.button_pressed = False
            except:
                pass

        elif packet_type == PACKET_GAME_OVER:
            try:
                data = json.loads(packet.data[1:].decode())
                winner = data.get("winner")
                my_id = badge.contacts.my_contact().badge_id if badge.contacts.my_contact() else 0

                if winner == my_id:
                    self.client.state = "won"
                    # Victory fanfare
                    for freq in [1200, 1400, 1600, 1800]:
                        badge.buzzer.tone(freq, 0.15)
                        time.sleep(0.05)
                else:
                    self.client.state = "eliminated"
                    winner_name = data.get("winner_name", "Someone")
                    self.client.last_message = f"{winner_name} won!"
            except:
                pass
