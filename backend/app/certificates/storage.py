"""Local‑disk storage implementation for certificate PDFs.

The ``store_pdf`` function writes the PDF bytes to a file under the directory
specified by ``settings.STORAGE_DIR`` and returns the relative storage key (the
filename). The directory is created automatically if missing.
"""

import os
from pathlib import Path
from uuid import uuid4

from app.core.config import settings


def store_pdf(pdf_bytes: bytes, prefix: str = "cert") -> str:
    """Save *pdf_bytes* to ``settings.STORAGE_DIR`` and return the storage key.

    The filename is generated as ``{prefix}_{uuid4()}.pdf`` to avoid collisions.
    """
    storage_dir = Path(settings.STORAGE_DIR)
    storage_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{prefix}_{uuid4().hex}.pdf"
    file_path = storage_dir / filename
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)
    return str(filename)
