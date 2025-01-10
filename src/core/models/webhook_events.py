from pydantic import BaseModel


class BaseWebhookEvent(BaseModel):
    wallet_id: str
    asset: str
    balance: float
    address: str
    transaction_hash: str
    chain_id: str


class FundsReceivedEvent(BaseWebhookEvent):
    amount_received: float


class FundsSentEvent(BaseWebhookEvent):
    amount_sent: float


WebhookEvent = FundsReceivedEvent | FundsSentEvent
