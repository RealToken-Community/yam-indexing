import signal

shutdown_requested = False
shutdown_reason = "unknown"

def request_shutdown(signum, frame):
    global shutdown_requested, shutdown_reason
    shutdown_requested = True

    if signum == signal.SIGINT:
        shutdown_reason = "Ctrl+C"
    elif signum == signal.SIGTERM:
        shutdown_reason = "docker stop"
    else:
        shutdown_reason = f"Signal {signum}"

def setup_signal_handlers():
    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)