"""Pydantic schemas for government review, certificate issuance, and verification.

- ``GovernmentReviewRequest`` already defined in ``ric.py`` (action + note).
- ``CertificateIssueResponse``: returned after successful issuance (certificate id, ric number).
- ``VerificationResponse`` already defined in ``ric.py``.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

class CertificateIssueResponse(BaseModel):
    certificate_id: str = Field(..., description="UUID of the issued certificate")
    ric_number: str = Field(..., description="12‑digit RIC number")
    status: str = Field(..., description="Certificate status (active)")

    model_config = ConfigDict(from_attributes=True)
