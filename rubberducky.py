# ==============================================================================
# MULTIPURPOSE HACKABLE CUBE (MHC) - DUCKYSCRIPT INTERPRETER
# Raspberry Pi Pico USB Rubber Ducky with OLED Display
# Author: Om
# Version: 1.0
#
# This file implements a DuckyScript interpreter that can execute
# payload scripts (.dd files) to emulate keyboard and mouse input.
# Supports standard DuckyScript commands plus custom extensions.
# ==============================================================================

# Import required libraries for HID emulation
import usb_hid                 # USB HID device support
from adafruit_hid.keyboard import Keyboard      # Keyboard emulation
from adafruit_hid.mouse import Mouse           # Mouse emulation and gestures

import json                     # JSON handling for settings

# Keyboard Layout Support
# NOTE: Change these imports for non-US keyboards
# Available layouts: keyboard_layout_us, keyboard_layout_de, etc.
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS as KeyboardLayout
from adafruit_hid.keycode import Keycode       # Key code definitions

# System and hardware control
import supervisor               # System control and auto-reload
import time                     # Timing and delays
import digitalio                # Digital I/O (not used in current version)
from board import *             # All board pin definitions
import pwmio                    # PWM output for LED control

# ==============================================================================
# LED FEEDBACK SYSTEM
# ==============================================================================

# Initialize onboard LED for visual feedback during payload execution
led = pwmio.PWMOut(LED, frequency=5000, duty_cycle=0)  # Start with LED off

def led_pwm_up(led):
    """
    Gradually brighten the LED using PWM.
    Provides visual feedback during payload execution start.
    """
    for i in range(100):
        if i < 50:
            # Fade in LED brightness over first half of range
            led.duty_cycle = int(i * 2 * 65535 / 100)
        time.sleep(0.01)

def led_pwm_down(led):
    """
    Gradually dim the LED using PWM.
    Provides visual feedback during payload execution end.
    """
    for i in range(100):
        if i >= 50:
            # Fade out LED brightness over second half of range
            led.duty_cycle = 65535 - int((i - 50) * 2 * 65535 / 100)
        time.sleep(0.01)

# ==============================================================================
# MOUSE GESTURE FUNCTIONS (Custom Extensions)
# ==============================================================================

def swipe(x_start, y_start, x_end, y_end, duration):
    """
    Perform a mouse swipe gesture from start to end coordinates.
    Useful for touchscreen-like interactions.
    
    Args:
        x_start, y_start: Starting coordinates
        x_end, y_end: Ending coordinates  
        duration: Number of steps for the swipe (affects speed)
    """
    # Move to starting position
    mouse.move(x_start, y_start)
    
    # Press and hold left button to begin drag
    mouse.press(Mouse.LEFT_BUTTON)
    
    # Calculate movement steps
    x_step = (x_end - x_start) / duration
    y_step = (y_end - y_start) / duration
    
    # Perform gradual movement
    for i in range(duration):
        mouse.move(int(x_step), int(y_step))
        time.sleep(0.01)  # Small delay between steps
    
    # Release button to complete swipe
    mouse.release(Mouse.LEFT_BUTTON)

def tap(x, y):
    """
    Perform a single mouse tap at specified coordinates.
    Simulates a quick click at the target location.
    
    Args:
        x, y: Coordinates to tap
    """
    # Move to tap position
    mouse.move(x, y)
    
    # Quick press and release (tap)
    mouse.press(Mouse.LEFT_BUTTON)
    mouse.release(Mouse.LEFT_BUTTON)

# ==============================================================================
# DUCKYSCRIPT COMMAND MAPPING
# ==============================================================================

