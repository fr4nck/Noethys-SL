from __future__ import annotations

import time
from typing import Any

from pywinauto import Desktop, keyboard

from recipe_recorder import NonAutomatable


def _text(wrapper) -> str:
    try:
        return str(wrapper.window_text() or "")
    except Exception:
        try:
            return str(wrapper.element_info.name or "")
        except Exception:
            return ""


def _control_type(wrapper) -> str:
    try:
        value = getattr(wrapper.element_info, "control_type", None)
        if value:
            return str(value)
    except Exception:
        pass
    try:
        return str(wrapper.friendly_class_name())
    except Exception:
        return ""


def backend_probe(driver, hwnd: int, stem: str) -> str:
    summaries: list[str] = []
    paths = driver.dump_window_accessibility(hwnd, stem)
    for backend in ("uia", "win32"):
        try:
            root = Desktop(backend=backend).window(handle=hwnd).wrapper_object()
            descendants = root.descendants()
            types: dict[str, int] = {}
            named = 0
            for ctrl in descendants:
                typ = _control_type(ctrl) or "?"
                types[typ] = types.get(typ, 0) + 1
                if _text(ctrl).strip():
                    named += 1
            summaries.append(f"{backend}: descendants={len(descendants)}, named={named}, types={types}")
        except Exception as exc:
            summaries.append(f"{backend}: unavailable ({type(exc).__name__}: {exc})")
    return "; ".join(summaries) + f"; dumps={paths}"


def unique_search_edit(driver, window_title: str):
    dialog = driver.wait_dialog(window_title)
    candidates = []
    diagnostics = []
    for backend in ("uia", "win32"):
        try:
            root = Desktop(backend=backend).window(handle=dialog.handle).wrapper_object()
            controls = root.descendants()
        except Exception as exc:
            diagnostics.append(f"{backend}:{type(exc).__name__}")
            continue
        local = []
        for ctrl in controls:
            typ = _control_type(ctrl).casefold()
            name = _text(ctrl).strip()
            class_name = ""
            try:
                class_name = str(ctrl.element_info.class_name or "")
            except Exception:
                pass
            if typ in {"edit", "searchbox"} or "search" in class_name.casefold():
                local.append(ctrl)
                diagnostics.append(f"{backend}:{typ}:{name!r}:{class_name}")
        if len(local) == 1:
            return local[0]
        candidates.extend(local)
    raise NonAutomatable(
        "SearchCtrl non identifié de manière unique par UIA/Win32; "
        f"candidats={len(candidates)} diagnostics={diagnostics}"
    )


def arm_search_timer(driver, window_title: str, text: str = "wx-timer-probe") -> str:
    edit = unique_search_edit(driver, window_title)
    try:
        edit.click_input()
        keyboard.send_keys("^a{BACKSPACE}", pause=0.01)
        keyboard.send_keys(text, with_spaces=True, pause=0.01)
    except Exception as exc:
        raise NonAutomatable(f"SearchCtrl trouvé mais frappe utilisateur impossible: {exc}") from exc
    value = _text(edit)
    return f"SearchCtrl exercised with real keyboard input; exposed_text={value!r}"


def observe_after_destroy(driver, closed_title: str, seconds: float = 1.25) -> str:
    """Observe beyond BarreRecherche's 1000 ms maximum timer delay."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        driver.ensure_alive()
        if driver.dialog_exists(closed_title):
            raise RuntimeError(f"Destroyed dialog unexpectedly reappeared: {closed_title}")
        driver.wait_responsive(driver.main_hwnd, timeout=min(1.0, max(0.2, deadline - time.monotonic())))
    return f"process responsive for {seconds:.2f}s after destruction; no dialog resurrection"


def probe_virtual_list(driver, window_title: str) -> str:
    dialog = driver.wait_dialog(window_title)
    findings: list[str] = []
    for backend in ("uia", "win32"):
        try:
            root = Desktop(backend=backend).window(handle=dialog.handle).wrapper_object()
            for ctrl in root.descendants():
                typ = _control_type(ctrl)
                class_name = ""
                try:
                    class_name = str(ctrl.element_info.class_name or "")
                except Exception:
                    pass
                if typ.casefold() in {"list", "datagrid", "listview"} or "listctrl" in class_name.casefold() or class_name == "SysListView32":
                    findings.append(f"{backend}:{typ}:{_text(ctrl)!r}:{class_name}")
        except Exception:
            pass
    if not findings:
        raise NonAutomatable("FastObjectListView/wx.ListCtrl non exposé comme liste par UIA ni Win32")
    return "virtual/native list exposed: " + " | ".join(findings[:12])


def right_click_first_row(driver, window_title: str) -> str:
    """Reusable primitive for later WIN-12 coverage; not used by the safe pilot lot."""
    dialog = driver.wait_dialog(window_title)
    for backend in ("uia", "win32"):
        try:
            root = Desktop(backend=backend).window(handle=dialog.handle).wrapper_object()
            rows = [
                ctrl for ctrl in root.descendants()
                if _control_type(ctrl).casefold() in {"dataitem", "listitem", "treeitem"}
            ]
            if rows:
                rows[0].right_click_input()
                return f"right-clicked first exposed row through {backend}"
        except Exception:
            pass
    raise NonAutomatable("Aucune ligne sélectionnable exposée pour un clic contextuel sûr")
