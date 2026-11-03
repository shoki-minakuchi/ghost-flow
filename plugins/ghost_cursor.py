"""
ghost_cursor_standalone.py - Zero-Dependency, Drop-in Human Cursor & Win32 Input Plugin.
Extracted from ghost-cursor-plugin. Pure Python standard library only (0 external packages).
"""

from dataclasses import dataclass
import ctypes
from ctypes import wintypes
import math
import platform
import random
import time
from typing import Callable, List, Optional, Tuple, Union

IS_WINDOWS = platform.system() == "Windows"

# Win32 Constants
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_CHAR = 0x0102
MK_LBUTTON = 0x0001
MK_RBUTTON = 0x0002


def makelparam(x: int, y: int) -> int:
    return ((int(y) & 0xFFFF) << 16) | (int(x) & 0xFFFF)


@dataclass
class TrajectoryPoint:
    x: float
    y: float
    timestamp_sec: float
    speed_px_per_sec: float = 0.0


class BezierCurve:
    """Generates human-like mouse trajectories using cubic Bezier curves with Fitts's law scaling."""

    def __init__(self, base_speed_px_per_sec: float = 1200.0, jitter_intensity: float = 0.5):
        self.base_speed = base_speed_px_per_sec
        self.jitter_intensity = jitter_intensity

    def calculate_duration(self, start: Tuple[float, float], end: Tuple[float, float]) -> float:
        dist = math.hypot(end[0] - start[0], end[1] - start[1])
        if dist < 1.0:
            return 0.05
        return max(0.12, min(0.08 * math.log2(1.0 + (dist / 15.0)), 1.2))

    def generate_trajectory(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        duration_sec: Optional[float] = None,
        points_per_sec: int = 120,
    ) -> List[TrajectoryPoint]:
        x0, y0 = float(start[0]), float(start[1])
        x3, y3 = float(end[0]), float(end[1])
        dist = math.hypot(x3 - x0, y3 - y0)

        if dist < 0.5:
            now = time.time()
            return [TrajectoryPoint(x=x3, y=y3, timestamp_sec=now, speed_px_per_sec=0.0)]

        dur = duration_sec if duration_sec is not None else self.calculate_duration(start, end)
        num_points = max(8, int(dur * points_per_sec))

        dx, dy = x3 - x0, y3 - y0
        perp_x = -dy / dist if dist > 0 else 0.0
        perp_y = dx / dist if dist > 0 else 0.0

        dev1 = random.uniform(-0.25, 0.25) * dist
        dev2 = random.uniform(-0.15, 0.15) * dist
        x1 = x0 + dx * 0.3 + perp_x * dev1
        y1 = y0 + dy * 0.3 + perp_y * dev1
        x2 = x0 + dx * 0.7 + perp_y * dev2
        y2 = y0 + dy * 0.7 + perp_x * dev2

        raw_points = []
        for i in range(num_points):
            t = i / (num_points - 1) if num_points > 1 else 1.0
            u = 1.0 - t
            px = (u**3)*x0 + 3*(u**2)*t*x1 + 3*u*(t**2)*x2 + (t**3)*x3
            py = (u**3)*y0 + 3*(u**2)*t*y1 + 3*u*(t**2)*y2 + (t**3)*y3
            raw_points.append((px, py))

        result = []
        start_time = time.time()
        prev = raw_points[0]
        for i, (cx, cy) in enumerate(raw_points):
            t_ratio = i / (len(raw_points) - 1) if len(raw_points) > 1 else 1.0
            eased_t = 3 * (t_ratio**2) - 2 * (t_ratio**3)
            pt_time = start_time + (eased_t * dur)

            if 0 < i < len(raw_points) - 1:
                cx += self.jitter_intensity * random.uniform(-0.8, 0.8)
                cy += self.jitter_intensity * random.uniform(-0.8, 0.8)

            step_dist = math.hypot(cx - prev[0], cy - prev[1])
            step_time = max(0.0001, pt_time - (result[-1].timestamp_sec if result else start_time))
            result.append(TrajectoryPoint(x=cx, y=cy, timestamp_sec=pt_time, speed_px_per_sec=step_dist/step_time))
            prev = (cx, cy)

        return result


