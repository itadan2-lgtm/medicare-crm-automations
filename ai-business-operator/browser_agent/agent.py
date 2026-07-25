"""Browser agent worker entrypoint.

Runs as its own process and deployment: a Playwright base image, a tighter network
policy, and no LLM or database credentials.

    python -m browser_agent.agent
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.worker import Worker
from agents.worker import main as worker_main


def main() -> None:
    # The generic worker CLI takes --agent; pin it so this image can only ever run
    # the browser agent.
    sys.argv = [sys.argv[0], "--agent", "browser_agent"]
    worker_main()


__all__ = ["Worker", "main"]

if __name__ == "__main__":
    main()
