"""career-graph: import career data, hold it as a graph of facts, generate documents from it."""

import os


def main() -> None:
    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")  # containers set 0.0.0.0; compose publishes it to localhost only
    port = int(os.environ.get("PORT", "8000"))
    reload = os.environ.get("RELOAD") == "1"  # dev only: restart the API when a source file under the package changes
    uvicorn.run("career_graph.web.app:create_app", factory=True, host=host, port=port,
                reload=reload, reload_dirs=[os.path.dirname(__file__)] if reload else None)
