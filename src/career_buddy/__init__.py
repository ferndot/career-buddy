"""career-buddy: import career data, hold it as a graph of facts, generate documents from it."""

import os
import subprocess
import sys
import threading
import webbrowser


def install_browser() -> int:
    """Download the Chromium that PDF output needs (about 150 MB, stored outside the project)."""
    return subprocess.call([sys.executable, "-m", "playwright", "install", "chromium"])


def main() -> None:
    if sys.argv[1:] == ["install-browser"]:
        raise SystemExit(install_browser())

    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")  # containers set 0.0.0.0; compose publishes it to localhost only
    port = int(os.environ.get("PORT", "8000"))
    reload = os.environ.get("RELOAD") == "1"  # dev only: restart the API when a source file under the package changes
    if not reload and os.environ.get("CAREER_BUDDY_NO_BROWSER") != "1":
        # Opens the app once the server is up; the 1.5 s delay is a guess, not a readiness check.
        threading.Timer(1.5, webbrowser.open, [f"http://127.0.0.1:{port}"]).start()
    uvicorn.run("career_buddy.web.app:create_app", factory=True, host=host, port=port,
                reload=reload, reload_dirs=[os.path.dirname(__file__)] if reload else None)