# Dictionary mapping DuckyScript commands to CircuitPython Keycode constants
# Supports standard Rubber Ducky syntax with aliases for common keys
duckyCommands = {
    # System Keys
    'WINDOWS': Keycode.WINDOWS, 'GUI': Keycode.GUI,
    'APP': Keycode.APPLICATION, 'MENU': Keycode.APPLICATION,
    
    # Modifier Keys
    'SHIFT': Keycode.SHIFT, 'ALT': Keycode.ALT, 
    'CONTROL': Keycode.CONTROL, 'CTRL': Keycode.CONTROL,
    
    # Arrow Keys
    'DOWNARROW': Keycode.DOWN_ARROW, 'DOWN': Keycode.DOWN_ARROW,
    'LEFTARROW': Keycode.LEFT_ARROW, 'LEFT': Keycode.LEFT_ARROW,
    'RIGHTARROW': Keycode.RIGHT_ARROW, 'RIGHT': Keycode.RIGHT_ARROW,
    'UPARROW': Keycode.UP_ARROW, 'UP': Keycode.UP_ARROW,
    
    # Special Keys
    'BREAK': Keycode.PAUSE, 'PAUSE': Keycode.PAUSE,
    'CAPSLOCK': Keycode.CAPS_LOCK, 'DELETE': Keycode.DELETE,
    'END': Keycode.END, 'ESC': Keycode.ESCAPE, 'ESCAPE': Keycode.ESCAPE,
    'HOME': Keycode.HOME, 'INSERT': Keycode.INSERT,
    'NUMLOCK': Keycode.KEYPAD_NUMLOCK, 'PAGEUP': Keycode.PAGE_UP,
    'PAGEDOWN': Keycode.PAGE_DOWN, 'PRINTSCREEN': Keycode.PRINT_SCREEN,
    'ENTER': Keycode.ENTER, 'SCROLLLOCK': Keycode.SCROLL_LOCK,
    'SPACE': Keycode.SPACE, 'TAB': Keycode.TAB, 'BACKSPACE': Keycode.BACKSPACE,
    
    # Letter Keys (A-Z)
    'A': Keycode.A, 'B': Keycode.B, 'C': Keycode.C, 'D': Keycode.D, 'E': Keycode.E,
    'F': Keycode.F, 'G': Keycode.G, 'H': Keycode.H, 'I': Keycode.I, 'J': Keycode.J,
    'K': Keycode.K, 'L': Keycode.L, 'M': Keycode.M, 'N': Keycode.N, 'O': Keycode.O,
    'P': Keycode.P, 'Q': Keycode.Q, 'R': Keycode.R, 'S': Keycode.S, 'T': Keycode.T,
    'U': Keycode.U, 'V': Keycode.V, 'W': Keycode.W, 'X': Keycode.X, 'Y': Keycode.Y,
    'Z': Keycode.Z,
    
    # Function Keys (F1-F12)
    'F1': Keycode.F1, 'F2': Keycode.F2, 'F3': Keycode.F3, 'F4': Keycode.F4,
    'F5': Keycode.F5, 'F6': Keycode.F6, 'F7': Keycode.F7, 'F8': Keycode.F8,
    'F9': Keycode.F9, 'F10': Keycode.F10, 'F11': Keycode.F11, 'F12': Keycode.F12,
}

# ==============================================================================
# DUCKYSCRIPT PARSING FUNCTIONS
# ==============================================================================

def convertLine(line):
    """
    Convert a line of DuckyScript key commands to CircuitPython keycodes.
    Supports both duckyCommands dictionary and direct Keycode attributes.
    
    Args:
        line: String containing space-separated key names
        
    Returns:
        List of Keycode objects for the keys
    """
    newline = []
    # Split line into individual key names, filter out empty strings
    for key in filter(None, line.split(" ")):
        key = key.upper()  # Convert to uppercase for consistency
        
        # Check if key is in our custom command dictionary
        command_keycode = duckyCommands.get(key, None)
        if command_keycode is not None:
            newline.append(command_keycode)
        # Check if key exists as a direct Keycode attribute
        elif hasattr(Keycode, key):
            newline.append(getattr(Keycode, key))
        else:
            print(f"Unknown key: <{key}>")
    return newline

def runScriptLine(line):
    """
    Execute a line of converted keycodes by pressing all keys simultaneously.
    Simulates key combinations like CTRL+ALT+DELETE.
    
    Args:
        line: List of Keycode objects to press
    """
    # Press all keys in the line
    for k in line:
        kbd.press(k)
    # Release all keys at once
    kbd.release_all()

def sendString(line):
    """
    Type a string of text using the keyboard layout.
    Handles character mapping and special characters.
    
    Args:
        line: String to type
    """
    layout.write(line)

def parseLine(line):
    """
    Parse and execute a single line of DuckyScript.
    Handles all supported DuckyScript commands and custom extensions.
    
    Args:
        line: Single line of DuckyScript code
    """
    global defaultDelay
    
    # Skip empty lines and comments
    if not line.strip() or line.startswith("REM"):
        pass  # REM = comment, ignore this line
    
    # Timing commands
    elif line.startswith("DELAY"):
        # DELAY 1000 = wait 1000 milliseconds
        delay_ms = float(line[6:])  # Extract delay value
        time.sleep(delay_ms / 1000)  # Convert to seconds
    
    elif line.startswith("DEFAULT_DELAY"):
        # Set default delay between all commands
        defaultDelay = int(line[14:]) * 10  # Convert to milliseconds
        
    elif line.startswith("DEFAULTDELAY"):
        # Alternative syntax for default delay
        defaultDelay = int(line[13:]) * 10
    
    # Text and output commands
    elif line.startswith("STRING"):
        # STRING Hello World = type "Hello World"
        sendString(line[7:])  # Extract text after "STRING "
        
    elif line.startswith("PRINT"):
        # PRINT message = print to console (debugging)
        print("[SCRIPT]: " + line[6:])
    
    # Script control commands
    elif line.startswith("IMPORT"):
        # IMPORT filename = execute another script file
        runScript(line[7:])  # Recursively run another script
    
    # Hardware control commands (custom extensions)
    elif line.startswith("LED"):
        # LED = toggle onboard LED
        led.value = not led.value
        
    elif line.startswith("SWIPE"):
        # SWIPE x_start y_start x_end y_end duration = mouse swipe gesture
        args = line[6:].split()
        if len(args) >= 5:
            swipe(int(args[0]), int(args[1]), int(args[2]), int(args[3]), int(args[4]))
        else:
            print("SWIPE command requires 5 arguments: x_start y_start x_end y_end duration")
    
    elif line.startswith("TAP"):
        # TAP x y = mouse tap at coordinates
        args = line[4:].split()
        if len(args) >= 2:
            tap(int(args[0]), int(args[1]))
        else:
            print("TAP command requires 2 arguments: x y")
    
    # Key press commands (default case)
    else:
        # Any other line is treated as key combination
        # Example: CTRL ALT DELETE
        newScriptLine = convertLine(line)
        if newScriptLine:  # Only execute if keys were found
            runScriptLine(newScriptLine)

