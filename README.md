Shoppulse E-commerce Analytics Backend Assessment

This project implements a multi-tenant, high-throughput analytics backend using Django and Django REST Framework, focusing on efficient data ingestion, transactional integrity, and low-memory operations suitable for millions of records.

Project Setup and Requirements

1. Prerequisites

Python 3.10+

Virtual Environment (venv recommended)

2. Setup Instructions

Clone the Repository (assuming project structure is shoppulse/):

# (Assuming cloning is done)
cd shoppulse


Install Dependencies:

pip install django djangorestframework faker tqdm requests
# Note: A full requirements.txt would list exact versions.


Run Migrations:

python manage.py makemigrations core
python manage.py migrate


Start Django Server:

python manage.py runserver


Data Generation and Performance Testing

The gen_dataset.py script generates the required synthetic data in chunks using Django's bulk_create for optimal local throughput.

1. Generate Initial Test Data

Run the generator using a small preset to populate the necessary Tenants and Products for API testing.

# Generates 10 Tenants, 1000 Products each, and reports throughput
python gen_dataset.py --tenants 10 --products 1000 --orders 1000


Note: The script includes throughput measurement (rows/sec) for orders/items insertion.

2. API 1 Performance Test (test_ingest.py)

This script verifies the Idempotency, Partial Failure Handling, and high-speed bulk insertion of the Order Ingest API.

Before Running: Ensure the MOCK_PRODUCT_ID and DEFAULT_TENANT_ID in test_ingest.py and core/views.py are updated with valid UUIDs that currently exist in your database (e.g., copy a Tenant_1 and associated Product PK).

# Run the test script in a separate terminal while the server is running
python test_ingest.py
