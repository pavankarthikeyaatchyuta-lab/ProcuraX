from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class BranchInput(Input):
    name: str = Field(min_length=2, max_length=120)
    code: str = Field(min_length=2, max_length=20, pattern=r"^[A-Z0-9_-]+$")
    address: str = ""
    budget: Decimal = Field(default=Decimal(200000), ge=0)
    manager_limit: Decimal = Field(default=Decimal(20000), ge=0)
    zoho_location_id: str | None = None
    version: int | None = None


class StaffInput(Input):
    email: str
    password: str = ""
    branch_id: str
    role: Literal["manager", "reviewer", "receiving"]


class BranchProductInput(Input):
    manual_demand: Decimal | None = Field(None, ge=0)
    storage_limit: Decimal | None = Field(None, gt=0)
    safety_days: int | None = Field(None, ge=0, le=365)


class Item(Input):
    product_id: str
    qty: Decimal = Field(gt=0, decimal_places=4)


class RFQInput(Input):
    title: str = Field(min_length=2)
    deadline: date
    supplier_ids: list[str] = Field(min_length=1)
    lines: list[Item] = Field(min_length=1)


class RFQResponse(Input):
    version: int
    quote_ids: list[str] = Field(min_length=1)


class Award(Input):
    version: int
    quote_ids: list[str] = Field(min_length=1)


class OrderItem(Input):
    quote_id: str
    qty: Decimal = Field(gt=0, decimal_places=4)
    branch_id: str | None = None


class OrderInput(Input):
    supplier_id: str
    expected: date
    lines: list[OrderItem] = Field(min_length=1)
    note: str = ""
    source_key: str = Field(min_length=8, max_length=150)
    basket_id: str | None = None
    rfq_id: str | None = None
    version: int | None = None


class Transition(Input):
    version: int
    action: Literal[
        "submit", "approve", "reject", "return", "ordered", "close", "cancel"
    ]
    reason: str = ""


class ReceiveItem(Input):
    order_line_id: str
    accepted: Decimal = Field(ge=0, decimal_places=4)
    rejected: Decimal = Field(default=Decimal(0), ge=0, decimal_places=4)


class Receive(Input):
    version: int
    idempotency_key: str = Field(min_length=8, max_length=150)
    lines: list[ReceiveItem] = Field(min_length=1)
    note: str = ""


class LinkInvoice(Input):
    transaction_id: str


class PaymentInput(Input):
    amount: Decimal = Field(gt=0, decimal_places=2)
    date: date
    method: Literal["cash", "bank_transfer", "upi", "cheque", "other"]
    reference: str = Field(min_length=1, max_length=150)
    idempotency_key: str = Field(min_length=8, max_length=150)
    version: int


class CreditInput(Input):
    return_id: str
    amount: Decimal = Field(gt=0, decimal_places=2)
    reference: str = Field(min_length=1, max_length=150)
    date: date
    version: int


class TransferInput(Input):
    destination_id: str
    lines: list[Item] = Field(min_length=1)


class TransferReceive(Input):
    version: int
    idempotency_key: str = Field(min_length=8, max_length=150)
    lines: list[Item] = Field(default_factory=list)
    shortages: list[Item] = Field(default_factory=list)
    reason: str = ""


class Page(BaseModel):
    items: list[dict]
    total: int
    page: int
    page_size: int


class BranchView(BaseModel):
    id: str
    business_id: str
    code: str
    name: str
    address: str
    budget: Decimal
    committed: Decimal
    manager_limit: Decimal
    zoho_location_id: str | None
    version: int