# ==============================================================================
# HID DEVICE INITIALIZATION
# ==============================================================================

# Initialize USB HID devices
print("Initializing HID devices...")
kbd = Keyboard(usb_hid.devices)     # Keyboard interface
layout = KeyboardLayout(kbd)        # US keyboard layout
mouse = Mouse(usb_hid.devices)      # Mouse interface
print("HID devices ready")

# ==============================================================================
# EXECUTION SETUP
# ==============================================================================

# Disable CircuitPython auto-reload to prevent interruptions during payload execution
supervisor.runtime.autoreload = False
time.sleep(0.5)  # Brief delay for system stability

# Provide visual feedback that payload is starting
print("Starting payload execution...")
led_pwm_up(led)  # Fade in LED to indicate start

# Global delay setting (milliseconds between commands)
defaultDelay = 0

# ==============================================================================
# SCRIPT EXECUTION FUNCTIONS
# ==============================================================================

def runScript(file):
    """
    Execute a DuckyScript file line by line.
    Supports REPEAT command and maintains previous line context.
    
    Args:
        file: Path to the .dd script file to execute
    """
    global defaultDelay
    print(f"Executing script: {file}")
    
    try:
        with open(file, "r", encoding='utf-8') as f:
            previousLine = ""  # Store previous line for REPEAT command
            line_number = 0
            
            for line in f:
                line_number += 1
                line = line.rstrip()  # Remove trailing whitespace/newlines
                
                # Skip empty lines
                if not line.strip():
                    continue
                    
                print(f"Line {line_number}: {line}")  # Debug output
                
                # Handle REPEAT command
                if line.startswith("REPEAT"):
                    # REPEAT 5 = repeat previous command 5 times
                    try:
                        repeat_count = int(line[7:])
                        for i in range(repeat_count):
                            print(f"  Repeat {i+1}/{repeat_count}: {previousLine}")
                            parseLine(previousLine)
                            time.sleep(float(defaultDelay) / 1000)  # Apply default delay
                    except ValueError:
                        print(f"Invalid REPEAT count: {line[7:]}")
                else:
                    # Execute normal command
                    parseLine(line)
                    previousLine = line  # Store for potential REPEAT
                
                # Apply default delay between commands
                time.sleep(float(defaultDelay) / 1000)
                
    except OSError as e:
        print(f"Error opening script file {file}: {e}")
    except Exception as e:
        print(f"Error executing script {file}: {e}")

def selectPayload():
    """
    Determine which payload file to execute based on settings.json.
    Falls back to default payload if settings file is missing or corrupted.
    
    Returns:
        String path to the payload file to execute
    """
    try:
        with open("settings.json", "r") as settings_file:
            settings = json.load(settings_file)
            payload = settings.get("selected_payload", "payload.dd")
            payload_path = "/payloads/" + payload
            print(f"Selected payload from settings: {payload}")
    except (OSError, ValueError) as e:
        print(f"Error reading settings.json: {e}")
        print("Using default payload")
        payload_path = "/payloads/payload.dd"

    return payload_path

def cleanup():
    """
    Clean up hardware resources after payload execution.
    Turns off LED and deinitializes PWM to free resources.
    """
    print("Cleaning up resources...")
    
    if led:
        led.duty_cycle = 0  # Turn off LED
        led.deinit()        # Free PWM resource
    
    # Could add other cleanup here (mouse, keyboard, etc.)
    print("Resource cleanup complete")

# ==============================================================================
# MAIN PAYLOAD EXECUTION
# ==============================================================================

# Determine which payload to run
payload = selectPayload()
print(f"Executing payload: {payload}")

# Execute the selected payload script
runScript(payload)

# Execution complete
print("Payload execution completed successfully")

# Clean up resources
cleanup()

# Brief delay before potential system reload
time.sleep(0.5)
print("DuckyScript interpreter finished")
