# GUI Control Layer - Installation Guide

This document provides comprehensive installation instructions for all GUI automation tools required by the enhanced GUI Control Layer.

## 📋 Prerequisites

The GUI Control Layer requires different tools depending on your Linux distribution and desktop environment:

- **X11 environments**: wmctrl, xprop, xdotool, xwininfo
- **Wayland environments**: swaymsg, wlr-randr, ydotool
- **Hybrid environments**: Both X11 and Wayland tools for maximum compatibility
- **Virtual/Headless**: Xvfb, VNC tools

## 🐧 Installation by Distribution

### Ubuntu/Debian-based Systems

```bash
# Update package lists
sudo apt update

# Core X11 GUI tools
sudo apt install -y wmctrl x11-utils xdotool

# Wayland tools (for Wayland desktops)
sudo apt install -y sway wlr-randr wayland-utils

# Screenshot tools
sudo apt install -y scrot gnome-screenshot

# Input automation tools
sudo apt install -y xvkbd

# For Wayland input automation (requires manual build)
# ydotool installation
sudo apt install -y libevdev-dev libudev-dev
git clone https://github.com/ReimuNotMoe/ydotool.git
cd ydotool
mkdir build && cd build
cmake ..
make
sudo make install

# Desktop portal integration
sudo apt install -y xdg-desktop-portal-gtk xdg-desktop-portal-kde xdg-desktop-portal-wlr

# Virtual display tools
sudo apt install -y xvfb tigervnc-standalone-server x11vnc

# Accessibility tools
sudo apt install -y at-spi2-core libatspi2.0-dev

# Python dependencies
sudo apt install -y python3-psutil
```

### Fedora/RHEL-based Systems

```bash
# Core X11 GUI tools
sudo dnf install -y wmctrl xorg-x11-utils xdotool

# Wayland tools
sudo dnf install -y sway wlr-randr wayland-utils

# Screenshot tools
sudo dnf install -y scrot gnome-screenshot

# Input automation
sudo dnf install -y xvkbd

# Desktop portals
sudo dnf install -y xdg-desktop-portal-gtk xdg-desktop-portal-kde xdg-desktop-portal-wlr

# Virtual display
sudo dnf install -y xorg-x11-server-Xvfb tigervnc-server x11vnc

# Python dependencies
sudo dnf install -y python3-psutil
```

### Arch Linux

```bash
# Core X11 tools
sudo pacman -S wmctrl xorg-xprop xorg-xwininfo xdotool

# Wayland tools
sudo pacman -S sway wlr-randr wayland-utils

# Screenshot tools
sudo pacman -S scrot gnome-screenshot

# Input automation
sudo pacman -S xvkbd

# For ydotool (Wayland input)
yay -S ydotool

# Desktop portals
sudo pacman -S xdg-desktop-portal-gtk xdg-desktop-portal-kde xdg-desktop-portal-wlr

# Virtual display
sudo pacman -S xorg-server-xvfb tigervnc x11vnc

# Python dependencies
sudo pacman -S python-psutil
```

## 🔧 Tool-by-Tool Installation

### Essential X11 Tools

#### wmctrl
Window manager control utility for X11.
```bash
# Ubuntu/Debian
sudo apt install wmctrl

# Fedora
sudo dnf install wmctrl

# Arch
sudo pacman -S wmctrl
```

#### xprop
X11 window property viewer.
```bash
# Ubuntu/Debian
sudo apt install x11-utils

# Fedora
sudo dnf install xorg-x11-utils

# Arch
sudo pacman -S xorg-xprop
```

#### xdotool
X11 automation utility.
```bash
# Ubuntu/Debian
sudo apt install xdotool

# Fedora
sudo dnf install xdotool

# Arch
sudo pacman -S xdotool
```

### Essential Wayland Tools

#### swaymsg
Sway window manager IPC tool.
```bash
# Ubuntu/Debian
sudo apt install sway

# Fedora
sudo dnf install sway

# Arch
sudo pacman -S sway
```

#### wlr-randr
Output management for wlroots compositors.
```bash
# Ubuntu/Debian
sudo apt install wlr-randr

# Fedora
sudo dnf install wlr-randr

# Arch
sudo pacman -S wlr-randr
```

#### ydotool
Generic command-line automation tool for Wayland.
```bash
# Build from source (most distributions)
git clone https://github.com/ReimuNotMoe/ydotool.git
cd ydotool
mkdir build && cd build
cmake ..
make
sudo make install

# Or use package manager where available
# Arch AUR
yay -S ydotool

# Enable ydotool service
sudo systemctl enable --now ydotoold
```

