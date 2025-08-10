import badge
import time
from badge.input import Buttons

packet_none = 0
packet_rock = 1
packet_paper = 2
packet_scissors = 3

marina_id = 0x1826
lucas_id = 0x2323

class App(badge.BaseApp):
    def __init__(self):
        super().__init__()
        self.opponent_packet = packet_none
        self.chosen_packet = packet_none
        self.opponent = lucas_id
        
    def on_open(self):
        try:
            self.paper_pbm = badge.display.import_pbm("/apps/rps/paper.pbm")
            self.rock_pbm = badge.display.import_pbm("/apps/rps/rock.pbm")
            self.scissors_pbm = badge.display.import_pbm("/apps/rps/scissors.pbm")
        except Exception as e:
            self.logger.error(f"Error loading PBM files: {e}")
            self.paper_pbm = None
            self.rock_pbm = None
            self.scissors_pbm = None
            
        self.logger.info("this app just launched! its listening for")
        badge.display.fill(1)
        badge.display.nice_text("Rock paper scissors!\nRock SW7\nPaper SW13\nScissors SW6", 0, 0)
        badge.display.show()

    def loop(self):
        if self.chosen_packet != packet_none and self.opponent_packet == packet_none:
            time.sleep(0.1)
            return

        if self.chosen_packet != packet_none and self.opponent_packet != packet_none:
            # Both players have chosen - show result
            self.show_result()
            time.sleep(0.1)
            return

        if badge.input.get_button(Buttons.SW7) and self.chosen_packet == packet_none:
            self.logger.info("SW7 pressed!")
            self.chosen_packet = packet_rock
            badge.display.fill(1)
            badge.display.nice_text("You chose Rock!", 0, 0)
            if self.rock_pbm:
                badge.display.blit(self.rock_pbm, 0, 80)
            badge.display.show()

        if badge.input.get_button(Buttons.SW13) and self.chosen_packet == packet_none:
            self.logger.info("SW13 pressed!")
            self.chosen_packet = packet_paper
            badge.display.fill(1)
            badge.display.nice_text("You chose Paper!", 0, 0)
            if self.paper_pbm:
                badge.display.blit(self.paper_pbm, 0, 80)
            badge.display.show()

        if badge.input.get_button(Buttons.SW6) and self.chosen_packet == packet_none:
            self.logger.info("SW6 pressed!")
            self.chosen_packet = packet_scissors
            badge.display.fill(1)
            badge.display.nice_text("You chose Scissors!", 0, 0)
            if self.scissors_pbm:
                badge.display.blit(self.scissors_pbm, 0, 80)
            badge.display.show()

        if self.chosen_packet != packet_none:
            badge.radio.send_packet(self.opponent, self.chosen_packet.to_bytes(1, 'big'))

        time.sleep(0.1)

    def on_packet(self, packet, _):
        self.opponent_packet = int.from_bytes(packet.data, 'big')
        self.logger.info(f"Received opponent choice: {self.opponent_packet}")

    def show_result(self):
        result = self.calculate_result(self.chosen_packet, self.opponent_packet)
        badge.display.fill(1)
        
        if result == 0:
            badge.display.nice_text("It's a tie!", 0, 0)
        elif result == 1:
            badge.display.nice_text("You win!", 0, 0)
        else:
            badge.display.nice_text("You lose!", 0, 0)
            
        badge.display.show()

    def calculate_result(self, chosen, opponent):
        if chosen == opponent:
            return 0  # tie
        elif (chosen == packet_rock and opponent == packet_scissors) or \
             (chosen == packet_paper and opponent == packet_rock) or \
             (chosen == packet_scissors and opponent == packet_paper):
            return 1  # win
        else:
            return 2  # lose