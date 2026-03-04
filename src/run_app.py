import threading
import webbrowser
import os

import uvicorn


APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", "8000"))


def start_server():
    uvicorn.run("app.main:app", host=APP_HOST, port=APP_PORT, log_level="error")


thread = threading.Thread(target=start_server, daemon=True)
thread.start()

url = f"http://{APP_HOST}:{APP_PORT}"
webbrowser.open(url)
print(f"Server started at {url}")
input("Press Enter to stop...\n")