### Desktop Portal Integration

Desktop portals provide standardized access to desktop features across different desktop environments.

```bash
# GNOME
sudo apt install xdg-desktop-portal-gnome

# KDE
sudo apt install xdg-desktop-portal-kde

# wlroots-based compositors (sway, etc.)
sudo apt install xdg-desktop-portal-wlr
```

### Virtual Display Tools

For headless operation or testing:

#### Xvfb
Virtual framebuffer X server.
```bash
# Ubuntu/Debian
sudo apt install xvfb

# Fedora
sudo dnf install xorg-x11-server-Xvfb

# Arch
sudo pacman -S xorg-server-xvfb
```

#### VNC Tools
For remote GUI access.
```bash
# TigerVNC
sudo apt install tigervnc-standalone-server

# x11vnc
sudo apt install x11vnc
```

## 🐍 Python Dependencies

Install required Python packages:

```bash
# Using pip
pip install psutil fastapi uvicorn pydantic

# For image processing (optional)
pip install Pillow opencv-python

# For OCR capabilities (optional)
pip install pytesseract

# For GUI automation (optional)
pip install pyautogui pynput
```

## 🔍 Verification

After installation, verify the tools are available:

```bash
# Test script to check installation
python3 -c "
import subprocess
import shutil

tools = [
    'wmctrl', 'xprop', 'xdotool', 'xwininfo',
    'swaymsg', 'wlr-randr', 'wayland-info',
    'scrot', 'gnome-screenshot',
    'Xvfb', 'vncserver', 'x11vnc',
    'ydotool'
]

print('GUI Tool Installation Status:')
print('=' * 40)

for tool in tools:
    status = '✅' if shutil.which(tool) else '❌'
    print(f'{status} {tool}')

print('\\nPython modules:')
modules = ['psutil', 'fastapi', 'pydantic']
for module in modules:
    try:
        __import__(module)
        print(f'✅ {module}')
    except ImportError:
        print(f'❌ {module}')
"
```

## 🚀 Testing the Installation

Test the GUI Control Layer:

```bash
# Run the standalone test
cd /path/to/GPT-API
python test_gui_standalone.py

# Start the API server to test endpoints
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Test GUI session detection
curl -H "x-api-key: your-api-key" http://localhost:8000/gui/session
```

## 🔧 Troubleshooting

### Common Issues

#### 1. Permission Denied Errors
Some tools require specific permissions:
```bash
# Add user to input group for ydotool
sudo usermod -a -G input $USER

# Enable ydotool daemon
sudo systemctl enable --now ydotoold
```

#### 2. Wayland Security Restrictions
Some Wayland compositors restrict automation:
```bash
# For development, you may need to disable security features
# (Not recommended for production)
export WAYLAND_DEBUG=1
```

#### 3. Missing Dependencies
Install build dependencies for source compilation:
```bash
# Ubuntu/Debian
sudo apt install build-essential cmake pkg-config libevdev-dev libudev-dev

# Fedora
sudo dnf groupinstall "Development Tools"
sudo dnf install cmake libevdev-devel systemd-devel
```

### Environment-Specific Configuration

#### For Ubuntu 20.04+
```bash
# Ensure snap packages work
sudo snap install code --classic

# For older versions, add PPAs for newer tools
sudo add-apt-repository ppa:kgilmer/speed-ricer
sudo apt update
```

#### For Wayland-only Systems
```bash
# Install XWayland for X11 app compatibility
sudo apt install xwayland

# Set fallback environment variables
export DISPLAY=:0
export WAYLAND_DISPLAY=wayland-0
```

## 📚 Additional Resources

- [wmctrl documentation](http://tripie.sweb.cz/utils/wmctrl/)
- [xdotool tutorial](https://www.semicomplete.com/projects/xdotool/xdotool.xhtml)
- [Sway user guide](https://github.com/swaywm/sway/wiki)
- [ydotool documentation](https://github.com/ReimuNotMoe/ydotool)
- [Desktop Portal specification](https://flatpak.github.io/xdg-desktop-portal/)

## 🎯 Summary

After following this guide, you should have:

- ✅ All necessary GUI automation tools installed
- ✅ Support for both X11 and Wayland environments
- ✅ Virtual display capabilities for headless operation
- ✅ Desktop portal integration for cross-desktop compatibility
- ✅ Python dependencies for the GUI Control Layer
- ✅ Verification that everything works correctly

The GUI Control Layer will automatically detect available tools and adapt its capabilities accordingly.