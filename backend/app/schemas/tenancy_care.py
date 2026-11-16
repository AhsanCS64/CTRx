from base64 import b64decode
from binascii import Error
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, model_validator

Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Detail = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class Photo(BaseModel):
    taken_on: date
    data: str = Field(max_length=1_400_000)

    @model_validator(mode="after")
    def validate_image(self):
        header, _, encoded = self.data.partition(",")
        try:
            raw = b64decode(encoded, validate=True)
        except Error as exc:
            raise ValueError("Invalid photo encoding") from exc
        if not (
            header == "data:image/png;base64" and raw.startswith(b"\x89PNG\r\n\x1a\n")
            or header == "data:image/jpeg;base64" and raw.startswith(b"\xff\xd8\xff")
            or header == "data:image/webp;base64" and raw.startswith(b"RIFF") and raw[8:12] == b"WEBP"
        ):
            raise ValueError("Use a JPEG, PNG or WebP photo")
        return self


class Room(BaseModel):
    name: Label
    check: Label
    condition: Literal["good", "worn", "damaged", "not_checked"]
    notes: str = Field(default="", max_length=1000)


class Inspection(BaseModel):
    kind: Literal["move_in", "move_out"]
    inspected_on: date
    rooms: list[Room] = Field(min_length=1, max_length=30)
    meters: Detail
    keys: Detail
    photos: list[Photo] = Field(default_factory=list, max_length=4)


class Maintenance(BaseModel):
    kind: Literal["maintenance"]
    title: Label
    description: Detail
    photos: list[Photo] = Field(default_factory=list, max_length=4)


class Deduction(BaseModel):
    description: Label
    amount: Annotated[Money, Field(gt=0)]
    evidence: Detail
    photo: Photo | None = None


class Deposit(BaseModel):
    kind: Literal["deposit"]
    deductions: list[Deduction] = Field(max_length=8)
    returned: Money
    returned_on: date | None = None
    reference: str = Field(default="", max_length=160)


CareCreate = Annotated[Inspection | Maintenance | Deposit, Field(discriminator="kind")]


class Acknowledge(BaseModel):
    action: Literal["acknowledge"]


class RepairUpdate(BaseModel):
    action: Literal["repair"]
    status: Literal["scheduled", "in_progress", "completed"]
    scheduled_for: date | None = None
    note: Detail


class DeductionResponse(BaseModel):
    action: Literal["deduction"]
    index: int = Field(ge=0)
    decision: Literal["acknowledged", "disputed"]
    note: str = Field(default="", max_length=2000)


class LinkDispute(BaseModel):
    action: Literal["link_case"]
    case_id: UUID


class RecordReturn(BaseModel):
    action: Literal["record_return"]
    amount: Annotated[Money, Field(gt=0)]
    returned_on: date
    reference: str = Field(default="", max_length=160)


CareUpdate = Annotated[Acknowledge | RepairUpdate | DeductionResponse | LinkDispute | RecordReturn, Field(discriminator="action")]

