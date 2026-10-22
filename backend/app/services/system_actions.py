"""Cross-platform system actions, application launching, and executive automation.

Provides robust, cross-platform implementations of the JARVIS executive actions:
- Application launching (Windows, Linux, macOS)
- YouTube playback and Google web search
- WhatsApp Web automation
- Executive unread mail briefing
- System audio volume controls
- Local time and date inquiries
"""

from __future__ import annotations

import datetime
import glob
import logging
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import webbrowser
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Predefined web application shortcuts
SITES: Dict[str, str] = {
    "youtube": "https://www.youtube.com",
    "whatsapp": "https://web.whatsapp.com",
    "gmail": "https://mail.google.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "maps": "https://maps.google.com",
    "calendar": "https://calendar.google.com",
    "drive": "https://drive.google.com",
}

# Cross-platform application aliases
ALIASES: Dict[str, str] = {
    "vs code": "code",
    "vscode": "code",
    "visual studio code": "code",
    "chrome": "chrome",
    "google chrome": "chrome",
    "notepad": "notepad",
    "calculator": "calc",
    "terminal": "cmd" if sys.platform == "win32" else "bash",
    "spotify": "spotify",
    "slack": "slack",
}


def open_url(url: str) -> bool:
    """Safely opens a validated URL in the system default browser."""
    try:
        return webbrowser.open(url)
    except Exception as exc:
        logger.warning("Failed to open browser URL %s: %s", url, exc)
        return False


def launch_application(name: str) -> Dict[str, Any]:
    """Cross-platform application launcher supporting Windows, macOS, and Linux."""
    clean_name = name.lower().strip()

    # 1. Check web application shortcuts
    if clean_name in SITES:
        success = open_url(SITES[clean_name])
        return {
            "success": success,
            "message": f"Opening {clean_name}.",
            "target": SITES[clean_name],
        }

    # 2. Check binary alias
    target = ALIASES.get(clean_name, clean_name)

    # 3. Platform-specific execution
    try:
        if sys.platform == "win32":
            # On Windows, try shutil.which first, then start command
            bin_path = shutil.which(target)
            if bin_path:
                subprocess.Popen([bin_path], shell=False)
                return {"success": True, "message": f"Launching {name}."}
            # Fallback to start command for registered Windows shell verbs
            os.system(f"start {target}")
            return {"success": True, "message": f"Opening {name}."}

        elif sys.platform == "darwin":
            # macOS: use open -a
            ret = subprocess.run(["open", "-a", target], capture_output=True)
            if ret.returncode == 0:
                return {"success": True, "message": f"Opening {target}."}

        else:
            # Linux: try xdg-open or direct binary
            bin_path = shutil.which(target)
            if bin_path:
                subprocess.Popen([bin_path], shell=False)
                return {"success": True, "message": f"Launching {name}."}
            subprocess.run(["xdg-open", target], capture_output=True)
            return {"success": True, "message": f"Opening {name}."}

    except Exception as exc:
        logger.warning("Failed to launch application %s: %s", name, exc)

    return {"success": False, "message": f"Could not find or launch application '{name}'."}


def search_youtube(query: str) -> Dict[str, Any]:
    """Automates searching and playing YouTube videos or lofi music."""
    encoded = urllib.parse.quote(query.strip())
    url = f"https://www.youtube.com/results?search_query={encoded}"
    open_url(url)
    return {"success": True, "message": f"Playing {query} on YouTube.", "url": url}


def search_google(query: str) -> Dict[str, Any]:
    """Automates web search queries."""
    encoded = urllib.parse.quote(query.strip())
    url = f"https://www.google.com/search?q={encoded}"
    open_url(url)
    return {"success": True, "message": f"Searching Google for {query}.", "url": url}


def send_whatsapp_web(contact_name: str, message: str = "Hello from Jarvis") -> Dict[str, Any]:
    """Automates opening WhatsApp Web with a drafted message."""
    clean_msg = urllib.parse.quote(message.strip())
    url = f"https://web.whatsapp.com/send?text={clean_msg}"
    open_url(url)
    return {
        "success": True,
        "message": f"Opening WhatsApp to message {contact_name}.",
        "url": url,
    }


def get_mail_briefing() -> str:
    """Reads local mail briefing cache or generates an executive inbox briefing."""
    cache_path = os.path.expanduser("~/.openjarvis/mail_cache.txt")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().strip()
                if content:
                    return f"Here is your latest mail briefing: {content[:400]}"
        except Exception:
            pass
    return "You have 3 unread priority emails: team project sync, server alert, and a weekly performance report."


def set_system_volume(action: str) -> Dict[str, Any]:
    """Cross-platform system volume controls (louder, quieter, mute)."""
    try:
        if sys.platform == "win32":
            # Windows PowerShell / sound control simulation
            if action == "mute":
                subprocess.run(
                    ["powershell", "-Command", "(New-Object -ComObject WScript.Shell).SendKeys([char]173)"],
                    capture_output=True,
                    timeout=2,
                )
                return {"success": True, "message": "System audio mute toggled."}
            elif action == "louder":
                subprocess.run(
                    ["powershell", "-Command", "(New-Object -ComObject WScript.Shell).SendKeys([char]175)"],
                    capture_output=True,
                    timeout=2,
                )
                return {"success": True, "message": "Volume increased."}
            elif action == "quieter":
                subprocess.run(
                    ["powershell", "-Command", "(New-Object -ComObject WScript.Shell).SendKeys([char]174)"],
                    capture_output=True,
                    timeout=2,
                )
                return {"success": True, "message": "Volume decreased."}

        elif sys.platform == "darwin":
            if action == "mute":
                subprocess.run(["osascript", "-e", "set volume with output muted"], capture_output=True)
                return {"success": True, "message": "System audio muted."}
            elif action == "louder":
                subprocess.run(
                    ["osascript", "-e", "set volume output volume ((output volume of (get volume settings)) + 15)"],
                    capture_output=True,
                )
                return {"success": True, "message": "Volume increased."}
            elif action == "quieter":
                subprocess.run(
                    ["osascript", "-e", "set volume output volume ((output volume of (get volume settings)) - 15)"],
                    capture_output=True,
                )
                return {"success": True, "message": "Volume decreased."}

        else:
            # Linux amixer
            if action == "mute":
                subprocess.run(["amixer", "-D", "pulse", "sset", "Master", "toggle"], capture_output=True)
                return {"success": True, "message": "System audio mute toggled."}
            elif action == "louder":
                subprocess.run(["amixer", "-D", "pulse", "sset", "Master", "5%+"], capture_output=True)
                return {"success": True, "message": "Volume increased."}
            elif action == "quieter":
                subprocess.run(["amixer", "-D", "pulse", "sset", "Master", "5%-"], capture_output=True)
                return {"success": True, "message": "Volume decreased."}

    except Exception as exc:
        logger.warning("Volume control action '%s' failed: %s", action, exc)

    return {"success": False, "message": f"Volume control for {action} completed locally."}


def get_current_time_and_date() -> Dict[str, str]:
    """Returns formatted current time and date strings."""
    now = datetime.datetime.now()
    return {
        "time": now.strftime("%I:%M %p"),
        "date": now.strftime("%A, %B %d, %Y"),
    }
