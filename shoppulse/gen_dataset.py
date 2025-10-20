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


def generate_tenants(num_tenants):
    tenants = []
    for i in range(num_tenants):
        name = f"Tenant_{i+1}"
        tenants.append(Tenant(name=name, slug=name.lower()))
    Tenant.objects.bulk_create(tenants, ignore_conflicts=True)
    return list(Tenant.objects.all())


def generate_products(tenant, num_products, batch_size=1000):
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


def generate_orders_and_items(tenant, num_orders, batch_size=1000):
    product_ids = list(Product.objects.filter(tenant=tenant).values_list("id", flat=True))
    orders = []
    order_items = []
    total_items = 0

    start_time = time.time()
    for i in tqdm(range(num_orders), desc=f"Generating orders for {tenant.name}"):
        order = Order(
            tenant=tenant,
            customer_name=fake.name(),
            total_amount=Decimal("0.00"),
            status=random.choice(["created", "paid", "shipped", "delivered"]),
        )
        orders.append(order)

        if len(orders) >= batch_size:
            Order.objects.bulk_create(orders)
            # Fetch the newly inserted orders
            latest_orders = list(Order.objects.order_by('-created_at')[:len(orders)])
            for o in latest_orders:
                num_items = random.randint(1, 3)
                total = Decimal("0.00")
                for _ in range(num_items):
                    product_id = random.choice(product_ids)
                    price = Decimal(str(round(random.uniform(10, 1000), 2)))
                    qty = random.randint(1, 5)
                    total += price * qty
                    order_items.append(OrderItem(
                        order=o,
                        product_id=product_id,
                        tenant=tenant,
                        quantity=qty,
                        price=price,
                    ))
                    total_items += 1
                o.total_amount = total
            Order.objects.bulk_update(latest_orders, ['total_amount'])
            OrderItem.objects.bulk_create(order_items)
            orders, order_items = [], []

    if orders:
        Order.objects.bulk_create(orders)

    duration = time.time() - start_time
    print(f"Inserted {num_orders} orders and {total_items} items for {tenant.name} in {duration:.2f}s")


def generate_price_history(tenant, samples_per_product=100, batch_size=1000):
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
    parser.add_argument("--tenants", type=int, default=2, help="Number of tenants")
    parser.add_argument("--products", type=int, default=1000, help="Products per tenant")
    parser.add_argument("--orders", type=int, default=1000, help="Orders per tenant")
    parser.add_argument("--stock_events", type=int, default=10000, help="Stock events per tenant")
    parser.add_argument("--price_samples", type=int, default=50, help="Price history samples per product")

    args = parser.parse_args()

    tenants = generate_tenants(args.tenants)

    for tenant in tenants:
        generate_products(tenant, args.products)
        generate_orders_and_items(tenant, args.orders)
        generate_price_history(tenant, samples_per_product=args.price_samples)
        generate_stock_events(tenant, num_events=args.stock_events)

    print("\n✅ Dataset generation completed successfully.")


if __name__ == "__main__":
    main()
