"""Payments are behind an interface and not implemented yet.

Candidates for South Africa: PayFast, Yoco, Paystack. Whichever is chosen
implements PaymentProvider; a successful payment then writes a positive row to
`credit_ledger`, which is all the rest of the app looks at.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Checkout:
    url: str
    reference: str


class PaymentProvider(Protocol):
    name: str

    async def create_checkout(
        self, *, amount_cents: int, credit_count: int, reference: str
    ) -> Checkout:
        """Starts a payment and returns where to send the payer."""
        ...

    async def verify_webhook(self, headers: dict[str, str], body: bytes) -> str | None:
        """Returns the reference of a confirmed payment, or None if the call is not genuine."""
        ...


class NoPaymentProvider:
    """The stub in use until a gateway is chosen."""

    name = "none"

    async def create_checkout(
        self, *, amount_cents: int, credit_count: int, reference: str
    ) -> Checkout:
        raise NotImplementedError("No payment gateway is configured yet.")

    async def verify_webhook(self, headers: dict[str, str], body: bytes) -> str | None:
        return None
