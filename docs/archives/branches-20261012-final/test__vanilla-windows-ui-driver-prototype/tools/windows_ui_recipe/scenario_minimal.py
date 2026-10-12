from __future__ import annotations

import argparse
import sys
from pathlib import Path

from interaction_extensions import (
    arm_search_timer,
    backend_probe,
    observe_after_destroy,
    probe_virtual_list,
)
from noethys_ui_driver import NoethysUiDriver
from recipe_recorder import NonAutomatable, PilotRecorder, PilotStatus

SCENARIO = "noethys-vanilla-windows-pilot-a-e"
WAITING_TITLE = "Liste d'attente"
CONSUMPTION_TITLE = "Liste détaillée des consommations"
DISPLAY_DIALOG_TITLE = "Sauvegarde d'une disposition"
DISPLAY_DIALOG_MENU_ITEM = "Sauvegarder la disposition actuelle"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive Windows recipe prototype for Noethys Vanilla")
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--profile-root", required=True, type=Path)
    parser.add_argument("--expected-db-host", required=True)
    parser.add_argument("--expected-db-name", required=True)
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts/noethys-ui"))
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--consumption-menu-item", default="Liste détaillée des consommations")
    return parser.parse_args()


def wait_main_and_probe(driver: NoethysUiDriver) -> str:
    main = driver.wait_main_window()
    return (
        f"main={driver._text(main)!r}; "
        + backend_probe(driver, int(main.handle), "a-main-window")
    )


def open_display_menu(driver: NoethysUiDriver) -> str:
    driver.open_menu("Affichage")
    driver.dismiss_menu()
    driver.ensure_alive()
    return "Affichage popup opened by real click_input then dismissed with ESC"


def open_display_dialog(driver: NoethysUiDriver) -> str:
    driver.choose_menu_item("Affichage", DISPLAY_DIALOG_MENU_ITEM)
    dialog = driver.wait_dialog(DISPLAY_DIALOG_TITLE)
    probe = backend_probe(driver, int(dialog.handle), "b-display-dialog")
    return f"dialog={DISPLAY_DIALOG_TITLE!r} hwnd={dialog.handle}; {probe}"


def cancel_dialog_button(driver: NoethysUiDriver, title: str) -> str:
    driver.close_dialog_button(title, "Annuler")
    return f"dialog={title!r} cancelled through visible Annuler button"


def cancel_dialog_escape(driver: NoethysUiDriver, title: str) -> str:
    driver.send_key("ESC")
    driver.wait_for(lambda: not driver.dialog_exists(title), driver.default_timeout, f"{title!r} to close with Escape")
    driver.ensure_alive()
    return f"dialog={title!r} cancelled with ESC"


def open_and_wait(driver: NoethysUiDriver, item: str, title: str, probe: str | None = None) -> str:
    driver.choose_menu_item("Consommations", item)
    dialog = driver.wait_dialog(title)
    driver.wait_responsive(int(dialog.handle), timeout=min(driver.default_timeout, 10.0))
    dumps = driver.dump_window_accessibility(int(dialog.handle), probe) if probe else []
    return f"dialog={title!r} visible hwnd={dialog.handle}; accessibility_dumps={dumps}"


def close_button_and_check(driver: NoethysUiDriver, title: str) -> str:
    driver.close_dialog_button(title, "Fermer")
    driver.wait_responsive(driver.main_hwnd, timeout=min(driver.default_timeout, 10.0))
    return f"dialog={title!r} closed via Fermer; Noethys alive"


def close_first_visible(driver: NoethysUiDriver, item: str, title: str) -> str:
    driver.choose_menu_item("Consommations", item)
    # DLG_Liste_consommations performs part of its load before ShowModal().
    # A black-box UI recipe can only close it from the first user-visible instant.
    dialog = driver.wait_dialog(title, visible_only=True)
    driver.close_dialog_button(title, "Fermer")
    driver.wait_responsive(driver.main_hwnd, timeout=min(driver.default_timeout, 10.0))
    return f"first user-visible hwnd={dialog.handle} closed immediately via Fermer"


