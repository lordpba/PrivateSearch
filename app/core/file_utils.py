import os
import subprocess
import platform
import logging

logger = logging.getLogger(__name__)

def open_file(filepath: str):
    """
    Open a file using the system's default application.
    Works across Windows, macOS, and Linux.
    """
    if not os.path.exists(filepath):
        logger.error(f"File not found: {filepath}")
        return False

    try:
        if platform.system() == "Windows":
            os.startfile(filepath)
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(["open", filepath], check=True)
        else:  # Linux
            subprocess.run(["xdg-open", filepath], check=True)
        return True
    except Exception as e:
        logger.error(f"Error opening file {filepath}: {e}")
        return False

def get_file_stats(filepath: str):
    """Return basic file information."""
    if not os.path.exists(filepath):
        return None
    
    stat = os.stat(filepath)
    return {
        "size": stat.st_size,
        "modified": stat.st_mtime,
        "extension": os.path.splitext(filepath)[1].lower()
    }
