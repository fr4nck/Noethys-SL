from __future__ import annotations

import ctypes
import datetime as dt
import ipaddress
import json
import os
import re
import socket
import subprocess
import time
import traceback
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

import psutil
from PIL import ImageGrab
from pywinauto import Desktop, keyboard


class StepStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    TIMEOUT = "TIMEOUT"
    CRASH = "CRASH"


class DriverError(RuntimeError):
    pass


class DriverTimeout(DriverError):
    pass


class UnexpectedProcessExit(DriverError):
    pass


class UnsafeAction(DriverError):
    pass


@dataclass
class StepResult:
    scenario: str
    step: str
    action: str
    expected: str
    status: str
    actual: str
    duration_s: float
    timestamp: str
    active_window_title: str
    process_state: dict[str, Any]
    screenshot: Optional[str] = None
    technical_trace: Optional[str] = None
    event_log: Optional[list[dict[str, Any]]] = None


class WindowsEventCorrelator:
    """Best-effort Application-log correlation; absence of a match is not proof."""

    @staticmethod
    def _local_naive(value: dt.datetime) -> dt.datetime:
        if value.tzinfo is None:
            return value
        return value.astimezone().replace(tzinfo=None)

    def correlate(self, start: dt.datetime, end: dt.datetime) -> list[dict[str, Any]]:
        if os.name != "nt":
            return []
        try:
            import win32evtlog
        except Exception:
            return []
        start = self._local_naive(start) - dt.timedelta(seconds=5)
        end = self._local_naive(end) + dt.timedelta(seconds=5)
        handle = None
        found: list[dict[str, Any]] = []
        try:
            handle = win32evtlog.OpenEventLog(None, "Application")
            flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
            inspected = 0
            while inspected < 2000:
                records = win32evtlog.ReadEventLog(handle, flags, 0)
                if not records:
                    break
                for record in records:
                    inspected += 1
                    generated = self._local_naive(record.TimeGenerated)
                    if generated < start:
                        return found
                    if generated > end:
                        continue
                    event_id = record.EventID & 0xFFFF
                    strings = [str(x) for x in (record.StringInserts or [])]
                    text = " | ".join(strings).lower()
                    app_error = event_id == 1000 or record.SourceName == "Application Error"
                    noethys = "noethys.exe" in text
                    access_violation = "0xc0000005" in text
                    if app_error and (noethys or access_violation):
                        found.append({
                            "event_id": event_id,
                            "source": record.SourceName,
                            "time_generated": generated.isoformat(),
                            "mentions_noethys": noethys,
                            "mentions_0xc0000005": access_violation,
                            "strings": strings,
                        })
        except Exception:
            pass
        finally:
            if handle is not None:
                try:
                    win32evtlog.CloseEventLog(handle)
                except Exception:
                    pass
        return found


