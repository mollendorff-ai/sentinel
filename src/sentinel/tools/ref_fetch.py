"""Ref CLI wrapper — fetches web content as structured JSON for LLM agents."""

import asyncio
import json
import logging
from typing import Any

from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


class RefFetchTool(BaseTool):
    """Fetch web content via Ref CLI (headless Chrome, structured JSON output)."""

    name: str = "ref_fetch"
    description: str = (
        "Fetch a web page and return structured JSON with title, sections, and links. "
        "Uses headless Chrome to render SPAs and bypass bot protection. "
        "Input is a URL string."
    )
    timeout_ms: int = 30000

    def _run(self, url: str) -> dict[str, Any]:
        """Run synchronously by delegating to the async implementation."""
        return asyncio.run(self._arun(url))

    async def _arun(self, url: str) -> dict[str, Any]:
        """Fetch *url* via ``ref fetch`` and return parsed JSON."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ref",
                "fetch",
                "--timeout",
                str(self.timeout_ms),
                url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout_ms / 1000 + 10,  # CLI timeout + buffer
            )

            if proc.returncode != 0:
                error_msg = stderr.decode().strip()
                logger.error("ref fetch failed (rc=%d): %s", proc.returncode, error_msg)
                return {"url": url, "status": "error", "error": error_msg}

            return json.loads(stdout.decode())  # type: ignore[no-any-return]

        except FileNotFoundError:
            return {"url": url, "status": "error", "error": "ref CLI not found in PATH"}
        except TimeoutError:
            return {
                "url": url,
                "status": "error",
                "error": f"Timeout after {self.timeout_ms}ms",
            }
        except json.JSONDecodeError as exc:
            return {"url": url, "status": "error", "error": f"Invalid JSON from ref: {exc}"}
