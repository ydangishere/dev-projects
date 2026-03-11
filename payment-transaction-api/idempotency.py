import hashlib
import json
import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database import IdempotencyKey, IdempotencyStatus
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


def calculate_request_hash(body: dict) -> str:
    """Calculate hash of request body for idempotency check"""
    body_str = json.dumps(body, sort_keys=True)
    return hashlib.sha256(body_str.encode()).hexdigest()


def handle_idempotency(
    db: Session,
    idempotency_key: str,
    request_body: dict
) -> tuple[bool, dict | None]:
    """
    Handle idempotency check and insert.
    Returns: (is_replay, response_body_dict)
    - is_replay=True: return cached response
    - is_replay=False: proceed with new request
    """
    request_hash = calculate_request_hash(request_body)
    
    # Try to insert new idempotency key
    new_key = IdempotencyKey(
        key=idempotency_key,
        request_hash=request_hash,
        status=IdempotencyStatus.IN_PROGRESS
    )
    
    try:
        db.add(new_key)
        db.commit()
        # Insert successful - this is a new request
        logger.info(f"New idempotency key created: {idempotency_key[:16]}...")
        return False, None
    except IntegrityError:
        # Key already exists - check status and hash
        db.rollback()
        logger.info(f"Idempotency key exists: {idempotency_key[:16]}..., checking status")
        existing_key = db.query(IdempotencyKey).filter(
            IdempotencyKey.key == idempotency_key
        ).first()
        
        if not existing_key:
            # Should not happen, but handle edge case
            logger.error(f"IntegrityError but key not found: {idempotency_key[:16]}...")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Idempotency key conflict"
            )
        
        # Check if request hash matches
        if existing_key.request_hash != request_hash:
            logger.warning(f"Key reuse with different body: {idempotency_key[:16]}...")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency-Key reused with different request body"
            )
        
        # Check status
        if existing_key.status == IdempotencyStatus.COMPLETED:
            # Return cached response
            logger.info(f"Returning cached response for completed key: {idempotency_key[:16]}...")
            if existing_key.response_body:
                response_dict = json.loads(existing_key.response_body)
                response_dict["idempotentReplay"] = True
                return True, response_dict
            else:
                # Should not happen, but handle gracefully
                logger.error(f"Completed key missing response body: {idempotency_key[:16]}...")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Completed idempotency key missing response body"
                )
        elif existing_key.status == IdempotencyStatus.IN_PROGRESS:
            # Another request is processing - return 425
            logger.warning(f"Key still in progress: {idempotency_key[:16]}...")
            raise HTTPException(
                status_code=status.HTTP_425_TOO_EARLY,
                detail="Request with same Idempotency-Key is still being processed"
            )
    
    return False, None


def save_idempotency_response(
    db: Session,
    idempotency_key: str,
    response_body: dict
):
    """Save response body to idempotency key record"""
    try:
        existing_key = db.query(IdempotencyKey).filter(
            IdempotencyKey.key == idempotency_key
        ).first()
        
        if existing_key:
            existing_key.status = IdempotencyStatus.COMPLETED
            existing_key.response_body = json.dumps(response_body)
            db.commit()
            logger.info(f"Saved idempotency response for key: {idempotency_key[:16]}...")
        else:
            logger.warning(f"Idempotency key not found when saving response: {idempotency_key[:16]}...")
    except Exception as e:
        logger.error(f"Failed to save idempotency response: {e}", exc_info=True)
        db.rollback()
        raise
