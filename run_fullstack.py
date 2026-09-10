"""全栈开发入口：启动 FastAPI，等待就绪后打开前端工作台。"""

import os
import threading
import time
import urllib.error
import urllib.request
import webbrowser

import uvicorn


def wait_and_open_browser(frontend_url: str, timeout: float = 30.0) -> None:
    """等待后端健康检查通过，再打开浏览器。"""
    deadline = time.monotonic() + timeout
    health_url = frontend_url.replace("/app/", "/health")

    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=1.5) as response:
                if response.status == 200:
                    webbrowser.open(frontend_url)
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.5)


if __name__ == "__main__":
    host = os.getenv("BACKEND_HOST", "127.0.0.1")
    port = int(os.getenv("BACKEND_PORT", "8000"))
    reload_enabled = os.getenv("BACKEND_RELOAD", "1").lower() not in {
        "0",
        "false",
        "no",
    }
    open_browser = os.getenv("OPEN_BROWSER", "1").lower() not in {
        "0",
        "false",
        "no",
    }
    frontend_url = f"http://{host}:{port}/app/"

    if open_browser:
        threading.Thread(
            target=wait_and_open_browser,
            args=(frontend_url,),
            daemon=True,
        ).start()

    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=reload_enabled,
        reload_dirs=["backend", "frontend"],
    )
