# ==============================================================================
# MULTIPURPOSE HACKABLE CUBE (MHC) - MAIN APPLICATION
# Raspberry Pi Pico USB Rubber Ducky with OLED Display
# Author: Om
# Version: 1.0
# ==============================================================================

# Import required libraries
import board                    # Hardware pin definitions
import busio                    # Bus communication (I2C, SPI, etc.)
import displayio                # Display management
import terminalio               # Built-in terminal font
import adafruit_ssd1306        # OLED display driver
from adafruit_display_text import label  # Text display functionality
import time                     # Time and delay functions
import digitalio                # Digital I/O for buttons
import math                     # Mathematical functions
import microcontroller         # Access to MCU features (temperature sensor)
import os                       # Operating system interface
import json                     # JSON file handling

# ==============================================================================
# HARDWARE CONFIGURATION
# ==============================================================================

# Display Initialization - SSD1306 OLED (128x64) via I2C
SDA = board.GP8                 # I2C Data pin
SCL = board.GP9                 # I2C Clock pin
i2c = busio.I2C(SCL, SDA)       # Initialize I2C bus
oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)  # Initialize OLED display

# ==============================================================================
# BUTTON AND UI STATE CONFIGURATION
# ==============================================================================

# Button Configuration - GPIO pins for navigation
# GP0: UP button - Navigate up in menus
# GP1: OK button - Select/confirm actions 
# GP2: DOWN button - Navigate down in menus
# GP3: BACK button - Return to previous menu
# GP4: MODE button - Special functions (boot modes)
button_pins = [board.GP0, board.GP1, board.GP2, board.GP3, board.GP4]
buttons = []                    # List to store initialized button objects

# Menu Structure Definition
menu_items = ["Temperature", "Rubber Ducky", "Settings"]  # Main menu options
rubber_ducky_menu_items = ["Select Payload", "Auto Execute", "Execute Now"]  # Rubber Ducky submenu
settings_menu_items = ["About"] # Settings submenu

# ==============================================================================
# UI STATE VARIABLES
# ==============================================================================

# Menu Navigation State
current_selection = 0           # Currently selected item in main menu
rubber_ducky_selection = 0      # Currently selected item in rubber ducky menu
payload_selection = 0           # Currently selected payload file
settings_selection = 0          # Currently selected settings item

# File Management
payload_files = []              # List of available .dd payload files

# Display Management
timeout_seconds = 30            # Seconds before display auto-sleep
last_input_time = time.monotonic()  # Last time a button was pressed
last_time_update = time.monotonic() # Last time the home screen was updated
display_on = True               # Current display power state

# Application State Flags - Track which screen/menu is currently active
on_home_screen = True           # Home screen with clock
in_main_menu = False            # Main menu (Temperature, Rubber Ducky, Settings)
in_rubber_ducky_menu = False    # Rubber Ducky submenu
in_temperature_app = False      # Temperature monitoring screen
in_payload_selection = False    # Payload file selection screen
in_auto_execute_option = False  # Auto-execute configuration screen
in_settings_menu = False        # Settings menu screen

# Application Settings
temperature_unit = "C"          # Temperature display unit (C/F)

# ==============================================================================
# PERSISTENT SETTINGS CONFIGURATION
# ==============================================================================

# Settings file and variables
settings_file = "settings.json" # JSON file for persistent configuration
auto_execute = False            # Auto-execute payload on boot
selected_payload = ""           # Currently selected payload file


# ==============================================================================
# BUTTON INITIALIZATION
# ==============================================================================

