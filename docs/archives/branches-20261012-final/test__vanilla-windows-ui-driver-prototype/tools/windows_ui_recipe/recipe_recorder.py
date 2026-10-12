from __future__ import annotations

import datetime as dt
import json
import re
import time
import traceback
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from noethys_ui_driver import DriverTimeout, UnexpectedProcessExit


class PilotStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    TIMEOUT = "TIMEOUT"
    CRASH = "CRASH"
    NON_AUTOMATISABLE = "NON_AUTOMATISABLE"


class NonAutomatable(RuntimeError):
    """The user path exists, but the safe UI driver cannot exercise it reliably."""


@dataclass
class PilotStepResult:
    win: str
    section: str
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
    accessibility_dumps: Optional[list[str]] = None
    technical_trace: Optional[str] = None
    noethys_log_tail: Optional[str] = None
    wx_errors: Optional[list[str]] = None
    event_log: Optional[list[dict[str, Any]]] = None
    application_error_1000: bool = False
    exception_codes: Optional[list[str]] = None


class PilotRecorder:
    def __init__(self, driver, scenario: str, trace_path: Path) -> None:
        self.driver = driver
        self.scenario = scenario
        self.trace_path = trace_path
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        self.results: list[PilotStepResult] = []

    def _journal_tail(self, max_bytes: int = 24000) -> Optional[str]:
        candidates = [
            self.driver.profile_root / "Roaming" / "noethys" / "journal.log",
            self.driver.profile_root / "Roaming" / "noethys" / "Journal.log",
        ]
        for path in candidates:
            try:
                if path.is_file():
                    data = path.read_bytes()
                    return data[-max_bytes:].decode("utf-8", errors="replace")
            except Exception:
                pass
        return None

    @staticmethod
    def _wx_errors(text: Optional[str]) -> list[str]:
        if not text:
            return []
        patterns = (
            r".*PyDeadObjectError.*",
            r".*wxAssertionError.*",
            r".*wx.*assert.*",
            r".*Traceback \(most recent call last\):.*",
            r".*access violation.*",
        )
        found: list[str] = []
        for line in text.splitlines():
            if any(re.search(pattern, line, re.I) for pattern in patterns):
                found.append(line[-1000:])
        return found[-50:]

    @staticmethod
    def _event_metadata(events: list[dict[str, Any]]) -> tuple[bool, list[str]]:
        app1000 = False
        codes: set[str] = set()
        for event in events:
            try:
                app1000 = app1000 or int(event.get("event_id", -1)) == 1000
            except Exception:
                pass
            if event.get("mentions_0xc0000005"):
                codes.add("0xc0000005")
            for value in event.get("strings") or []:
                for code in re.findall(r"0x[0-9a-fA-F]{8}", str(value)):
                    codes.add(code.lower())
        return app1000, sorted(codes)

    def run_step(
        self,
        win: str,
        section: str,
        step: str,
        action: str,
        expected: str,
        operation: Callable[[], Optional[str]],
    ) -> PilotStepResult:
        wall_start = dt.datetime.now().astimezone()
        mono_start = time.monotonic()
        status = PilotStatus.PASS
        actual = "Expected state observed"
        technical: Optional[str] = None
        try:
            note = operation()
            if note:
                actual = note
        except NonAutomatable as exc:
            status = PilotStatus.NON_AUTOMATISABLE
            actual = f"{type(exc).__name__}: {exc}"
        except DriverTimeout as exc:
            status = PilotStatus.TIMEOUT
            actual = f"{type(exc).__name__}: {exc}"
            technical = traceback.format_exc()
        except UnexpectedProcessExit as exc:
            status = PilotStatus.CRASH
            actual = f"{type(exc).__name__}: {exc}"
            technical = traceback.format_exc()
        except Exception as exc:
            try:
                alive = self.driver.is_process_alive()
            except Exception:
                alive = False
            status = PilotStatus.FAIL if alive else PilotStatus.CRASH
            actual = f"{type(exc).__name__}: {exc}"
            technical = traceback.format_exc()

        wall_end = dt.datetime.now().astimezone()
        screenshot = None
        dumps: list[str] = []
        events: list[dict[str, Any]] = []
        journal = None
        wx_errors: list[str] = []
        if status is not PilotStatus.PASS:
            stem = f"{win.lower()}-{section.lower()}-{step}-{status.value.lower()}-{int(time.time())}"
            try:
                screenshot = self.driver.capture_screenshot(stem)
            except Exception:
                pass
            try:
                dumps = self.driver.dump_accessibility(stem)
            except Exception:
                pass
            try:
                events = self.driver.events.correlate(wall_start, wall_end)
            except Exception:
                pass
            journal = self._journal_tail()
            wx_errors = self._wx_errors(journal)

        app1000, codes = self._event_metadata(events)
        result = PilotStepResult(
            win=win,
            section=section,
            step=step,
            action=action,
            expected=expected,
            status=status.value,
            actual=actual,
            duration_s=round(time.monotonic() - mono_start, 3),
            timestamp=wall_end.isoformat(),
            active_window_title=self.driver.active_window_title(),
            process_state=self.driver.process_state(),
            screenshot=screenshot,
            accessibility_dumps=dumps or None,
            technical_trace=technical,
            noethys_log_tail=journal,
            wx_errors=wx_errors or None,
            event_log=events or None,
            application_error_1000=app1000,
            exception_codes=codes or None,
        )
        self.results.append(result)
        with self.trace_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")
        print(f"{result.status} {win}/{section}/{step} - {action}")
        return result

    def write_summary(self, path: Path) -> dict[str, Any]:
        counts = {status.value: 0 for status in PilotStatus}
        for result in self.results:
            counts[result.status] = counts.get(result.status, 0) + 1
        payload = {
            "scenario": self.scenario,
            "counts": counts,
            "steps": len(self.results),
            "windows": sorted({result.win for result in self.results}),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload
