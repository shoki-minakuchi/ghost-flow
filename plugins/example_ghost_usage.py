# Example: Using ghost_cursor inside this repository
import sys
from pathlib import Path

# Ensure project root & plugins are on sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from plugins.ghost_cursor import GhostCursor
except ImportError:
    from ghost_cursor import GhostCursor

def main():
    # Initialize zero-focus humanized cursor
    cursor = GhostCursor(mock_mode=True)
    print("Moving cursor along human Bezier curve...")
    traj = cursor.move_to(500, 300, duration_sec=0.3)
    print(f"Movement generated {len(traj)} smooth trajectory points.")

    # Perform zero-focus click
    cursor.click()
    print("Zero-focus click simulated successfully.")

if __name__ == "__main__":
    main()
