from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class OrderItem(BaseModel):
    productId: str
    qty: int


class CreateOrderRequest(BaseModel):
    customerId: str
    items: List[OrderItem]


class OrderResponse(BaseModel):
    orderId: str
    status: str
    total: float
    idempotentReplay: Optional[bool] = None


class Product(BaseModel):
    id: str
    name: str
    price: float


class ProductResponse(BaseModel):
    products: List[Product]
