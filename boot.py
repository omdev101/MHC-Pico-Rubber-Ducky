# ==============================================================================
# MULTIPURPOSE HACKABLE CUBE (MHC) - BOOT CONFIGURATION
# Raspberry Pi Pico USB Rubber Ducky with OLED Display
# Author: Om
# Version: 1.0
# 
# This file handles boot sequence, button detection for boot modes,
# storage configuration, and boot logo display.
# ==============================================================================

# Import required libraries for boot sequence
import board                    # Hardware pin definitions
import digitalio                # Digital I/O for buttons
import storage                  # USB mass storage control
import supervisor               # System control and code execution
import json                     # JSON file handling for settings
import busio                    # Bus communication (I2C)
import adafruit_ssd1306        # OLED display driver
import time                     # Time and delay functions
import terminalio               # Built-in terminal font
from adafruit_display_text import label  # Text display functionality
import gc                       # Garbage collection for memory management
import os                       # Operating system interface

# ==============================================================================
# BOOT SEQUENCE INITIALIZATION
# ==============================================================================

print("=== MHC Boot Sequence Starting ===")
print(f"Free memory before script execution: {gc.mem_free()} bytes")
gc.collect()  # Force garbage collection to free up memory
print(f"Free memory after cleanup: {gc.mem_free()} bytes")

# Display Initialization for boot logo
print("Initializing boot display...")
i2cdisp = busio.I2C(board.GP9, board.GP8)  # I2C bus (SCL=GP9, SDA=GP8)
display = adafruit_ssd1306.SSD1306_I2C(128, 64, i2cdisp)  # 128x64 OLED display

# ==============================================================================
# BOOT LOGO DISPLAY FUNCTIONS
# ==============================================================================

def display_bitmap(filename, x, y):
    """
    Load and display a 1-bit monochrome bitmap on the OLED.
    Used to show the custom boot logo during startup.
    
    Args:
        filename: Path to the .bmp file
        x, y: Starting coordinates for the bitmap
    """
    try:
        with open(filename, "rb") as f:
            f.seek(62)  # Skip BMP header (54 bytes + 8 bytes color table for monochrome)
            
            # Read bitmap data row by row (64 pixels high)
            for j in range(64):
                # Read width data (58 pixels wide = ~8 bytes per row)
                for i in range(8):
                    byte = f.read(1)
                    if not byte:
                        break  # Stop if end of file reached
                    
                    byte = byte[0]  # Convert bytes object to integer
                    
                    # Extract individual bits and set pixels
                    for bit in range(8):
                        if (i * 8 + bit) < 58:  # Stay within 58-pixel width
                            # Check if bit is set (1 = white pixel, 0 = black pixel)
                            color = 1 if (byte & (1 << (7 - bit))) else 0
                            display.pixel(x + (i * 8) + bit, y + j, color)
    except OSError as e:
        print(f"Error loading boot logo: {e}")
        # Display text fallback if logo fails to load
        display.text("MHC", 50, 25, 1)

# ==============================================================================
# BOOT LOGO DISPLAY
# ==============================================================================

print("Displaying boot logo...")
# Position logo at top-left corner
x_start = 0  # Left edge of display
y_start = 0  # Top edge of display

# Display the custom boot logo bitmap
display_bitmap("/boot_logo_bitmap_1bit.bmp", x_start, y_start)

# Add project text next to the logo
display.text("Multipurpose", 60, 20, 1)  # Project name line 1
display.text("Hackable", 60, 30, 1)      # Project name line 2
display.text("Cube", 60, 40, 1)          # Project name line 3

# Update display and show for 2 seconds
display.show()
print("Boot logo displayed")
time.sleep(2)  # Keep the logo visible during boot

# ==============================================================================
# SETTINGS AND BOOT MODE DETECTION
# ==============================================================================

# Load user settings to determine boot behavior
print("Loading settings...")
try:
    with open("/settings.json", "r") as f:
        settings = json.load(f)
    print(f"Settings loaded: {settings}")
except (OSError, ValueError) as e:
    print(f"Error loading settings: {e}")
    # Use default settings if file is missing or corrupted
    settings = {"auto_execute": False, "selected_payload": ""}

# Configure boot mode detection buttons
# GP4: MODE button - Hold during boot for special modes
# GP3: BACK button - Used in combination with GP4
print("Configuring boot mode detection...")
button_gp4 = digitalio.DigitalInOut(board.GP4)
button_gp4.switch_to_input(pull=digitalio.Pull.UP)

button_gp3 = digitalio.DigitalInOut(board.GP3)
button_gp3.switch_to_input(pull=digitalio.Pull.UP)

# Track which objects have been deinitialized for cleanup
deinited_objects = {"i2cdisp": False, "button_gp4": False, "button_gp3": False}

# ==============================================================================
# BOOT CLEANUP FUNCTIONS
# ==============================================================================