class ZeroFocusWin32Engine:
    """Sends background mouse and keyboard events directly without focus theft."""

    def __init__(self, mock_mode: bool = False):
        self.mock_mode = mock_mode or not IS_WINDOWS
        self.user32 = ctypes.windll.user32 if not self.mock_mode else None
        self._sent_messages = []

    def is_valid_window(self, hwnd: int) -> bool:
        return (hwnd > 0) if self.mock_mode else bool(self.user32.IsWindow(hwnd))

    def find_window_by_title(self, title_substr: str) -> Optional[int]:
        if self.mock_mode:
            return 1001 if title_substr else None
        found = None
        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _cb(hwnd, _):
            nonlocal found
            if self.user32.IsWindowVisible(hwnd):
                length = self.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    self.user32.GetWindowTextW(hwnd, buf, length + 1)
                    if title_substr.lower() in buf.value.lower():
                        found = hwnd
                        return False
            return True
        self.user32.EnumWindows(WNDENUMPROC(_cb), 0)
        return found

    def post_mouse_move(self, hwnd: int, x: int, y: int) -> bool:
        lparam = makelparam(x, y)
        if self.mock_mode:
            self._sent_messages.append((hwnd, WM_MOUSEMOVE, 0, lparam))
            return True
        return bool(self.user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lparam))

    def post_click(self, hwnd: int, x: int, y: int, button: str = "left", double: bool = False) -> bool:
        lparam = makelparam(x, y)
        down_msg = WM_LBUTTONDOWN if button == "left" else WM_RBUTTONDOWN
        up_msg = WM_LBUTTONUP if button == "left" else WM_RBUTTONUP
        dbl_msg = WM_LBUTTONDBLCLK if button == "left" else WM_RBUTTONDBLCLK
        wparam = MK_LBUTTON if button == "left" else MK_RBUTTON

        if self.mock_mode:
            self._sent_messages.extend([(hwnd, down_msg, wparam, lparam), (hwnd, up_msg, 0, lparam)])
            return True

        if double:
            self.user32.PostMessageW(hwnd, down_msg, wparam, lparam)
            self.user32.PostMessageW(hwnd, up_msg, 0, lparam)
            time.sleep(0.02)
            self.user32.PostMessageW(hwnd, dbl_msg, wparam, lparam)
            return bool(self.user32.PostMessageW(hwnd, up_msg, 0, lparam))

        self.user32.PostMessageW(hwnd, down_msg, wparam, lparam)
        time.sleep(0.02)
        return bool(self.user32.PostMessageW(hwnd, up_msg, 0, lparam))

    def post_char(self, hwnd: int, char: str) -> bool:
        if self.mock_mode:
            self._sent_messages.append((hwnd, WM_CHAR, ord(char), 1))
            return True
        return bool(self.user32.PostMessageW(hwnd, WM_CHAR, ord(char), 1))


class GhostCursor:
    """Universal drop-in humanized cursor controller with zero external dependencies."""

    def __init__(
        self,
        target_hwnd: Optional[int] = None,
        window_title: Optional[str] = None,
        mock_mode: bool = False,
    ):
        self.win32 = ZeroFocusWin32Engine(mock_mode=mock_mode)
        self.bezier = BezierCurve()
        self.hwnd = target_hwnd
        if self.hwnd is None and window_title:
            self.hwnd = self.win32.find_window_by_title(window_title)
        self.current_x = 0.0
        self.current_y = 0.0

    def move_to(self, x: float, y: float, duration_sec: Optional[float] = None) -> List[TrajectoryPoint]:
        traj = self.bezier.generate_trajectory((self.current_x, self.current_y), (float(x), float(y)), duration_sec)
        for pt in traj:
            if self.hwnd and self.win32.is_valid_window(self.hwnd):
                self.win32.post_mouse_move(self.hwnd, int(pt.x), int(pt.y))
        self.current_x, self.current_y = float(x), float(y)
        return traj

    def click(self, x: Optional[float] = None, y: Optional[float] = None, button: str = "left", double: bool = False) -> bool:
        if x is not None and y is not None:
            self.move_to(x, y)
        time.sleep(random.uniform(0.04, 0.08))
        if self.hwnd:
            return self.win32.post_click(self.hwnd, int(self.current_x), int(self.current_y), button=button, double=double)
        return True

    def type_text(self, text: str, cpm: int = 350) -> None:
        base_interval = 60.0 / max(10, cpm)
        for ch in text:
            if self.hwnd:
                self.win32.post_char(self.hwnd, ch)
            time.sleep(max(0.015, base_interval + random.gauss(0, base_interval * 0.25)))
