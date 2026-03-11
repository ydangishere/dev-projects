from fastapi import FastAPI, Depends, HTTPException, Header, status, Response
from sqlalchemy.orm import Session
from typing import Optional
import uuid
import logging
from datetime import datetime

from database import get_db, Order, OrderStatus
from models import CreateOrderRequest, OrderResponse, ProductResponse, Product
from idempotency import handle_idempotency, save_idempotency_response
from cache import get_cache, set_cache

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Order/Payment API", version="1.0.0")

# Mock products data (in real app, this would come from DB)
MOCK_PRODUCTS = [
    {"id": "p1", "name": "Product 1", "price": 50.00},
    {"id": "p2", "name": "Product 2", "price": 20.50},
    {"id": "p3", "name": "Product 3", "price": 30.00},
]


@app.get("/")
def root():
    return {"message": "Order/Payment API", "version": "1.0.0"}


@app.post(
    "/orders", 
    response_model=OrderResponse, 
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Order created successfully",
            "content": {
                "application/json": {
                    "example": {"orderId": "o_a1b2c3d4", "status": "CREATED", "total": 120.5}
                }
            }
        },
        200: {
            "description": "Idempotent replay - order already exists",
            "content": {
                "application/json": {
                    "example": {"orderId": "o_a1b2c3d4", "status": "CREATED", "total": 120.5, "idempotentReplay": True}
                }
            }
        },
        400: {"description": "Invalid request or missing Idempotency-Key"},
        409: {"description": "Idempotency-Key reused with different payload"},
        425: {"description": "Request still being processed"}
    }
)
def create_order(
    request: CreateOrderRequest,
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key", description="Unique key to prevent duplicate payments"),
    db: Session = Depends(get_db)
):
    """
    Create a payment transaction with idempotency guarantees.
    
    **Prevents double-charges** by using Idempotency-Key header.
    
    **Example Request Body:**
    ```json
    {
      "customerId": "c123",
      "items": [
        {"productId": "p1", "qty": 2},
        {"productId": "p2", "qty": 1}
      ]
    }
    ```
    
    **Available Products:**
    - p1: $50.00, p2: $20.50, p3: $30.00
    
    **Flow:**
    1. First call with key → 201 Created (new payment)
    2. Repeat with same key + same body → 200 OK (replay, no charge)
    3. Same key + different body → 409 Conflict (security)
    """
    logger.info(f"Creating order with Idempotency-Key: {idempotency_key[:16]}...")
    
    # Validate request
    if not request.items or len(request.items) == 0:
        logger.warning(f"Empty items list for customer {request.customerId}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order must contain at least one item"
        )
    
    # Check idempotency
    try:
        is_replay, cached_response = handle_idempotency(
            db, idempotency_key, request.dict()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Idempotency check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process idempotency check"
        )
    
    if is_replay and cached_response:
        # Return cached response with 200 status
        logger.info(f"Returning cached response for key: {idempotency_key[:16]}...")
        response.status_code = status.HTTP_200_OK
        return OrderResponse(**cached_response)
    
    # Calculate total
    total = 0.0
    for item in request.items:
        # Validate quantity
        if item.qty <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Quantity must be greater than 0 for product {item.productId}"
            )
        
        # Find product price
        product = next((p for p in MOCK_PRODUCTS if p["id"] == item.productId), None)
        if not product:
            logger.warning(f"Product not found: {item.productId}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product {item.productId} not found"
            )
        total += product["price"] * item.qty
    
    # Create order
    order_id = f"o_{uuid.uuid4().hex[:8]}"
    try:
        order = Order(
            id=order_id,
            customer_id=request.customerId,
            status=OrderStatus.CREATED,
            total=round(total, 2),
            created_at=datetime.utcnow()
        )
        
        db.add(order)
        db.commit()
        db.refresh(order)
        
        logger.info(f"Order created: {order_id} for customer {request.customerId}, total: {total}")
    except Exception as e:
        logger.error(f"Failed to create order: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create order"
        )
    
    # Prepare response
    response_data = {
        "orderId": order_id,
        "status": order.status.value,
        "total": order.total
    }
    
    # Save response for idempotency replay
    try:
        save_idempotency_response(db, idempotency_key, response_data)
    except Exception as e:
        logger.error(f"Failed to save idempotency response: {e}", exc_info=True)
        # Don't fail the request if saving replay fails
    
    return OrderResponse(**response_data)


