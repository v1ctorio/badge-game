import badge
import time
from badge.input import Buttons

# Adrian's Badge ID
adrian_id = 0x4a23

# Define the buttons and their associated packet values
button_choices = {
    Buttons.SW15: 1,
    Buttons.SW8: 2,
    Buttons.SW16: 3,
    Buttons.SW7: 4,
    Buttons.SW13: 5,
    Buttons.SW6: 6,
    Buttons.SW14: 7,
    Buttons.SW18: 8,
    Buttons.SW10: 9,
    Buttons.SW17: 10,
    Buttons.SW12: 11,
    Buttons.SW4: 12,
    Buttons.SW11: 13,
    Buttons.SW3: 14, # Added SW3 to fill the spot
}

class App(badge.BaseApp):
    def __init__(self):
        super().__init__()
        self.chosen_packet = None
        self.result = None
        
    def on_open(self):
        badge.display.fill(1)
        badge.display.nice_text("Choose your button!\nWait for Adrian.", 0, 0)
        badge.display.show()

    def loop(self):
        # Only allow a choice if one hasn't been made yet
        if self.chosen_packet is None:
            for button, packet_value in button_choices.items():
                if badge.input.get_button(button):
                    self.chosen_packet = packet_value
                    self.logger.info(f"Button {button} pressed, choice: {packet_value}")
                    badge.radio.send_packet(adrian_id, self.chosen_packet.to_bytes(1, 'big'))
                    
                    badge.display.fill(1)
                    badge.display.nice_text(f"You chose button {packet_value}!\nWaiting for results...", 0, 0)
                    badge.display.show()
                    time.sleep(0.1) # Debounce

        # If a result has been received, show it
        if self.result is not None:
            badge.display.fill(1)
            badge.display.nice_text(self.result, 0, 0)
            badge.display.nice_text("Press SW18 to play again", 0, 100)
            badge.display.show()
            if badge.input.get_button(Buttons.SW18):
                self.chosen_packet = None
                self.result = None
                self.on_open()
            time.sleep(0.1)
    
    def on_packet(self, packet, _):
        # A result packet from Adrian is a single byte: 0 for lose, 1 for win
        result_value = int.from_bytes(packet.data, 'big')
        if result_value == 1:
            self.result = "You WIN! 🎉"
        else:
            self.result = "You LOSE. 💀"
        self.logger.info(f"Received result: {self.result}")