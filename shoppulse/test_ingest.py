import requests
import json
import uuid
import time
from datetime import datetime
import random 

# --- Configuration ---
# IMPORTANT: Update this URL if your Django server is running on a different port or host.
BASE_URL = "http://127.0.0.1:8000"
INGEST_ENDPOINT = f"{BASE_URL}/api/v1/ingest/orders/"

# ==============================================================================
# *** ACTION REQUIRED: FIX FOREIGN KEY ERROR ***
# Replace the placeholder below with a VALID Product ID from your core_product table.
# If this is not done, the test will correctly fail with FOREIGN KEY constraint failed.
# ==============================================================================
MOCK_PRODUCT_ID = "8784393103754b81ab474277a781827b" # EXAMPLE UUID - REPLACE THIS!
MOCK_TENANT_ID = "937942db-e55e-4a4f-9e49-81a7c44f02c7" 


def create_mock_payload(num_orders, insert_error=False):
    """Generates a list of mock order payloads, optionally including an invalid one."""
    orders = []
    
    for i in range(1, num_orders + 1):
        order_data = {
            "order_id": str(uuid.uuid4()),
            "customer_name": f"Customer {i}",
            "customer_email": f"customer{i}@example.com",
            # Pass Decimal as string for consistency with serializer validation
            "total_amount": f"{random.randint(100, 1000)}.00", 
            "status": random.choice(["created", "paid", "shipped"]),
            "items": [
                {
                    "product_id": MOCK_PRODUCT_ID,
                    "quantity": random.randint(1, 5),
                    "price": f"{random.randint(10, 100)}.00"
                }
            ]
        }
        orders.append(order_data)

    if insert_error:
        # Create a validation error (e.g., product_id is an invalid format)
        error_order_validation = {
            "order_id": str(uuid.uuid4()),
            "customer_name": "Bad Customer",
            "total_amount": "99.99",
            "status": "created",
            "items": [
                {
                    # Invalid UUID format for product_id
                    "product_id": "NOT_A_VALID_UUID", 
                    "quantity": 1,
                    "price": "50.00"
                }
            ]
        }
        # Insert the invalid row into the batch
        orders.insert(random.randint(0, len(orders)), error_order_validation)
        
    return {"orders": orders}


def run_test(key: str, payload: dict):
    """Executes the POST request and prints the result."""
    print(f"\n--- Running Test for Key: {key} ---")
    headers = {
        'Content-Type': 'application/json',
        'Idempotency-Key': key
    }
    
    try:
        start = time.time()
        # Use json.dumps to send the payload as JSON bytes
        response = requests.post(INGEST_ENDPOINT, headers=headers, data=json.dumps(payload))
        duration = time.time() - start
        
        print(f"Status Code: {response.status_code}")
        print(f"Time Taken: {duration:.2f}s")
        
        # Try to parse the response JSON
        try:
            summary = response.json()
            print("Response Summary:")
            print(json.dumps(summary, indent=2))
        except json.JSONDecodeError:
            print("Failed to decode response JSON.")
            print(f"Raw Response: {response.text[:200]}...")

    except requests.exceptions.ConnectionError:
        print(f"ERROR: Could not connect to {INGEST_ENDPOINT}. Is your Django server running?")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def main():
    """Runs a sequence of tests: First run, Partial Success run, and Idempotency hit."""
    
    # 1. Initial successful run
    idempotency_key_1 = str(uuid.uuid4())
    payload_1 = create_mock_payload(num_orders=10)
    print("--- Test 1: Initial Successful Ingestion ---")
    run_test(idempotency_key_1, payload_1)

    # 2. Idempotency test (re-run the same request)
    print("\n\n--- Test 2: Idempotency Hit (Re-run Test 1) ---")
    print("Expected: Status 200, same row counts, Time < 0.05s.")
    run_test(idempotency_key_1, payload_1)

    # 3. Test with a partial failure (client-side validation error)
    idempotency_key_3 = str(uuid.uuid4())
    payload_3 = create_mock_payload(num_orders=10, insert_error=True)
    print("\n\n--- Test 3: Partial Failure Test ---")
    print("Expected: Status 200, rows_failed > 0 due to validation, detailed error message.")
    run_test(idempotency_key_3, payload_3)


if __name__ == "__main__":
    # Ensure you have 'requests' installed: pip install requests
    main()