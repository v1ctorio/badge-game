# HOST

import badge
from badge.input import Buttons

class App(badge.BaseApp):
    def __init__(self):
        super().__init__()
        self.button_rects = {
            "SW15": {"x": 40, "y": 10, "w": 10, "h": 10},
            "SW8": {"x": 90, "y": 10, "w": 10, "h": 10},
            "SW16": {"x": 140, "y": 10, "w": 10, "h": 10},
            "SW9": {"x": 10, "y": 50, "w": 10, "h": 10},
            "SW18": {"x": 10, "y": 100, "w": 10, "h": 10},
            "SW10": {"x": 10, "y": 150, "w": 10, "h": 10},
            "SW12": {"x": 40, "y": 190, "w": 10, "h": 10},
            "SW4": {"x": 90, "y": 190, "w": 10, "h": 10},
            "SW11": {"x": 140, "y": 190, "w": 10, "h": 10},
            "SW7": {"x": 170, "y": 50, "w": 10, "h": 10},
            "SW13": {"x": 170, "y": 100, "w": 10, "h": 10},
            "SW6": {"x": 170, "y": 150, "w": 10, "h": 10},

        }

        self.button_mapping = {
            "SW15": Buttons.SW15,
            "SW9": Buttons.SW9,
            "SW8": Buttons.SW8,
            "SW16": Buttons.SW16,
            "SW18": Buttons.SW18,
            "SW10": Buttons.SW10,
            "SW12": Buttons.SW12,
            "SW4": Buttons.SW4,
            "SW11": Buttons.SW11,
            "SW7": Buttons.SW7,
            "SW13": Buttons.SW13,
            "SW6": Buttons.SW6,
        }

        self.selected_button = None

        self.button_pressed = {name: False for name in self.button_mapping.keys()}

    def on_open(self):
        self.draw_all_buttons()

    def draw_all_buttons(self):
        badge.display.fill(1)

        for button_name, rect in self.button_rects.items():
            if button_name == self.selected_button:
                badge.display.fill_rect(x=rect["x"], y=rect["y"], w=rect["w"], h=rect["h"], color=0)
            else:
                badge.display.rect(x=rect["x"], y=rect["y"], w=rect["w"], h=rect["h"], color=0)

        badge.display.show()

    def check_buttons(self):
        for button_name, button_enum in self.button_mapping.items():
            button_currently_pressed = badge.input.get_button(button_enum)

            if button_currently_pressed and not self.button_pressed[button_name]:
                self.logger.info(f"{button_name} pressed!")

                if self.selected_button == button_name:
                    self.selected_button = None
                    self.logger.info(f"{button_name} deselected")
                else:
                    self.selected_button = button_name
                    self.logger.info(f"{button_name} selected")

                self.draw_all_buttons()

            self.button_pressed[button_name] = button_currently_pressed

    def loop(self):
        self.check_buttons()