def repeat_close_reopen(driver: NoethysUiDriver, item: str, title: str, count: int) -> str:
    for _index in range(1, count + 1):
        driver.close_dialog_button(title, "Fermer")
        driver.choose_menu_item("Consommations", item)
        dialog = driver.wait_dialog(title)
        driver.wait_responsive(int(dialog.handle), timeout=min(driver.default_timeout, 10.0))
        driver.ensure_alive()
    return f"{count}/{count} close/reopen cycles completed; last dialog remains open for X test"


def close_x_and_check(driver: NoethysUiDriver, title: str) -> str:
    driver.close_dialog_x(title)
    driver.wait_responsive(driver.main_hwnd, timeout=min(driver.default_timeout, 10.0))
    return f"dialog={title!r} closed by the real Windows title-bar X"


def virtual_list_close_reopen(driver: NoethysUiDriver, item: str) -> str:
    driver.choose_menu_item("Consommations", item)
    dialog = driver.wait_dialog(CONSUMPTION_TITLE)
    exposure = probe_virtual_list(driver, CONSUMPTION_TITLE)
    driver.close_dialog_button(CONSUMPTION_TITLE, "Fermer")
    driver.choose_menu_item("Consommations", item)
    reopened = driver.wait_dialog(CONSUMPTION_TITLE)
    driver.wait_responsive(int(reopened.handle), timeout=min(driver.default_timeout, 10.0))
    return f"{exposure}; close/reopen succeeded hwnd={dialog.handle}->{reopened.handle}"


def timer_close_and_observe(driver: NoethysUiDriver) -> str:
    armed = arm_search_timer(driver, CONSUMPTION_TITLE)
    driver.close_dialog_button(CONSUMPTION_TITLE, "Fermer")
    observed = observe_after_destroy(driver, CONSUMPTION_TITLE, 1.25)
    return f"{armed}; closed immediately; {observed}"


def non_automatable_double_close() -> str:
    raise NonAutomatable(
        "A second physical click after the first click destroys the dialog can land on an unrelated control underneath. "
        "Sending WM_CLOSE twice would no longer be a real-user test, so the prototype deliberately does neither."
    )


def non_automatable_callafter() -> str:
    raise NonAutomatable(
        "A black-box desktop driver cannot force or identify an internal wx.CallAfter/CallLater callback after destruction "
        "without instrumenting Noethys. The real search-timer late-callback path is exercised separately."
    )


def final_check(driver: NoethysUiDriver) -> str:
    driver.ensure_alive()
    driver.wait_responsive(driver.main_hwnd, timeout=min(driver.default_timeout, 10.0))
    state = driver.process_state()
    if state.get("hung") or state.get("responsive") is False:
        raise RuntimeError(f"Noethys alive but non-responsive: {state}")
    return f"Noethys.exe alive and responsive: {state}"