class NoethysUiDriver:
    MAIN_TITLE_RE = re.compile(r"^Noethys(?:\s+v.*)?$|^Noethys\s+v.*", re.I)
    RECIPE_MARKER = "NOETHYS_UI_RECIPE_PROFILE=1"
    FORBIDDEN = ("supprim", "effac", "envoy", "expedi", "factur", "publ")

    def __init__(
        self,
        exe_path: Path,
        profile_root: Path,
        expected_db_host: str,
        expected_db_name: str,
        artifact_root: Path,
        default_timeout: float = 20.0,
        poll_interval: float = 0.10,
    ) -> None:
        self.exe_path = exe_path.resolve()
        self.profile_root = profile_root.resolve()
        self.expected_db_host = expected_db_host.strip()
        self.expected_db_name = expected_db_name.strip()
        self.artifact_root = artifact_root.resolve()
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self.default_timeout = float(default_timeout)
        self.poll_interval = max(0.05, float(poll_interval))
        self.proc: Optional[subprocess.Popen[Any]] = None
        self.ps_proc: Optional[psutil.Process] = None
        self.pid: Optional[int] = None
        self.main_hwnd: Optional[int] = None
        self.events = WindowsEventCorrelator()

    # Safety -----------------------------------------------------------------
    def validate_environment(self) -> dict[str, Any]:
        if os.name != "nt":
            raise DriverError("Windows is required")
        if not self.exe_path.is_file() or self.exe_path.name.lower() != "noethys.exe":
            raise DriverError(f"Invalid Noethys executable: {self.exe_path}")
        marker = self.profile_root / "NOETHYS_UI_RECIPE_PROFILE.txt"
        if not marker.is_file() or marker.read_text(encoding="utf-8-sig").strip() != self.RECIPE_MARKER:
            raise DriverError("Recipe profile marker missing or invalid")
        config_path = self.profile_root / "Roaming" / "noethys" / "Config.json"
        if not config_path.is_file():
            raise DriverError(f"Recipe Config.json missing: {config_path}")
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        info = self._parse_network_db(str(config.get("nomFichier") or ""))
        if info["host"].casefold() != self.expected_db_host.casefold():
            raise DriverError(f"DB host mismatch: {info['host']!r}")
        if info["database"].casefold() != self.expected_db_name.casefold():
            raise DriverError(f"DB name mismatch: {info['database']!r}")
        if not self._is_loopback(info["host"]):
            raise DriverError("Refusing a non-loopback DB host; Docker recipe DB must be local")
        if config.get("assistant_demarrage") is not True:
            raise DriverError("assistant_demarrage must be true in the isolated recipe profile")
        return info

    @staticmethod
    def _parse_network_db(value: str) -> dict[str, Any]:
        if "[RESEAU]" not in value:
            raise DriverError("Recipe profile must point to a MySQL/network database")
        prefix, database = value.split("[RESEAU]", 1)
        parts = prefix.split(";")
        if len(parts) != 4:
            raise DriverError("Unexpected Noethys network DB descriptor")
        port, host, user, _password = parts
        return {"port": int(port), "host": host.strip(), "user": user, "database": database.strip()}

    @staticmethod
    def _is_loopback(host: str) -> bool:
        candidate = host.strip().strip("[]")
        if candidate.casefold() == "localhost":
            return True
        try:
            return ipaddress.ip_address(candidate).is_loopback
        except ValueError:
            pass
        try:
            addresses = {x[4][0].split("%", 1)[0] for x in socket.getaddrinfo(candidate, None)}
            return bool(addresses) and all(ipaddress.ip_address(x).is_loopback for x in addresses)
        except Exception:
            return False

    def _safe_label(self, label: str) -> None:
        folded = label.casefold()
        if any(token in folded for token in self.FORBIDDEN):
            raise UnsafeAction(f"Refusing potentially destructive action: {label!r}")

    # Launch/process ----------------------------------------------------------
    def launch(self) -> int:
        self.validate_environment()
        roaming = self.profile_root / "Roaming"
        local = self.profile_root / "Local"
        roaming.mkdir(parents=True, exist_ok=True)
        local.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["APPDATA"] = str(roaming)
        env["LOCALAPPDATA"] = str(local)
        self.proc = subprocess.Popen(
            [str(self.exe_path)],
            cwd=str(self.exe_path.parent),
            env=env,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        self.pid = self.proc.pid
        self.ps_proc = psutil.Process(self.pid)
        self.wait_for(self.is_process_alive, 3.0, "Noethys process to remain alive")
        return self.pid

    def is_process_alive(self) -> bool:
        if self.proc is None or self.pid is None or self.proc.poll() is not None:
            return False
        try:
            return psutil.pid_exists(self.pid) and self.ps_proc is not None and self.ps_proc.is_running()
        except psutil.Error:
            return False

    def ensure_alive(self) -> None:
        if not self.is_process_alive():
            code = self.proc.poll() if self.proc else None
            raise UnexpectedProcessExit(f"Noethys.exe exited unexpectedly (exit_code={code})")

    def process_state(self) -> dict[str, Any]:
        state: dict[str, Any] = {
            "pid": self.pid,
            "alive": self.is_process_alive(),
            "exit_code": self.proc.poll() if self.proc else None,
            "hung": None,
            "responsive": None,
        }
        if state["alive"] and self.main_hwnd:
            state["hung"] = self._is_hung(self.main_hwnd)
            state["responsive"] = not state["hung"] and self._wm_null(self.main_hwnd, 1000)
        return state

    # Waits -------------------------------------------------------------------
    def wait_for(self, predicate: Callable[[], bool], timeout: float, description: str) -> None:
        deadline = time.monotonic() + timeout
        last: Optional[Exception] = None
        while time.monotonic() < deadline:
            self.ensure_alive()
            try:
                if predicate():
                    return
            except UnexpectedProcessExit:
                raise
            except Exception as exc:
                last = exc
            time.sleep(min(self.poll_interval, max(0.0, deadline - time.monotonic())))
        extra = f"; last_error={last}" if last else ""
        raise DriverTimeout(f"Timeout waiting for {description}{extra}")

    def wait_value(self, supplier: Callable[[], Optional[Any]], timeout: float, description: str) -> Any:
        value: list[Any] = []
        def ready() -> bool:
            candidate = supplier()
            if candidate is None:
                return False
            value.append(candidate)
            return True
        self.wait_for(ready, timeout, description)
        return value[0]

    def wait_main_window(self):
        def locate():
            for window in Desktop(backend="win32").windows(process=self.pid, visible_only=True):
                if self.MAIN_TITLE_RE.match(self._text(window)):
                    return window
            return None
        window = self.wait_value(locate, self.default_timeout, "main Noethys window")
        self.main_hwnd = int(window.handle)
        self.wait_responsive(self.main_hwnd)
        return window

    def wait_dialog(self, title: str, visible_only: bool = True):
        def locate():
            for window in Desktop(backend="win32").windows(process=self.pid, visible_only=visible_only):
                if self._text(window) == title:
                    return window
            return None
        return self.wait_value(locate, self.default_timeout, f"dialog {title!r}")

    def dialog_exists(self, title: str) -> bool:
        if not self.is_process_alive():
            return False
        return any(self._text(w) == title for w in Desktop(backend="win32").windows(process=self.pid, visible_only=True))

    def wait_responsive(self, hwnd: Optional[int] = None, timeout: float = 10.0) -> None:
        hwnd = hwnd or self.main_hwnd
        if not hwnd:
            raise DriverError("No HWND available for responsiveness check")
        self.wait_for(lambda: not self._is_hung(hwnd) and self._wm_null(hwnd, 750), timeout, "responsive window")

    @staticmethod
    def _is_hung(hwnd: int) -> bool:
        try:
            return bool(ctypes.windll.user32.IsHungAppWindow(int(hwnd)))
        except Exception:
            return False

    @staticmethod
    def _wm_null(hwnd: int, timeout_ms: int) -> bool:
        try:
            result = ctypes.c_size_t(0)
            return bool(ctypes.windll.user32.SendMessageTimeoutW(
                int(hwnd), 0, 0, 0, 0x0002, int(timeout_ms), ctypes.byref(result)
            ))
        except Exception:
            return False

    # User interaction --------------------------------------------------------
    def active_window_title(self) -> str:
        try:
            import win32gui
            return win32gui.GetWindowText(win32gui.GetForegroundWindow()) or ""
        except Exception:
            return ""

    def send_key(self, key: str) -> None:
        mapping = {"ENTER": "{ENTER}", "ESC": "{ESC}", "TAB": "{TAB}", "SHIFT+TAB": "+{TAB}"}
        if key.upper() not in mapping:
            raise DriverError(f"Unsupported key: {key}")
        keyboard.send_keys(mapping[key.upper()], pause=0.02)

    def open_menu(self, label: str):
        self._safe_label(label)
        item = self._find_menu_item(label, top_level=True)
        self._physical_click(item)
        self.wait_for(self._menu_popup_present, self.default_timeout, f"menu {label!r} popup")
        return item

    def choose_menu_item(self, top_label: str, item_label: str) -> None:
        self._safe_label(top_label)
        self._safe_label(item_label)
        self.open_menu(top_label)
        self._physical_click(self._find_menu_item(item_label, top_level=False))

    def dismiss_menu(self) -> None:
        self.send_key("ESC")
        self.wait_for(lambda: not self._menu_popup_present(), 5.0, "menu to close")

    def close_dialog_button(self, title: str, button_text: str = "Fermer") -> None:
        self._safe_label(button_text)
        dialog = self.wait_dialog(title)
        button = self._find_control(dialog, button_text, ("Button",))
        self._physical_click(button)
        self.wait_for(lambda: not self.dialog_exists(title), self.default_timeout, f"{title!r} to close")
        self.ensure_alive()

    def close_dialog_x(self, title: str) -> None:
        dialog = self.wait_dialog(title)
        clicked = False
        try:
            root = Desktop(backend="uia").window(handle=dialog.handle).wrapper_object()
            for bar in root.descendants(control_type="TitleBar"):
                for button in bar.descendants(control_type="Button"):
                    if self._text(button).strip().casefold() in {"fermer", "close"}:
                        self._physical_click(button)
                        clicked = True
                        break
                if clicked:
                    break
        except Exception:
            clicked = False
        if not clicked:
            raise DriverError("Real Windows title-bar X is not exposed/clickable; no WM_CLOSE fallback allowed")
        self.wait_for(lambda: not self.dialog_exists(title), self.default_timeout, f"{title!r} to close through X")
        self.ensure_alive()

    def click_control(self, window_title: str, text: str, types: Sequence[str] = ("Button",)) -> None:
        self._safe_label(text)
        window = self.wait_dialog(window_title)
        self._physical_click(self._find_control(window, text, types))

    def select_item(self, window_title: str, text: str) -> None:
        self._safe_label(text)
        window = self.wait_dialog(window_title)
        self._physical_click(self._find_control(window, text, ("ListItem", "DataItem", "TreeItem")))

    def double_click_row(self, window_title: str, row_index: int = 0) -> None:
        window = self.wait_dialog(window_title)
        def locate():
            for backend in ("uia", "win32"):
                try:
                    root = Desktop(backend=backend).window(handle=window.handle).wrapper_object()
                    if backend == "uia":
                        rows = root.descendants(control_type="DataItem") or root.descendants(control_type="ListItem")
                        if len(rows) > row_index:
                            return rows[row_index]
                    else:
                        for child in root.descendants():
                            if "ListView" in child.__class__.__name__:
                                try:
                                    return child.get_item(row_index)
                                except Exception:
                                    pass
                except Exception:
                    pass
            return None
        self.wait_value(locate, self.default_timeout, f"row {row_index}").double_click_input()

    # Locators ----------------------------------------------------------------
    def _find_menu_item(self, text: str, top_level: bool):
        wanted = text.strip().casefold()
        def locate():
            try:
                if top_level and self.main_hwnd:
                    roots = [Desktop(backend="uia").window(handle=self.main_hwnd).wrapper_object()]
                    items = [x for root in roots for x in root.descendants(control_type="MenuItem")]
                else:
                    items = []
                    for menu in Desktop(backend="uia").windows(process=self.pid, control_type="Menu", visible_only=True):
                        items.extend(menu.descendants(control_type="MenuItem"))
                for item in items:
                    if self._text(item).strip().casefold() == wanted:
                        return item
            except Exception:
                pass
            if self.main_hwnd:
                try:
                    root = Desktop(backend="win32").window(handle=self.main_hwnd).wrapper_object()
                    menu = root.menu()
                    for path in self._menu_paths(menu):
                        item = menu.get_menu_path(path)[-1]
                        if self._text(item).replace("&", "").strip().casefold() == wanted:
                            return item
                except Exception:
                    pass
            return None
        return self.wait_value(locate, self.default_timeout, f"menu item {text!r}")

    @staticmethod
    def _menu_paths(menu) -> list[str]:
        paths: list[str] = []
        try:
            for i in range(menu.item_count()):
                item = menu.item(i)
                text = NoethysUiDriver._text(item).replace("&", "")
                if text and text != "<Separator>":
                    paths.append(f"#{i}")
                    try:
                        sub = item.sub_menu()
                        if sub is not None:
                            for j in range(sub.item_count()):
                                paths.append(f"#{i}->#{j}")
                    except Exception:
                        pass
        except Exception:
            pass
        return paths

    def _find_control(self, window, text: str, types: Sequence[str]):
        wanted = text.strip().casefold()
        def locate():
            for backend in ("uia", "win32"):
                try:
                    root = Desktop(backend=backend).window(handle=window.handle).wrapper_object()
                    for control in root.descendants():
                        if self._text(control).strip().casefold() != wanted:
                            continue
                        if backend == "uia" and types:
                            try:
                                if control.element_info.control_type not in types:
                                    continue
                            except Exception:
                                pass
                        return control
                except Exception:
                    pass
            return None
        return self.wait_value(locate, self.default_timeout, f"control {text!r}")

    @staticmethod
    def _physical_click(wrapper) -> None:
        try:
            wrapper.set_focus()
        except Exception:
            pass
        wrapper.click_input()

    def _menu_popup_present(self) -> bool:
        try:
            if any(w.class_name() == "#32768" for w in Desktop(backend="win32").windows(process=self.pid, visible_only=True)):
                return True
        except Exception:
            pass
        try:
            return bool(Desktop(backend="uia").windows(process=self.pid, control_type="Menu", visible_only=True))
        except Exception:
            return False

    @staticmethod
    def _text(wrapper) -> str:
        for method in ("window_text", "text"):
            try:
                value = getattr(wrapper, method)()
                if value:
                    return str(value)
            except Exception:
                pass
        try:
            return str(wrapper.element_info.name or "")
        except Exception:
            return ""

    # Diagnostics -------------------------------------------------------------
    def capture_screenshot(self, stem: str) -> Optional[str]:
        path = self.artifact_root / f"{stem}.png"
        try:
            ImageGrab.grab(all_screens=True).save(path)
            return str(path)
        except Exception:
            return None

    def dump_window_accessibility(self, hwnd: int, stem: str, max_items: int = 600) -> list[str]:
        paths: list[str] = []
        for backend in ("uia", "win32"):
            path = self.artifact_root / f"{stem}-{backend}.txt"
            lines: list[str] = []
            try:
                root = Desktop(backend=backend).window(handle=int(hwnd)).wrapper_object()
                for index, item in enumerate(([root] + list(root.descendants()))[:max_items]):
                    entry: dict[str, Any] = {
                        "index": index,
                        "text": self._text(item),
                        "class": self._safe_attr(item, "class_name"),
                        "rectangle": str(self._safe_attr(item, "rectangle")),
                    }
                    if backend == "uia":
                        try:
                            entry.update({
                                "control_type": item.element_info.control_type,
                                "automation_id": item.element_info.automation_id,
                                "framework_id": item.element_info.framework_id,
                            })
                        except Exception:
                            pass
                    lines.append(json.dumps(entry, ensure_ascii=False))
            except Exception:
                lines.append(traceback.format_exc())
            path.write_text("\n".join(lines), encoding="utf-8")
            paths.append(str(path))
        return paths

    def dump_accessibility(self, stem: str) -> list[str]:
        paths: list[str] = []
        try:
            windows = Desktop(backend="win32").windows(process=self.pid, visible_only=True)
        except Exception:
            windows = []
        for i, window in enumerate(windows):
            paths.extend(self.dump_window_accessibility(int(window.handle), f"{stem}-window-{i}"))
        return paths

    @staticmethod
    def _safe_attr(wrapper, name: str):
        try:
            attr = getattr(wrapper, name)
            return attr() if callable(attr) else attr
        except Exception:
            return None


class ScenarioRecorder:
    def __init__(self, driver: NoethysUiDriver, scenario: str, trace_path: Path) -> None:
        self.driver = driver
        self.scenario = scenario
        self.trace_path = trace_path
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)

    def run_step(self, step: str, action: str, expected: str, operation: Callable[[], Optional[str]]) -> StepResult:
        wall_start = dt.datetime.now().astimezone()
        mono_start = time.monotonic()
        status = StepStatus.PASS
        actual = "Expected state observed"
        technical: Optional[str] = None
        screenshot: Optional[str] = None
        events: Optional[list[dict[str, Any]]] = None
        try:
            note = operation()
            if note:
                actual = note
            self.driver.ensure_alive()
        except DriverTimeout as exc:
            status, actual, technical = StepStatus.TIMEOUT, str(exc), traceback.format_exc()
        except UnexpectedProcessExit as exc:
            status, actual, technical = StepStatus.CRASH, str(exc), traceback.format_exc()
        except Exception as exc:
            status = StepStatus.CRASH if not self.driver.is_process_alive() else StepStatus.FAIL
            actual, technical = f"{type(exc).__name__}: {exc}", traceback.format_exc()
        wall_end = dt.datetime.now().astimezone()
        if status is not StepStatus.PASS:
            stem = f"step-{step}-{status.value.lower()}-{int(time.time())}"
            screenshot = self.driver.capture_screenshot(stem)
            dumps = self.driver.dump_accessibility(stem)
            events = self.driver.events.correlate(wall_start, wall_end) or None
            technical = (technical or "") + f"\naccessibility_dumps={dumps}"
        result = StepResult(
            scenario=self.scenario,
            step=str(step),
            action=action,
            expected=expected,
            status=status.value,
            actual=actual,
            duration_s=round(time.monotonic() - mono_start, 3),
            timestamp=wall_end.isoformat(),
            active_window_title=self.driver.active_window_title(),
            process_state=self.driver.process_state(),
            screenshot=screenshot,
            technical_trace=technical,
            event_log=events,
        )
        with self.trace_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")
        print(status.value, flush=True)
        return result
