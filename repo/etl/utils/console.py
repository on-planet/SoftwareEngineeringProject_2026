from __future__ import annotations

import signal
import sys
from typing import Callable

try:
    import ctypes
except Exception:  # pragma: no cover
    ctypes = None


def install_console_shutdown(handler: Callable[[], None]) -> None:
    """Run cleanup when the console is interrupted, then let the process exit normally."""

    def _run_handler() -> None:
        handler()

    def _handle_signal(signum=None, frame=None):
        _run_handler()
        if signum == signal.SIGINT:
            raise KeyboardInterrupt()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if sys.platform != "win32" or ctypes is None:
        return

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handler_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)

    @handler_type
    def _console_handler(ctrl_type):
        if ctrl_type in (0, 2, 5, 6):
            _run_handler()
            return False
        return False

    kernel32.SetConsoleCtrlHandler(_console_handler, True)