def main() -> int:
    args = parse_args()
    if args.repeat < 1:
        raise SystemExit("--repeat must be >= 1")
    artifacts = args.artifacts.resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    trace = artifacts / "scenario.jsonl"
    if trace.exists():
        trace.unlink()

    driver = NoethysUiDriver(
        args.exe,
        args.profile_root,
        args.expected_db_host,
        args.expected_db_name,
        artifacts,
        default_timeout=args.timeout,
    )
    rec = PilotRecorder(driver, SCENARIO, trace)

    steps = [
        ("WIN-01", "A", "A1", "Launch Noethys.exe", "Process starts and remains alive", lambda: f"pid={driver.launch()}"),
        ("WIN-01", "A", "A2", "Wait for main window and probe accessibility", "Main Noethys window visible/responsive; UIA and Win32 trees captured", lambda: wait_main_and_probe(driver)),

        ("WIN-01", "B", "B1", "Open Affichage menu", "Affichage popup becomes visible and can be dismissed", lambda: open_display_menu(driver)),
        ("WIN-01", "B", "B2", f"Open Affichage > {DISPLAY_DIALOG_MENU_ITEM}", "Safe display dialog appears", lambda: open_display_dialog(driver)),
        ("WIN-01", "B", "B3", "Cancel display dialog normally", "Annuler closes the dialog", lambda: cancel_dialog_button(driver, DISPLAY_DIALOG_TITLE)),
        ("WIN-01", "B", "B4", "Reopen display dialog", "Same dialog reopens", lambda: open_display_dialog(driver)),
        ("WIN-13", "B", "B5", "Cancel reopened display dialog with Escape", "ESC closes the modal dialog cleanly", lambda: cancel_dialog_escape(driver, DISPLAY_DIALOG_TITLE)),

        ("WIN-06", "C", "C1", "Open Consommations > Liste d'attente", "Liste d'attente dialog appears", lambda: open_and_wait(driver, "Liste d'attente", WAITING_TITLE, "c-waiting-list")),
        ("WIN-06", "C", "C2", "Close Liste d'attente using Fermer", "Dialog closes and Noethys remains responsive", lambda: close_button_and_check(driver, WAITING_TITLE)),
        ("WIN-06", "C", "C3", "Reopen Liste d'attente immediately", "Dialog reopens", lambda: open_and_wait(driver, "Liste d'attente", WAITING_TITLE)),
        ("WIN-13", "C", "C4", "Cancel Liste d'attente with Escape", "ESC closes the dialog cleanly", lambda: cancel_dialog_escape(driver, WAITING_TITLE)),

        ("WIN-04", "D", "D1", "Open consumption list and close at first user-visible instant", "No crash/hang during earliest real-user close", lambda: close_first_visible(driver, args.consumption_menu_item, CONSUMPTION_TITLE)),
        ("WIN-04", "D", "D2", "Reopen consumption list immediately", "Dialog reopens and is responsive", lambda: open_and_wait(driver, args.consumption_menu_item, CONSUMPTION_TITLE, "d-consumption-list")),
        ("WIN-04", "D", "D3", f"Repeat close/reopen {args.repeat} times", "Every cycle succeeds with live process", lambda: repeat_close_reopen(driver, args.consumption_menu_item, CONSUMPTION_TITLE, args.repeat)),
        ("WIN-04", "D", "D4", "Close consumption dialog using Windows X", "Real title-bar X closes dialog without crash", lambda: close_x_and_check(driver, CONSUMPTION_TITLE)),

        ("WIN-13", "E", "E1", "Exercise virtual list then close/reopen", "List is exposed by at least one backend and survives lifecycle cycle", lambda: virtual_list_close_reopen(driver, args.consumption_menu_item)),
        ("WIN-13", "E", "E2", "Type into SearchCtrl then close with its timer pending", "Real EVT_TEXT schedules timer; destruction leaves Noethys alive past 1000 ms maximum delay", lambda: timer_close_and_observe(driver)),
        ("WIN-13", "E", "E3", "Attempt a real-user double close", "Only execute if second physical close cannot hit unrelated UI", non_automatable_double_close),
        ("WIN-13", "E", "E4", "Force an arbitrary wx.CallAfter after destruction", "Only execute if observable without application instrumentation", non_automatable_callafter),
        ("WIN-13", "E", "E5", "Final process responsiveness check", "Noethys.exe remains alive and responsive", lambda: final_check(driver)),
    ]

    hard_failure = False
    try:
        for win, section, step, action, expected, operation in steps:
            result = rec.run_step(win, section, step, action, expected, operation)
            if result.status in {PilotStatus.FAIL.value, PilotStatus.TIMEOUT.value, PilotStatus.CRASH.value}:
                hard_failure = True
                break
    finally:
        summary = rec.write_summary(artifacts / "summary.json")
        print(f"SUMMARY {summary}")
        # The process is owned by the recipe. End it out-of-band after the final
        # responsiveness assertion so the recipe never clicks a production-like Quit flow.
        try:
            if driver.proc is not None and driver.is_process_alive():
                driver.proc.terminate()
                driver.proc.wait(timeout=5)
        except Exception:
            try:
                if driver.proc is not None:
                    driver.proc.kill()
            except Exception:
                pass

    return 10 if hard_failure else 0


if __name__ == "__main__":
    sys.exit(main())
