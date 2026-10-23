"""Prepare the PyPI description without changing the checkout's README."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from hatchling.metadata.plugin.interface import MetadataHookInterface

_LOCAL_GIF = re.compile(r"(!\[[^\]\n]*\]\()(assets/[^\s)]+\.gif)(\))")


class CustomMetadataHook(MetadataHookInterface):
    """Resolve local demo images against the versioned public asset repository."""

    def update(self, metadata: dict[str, Any]) -> None:
        readme = Path(self.root, "README.md").read_text(encoding="utf-8")
        image_base = self.config["image-base-url"].format(version=metadata["version"]).rstrip("/")
        metadata["readme"] = {
            "content-type": "text/markdown",
            "text": _LOCAL_GIF.sub(
                lambda match: f"{match[1]}{image_base}/{match[2]}{match[3]}", readme
            ),
        }
