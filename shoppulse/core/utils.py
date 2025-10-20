import json
import time
import uuid
import hashlib
from django.db import IntegrityError, transaction
from django.db import models 

from core.models import IdempotencyKey 


def generate_request_hash(data: dict) -> str:
    """
    Generates a consistent hash of the request data for validation.
    Ensures that complex data types (Decimal, UUID) are safely and consistently 
    serialized to a string before hashing, making the hash repeatable for identical payloads.
    """
    # Use default=str and sort_keys=True for consistent byte representation.
    data_string = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(data_string.encode('utf-8')).hexdigest()


def handle_idempotency(idempotency_key: str, request_data: dict):
    """
    Checks for an existing key or reserves a new one transactionally.
    Returns (result, status) where result is IdempotencyKey object or response metadata.
    """
    if not idempotency_key:
        return None, 'NO_KEY'

    # 1. Check if key exists
    try:
        existing_key = IdempotencyKey.objects.get(key=idempotency_key)
        
        # Verify payload hash to ensure client isn't using the key for different data
        current_hash = generate_request_hash(request_data)
        
        # CRITICAL FIX: If the payload is identical, return the HIT status.
        if current_hash != existing_key.metadata.get('request_hash'):
             return {'error': 'Idempotency key reused with different payload'}, 'CONFLICT'
        
        # If hash matches, return the stored successful response metadata
        return existing_key.metadata, 'HIT' 

    except IdempotencyKey.DoesNotExist:
        pass # Proceed to attempt reservation

    # 2. Reserve the key before starting processing (Transactional Path)
    try:
        with transaction.atomic():
            new_key = IdempotencyKey.objects.create(
                key=idempotency_key,
                metadata={
                    'status': 'PENDING',
                    'request_hash': generate_request_hash(request_data)
                }
            )
        return new_key, 'MISS'
    except IntegrityError:
        # Key was created by a concurrent request, wait briefly and retry the lookup
        time.sleep(0.1) 
        return handle_idempotency(idempotency_key, request_data)


def finalize_idempotency(idempotency_key_instance, response_summary: dict):
    """Updates the IdempotencyKey with the final response/summary after success."""
    # Check if instance is an IdempotencyKey object
    if idempotency_key_instance and isinstance(idempotency_key_instance, models.Model): 
        # Set the final status and response metadata
        response_summary['status'] = 'COMPLETED'
        idempotency_key_instance.metadata = response_summary
        idempotency_key_instance.save()