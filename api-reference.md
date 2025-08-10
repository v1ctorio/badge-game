An app consists of a directory, placed in `/apps/`. This directory must be named in a python-importable way, must contain a `manifest.json` file and a `main.py` file.

## manifest.json

This file describes to the OS how your app should be handled. It contains the following keys:

* **displayName**: string 
    * The name of your app as it appears on the home screen. Keep this short.
    * Example: `"My App"`
    * Required
* **logoPath**: string
    * A path to a 48x48 PBM image file, relative to the app directory. This image appears on the home screen.
    * Example: `"logo.pbm"`
    * Not required (a missing texture icon will be used instead)
* **permissions**: array[string]
    * A list of extra permissions the app requires. Available permissions include:
        * `contacts:write` - the ability to change the internal contacts database  
    (this was going to be a more in-depth system but in practice only the contacts permission is used)
    * Example: `["contacts:write"]` 
    * Not required (default: `[]`)
* **appNumber**: int
    * A number unique to this app used mainly for communicating with other badges.
    * Example: `4324`
    * Required, pick a random one between 10 and 65535, and put it in the [canvas in Slack](https://hackclub.slack.com/docs/T0266FRGM/F099G8ZT3TL) so others don't pick it

## main.py

This file contains the app logic. It is expected to define a class called `App` descending from `badge.BaseApp` and implementing at least an `on_open()` function and a `loop()` function. If the app needs to handle radio packets, it should also implement the `on_packet(packet: badge.radio.Packet, is_foreground: bool)` function.

## badge

The library for interacting with the badge. Contains the following modules:

### badge.display

API for interacting with the 200x200 E-Ink display. Uses a framebuffer-based approach where you draw to memory and then call `show()` to update the physical display.

**Display properties:**
- `width = 200` - Display width in pixels
- `height = 200` - Display height in pixels  

**Basic drawing functions:**
- `show() -> None` - Push the framebuffer contents to the E-Ink display (takes a few seconds for full refresh). **YOUR DRAWING WILL NOT DO ANYTHING UNTIL YOU CALL THIS FUNCTION!**
- `fill(color: int) -> None` - Fill entire display with color (0=black, 1=white)
- `pixel(x: int, y: int, color: int) -> None` - Set a single pixel
- `hline(x: int, y: int, w: int, color: int) -> None` - Draw horizontal line
- `vline(x: int, y: int, h: int, color: int) -> None` - Draw vertical line  
- `line(x1: int, y1: int, x2: int, y2: int, color: int) -> None` - Draw line between two points
- `rect(x: int, y: int, w: int, h: int, color: int) -> None` - Draw rectangle outline
- `fill_rect(x: int, y: int, w: int, h: int, color: int) -> None` - Draw filled rectangle

**Text functions:**
- `text(text: str, x: int, y: int, color: int = 0) -> None` - Draw 8x8 pixel text
- `nice_text(text: str, x: int, y: int, font: Union[int, MicroFont] = 18, color: int = 0, *, rot: int = 0, x_spacing: int = 0, y_spacing: int = 0) -> None` - Draw text using Victor Mono Bold font. Available sizes: 18, 24, 32, 42, 54, 68 point

**Image functions:**
- `blit(fb: framebuf.FrameBuffer, x: int, y: int) -> None` - Blit a FrameBuffer onto the display
- `import_pbm(file_path: str) -> framebuf.FrameBuffer` - Import a PBM image file (P4 format) as a FrameBuffer. PBM is a minimalist image format, a known-good converter from PNG is available [here](https://convertio.co/png-pbm/).

*Note: Display functions can only be called from the foreground app context.*

### badge.input

API for getting button presses. The badge has 16 buttons labelled SW3 to SW18. You can access buttons by name with `badge.input.Buttons`, e.g. `badge.input.get_button(badge.input.Buttons.SW9)`

**Functions:**
- `get_button(button: badge.input.Button) -> bool` - Get current state of a button. Returns True if pressed, False if not pressed.

*Note: Button 0 is reserved as the home button and cannot be accessed by apps.*

### badge.buzzer

API for playing audio tones on the buzzer.

**Functions:**
- `tone(frequency: float, length: float) -> None` - Play a tone at the specified frequency (Hz) for the given duration (seconds). This function blocks until the tone is finished.
- `no_tone() -> None` - Stop any currently playing tone immediately.

### badge.radio

API for communicating with other badges over radio.

**Data types:**
- `Packet` - Represents a radio packet with fields:
  - `source: int` - Badge ID of sender (automatically set)
  - `dest: int` - Badge ID of intended recipient  
  - `app_number: int` - App number (automatically set by OS)
  - `data: bytes` - Raw packet data (max 227 bytes)

**Functions:**
- `send_packet(dest: int, data: bytes) -> None` - Send packet to destination badge. Rate limited to 1 packet per 1.5 seconds, but ideally be even slower than this to reduce contention for bandwidth; additional packets are queued. Only one packet per app allowed in queue at a time.

*Note: To receive packets, implement a on_packet function in your app class as described above. Packets are automatically filtered so you only receive packets addressed to your app on your badge.*

### badge.time

Time-related functions.

**Functions:**
- `monotonic() -> float` - Number of seconds since the badge started (monotonic clock that never goes backwards)
- `get_epoch_time() -> float` - Current timestamp according to internal RTC.
- `set_epoch_time(epoch_time: int) -> None` - Set the current time on the internal RTC using MicroPython epoch

### badge.utils

Miscellaneous utility functions.

**Functions:**
- `get_data_dir() -> str` - Get path to app's persistent data directory (`/data/appname/`), creating it if needed. Use this to store files that should persist between app launches.
- `set_led(value: bool)` - Turn on or off the badge's LED.
- `set_led_pwm(value: int)` - Set the badge's LED to a variable brightness between 0 and 65535.

### badge.uart

**this is in a half-implemented state. Ask @mpk about its current status if you want to use it.**
Talk to another badge by plugging into it. This is intended for transferring more data than the radio can handle - say, if you wanted to share contacts, apps, or high scores.

**Functions:**
- `present() -> bool` - Check if there's another badge physically plugged into this one. If this returns `True`, you can't necessarily talk to the other badge - you have to connect first.
- `try_connect() -> bool` - Try to connect to the other badge over UART. Returns `True` if connection was successful, `False` if not.
- `is_connected() -> bool` - Check if there's still a good connection to the other badge.
- `send(data: bytes)` - Send data over UART to the other badge.
- `read(num_bytes: int) -> bytes` - Read data out of the UART receive buffer.

### badge.contacts

API for managing contact information. The primary key is the badge ID.

**Data types:**
- `Contact` - Represents a contact with fields:
  - `name: str` - Contact's name
  - `pronouns: str` - Contact's pronouns  
  - `badge_id: int` - Contact's badge ID (unique identifier). Usually displayed in hex.
  - `handle: str` - Contact's handle/username

**Functions:**
- `my_contact() -> Optional[Contact]` - Get contact info for current user
- `get_contact_by_badge_id(badge_id: int) -> Optional[Contact]` - Get contact by badge ID
- `get_contact_by_name(name: str) -> Optional[Contact]` - Get contact by name
- `get_all_contacts() -> List[Contact]` - Get all stored contacts
- `add_contact(contact: Contact) -> None` - Add new contact (requires `contacts:write` permission)
- `remove_contact_by_badge_id(badge_id: str) -> bool` - Remove contact by badge ID (requires `contacts:write` permission)
- `remove_contact_by_name(name: str) -> bool` - Remove contact by name (requires `contacts:write` permission)

## badge.BaseApp

The base class that all apps must inherit from. Your app class should be named `App` and inherit from `BaseApp`.

**Required methods to implement:**
- `on_open() -> None` - Called once when the app is opened from the home screen
- `loop() -> None` - Called repeatedly while the app is running (main app loop)

**Optional methods to implement:**
- `on_packet(packet: Packet, in_foreground: bool) -> None` - Called when a radio packet is received. **WARNING: This runs on a different thread - treat like an interrupt handler, i.e. run quick, think about concurrency/race conditions, etc!**

**Available properties:**
- `logger: logging.Logger` - Logger instance for debugging over USB
