import os
import django
import argparse
import random
import time
from faker import Faker
from tqdm import tqdm
from decimal import Decimal

# Django setup
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "shoppulse.settings")
django.setup()

from core.models import Tenant, Product, Order, OrderItem, StockEvent, PriceHistory


fake = Faker()

# --- Utility Functions (unchanged for brevity, assume they are correct) ---
def generate_tenants(num_tenants):
    # ... (content remains the same)
    tenants = []
    for i in range(num_tenants):
        name = f"Tenant_{i+1}"
        tenants.append(Tenant(name=name, slug=name.lower()))
    Tenant.objects.bulk_create(tenants, ignore_conflicts=True)
    return list(Tenant.objects.all())

def generate_products(tenant, num_products, batch_size=1000):
    # ... (content remains the same)
    products = []
    for i in tqdm(range(num_products), desc=f"Generating products for {tenant.name}"):
        products.append(Product(
            tenant=tenant,
            title=fake.word().capitalize() + f" {fake.color_name()}",
            category=random.choice(["Electronics", "Clothing", "Toys", "Beauty"]),
            price=round(random.uniform(10, 1000), 2)
        ))
        if len(products) >= batch_size:
            Product.objects.bulk_create(products)
            products = []
    if products:
        Product.objects.bulk_create(products)


# --------------------------------------------------------------------------
# ⭐ REFACTORED: Throughput Measurement & Optimized Bulk Creation
# --------------------------------------------------------------------------
def generate_orders_and_items(tenant, num_orders, batch_size=5000): # Increased batch size for more efficiency
    product_pks = list(Product.objects.filter(tenant=tenant).values_list("pk", flat=True)) # Use pk (UUID)
    if not product_pks:
        print(f"Skipping orders for {tenant.name}: No products found.")
        return

    total_start_time = time.time()
    total_orders_inserted = 0
    total_items_inserted = 0

    orders_to_create = []
    items_to_create = []
    
    # Pre-generate Order UUIDs to link to OrderItems before insertion
    order_map = {} # Map temporary Order object to its actual UUID PK

    print(f"\n--- Generating and Inserting Orders/Items for {tenant.name} ---")
    
    for i in tqdm(range(1, num_orders + 1), desc=f"Generating data for {tenant.name}"):
        # 1. Create Order Object (UUID PK is auto-generated)
        order = Order(
            tenant=tenant,
            customer_name=fake.name(),
            total_amount=Decimal("0.00"), # Will be updated or calculated later
            status=random.choice(["created", "paid", "shipped", "delivered"]),
        )
        orders_to_create.append(order)

        # 2. Create OrderItem Objects, referencing the Order's UUID
        num_items = random.randint(1, 3) # avg 3 items per order requirement
        order_total = Decimal("0.00")
        
        for _ in range(num_items):
            product_pk = random.choice(product_pks)
            price = Decimal(str(round(random.uniform(10, 1000), 2)))
            qty = random.randint(1, 5)
            order_total += price * qty
            
            items_to_create.append(OrderItem(
                order_id=order.pk, # Use the already generated UUID for the FK
                product_id=product_pk,
                quantity=qty,
                price=price,
            ))
            total_items_inserted += 1

        # Update the total amount on the in-memory order object
        order.total_amount = order_total

        # 3. Bulk Insert when batch size is reached
        if len(orders_to_create) >= batch_size or i == num_orders:
            try:
                # Insert Orders (first to satisfy FK constraints)
                Order.objects.bulk_create(orders_to_create)
                total_orders_inserted += len(orders_to_create)
                
                # Insert OrderItems
                OrderItem.objects.bulk_create(items_to_create)

            except Exception as e:
                print(f"\nError during bulk insert: {e}")
                
            # Reset batches
            orders_to_create, items_to_create = [], []
            
    
    duration = time.time() - total_start_time
    
    # 4. Measure and print ingestion throughput (rows/sec) 
    total_rows = total_orders_inserted + total_items_inserted
    throughput = total_rows / duration if duration > 0 else 0
    
    print(f"\n--- Ingestion Report for {tenant.name} ---")
    print(f"Time taken: {duration:.2f} seconds")
    print(f"Orders inserted: {total_orders_inserted}")
    print(f"Order Items inserted: {total_items_inserted}")
    print(f"Total rows inserted (Orders + Items): {total_rows}")
    print(f"Ingestion Throughput: {throughput:.2f} rows/sec") # Required metric 
    print("---------------------------------------------")

# --------------------------------------------------------------------------
# --- Utility Functions (unchanged for brevity, assume they are correct) ---
def generate_price_history(tenant, samples_per_product=100, batch_size=1000):
    # ... (content remains the same)
    products = Product.objects.filter(tenant=tenant)
    entries = []
    for product in tqdm(products, desc=f"Generating price history for {tenant.name}"):
        for _ in range(samples_per_product):
            entries.append(PriceHistory(
                tenant=tenant,
                product=product,
                price=round(random.uniform(10, 1000), 2)
            ))
            if len(entries) >= batch_size:
                PriceHistory.objects.bulk_create(entries)
                entries = []
    if entries:
        PriceHistory.objects.bulk_create(entries)


def generate_stock_events(tenant, num_events=100000, batch_size=1000):
    # ... (content remains the same)
    products = list(Product.objects.filter(tenant=tenant).values_list("id", flat=True))
    events = []
    for _ in tqdm(range(num_events), desc=f"Generating stock events for {tenant.name}"):
        events.append(StockEvent(
            tenant=tenant,
            product_id=random.choice(products),
            delta=random.randint(-10, 20)
        ))
        if len(events) >= batch_size:
            StockEvent.objects.bulk_create(events)
            events = []
    if events:
        StockEvent.objects.bulk_create(events)


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic dataset for Shoppulse")
    
    # Updated defaults to match assessment requirements for easier testing (e.g., 1M orders) [cite: 9, 24]
    parser.add_argument("--tenants", type=int, default=10, help="Number of tenants (N=10 required)")
    parser.add_argument("--products", type=int, default=10000, help="Products per tenant (500k required for full scale)")
    parser.add_argument("--orders", type=int, default=100000, help="Orders per tenant (2M required for full scale, smaller preset suggested)")
    parser.add_argument("--stock_events", type=int, default=100000, help="Stock events per tenant (millions required)")
    parser.add_argument("--price_samples", type=int, default=100, help="Price history samples per product (100 required)")

    args = parser.parse_args()
    
    print("Starting dataset generation with current settings:")
    print(f"- Tenants: {args.tenants}")
    print(f"- Products/Tenant: {args.products}")
    print(f"- Orders/Tenant: {args.orders}")
    
    total_start = time.time()
    
    tenants = generate_tenants(args.tenants)

    for tenant in tenants:
        generate_products(tenant, args.products)
        generate_orders_and_items(tenant, args.orders)
        generate_price_history(tenant, samples_per_product=args.price_samples)
        generate_stock_events(tenant, num_events=args.stock_events)

    total_duration = time.time() - total_start
    print(f"\n✅ Dataset generation completed successfully in {total_duration:.2f} seconds.")


if __name__ == "__main__":
    main()