@app.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: str, db: Session = Depends(get_db)):
    """
    Get order by ID with Redis caching.
    """
    cache_key = f"order:{order_id}"
    
    # Check cache first
    cached_order = get_cache(cache_key)
    if cached_order:
        logger.info(f"Cache hit for order: {order_id}")
        return OrderResponse(**cached_order)
    
    logger.info(f"Cache miss for order: {order_id}, querying DB")
    
    # Get from database
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        logger.warning(f"Order not found: {order_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found"
        )
    
    response_data = {
        "orderId": order.id,
        "status": order.status.value,
        "total": order.total
    }
    
    # Cache for 60 seconds
    set_cache(cache_key, response_data, ttl=60)
    
    return OrderResponse(**response_data)


@app.post("/orders/{order_id}/confirm", response_model=dict)
def confirm_order(order_id: str, db: Session = Depends(get_db)):
    """
    Confirm an order. Idempotent - if already confirmed, returns success.
    """
    logger.info(f"Confirming order: {order_id}")
    
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        logger.warning(f"Order not found for confirmation: {order_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found"
        )
    
    # Idempotent: if already confirmed, return success
    if order.status == OrderStatus.CONFIRMED:
        logger.info(f"Order {order_id} already confirmed, returning idempotent response")
        return {
            "orderId": order_id,
            "status": "CONFIRMED",
            "message": "Order already confirmed",
            "idempotentReplay": True
        }
    
    # Update status
    try:
        order.status = OrderStatus.CONFIRMED
        db.commit()
        logger.info(f"Order {order_id} confirmed successfully")
    except Exception as e:
        logger.error(f"Failed to confirm order {order_id}: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to confirm order"
        )
    
    # Invalidate cache
    cache_key = f"order:{order_id}"
    try:
        from cache import redis_client
        redis_client.delete(cache_key)
        logger.info(f"Cache invalidated for order: {order_id}")
    except Exception as e:
        logger.warning(f"Failed to invalidate cache: {e}")
    
    return {
        "orderId": order_id,
        "status": "CONFIRMED",
        "message": "Order confirmed successfully"
    }


@app.get(
    "/products", 
    response_model=ProductResponse,
    responses={
        200: {
            "description": "List of available products",
            "content": {
                "application/json": {
                    "example": {
                        "products": [
                            {"id": "p1", "name": "Product 1", "price": 50.0},
                            {"id": "p2", "name": "Product 2", "price": 20.5},
                            {"id": "p3", "name": "Product 3", "price": 30.0}
                        ]
                    }
                }
            }
        }
    }
)
def get_products():
    """
    Get all products with Redis caching (TTL 60 seconds).
    
    **Available Products:**
    - `p1`: Product 1 - $50.00
    - `p2`: Product 2 - $20.50
    - `p3`: Product 3 - $30.00
    
    **Caching:**
    - First call: Queries source and caches result
    - Subsequent calls (within 60s): Returns from Redis cache
    """
    cache_key = "products:v1"
    
    # Check cache
    cached_products = get_cache(cache_key)
    if cached_products:
        logger.info("Cache hit for products")
        return ProductResponse(**cached_products)
    
    logger.info("Cache miss for products, returning from source")
    
    # Return products
    products = [Product(**p) for p in MOCK_PRODUCTS]
    response_data = {"products": [p.dict() for p in products]}
    
    # Cache for 60 seconds
    set_cache(cache_key, response_data, ttl=60)
    
    return ProductResponse(**response_data)


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
