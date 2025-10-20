from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser # Needed for data handling

from django.db import connection, transaction
from django.conf import settings
from datetime import datetime
import time
import uuid

# Import your serializers and utils
from .serializers import BulkOrderIngestSerializer
from .utils import handle_idempotency, finalize_idempotency 
# Import Order for UUID generation (if order_id is not provided)
from core.models import Order 


# Placeholder for Tenant ID (MUST be obtained from authentication in a production app)
# Assuming a default tenant exists for testing
DEFAULT_TENANT_ID = uuid.UUID('00000000-0000-0000-0000-000000000001')


class OrderIngestView(APIView):
    """
    POST /api/v1/ingest/orders/
    Handles chunked, idempotent bulk ingestion of order records via raw SQL.
    Supports application/json (assuming 'orders' key is used).
    """
    # Define parsers to handle different content types (simplified here)
    parser_classes = [JSONParser, FormParser, MultiPartParser] 

    
    def post(self, request, *args, **kwargs):
        tenant_id = DEFAULT_TENANT_ID
        idempotency_key = request.META.get('HTTP_IDEMPOTENCY_KEY')
        
        start_time = time.time()
        rows_received = 0
        rows_inserted = 0
        rows_failed = 0
        errors_metadata = []

        # --- 1. Handle Idempotency ---
        # Assuming the entire request payload is the data for hashing
        key_or_response, status = handle_idempotency(idempotency_key, request.data)

        if status == 'HIT':
            return Response(key_or_response, status=200) # Return cached result
        if status == 'CONFLICT':
            return Response(key_or_response, status=409) # Key reused with different data
        
        key_instance = key_or_response # This is the PENDING IdempotencyKey object

        # --- 2. Extract Data Stream ---
        # For JSON: check if the data is a list of orders directly or under an 'orders' key
        if isinstance(request.data, list):
            data_stream = request.data
        else:
            data_stream = request.data.get('orders', [])

        if not data_stream:
            return Response({"error": "No order data found in payload."}, status=400)
        
        # --- 3. Process, Validate, and Batch Insert ---
        batch_size = 5000 # Optimal batch size depends on your database
        order_batch_data = []
        item_batch_data = []
        
        # Raw SQL templates for sqlite3/Postgres (using ? or %s placeholders)
        # Using ? for compatibility with sqlite3's executemany
        ORDER_SQL = """INSERT INTO core_order (id, tenant_id, customer_name, total_amount, status, created_at) 
                       VALUES (?, ?, ?, ?, ?, ?);"""
        ITEM_SQL = """INSERT INTO core_orderitem (order_id, product_id, quantity, price) 
                      VALUES (?, ?, ?, ?);"""
        
        # Note: In a production system, complex validation (e.g., product_id existence) 
        # should happen here to ensure FK integrity.
        
        for row in data_stream: 
            rows_received += 1
            serializer = BulkOrderIngestSerializer(data=row) 

            if serializer.is_valid():
                validated_data = serializer.validated_data
                
                # Ensure UUIDs are handled correctly as strings for SQL parameters
                order_id = str(validated_data.get('order_id') or uuid.uuid4())
                current_time = datetime.now().isoformat()
                
                # Prepare Order Data tuple
                order_batch_data.append((
                    order_id,
                    str(tenant_id), 
                    validated_data['customer_name'],
                    validated_data['total_amount'],
                    validated_data['status'],
                    current_time, 
                ))
                
                # Prepare Item Data tuples
                for item in validated_data['items']:
                    item_batch_data.append((
                        order_id,
                        str(item['product_id']),
                        item['quantity'],
                        item['price']
                    ))
                
                if len(order_batch_data) >= batch_size:
                    # Execute bulk insert for the batch transactionally
                    try:
                        with transaction.atomic():
                            with connection.cursor() as cursor:
                                # Insert Orders first to satisfy foreign key constraints
                                cursor.executemany(ORDER_SQL, order_batch_data)
                                cursor.executemany(ITEM_SQL, item_batch_data)
                            rows_inserted += len(order_batch_data)
                    except Exception as e:
                        # Log and handle database error for the whole batch (partial failure)
                        rows_failed += len(order_batch_data)
                        errors_metadata.append({
                            'type': 'Batch DB Error', 
                            'detail': f"Batch starting at row {rows_received - len(order_batch_data)} failed: {str(e)}",
                            'first_order_id': order_batch_data[0][0]
                        })

                    # Reset batches after insert or failure
                    order_batch_data, item_batch_data = [], []

            else:
                # Validation failed, record error metadata (partial success)
                rows_failed += 1
                errors_metadata.append({'row_number': rows_received, 'errors': serializer.errors})

        # --- 4. Process remaining batch (if any) ---
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

        # --- 5. Final Response and Idempotency Finalization ---
        response_summary = {
            "rows_received": rows_received,
            "rows_inserted": rows_inserted,
            "rows_failed": rows_failed,
            "processing_time": f"{time.time() - start_time:.2f}s",
            "idempotency_key": idempotency_key,
            # Return limited error details unless in debug mode
            "errors": errors_metadata if settings.DEBUG or rows_failed > 0 else [], 
        }
        
        # Only finalize the key if a key was provided
        if key_instance:
            finalize_idempotency(key_instance, response_summary)

        status_code = 200 if rows_inserted > 0 else 400
        return Response(response_summary, status=status_code)
