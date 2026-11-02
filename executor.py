#!/usr/bin/env python3
"""
gwperintahin — Macro Executor Engine
Runtime engine that loads and executes macro .json files.

Usage:
    python executor.py --macro macros/example.json --log logs/run.log
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pyautogui
import pygetwindow as gw
from PIL import Image, ImageGrab

# ── Safety ──────────────────────────────────────────────────────────────
pyautogui.FAILSAFE = True      # move mouse to top-left corner to abort
pyautogui.PAUSE = 0.05         # small delay after each action

# ── Logging ─────────────────────────────────────────────────────────────
logger = logging.getLogger("executor")
# Prevent handler accumulation on repeated instantiations
if not logger.handlers:
    logger.setLevel(logging.INFO)
    _fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _ch = logging.StreamHandler()
    _ch.setFormatter(_fmt)
    logger.addHandler(_ch)


# ═════════════════════════════════════════════════════════════════════════
#  Macro Executor
# ═════════════════════════════════════════════════════════════════════════

class MacroExecutor:
    """Loads a macro .json and runs its steps sequentially."""

    def __init__(self, macro_path: str, log_path: str | None = None):
        self.macro_path = Path(macro_path).resolve()
        # Walk up from macro file to find project root (where executor.py lives)
        self.base_dir = self._find_base_dir(self.macro_path)
        self.log_path = log_path
        self.steps: list[dict] = []
        self.name = ""
        self.description = ""
        self.version = "1.0"
        self.current_step_index = 0
        self.variables: dict = {}          # for loop counters & condition values
        self._aborted = False

        self._setup_file_logging()
        self._load_macro()

    @staticmethod
    def _find_base_dir(macro_path: Path) -> Path:
        """Walk up from macro file to find project root.
        
        Priority:
        1. Parent of `macros/` folder (standard layout)
        2. Directory containing `executor.py`
        3. Fall back to macro's grandparent
        """
        # Check if we're in standard layout: .../macros/file.json
        if macro_path.parent.name == "macros":
            return macro_path.parent.parent
        # Check if we're in a subfolder of macros
        for parent in macro_path.parents:
            if parent.name == "macros":
                return parent.parent
            # Also check for sentinel files
            if (parent / "executor.py").exists() or (parent / "gwperintahin.py").exists():
                return parent
        # Fallback
        return macro_path.parent.parent

    # ── Helpers ─────────────────────────────────────────────────────────

    def _setup_file_logging(self):
        """Add file handler only (console handler is set up at module level)."""
        if self.log_path:
            _fmt = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            fh = logging.FileHandler(self.log_path, encoding="utf-8")
            fh.setFormatter(_fmt)
            logger.addHandler(fh)

    def _load_macro(self):
        if not self.macro_path.exists():
            logger.error(f"Macro file not found: {self.macro_path}")
            sys.exit(1)

        with open(self.macro_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.name = data.get("name", "unnamed")
        self.description = data.get("description", "")
        self.version = data.get("version", "1.0")
        self.steps = data.get("steps", [])

        logger.info(f"Loaded macro: {self.name} (v{self.version}) — {len(self.steps)} steps")

    # ── Main loop ───────────────────────────────────────────────────────

    def run(self):
        logger.info(f"{'='*50}")
        logger.info(f"Starting macro: {self.name}")
        logger.info(f"{'='*50}")

        self.current_step_index = 0
        while self.current_step_index < len(self.steps) and not self._aborted:
            step = self.steps[self.current_step_index]
            action = step.get("action", "")
            step_id = step.get("id", self.current_step_index + 1)

            try:
                logger.info(f"[Step {step_id}] {action}")
                self._execute_step(step)
                self.current_step_index += 1
            except SystemExit:
                raise
            except Exception as e:
                logger.error(f"Error in step {step_id} ({action}): {e}")
                on_error = step.get("on_error", "abort")
                if on_error == "skip":
                    self.current_step_index += 1
                elif on_error == "retry":
                    logger.info(f"Retrying step {step_id}…")
                    continue
                else:  # abort
                    logger.error("Aborting macro due to error.")
                    break

        logger.info(f"{'='*50}")
        logger.info(f"Macro finished: {self.name}")
        logger.info(f"{'='*50}")

    def _execute_step(self, step: dict):
        action = step.get("action", "")
        handler = getattr(self, f"_action_{action}", None)
        if handler is None:
            logger.warning(f"Unknown action: {action} — skipping")
            return
        handler(step)

    # ═════════════════════════════════════════════════════════════════════
    #  Screen / Image Helpers
    # ═════════════════════════════════════════════════════════════════════

    @staticmethod
    def _grab_screen(region=None):
        """Return a PIL Image of the screen (or region)."""
        return ImageGrab.grab(bbox=region)

    def _resolve_path(self, path_str: str) -> Path:
        p = Path(path_str)
        if not p.is_absolute():
            p = self.base_dir / p
        return p.resolve()

    # ── Image matching ──────────────────────────────────────────────────

    def _find_image(self, target: str, confidence: float = 0.8,
                    region=None) -> tuple[int, int] | None:
        """Template-matching via PIL + NumPy NCC; returns (center_x, center_y) or None."""
        fp = self._resolve_path(target)
        if not fp.exists():
            logger.warning(f"Template not found: {fp}")
            return None

        try:
            template_rgb = np.array(Image.open(str(fp)).convert('RGB'), dtype=np.float32)
        except Exception:
            logger.warning(f"Cannot decode image: {fp}")
            return None

        t_h, t_w = template_rgb.shape[:2]

        screen_rgb = np.array(ImageGrab.grab(bbox=region).convert('RGB'), dtype=np.float32)
        s_h, s_w = screen_rgb.shape[:2]

        if s_h < t_h or s_w < t_w:
            logger.warning("Screen smaller than template — skipping match")
            return None

        # Grayscale for faster computation
        template = np.mean(template_rgb, axis=2)
        screen = np.mean(screen_rgb, axis=2)

        # Normalise template to zero mean, unit variance
        t_mean = np.mean(template)
        t_std = max(np.std(template), 1.0)
        t_norm = (template - t_mean) / t_std

        best_val = -1.0
        best_x = best_y = 0

        # Adaptive stride — coarser for large templates, finer for small ones
        stride = max(1, min(t_h, t_w) // 6)

        # ── Coarse pass ──────────────────────────────────────────────
        for y in range(0, s_h - t_h + 1, stride):
            for x in range(0, s_w - t_w + 1, stride):
                patch = screen[y:y + t_h, x:x + t_w]
                p_mean = np.mean(patch)
                p_std = max(np.std(patch), 1.0)
                p_norm = (patch - p_mean) / p_std
                corr = float(np.mean(t_norm * p_norm))
                if corr > best_val:
                    best_val = corr
                    best_x, best_y = x, y

        # ── Fine pass around best match ──────────────────────────────
        if stride > 1:
            x_start = max(0, best_x - stride + 1)
            x_end = min(s_w - t_w, best_x + stride)
            y_start = max(0, best_y - stride + 1)
            y_end = min(s_h - t_h, best_y + stride)

            for y in range(y_start, y_end + 1):
                for x in range(x_start, x_end + 1):
                    patch = screen[y:y + t_h, x:x + t_w]
                    p_mean = np.mean(patch)
                    p_std = max(np.std(patch), 1.0)
                    p_norm = (patch - p_mean) / p_std
                    corr = float(np.mean(t_norm * p_norm))
                    if corr > best_val:
                        best_val = corr
                        best_x, best_y = x, y

        logger.info(f"  → match confidence: {best_val:.4f} (threshold: {confidence})")

        if best_val >= confidence:
            cx = best_x + t_w // 2
            cy = best_y + t_h // 2
            if region:
                cx += region[0]
                cy += region[1]
            return (cx, cy)
        return None

    # ── Color detection ─────────────────────────────────────────────────

    def _find_color(self, color: str, region=None,
                    tolerance: int = 20) -> tuple[int, int] | None:
        """Scan a region for a pixel matching the hex color (± tolerance)."""
        color = color.lstrip("#")
        target = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))

        img = self._grab_screen(region)
        w, h = img.size
        pixels = img.load()

        # Optimisation: step every 3 pixels for speed
        step = 3
        for y in range(0, h, step):
            for x in range(0, w, step):
                px = pixels[x, y]
                if all(abs(px[i] - target[i]) <= tolerance for i in range(3)):
                    ax = x + (region[0] if region else 0)
                    ay = y + (region[1] if region else 0)
                    return (ax, ay)
        return None

    # ── Fallback chain ──────────────────────────────────────────────────

    def _image_color_coord(self, step: dict) -> tuple[int, int] | None:
        """Try image → color → coord fallback, return coords or None."""
        # 1) Image match
        target = step.get("target")
        if target:
            res = self._find_image(target, step.get("confidence", 0.8),
                                   step.get("region"))
            if res:
                return res

        # 2) Color detection
        fb_color = step.get("fallback_color") or step.get("color")
        if fb_color:
            res = self._find_color(
                fb_color, step.get("region"), step.get("tolerance", 20)
            )
            if res:
                return res

        # 3) Hard-coded coordinate
        fb_coord = step.get("fallback_coord")
        if fb_coord and len(fb_coord) == 2:
            return (fb_coord[0], fb_coord[1])

        return None

    # ═════════════════════════════════════════════════════════════════════
    #  Action Handlers
    # ═════════════════════════════════════════════════════════════════════

    # ── wait_for_image ──────────────────────────────────────────────────

    def _action_wait_for_image(self, step: dict):
        target = step["target"]
        timeout = step.get("timeout", 30)
        confidence = step.get("confidence", 0.85)
        region = step.get("region")
        on_timeout = step.get("on_timeout", "exit")

        logger.info(f"  Waiting for image: {target} (timeout: {timeout}s)")
        start = time.time()
        while time.time() - start < timeout:
            res = self._find_image(target, confidence, region)
            if res:
                logger.info(f"  → Image found at {res}")
                return
            time.sleep(0.3)

        logger.warning(f"  ✗ Image NOT found within {timeout}s: {target}")
        if on_timeout == "exit":
            self._aborted = True
        elif on_timeout == "fallback_coord":
            fb_coord = step.get("fallback_coord")
            if fb_coord and len(fb_coord) == 2:
                logger.info(f"  Using fallback coordinate: {fb_coord}")
                pyautogui.click(*fb_coord)

    # ── wait_for_color ──────────────────────────────────────────────────

    def _action_wait_for_color(self, step: dict):
        color = step["color"]
        timeout = step.get("timeout", 10)
        region = step.get("region")
        tolerance = step.get("tolerance", 20)
        on_timeout = step.get("on_timeout", "exit")

        logger.info(f"  Waiting for colour: {color} (timeout: {timeout}s)")
        start = time.time()
        while time.time() - start < timeout:
            res = self._find_color(color, region, tolerance)
            if res:
                logger.info(f"  → Colour found at {res}")
                return
            time.sleep(0.2)

        logger.warning(f"  ✗ Colour NOT found within {timeout}s: {color}")
        if on_timeout == "exit":
            self._aborted = True
        elif on_timeout == "fallback_coord":
            fb_coord = step.get("fallback_coord")
            if fb_coord and len(fb_coord) == 2:
                logger.info(f"  Using fallback coordinate: {fb_coord}")
                pyautogui.click(*fb_coord)

    # ── click_image ─────────────────────────────────────────────────────

    def _action_click_image(self, step: dict):
        pos = self._image_color_coord(step)
        if pos:
            logger.info(f"  Clicking at {pos}")
            pyautogui.click(*pos)
        else:
            logger.warning(f"  Cannot click — no target found: {step.get('target')}")

    # ── click_color ─────────────────────────────────────────────────────

    def _action_click_color(self, step: dict):
        color = step.get("color", "")
        region = step.get("region")
        tolerance = step.get("tolerance", 20)

        pos = self._find_color(color, region, tolerance)
        if pos:
            logger.info(f"  Clicking colour at {pos}")
            pyautogui.click(*pos)
        else:
            fb = step.get("fallback_coord")
            if fb:
                logger.info(f"  Colour not found, using fallback coord {fb}")
                pyautogui.click(*fb)
            else:
                logger.warning(f"  Colour not found: {color}")

    # ── click_coord ─────────────────────────────────────────────────────

    def _action_click_coord(self, step: dict):
        x = step.get("x", 0)
        y = step.get("y", 0)
        button = step.get("button", "left")
        logger.info(f"  Click ({x}, {y}) [{button}]")
        pyautogui.click(x, y, button=button)

    # ── right_click_coord ───────────────────────────────────────────────

    def _action_right_click_coord(self, step: dict):
        x = step.get("x", 0)
        y = step.get("y", 0)
        logger.info(f"  Right-click ({x}, {y})")
        pyautogui.rightClick(x, y)

    # ── double_click ────────────────────────────────────────────────────

    def _action_double_click(self, step: dict):
        x, y = step.get("x"), step.get("y")

        # Try image target first
        target = step.get("target")
        if target:
            pos = self._find_image(target, step.get("confidence", 0.8))
            if pos:
                x, y = pos

        if x is not None and y is not None:
            logger.info(f"  Double-click ({x}, {y})")
            pyautogui.doubleClick(x, y)
        else:
            logger.warning("  No coordinate or target for double-click")

    # ── type_text ───────────────────────────────────────────────────────

    def _action_type_text(self, step: dict):
        text = step.get("text", "")
        delay = step.get("delay_between_keys", 0.02)
        preview = text[:60] + "…" if len(text) > 60 else text
        logger.info(f"  Type: \"{preview}\"")
        pyautogui.write(text, interval=delay)

    # ── press_key ───────────────────────────────────────────────────────

    def _action_press_key(self, step: dict):
        key = step.get("key", "")
        logger.info(f"  Press: {key}")

        if "+" in key:
            parts = key.lower().split("+")
            mods, main = parts[:-1], parts[-1]
            for m in mods:
                pyautogui.keyDown(m.strip())
            pyautogui.press(main.strip())
            for m in reversed(mods):
                pyautogui.keyUp(m.strip())
        else:
            pyautogui.press(key.lower())

    # ── scroll ──────────────────────────────────────────────────────────

    def _action_scroll(self, step: dict):
        direction = step.get("direction", "down")
        amount = step.get("amount", 3)
        x, y = step.get("x"), step.get("y")

        if x is not None and y is not None:
            pyautogui.moveTo(x, y)

        clicks = amount if direction == "down" else -amount
        pyautogui.scroll(clicks)
        logger.info(f"  Scroll {direction} ×{amount}")

    # ── wait_seconds ────────────────────────────────────────────────────

    def _action_wait_seconds(self, step: dict):
        dur = step.get("duration", 1.0)
        logger.info(f"  Wait {dur}s")
        time.sleep(dur)

    # ── wait_for_window ─────────────────────────────────────────────────

    def _action_wait_for_window(self, step: dict):
        title = step.get("title", "")
        timeout = step.get("timeout", 30)
        logger.info(f"  Waiting for window: \"{title}\" (timeout: {timeout}s)")

        start = time.time()
        while time.time() - start < timeout:
            wins = gw.getWindowsWithText(title)
            if wins:
                logger.info(f"  → Window found: \"{wins[0].title}\"")
                return
            time.sleep(0.5)

        logger.warning(f"  ✗ Window NOT found: \"{title}\"")

    # ── focus_window ────────────────────────────────────────────────────

    def _action_focus_window(self, step: dict):
        title = step.get("title", "")
        logger.info(f"  Focus window: \"{title}\"")

        wins = gw.getWindowsWithText(title)
        if wins:
            try:
                wins[0].activate()
                time.sleep(0.3)
            except Exception as e:
                logger.warning(f"  Cannot activate window: {e}")
        else:
            logger.warning(f"  Window not found: \"{title}\"")

    # ── screenshot ──────────────────────────────────────────────────────

    def _action_screenshot(self, step: dict):
        save_path = step.get("save_path", "")
        region = step.get("region")

        if not save_path:
            ts = time.strftime("%Y%m%d_%H%M%S")
            save_path = self.base_dir / "logs" / f"screenshot_{ts}.png"
        else:
            save_path = self._resolve_path(save_path)

        self._grab_screen(region).save(str(save_path))
        logger.info(f"  Screenshot saved: {save_path}")

    # ── loop ────────────────────────────────────────────────────────────

    def _action_loop(self, step: dict):
        loop_steps = step.get("steps", [])
        count = step.get("count", 1)
        until = step.get("until")  # not implemented yet

        logger.info(f"  Loop {count}× ({len(loop_steps)} sub-steps)")
        for iteration in range(count):
            logger.info(f"    Iteration {iteration+1}/{count}")
            for s in loop_steps:
                self._execute_step(s)
                time.sleep(0.05)
            # Future: check until condition

    # ── if_else ─────────────────────────────────────────────────────────

    def _action_if_else(self, step: dict):
        condition = step.get("condition", {})
        then_steps = step.get("then_steps", [])
        else_steps = step.get("else_steps", [])

        if self._eval_condition(condition):
            logger.info("  Condition → TRUE (then)")
            for s in then_steps:
                self._execute_step(s)
        else:
            logger.info("  Condition → FALSE (else)")
            for s in else_steps:
                self._execute_step(s)

    def _eval_condition(self, cond: dict) -> bool:
        ctype = cond.get("type", "")
        if ctype == "image_exists":
            return self._find_image(
                cond.get("target", ""),
                cond.get("confidence", 0.8),
                cond.get("region"),
            ) is not None
        elif ctype == "color_exists":
            return self._find_color(
                cond.get("color", ""),
                cond.get("region"),
                cond.get("tolerance", 20),
            ) is not None
        elif ctype == "window_exists":
            return bool(gw.getWindowsWithText(cond.get("title", "")))
        elif ctype == "variable":
            var = self.variables.get(cond.get("variable", ""), 0)
            op = cond.get("operator", "==")
            val = cond.get("value", 0)
            if op == "==":  return var == val
            elif op == "!=": return var != val
            elif op == ">":  return var > val
            elif op == "<":  return var < val
            elif op == ">=": return var >= val
            elif op == "<=": return var <= val
        return False

    # ── exit ────────────────────────────────────────────────────────────

    def _action_exit(self, step: dict):
        logger.info("  Exit action — stopping macro")
        self._aborted = True

    # ── set_variable ────────────────────────────────────────────────────

    def _action_set_variable(self, step: dict):
        name = step.get("name", "")
        value = step.get("value", 0)
        self.variables[name] = value
        logger.info(f"  Variable {name} = {value}")


# ═════════════════════════════════════════════════════════════════════════
#  CLI Entry Point
# ═════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="gwperintahin — Macro Executor Engine"
    )
    parser.add_argument("--macro", required=True,
                        help="Path to macro .json file")
    parser.add_argument("--log", help="Path to log file")
    args = parser.parse_args()

    executor = MacroExecutor(args.macro, args.log)
    executor.run()


if __name__ == "__main__":
    main()
