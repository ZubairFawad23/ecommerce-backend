hoppulse E-commerce Analytics Backend Assessment

This project delivers a multi-tenant backend solution designed for high-throughput e-commerce analytics. Built with Django and Django REST Framework, the architecture prioritizes efficient data ingestion, transactional integrity, and low-memory consumption to handle the scale required for millions of records, meeting the core requirements of the assessment.

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

The foundational gen_dataset.py script is implemented to efficiently generate the required synthetic data. It uses Django's bulk_create method and batching to insert large volumes of data (Tenants, Products, Orders) and includes reporting on the achieved ingestion throughput (rows/sec). The script supports adjustable command-line arguments to simulate the target scale (10 tenants, millions of records) or smaller presets for quick local testing. The project also includes test_ingest.py, a dedicated performance script utilizing the requests library to specifically benchmark the Bulk Ingest API's throughput and verify the idempotency mechanism.

Architectural Design and Optimizations

The data model uses UUIDs as primary keys for all core entities (Tenant, Product, Order), which is a prerequisite for horizontal scaling and database sharding in a high-scale environment. Multi-tenancy is rigidly enforced via Foreign Key relationships on all transactional tables, ensuring data isolation and simplifying tenant-scoped queries. For the high-volume API implementations, several key performance choices were made. The Bulk Order Ingest API leverages a custom NDJSONStreamParser to read the request body line-by-line, achieving a near-zero memory footprint on the server, which directly satisfies the low-memory budget target for streaming operations. Furthermore, insertion speed is maximized by using transactional raw SQL (connection.cursor().executemany) to bypass the ORM layer, providing the highest possible batch throughput. Finally, compound indexes and a transactional IdempotencyKey reservation system ensure data integrity, query speed for analytics (e.g., filtering by tenant_id and created_at), and reliable protection against webhook retries.

Production Migration Plan (PostgreSQL)

Migrating this platform from SQLite to a scalable RDBMS like PostgreSQL requires several critical changes and optimizations to handle the target scale of 200 million+ records. The fastest possible ingestion will be achieved by replacing the Python executemany calls with the native PostgreSQL COPY FROM command. The schema must implement Declarative Table Partitioning on the Order and StockEvent tables, using range partitioning on the created_at field to dramatically improve range-based query performance (analytics) and simplify GDPR-related data deletion. Additionally, analytical requirements like FTS will be supported using PostgreSQL's native tsvector with a GIN index, and approximate aggregations will utilize the hll (HyperLogLog) extension for highly efficient unique counts. Estimated hardware for this scale includes a high-IOPS provisioned SSD, a 16 vCPU/128 GB RAM database server, and multiple load-balanced application instances to sustain high concurrency and low latency.

Blocked due to github/libraries/documentation not being availaible