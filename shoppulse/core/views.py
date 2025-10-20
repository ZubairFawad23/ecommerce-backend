from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import connection, transaction
from django.conf import settings
import time
import uuid
from datetime import datetime

# Import models for UUID generation and checking
from core.models import Order 
# Import your serializers and utils
from .serializers import BulkOrderIngestSerializer
from .utils import handle_idempotency, finalize_idempotency 


# NOTE: Placeholder Tenant ID. ENSURE this matches an existing Tenant in your DB!
DEFAULT_TENANT_ID = uuid.UUID('937942db-e55e-4a4f-9e49-81a7c44f02c7')


class OrderIngestView(APIView):
    """
    POST /api/v1/ingest/orders/
    Handles chunked, idempotent bulk ingestion of order records.
    Uses raw SQL executemany for high throughput.
    """
    
    def post(self, request, *args, **kwargs):
        tenant_id = DEFAULT_TENANT_ID
        idempotency_key = request.META.get('HTTP_IDEMPOTENCY_KEY')
        
        start_time = time.time()
        rows_received = 0
        rows_inserted = 0
        rows_failed = 0
        errors_metadata = []

        # --- 1. Handle Idempotency ---
        key_or_response, status = handle_idempotency(idempotency_key, request.data)

        if status == 'HIT':
            return Response(key_or_response, status=200) # Idempotent hit: return cached result
        
        if status == 'CONFLICT':
            return Response(key_or_response, status=409) # Key conflict: different payload

        key_instance = key_or_response # This is the PENDING IdempotencyKey object

        # --- 2. Stream and Process Payload (Simplified for JSON list) ---
        data_stream = request.data.get('orders', request.data) # Assume 'orders' list or root list
        
        batch_size = 5000
        order_batch_data = []
        item_batch_data = []
        
        # Raw SQL templates for sqlite3 (using ? placeholders)
        ORDER_SQL = """INSERT INTO core_order (id, tenant_id, customer_name, total_amount, status, created_at) 
                       VALUES (?, ?, ?, ?, ?, ?);"""
        ITEM_SQL = """INSERT INTO core_orderitem (order_id, product_id, quantity, price) 
                      VALUES (?, ?, ?, ?);"""
        
        tenant_id_str = str(tenant_id)

        for row in data_stream: 
            rows_received += 1
            serializer = BulkOrderIngestSerializer(data=row) 

            if serializer.is_valid():
                validated_data = serializer.validated_data
                
                order_id = str(validated_data.get('order_id') or uuid.uuid4())
                current_time = datetime.now()
                
                # Prepare Order Data
                order_batch_data.append((
                    order_id,
                    tenant_id_str, # Passed as string for raw SQL
                    validated_data['customer_name'],
                    validated_data['total_amount'],
                    validated_data['status'],
                    current_time.isoformat(), # Use ISO format for datetime insertion
                ))
                
                # Prepare Item Data
                for item in validated_data['items']:
                    item_batch_data.append((
                        order_id,
                        str(item['product_id']), # Must be cast to string if stored as text
                        item['quantity'],
                        item['price']
                    ))
                
                if len(order_batch_data) >= batch_size:
                    # Execute bulk insert for the batch transactionally
                    try:
                        with transaction.atomic():
                            with connection.cursor() as cursor:
                                cursor.executemany(ORDER_SQL, order_batch_data)
                                cursor.executemany(ITEM_SQL, item_batch_data)
                            rows_inserted += len(order_batch_data)
                    except Exception as e:
                        # Database error on the batch. Record failure.
                        rows_failed += len(order_batch_data)
                        errors_metadata.append({'type': 'Batch DB Error', 'detail': f"Batch starting at row {rows_received - len(order_batch_data)} failed: {str(e)}"})

                    order_batch_data, item_batch_data = [], []

            else:
                # Validation failed (partial success)
                rows_failed += 1
                errors_metadata.append({'row_number': rows_received, 'errors': serializer.errors})

        # --- 3. Process remaining batch (if any) ---
        if order_batch_data:
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.executemany(ORDER_SQL, order_batch_data)
                        cursor.executemany(ITEM_SQL, item_batch_data)
                    rows_inserted += len(order_batch_data)
            except Exception as e:
                rows_failed += len(order_batch_data)
                errors_metadata.append({'type': 'Final Batch DB Error', 'detail': f"Final batch failed: {str(e)}"})

        # --- 4. Final Response and Idempotency Finalization ---
        response_summary = {
            "rows_received": rows_received,
            "rows_inserted": rows_inserted,
            "rows_failed": rows_failed,
            "processing_time": f"{time.time() - start_time:.2f}s",
            "idempotency_key": idempotency_key,
            "errors": errors_metadata,
        }
        
        # Only finalize the key if an instance exists
        if key_instance:
            finalize_idempotency(key_instance, response_summary)

        status_code = 200 if rows_inserted > 0 else 400
        return Response(response_summary, status=status_code)