# Button Elimination Game

A multiplayer elimination game for Shipwrecked PCB badges with improved networking, UI, and game mechanics.

## Overview

This is a real-time multiplayer game where players must avoid pressing a specific "elimination button" each round. Players who press the elimination button are eliminated from the game. The last player standing wins!

## Features

### Core Game Mechanics
- **Multiplayer Support**: Up to 8 players per game
- **Round-based Elimination**: Each round has a different elimination button (SW4-SW18)
- **Real-time Communication**: Robust radio protocol with automatic discovery
- **Audio Feedback**: Different tones for safe vs elimination buttons
- **Automatic Timeouts**: Handles disconnected players gracefully

### Contact Management
- **Automatic Contact Saving**: Players' badge contacts are automatically saved when they join games
- **Real Name Display**: Shows configured badge names instead of just badge IDs
- **Contact Exchange**: Host and player information is shared and saved for future reference
- **Smart Name Resolution**: Falls back to badge ID format when no name is configured

### Networking Improvements
- **Automatic Host Discovery**: Clients automatically find and join available games
- **Robust Protocol**: JSON-based packet system with error handling
- **Connection Management**: Heartbeats, timeouts, and reconnection
- **Rate Limiting**: Respects badge radio constraints
- **Host Announcements**: Periodic broadcasts for discoverability
- **Thread Safety**: Proper queue-based packet handling to avoid OS thread blocking

### User Interface
- **Main Menu**: Choose between joining or hosting games
- **Dynamic Displays**: Real-time game status, player lists, timers
- **Visual Feedback**: Clear indication of game state and requirements
- **Player Management**: See all connected players and their status
- **Smart Button Layout**: Avoids SW3 (home button) and uses SW4-SW18 for gameplay

## Installation

1. Copy the entire `badge-game` directory to your badge's `/apps/` folder
2. You'll have two apps:
   - `bgs` - Full game (can host or join)
   - `bgh` - Host-only version

## How to Play

### Starting a Game

**Option 1: Host a Game**
1. Launch the `bgh` app (auto-starts as host)
2. Wait for players to join (displays player count)
3. Press SW5 when you have 2+ players to start

**Option 2: Join a Game**
1. Launch the `bgs` app
2. Select "Join Game" from the menu
3. The app will automatically find and join available games

### Gameplay

1. **Round Start**: Each round announces which button to avoid (e.g., "AVOID: SW7")
2. **Make Your Choice**: 
   - Press ANY button EXCEPT the elimination button to stay safe
   - Press nothing (also safe)
   - Don't press the elimination button!
3. **Round End**: Players who pressed the elimination button are eliminated
4. **Continue**: Rounds continue until only one player remains

### Controls

**Main Menu** (bgs app only):
- SW4/SW5: Navigate menu
- SW6: Select option

**During Game**:
- SW4-SW18: Game buttons (one will be elimination button each round)
- SW6: Start game (host only, when 2+ players)
- SW18: Return to main menu

**Note**: SW3 is reserved as the home button and is not used by the game.

## Technical Details

### Packet Protocol

The game uses a robust JSON-based packet system:

- `PACKET_HOST_ANNOUNCE` - Periodic host discovery broadcasts
- `PACKET_JOIN_REQUEST` - Client requests to join game  
- `PACKET_JOIN_RESPONSE` - Host accepts/rejects join
- `PACKET_GAME_START` - Round start with elimination button
- `PACKET_BUTTON_PRESS` - Player button press with timestamp
- `PACKET_ROUND_END` - Round results and eliminations
- `PACKET_GAME_OVER` - Final winner announcement
- `PACKET_HEARTBEAT` - Connection keep-alive
- `PACKET_PLAYER_LIST` - Current player roster
- `PACKET_DISCONNECT` - Clean disconnect

### Game Parameters

```python
ROUND_DURATION = 5.0        # Seconds per round
HEARTBEAT_INTERVAL = 10.0   # Seconds between heartbeats  
CONNECTION_TIMEOUT = 30.0   # Connection timeout
MAX_PLAYERS = 8             # Maximum players per game
DISCOVERY_INTERVAL = 3.0    # Host discovery frequency
```

### App Numbers

- `bgs`: 4325 (client/host)
- `bgh`: 4325 (host-only)

## File Structure

```
badge-game/
├── bgs/                    # Main game app
│   ├── manifest.json      # App metadata
│   └── main.py           # Complete game implementation
├── bgh/                   # Host-only app  
│   ├── manifest.json     # Host app metadata
│   └── main.py          # Host-focused version
└── README.md             # This file
```

## Implementation Highlights

### Robust Networking
- Automatic host discovery with periodic announcements
- JSON packet protocol for extensibility
- Connection timeouts and heartbeat system
- Graceful handling of player disconnections
- Rate limiting compliance (1.5s between packets)

### Game State Management
- Clean separation of host and client logic
- Comprehensive state machines for both modes
- Proper button debouncing and input handling
- Real-time display updates

### User Experience
- Intuitive menu system
- Clear visual feedback for all game states
- Audio cues for different actions
- Automatic game flow management
- Real name display when badges are properly configured
- Automatic contact management and saving

### Contact System Integration
- Uses `badge.contacts.my_contact()` to get user's configured name
- Automatically saves contacts using `badge.contacts.add_contact()`
- Shares badge information (name, handle, pronouns) during game join
- Displays real names in game UI when available
- Falls back gracefully when badges aren't configured with names

## Troubleshooting

### Connection Issues
- Ensure both badges are running compatible versions
- Check that app numbers don't conflict with other apps
- Verify badges are within radio range
- Host should appear in client's discovery list within 3-6 seconds

### Game Flow Issues  
- Host needs 2+ players to start a game
- Eliminated players can still watch but can't participate
- Games automatically end when 1 or 0 players remain
- Use SW6 to return to menu and restart

### Performance
- Game supports up to 8 players efficiently
- Host handles all game logic and state
- Clients are lightweight and responsive
- Radio usage is optimized for badge constraints

## Development Notes

This implementation demonstrates several advanced badge programming concepts:

- **Robust Radio Protocols**: JSON messaging with error handling
- **State Management**: Complex game state machines
- **Real-time UI**: Dynamic display updates
- **Multiplayer Architecture**: Host-client model with automatic discovery
- **Resource Management**: Efficient use of radio, display, and processing

The code is designed to be maintainable and extensible for future game modes or features.