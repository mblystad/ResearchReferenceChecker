from __future__ import annotations

import os
import socket
import sys
import traceback
from pathlib import Path

from streamlit.web import cli as stcli


def _configure_streamlit_runtime(selected_port: int) -> list[str]:
    # Frozen PyInstaller apps do not live under site-packages, which makes
    # Streamlit mis-detect them as development installs unless we override it.
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
    os.environ["STREAMLIT_SERVER_ADDRESS"] = "127.0.0.1"
    os.environ["STREAMLIT_SERVER_PORT"] = str(selected_port)
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "false"
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

    app_path = Path(__file__).resolve().parent / "app.py"
    return [
        "streamlit",
        "run",
        str(app_path),
        "--global.developmentMode=false",
        "--server.address=127.0.0.1",
        f"--server.port={selected_port}",
        "--server.headless=false",
        "--browser.gatherUsageStats=false",
    ]


def _log_error(message: str) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent
    log_path = base / "ReferenceChecker.log"
    log_path.write_text(message, encoding="utf-8")
    return log_path


def _show_error(log_path: Path) -> None:
    try:
        if sys.platform == "win32":
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0,
                "The app couldn't start. A log file was written to:\n"
                f"{log_path}\n\n"
                "Please share this file so we can fix the issue.",
                "Reference Checker failed to start",
                0x10,
            )
            return

        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Reference Checker failed to start",
            "The app couldn't start. A log file was written to:\n"
            f"{log_path}\n\n"
            "Please share this file so we can fix the issue.",
        )
        root.destroy()
    except Exception:
        pass


def main() -> None:
    preferred_port = 3000
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", preferred_port))
        except OSError:
            sock.bind(("127.0.0.1", 0))
        selected_port = sock.getsockname()[1]
    sys.argv = _configure_streamlit_runtime(selected_port)
    try:
        raise SystemExit(stcli.main())
    except SystemExit:
        raise
    except Exception:
        log_path = _log_error(traceback.format_exc())
        _show_error(log_path)
        raise


if __name__ == "__main__":
    main()