# Initialize each button with pull-up resistors
# Buttons read LOW (False) when pressed, HIGH (True) when released
for pin in button_pins:
    button = digitalio.DigitalInOut(pin)
    button.direction = digitalio.Direction.INPUT
    button.pull = digitalio.Pull.UP  # Enable internal pull-up resistor
    buttons.append(button)

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def get_visible_items(items, current_selection, max_visible=4):
    """
    Helper function to implement scrolling in menus with many items.
    Returns the subset of items that should be visible on screen.
    
    Args:
        items: List of menu items
        current_selection: Index of currently selected item
        max_visible: Maximum number of items to show on screen
    
    Returns:
        tuple: (visible_items, start_index)
    """
    total_items = len(items)
    start_index = max(0, min(current_selection - max_visible // 2, total_items - max_visible))
    end_index = min(total_items, start_index + max_visible)
    visible_items = items[start_index:end_index]
    return visible_items, start_index

# ==============================================================================
# SETTINGS MANAGEMENT FUNCTIONS
# ==============================================================================

def load_settings():
    """
    Load configuration settings from JSON file.
    Sets default values if file doesn't exist or contains invalid data.
    """
    global auto_execute, selected_payload
    if settings_file in os.listdir():  # Check if the settings file exists
        try:
            with open(settings_file, "r") as f:
                settings = json.load(f)
                auto_execute = settings.get("auto_execute", False)
                selected_payload = settings.get("selected_payload", "")
        except (OSError, ValueError) as e:
            print(f"Error loading settings: {e}")
            # Use default values if file is corrupted
            auto_execute = False
            selected_payload = ""

def save_settings():
    """
    Save current configuration settings to JSON file.
    Creates or overwrites the settings file with current values.
    """
    settings = {
        "auto_execute": auto_execute,
        "selected_payload": selected_payload
    }
    try:
        with open(settings_file, "w") as f:
            json.dump(settings, f)
    except OSError as e:
        print(f"Error saving settings: {e}")

def check_no_execute_file():
    """
    Check if the 'no_execute' file exists.
    This file is created by boot.py to prevent automatic payload execution.
    
    Returns:
        bool: True if file exists, False otherwise
    """
    try:
        os.stat("/no_execute")  # Attempt to get the file's status
        print("'no_execute' file exists.")
        return True
    except OSError:
        print("'no_execute' file does not exist.")
        return False

# ==============================================================================
# FILE MANAGEMENT FUNCTIONS
# ==============================================================================

def list_payload_files():
    """
    Scan the /payloads directory for .dd (DuckyScript) files.
    Updates the global payload_files list with available payloads.
    """
    try:
        global payload_files
        payload_files = [f for f in os.listdir('/payloads') if f.endswith(".dd")]
        print(f"Found {len(payload_files)} payload files: {payload_files}")
    except OSError as e:
        print(f"Error listing payload files: {e}")
        payload_files = []
    

# ==============================================================================
# DISPLAY FUNCTIONS
# ==============================================================================

def display_home_screen():
    """
    Display the home screen with greeting and current time.
    Updates automatically every minute while active.
    """
    oled.fill(0)  # Clear display (fill with black)
    current_time = time.localtime()
    time_string = "{:02}:{:02}".format(current_time.tm_hour, current_time.tm_min)
    oled.text("Hi There!", 26, 10, 1)  # Centered greeting message
    oled.text(time_string, 35, 30, 1)   # Centered time display
    oled.show()  # Update display

def read_temperature():
    """
    Read temperature from Pico's built-in CPU temperature sensor.
    
    Returns:
        float: Temperature in Celsius
    """
    temp_celsius = microcontroller.cpu.temperature
    return temp_celsius

def display_temperature():
    """
    Display the temperature monitoring screen.
    Shows CPU temperature in Celsius or Fahrenheit based on user preference.
    UP button switches to Celsius, DOWN button switches to Fahrenheit.
    """
    oled.fill(0)
    temp_celsius = read_temperature()
    
    # Convert temperature based on selected unit
    if temperature_unit == "C":
        temperature_str = "{:.2f} C".format(temp_celsius)
    else:
        temp_fahrenheit = (temp_celsius * 9 / 5) + 32
        temperature_str = "{:.2f} F".format(temp_fahrenheit)
    
    oled.text("Temperature App", 0, 0, 1)
    oled.text(temperature_str, 0, 20, 1)
    oled.text("UP=C, DOWN=F", 0, 40, 1)  # User instructions
    oled.show()

def display_menu():
    """
    Display the main menu with scrolling support.
    Shows selection cursor (>) for current item.
    """
    oled.fill(0)
    visible_items, start_index = get_visible_items(menu_items, current_selection)
    for i, item in enumerate(visible_items):
        if i + start_index == current_selection:
            oled.text(f"> {item}", 0, i * 15, 1)  # Selected item with cursor
        else:
            oled.text(item, 10, i * 15, 1)        # Unselected item, indented
    oled.show()

def display_rubber_ducky_menu():
    """
    Display the Rubber Ducky submenu with payload management options.
    Shows selection cursor (>) for current item.
    """
    oled.fill(0)
    visible_items, start_index = get_visible_items(rubber_ducky_menu_items, rubber_ducky_selection)
    for i, item in enumerate(visible_items):
        if i + start_index == rubber_ducky_selection:
            oled.text(f"> {item}", 0, i * 15, 1)  # Selected item with cursor
        else:
            oled.text(item, 10, i * 15, 1)        # Unselected item, indented
    oled.show()

def display_payload_menu():
    """
    Display the payload selection menu showing available .dd files.
    Shows "No .dd files found" if payloads directory is empty.
    """
    oled.fill(0)
    if payload_files:
        visible_items, start_index = get_visible_items(payload_files, payload_selection)
        for i, file in enumerate(visible_items):
            if i + start_index == payload_selection:
                oled.text(f"> {file}", 0, i * 15, 1)  # Selected file with cursor
            else:
                oled.text(file, 10, i * 15, 1)        # Unselected file, indented
    else:
        oled.text("No .dd files found", 0, 0, 1)  # Error message
        oled.text("Check /payloads/", 0, 15, 1)
    oled.show()
    
def display_settings_menu():
    """
    Display the settings menu with available configuration options.
    Shows selection cursor (>) for current item.
    """
    oled.fill(0)
    visible_items, start_index = get_visible_items(settings_menu_items, settings_selection)
    for i, item in enumerate(visible_items):
        if i + start_index == settings_selection:
            oled.text(f"> {item}", 0, i * 15, 1)  # Selected item with cursor
        else:
            oled.text(item, 10, i * 15, 1)        # Unselected item, indented
    oled.show()

def display_about_section():
    """
    Display the About screen with project information.
    Shows project name, platform, version, and author.
    """
    oled.fill(0)
    oled.text("About", 0, 0, 1)
    oled.text("MHC", 0, 15, 1)                    # Project acronym
    oled.text("Based on RPI Pico", 0, 30, 1)     # Hardware platform
    oled.text("Version 1.0", 0, 45, 1)           # Software version
    oled.text("By: Om", 0, 55, 1)                # Author
    oled.show()

def display_auto_execute_option():
    """
    Display the auto-execute configuration screen.
    Shows current status (On/Off) and allows toggling with OK button.
    """
    oled.fill(0)
    oled.text("Auto Execute", 0, 0, 1)
    oled.text(f"Status: {'On' if auto_execute else 'Off'}", 0, 20, 1)
    oled.text("OK to toggle", 0, 40, 1)  # User instruction
    oled.show()

# ==============================================================================
# DISPLAY POWER MANAGEMENT
# ==============================================================================

def turn_off_display():
    """
    Turn off the OLED display to save power.
    Sets display_on flag to False and clears the screen.
    """
    global display_on
    oled.fill(0)      # Clear display
    oled.show()       # Apply changes
    display_on = False
    print("Display turned off due to inactivity")

def turn_on_display():
    """
    Turn on the OLED display and restore the current screen.
    Automatically determines which screen should be displayed based on app state.
    """
    global display_on
    display_on = True
    print("Display turned on")
    
    # Restore the appropriate screen based on current state
    if on_home_screen:
        display_home_screen()
    elif in_main_menu:
        display_menu()
    elif in_rubber_ducky_menu:
        display_rubber_ducky_menu()
    elif in_payload_selection:
        display_payload_menu()
    elif in_auto_execute_option:
        display_auto_execute_option()
    elif in_temperature_app:
        display_temperature()
    elif in_settings_menu:
        display_settings_menu()

# ==============================================================================
# PAYLOAD EXECUTION FUNCTION
# ==============================================================================

def execute_rubber_ducky_script():
    """
    Execute the selected DuckyScript payload.
    Shows execution status on display and handles errors gracefully.
    """
    try:
        # Show execution start message
        oled.fill(0)
        oled.text("Running", 0, 0, 1)
        oled.text(selected_payload, 0, 15, 1)
        oled.show()
        time.sleep(0.5)
        
        # Clear display during execution
        oled.fill(0)
        oled.show()
        
        # Execute the DuckyScript interpreter
        exec(open("rubberducky.py").read())
        
    except Exception as e:
        # Display error message
        oled.fill(0)
        oled.text("Error executing", 0, 0, 1)
        oled.text("payload:", 0, 15, 1)
        oled.text(str(e)[:21], 0, 30, 1)  # Truncate long error messages
        oled.show()
        print(f"Payload execution error: {e}")
        time.sleep(3)  # Show error longer
        
    finally:
        # Show completion message
        print(f"Payload execution completed: {selected_payload}")
        oled.fill(0)
        oled.text("Execution", 0, 0, 1)
        oled.text("Complete!", 0, 15, 1)
        oled.show()
        time.sleep(1.5)
        
        # Return to rubber ducky menu
        display_rubber_ducky_menu()
            

# ==============================================================================
# APPLICATION INITIALIZATION
# ==============================================================================

# Load user settings from JSON file (auto_execute, selected_payload)
load_settings()
print(f"Settings loaded: auto_execute={auto_execute}, selected_payload={selected_payload}")

# Check for boot mode based on no_execute file
if check_no_execute_file():
    # Safe boot mode - skip automatic payload execution
    print("Boot mode: Safe mode - payload execution disabled")
else:
    # Normal boot mode - check if auto-execute is enabled
    if auto_execute and selected_payload:
        print(f"Boot mode: Auto-execute enabled for {selected_payload}")
        time.sleep(0.5)  # Brief delay before execution
        exec(open("rubberducky.py").read())
    else:
        print("Boot mode: Normal - manual execution only")

# Initialize the display with home screen
print("Initializing display...")
display_home_screen()
print("System ready!")

# ==============================================================================
# MAIN EVENT LOOP
# ==============================================================================

print("Starting main event loop...")
while True:
    current_time = time.monotonic()

    # ==================================================================
    # AUTOMATIC DISPLAY UPDATES
    # ==================================================================
    
    # Update home screen clock every minute (when display is on and on home screen)
    if on_home_screen and display_on and (current_time - last_time_update >= 60):
        display_home_screen()  # Refresh time display
        last_time_update = current_time
        print("Home screen time updated")

    # ==================================================================
    # BUTTON INPUT PROCESSING
    # ==================================================================
    
    # Scan all buttons for input
    for i, button in enumerate(buttons):
        if not button.value:  # Button pressed (pull-up resistor makes pressed = LOW)
            
            # Wake up display if it was sleeping
            if not display_on:
                turn_on_display()
                last_input_time = time.monotonic()
                last_time_update = time.monotonic()
                time.sleep(0.2)  # Debounce delay
                continue  # Skip further processing - just wake up this time

            # Update activity timer
            last_input_time = time.monotonic()

            if i == 3:  # Back button (GP3)
                if in_temperature_app:
                    in_temperature_app = False
                    in_main_menu = True
                    display_menu()
                elif in_payload_selection:
                    in_payload_selection = False
                    in_rubber_ducky_menu = True
                    display_rubber_ducky_menu()
                elif in_auto_execute_option:
                    in_auto_execute_option = False
                    in_rubber_ducky_menu = True
                    display_rubber_ducky_menu()
                elif in_rubber_ducky_menu:
                    in_rubber_ducky_menu = False
                    in_main_menu = True
                    display_menu()
                elif in_main_menu:
                    on_home_screen = True
                    in_main_menu = False
                    display_home_screen()
                last_input_time = time.monotonic()
                last_time_update = time.monotonic()
                time.sleep(0.2)  # Debounce delay

            if on_home_screen:
                if i == 1:  # OK button (GP1) takes to the menu
                    on_home_screen = False
                    in_main_menu = True
                    display_menu()
                    last_input_time = time.monotonic()
                    time.sleep(0.2)  # Debounce delay
                else:
                    display_home_screen()
            elif in_main_menu:
                if i == 0:  # Up button (GP0)
                    current_selection = (current_selection - 1) % len(menu_items)
                    display_menu()
                    last_input_time = time.monotonic()
                    time.sleep(0.2)  # Debounce delay

                if i == 2:  # Down button (GP2)
                    current_selection = (current_selection + 1) % len(menu_items)
                    display_menu()
                    last_input_time = time.monotonic()
                    time.sleep(0.2)  # Debounce delay

                if i == 1:  # OK button (GP1) selects the menu item
                    if menu_items[current_selection] == "Rubber Ducky":
                        in_rubber_ducky_menu = True
                        in_main_menu = False
                        display_rubber_ducky_menu()
                    elif menu_items[current_selection] == "Temperature":
                        in_temperature_app = True
                        in_main_menu = False
                        display_temperature()
                    elif menu_items[current_selection] == "Settings":
                        in_main_menu = False
                        in_settings_menu = True
                        display_settings_menu()

                    else:
                        oled.fill(0)
                        oled.text(f"Selected: {menu_items[current_selection]}", 0, 0, 1)
                        oled.show()
                        last_input_time = time.monotonic()
                        time.sleep(2)
                        display_menu()
                        time.sleep(0.2)
            elif in_temperature_app:
                if i == 0:  # Up button (GP0) - Toggle unit to Celsius
                    temperature_unit = "C"
                    display_temperature()
                    last_input_time = time.monotonic()
                    time.sleep(0.2)  # Debounce delay

                if i == 2:  # Down button (GP2) - Toggle unit to Fahrenheit
                    temperature_unit = "F"
                    display_temperature()
                    last_input_time = time.monotonic()
                    time.sleep(0.2)  # Debounce delay

            elif in_rubber_ducky_menu:
                if i == 0:  # Up button (GP0)
                    rubber_ducky_selection = (rubber_ducky_selection - 1) % len(rubber_ducky_menu_items)
                    display_rubber_ducky_menu()
                    last_input_time = time.monotonic()
                    time.sleep(0.2)  # Debounce delay

                if i == 2:  # Down button (GP2)
                    rubber_ducky_selection = (rubber_ducky_selection + 1) % len(rubber_ducky_menu_items)
                    display_rubber_ducky_menu()
                    last_input_time = time.monotonic()
                    time.sleep(0.2)  # Debounce delay

                if i == 1:  # OK button (GP1) selects the menu item
                    if rubber_ducky_menu_items[rubber_ducky_selection] == "Select Payload":
                        list_payload_files()
                        in_payload_selection = True
                        in_rubber_ducky_menu = False
                        display_payload_menu()
                    elif rubber_ducky_menu_items[rubber_ducky_selection] == "Auto Execute":
                        in_auto_execute_option = True
                        in_rubber_ducky_menu = False
                        display_auto_execute_option()
                    elif rubber_ducky_menu_items[rubber_ducky_selection] == "Execute Now":
                        execute_rubber_ducky_script()
                    else:
                        oled.fill(0)
                        oled.text(f"Selected: {rubber_ducky_menu_items[rubber_ducky_selection]}", 0, 0, 1)
                        oled.show()
                        last_input_time = time.monotonic()
                        time.sleep(2)
                        display_rubber_ducky_menu()
                        time.sleep(0.2)
            elif in_payload_selection:
                if i == 0:  # Up button (GP0)
                    payload_selection = (payload_selection - 1) % len(payload_files)
                    display_payload_menu()
                    last_input_time = time.monotonic()
                    time.sleep(0.2)  # Debounce delay

                if i == 2:  # Down button (GP2)
                    payload_selection = (payload_selection + 1) % len(payload_files)
                    display_payload_menu()
                    last_input_time = time.monotonic()
                    time.sleep(0.2)  # Debounce delay

                if i == 1:  # OK button (GP1) selects the payload
                    selected_payload = payload_files[payload_selection]
                    save_settings()
                    oled.fill(0)
                    oled.text(f"Selected: {selected_payload}", 0, 0, 1)
                    oled.show()
                    last_input_time = time.monotonic()
                    time.sleep(2)
                    in_payload_selection = False
                    in_rubber_ducky_menu = True
                    display_rubber_ducky_menu()
            elif in_auto_execute_option:
                if i == 1:  # OK button (GP1) toggles the auto execute option
                    auto_execute = not auto_execute
                    save_settings()
                    display_auto_execute_option()
                    last_input_time = time.monotonic()
                    time.sleep(2)
                    in_auto_execute_option = False
                    in_rubber_ducky_menu = True
                    display_rubber_ducky_menu()
            
            elif in_settings_menu:
                if i == 0:  # Up button (GP0)
                    settings_selection = (settings_selection - 1) % len(settings_menu_items)
                    display_settings_menu()
                    last_input_time = time.monotonic()
                    time.sleep(0.2)  # Debounce delay

                if i == 2:  # Down button (GP2)
                    settings_selection = (settings_selection + 1) % len(settings_menu_items)
                    display_settings_menu()
                    last_input_time = time.monotonic()
                    time.sleep(0.2)  # Debounce delay

                if i == 1:  # OK button (GP1) selects the menu item
                    if settings_menu_items[settings_selection] == "About":
                        in_settings_menu = False
                        display_about_section()
                        time.sleep(2)
                        in_settings_menu = True
                        display_settings_menu()

                if i == 3:  # Back button (GP3)
                    in_settings_menu = False
                    in_main_menu = True
                    display_menu()  # This will display the main menu
                    last_input_time = time.monotonic()
                    time.sleep(0.2)  # Debounce delay



    # Check for inactivity
    if current_time - last_input_time > timeout_seconds:
        turn_off_display()

    time.sleep(0.1)