def cleanupboot():
    """
    Clean up boot resources before transitioning to main application.
    Deinitializes display, I2C bus, and buttons to free resources for main app.
    """
    print("Cleaning up boot resources...")
    
    # Clear and turn off display
    if display:
        display.fill(0)  # Clear screen
        display.show()   # Apply changes
    
    # Deinitialize I2C bus (prevents conflicts with main app)
    if i2cdisp and not deinited_objects["i2cdisp"]:
        i2cdisp.deinit()
        deinited_objects["i2cdisp"] = True

    # Deinitialize boot detection buttons
    if button_gp4 and not deinited_objects["button_gp4"]:
        button_gp4.deinit()
        deinited_objects["button_gp4"] = True
    
    if button_gp3 and not deinited_objects["button_gp3"]:
        button_gp3.deinit()
        deinited_objects["button_gp3"] = True

    print("Boot resource cleanup complete")
    
def delete_no_execute_file():
    """
    Delete the 'no_execute' file if it exists.
    This file prevents automatic payload execution when present.
    Used when transitioning from safe mode to auto-execute mode.
    """
    try:
        os.stat("/no_execute")  # Check if file exists
        os.remove("/no_execute")  # Remove the file
        print("'no_execute' file deleted - auto-execution enabled")
    except OSError:
        print("'no_execute' file not found - no action needed")

# ==============================================================================
# BOOT MODE DETECTION AND CONFIGURATION
# ==============================================================================

print("Detecting boot mode...")
print(f"GP3 (BACK) state: {'PRESSED' if not button_gp3.value else 'RELEASED'}")
print(f"GP4 (MODE) state: {'PRESSED' if not button_gp4.value else 'RELEASED'}")

# BOOT MODE 1: Safe Mode + Mass Storage (Both GP3 and GP4 held)
if not button_gp3.value and not button_gp4.value:
    print("=== BOOT MODE 1: SAFE MODE + MASS STORAGE ===")
    print("Both BACK and MODE buttons held during boot")
    print("Enabling mass storage access and disabling auto-execution")
    
    # Enable write access to filesystem
    storage.remount("/", False)  # Make filesystem writable
    
    # Create no_execute file to prevent payload execution
    try:
        with open("/no_execute", "w") as f:
            f.write("This file prevents automatic payload execution.\n")
            f.write("Created by: Safe Mode Boot (GP3+GP4)\n")
            f.write(f"Timestamp: {time.monotonic()}\n")
        print("'no_execute' file created successfully")
    except Exception as e:
        print(f"Error creating 'no_execute' file: {e}")
    
    # Re-enable read-only filesystem and keep mass storage enabled    
    storage.remount("/", True)  # Make filesystem read-only again
    print("Mass storage enabled - device accessible as USB drive")
    cleanupboot()
    
# BOOT MODE 2: Mass Storage Only (Only GP4 held)    
elif not button_gp4.value:
    print("=== BOOT MODE 2: MASS STORAGE MODE ===")
    print("MODE button held during boot")
    print("Enabling mass storage access, disabling auto-execution")
    
    # Enable write access temporarily
    storage.remount("/", False)
    
    # Create no_execute file to disable payload execution
    try:
        with open("/no_execute", "w") as f:
            f.write("This file prevents automatic payload execution.\n")
            f.write("Created by: Mass Storage Boot (GP4)\n")
            f.write(f"Timestamp: {time.monotonic()}\n")
        print("'no_execute' file created successfully")
    except Exception as e:
        print(f"Error creating 'no_execute' file: {e}")
            
    # Keep mass storage enabled for file access
    print("Mass storage enabled - device accessible as USB drive")
    cleanupboot()
    
# BOOT MODE 3: Normal Operation (No buttons or auto-execute handling)    
else:
    print("=== BOOT MODE 3: NORMAL OPERATION ===")
    print("No boot mode buttons detected")
    
    # Check if auto-execute is enabled in settings
    if settings.get("auto_execute", False):
        print("Auto-execute enabled - disabling mass storage")
        print(f"Selected payload: {settings.get('selected_payload', 'None')}")
        
        # Disable mass storage for stealth operation
        storage.disable_usb_drive()  # Hide device from computer
        
        # Remove no_execute file if present (enable auto-execution)
        delete_no_execute_file()
        
        # Optimize memory for payload execution
        gc.collect()
        print(f"Memory optimized: {gc.mem_free()} bytes available")
        
    else:
        print("Auto-execute disabled - enabling interactive mode")
        
        # Disable mass storage but allow manual execution
        storage.disable_usb_drive()
        
        # Create no_execute file to prevent auto-execution
        try:
            with open("/no_execute", "w") as f:
                f.write("This file prevents automatic payload execution.\n")
                f.write("Created by: Interactive Mode Boot\n")
                f.write(f"Timestamp: {time.monotonic()}\n")
            print("'no_execute' file created - manual execution only")
        except Exception as e:
            print(f"Error creating 'no_execute' file: {e}")

    # Clean up boot resources
    cleanupboot()

# ==============================================================================
# TRANSITION TO MAIN APPLICATION
# ==============================================================================

print("Boot sequence complete - transitioning to main application")
print("Loading UI elements...")

# Transfer control to main application (code.py)
supervisor.set_next_code_file("code.py")
print("Starting main application...")
supervisor.reload()  # Reload system with main application
