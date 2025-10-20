from django.db import models
import uuid


class Tenant(models.Model):
    """Represents a store or client using Shoppulse."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    """Product belonging to a tenant."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='products')
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=100, blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['tenant', 'category']),
        ]

    def __str__(self):
        return self.title


class Order(models.Model):
    """Customer order."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='orders')
    customer_name = models.CharField(max_length=255)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=50, default='created', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['tenant', 'status']),
        ]

    def __str__(self):
        return f"Order {self.id}"


class OrderItem(models.Model):
    """Line items of each order."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.title} x {self.quantity}"


class StockEvent(models.Model):
    """Tracks changes in stock."""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    delta = models.IntegerField()  # positive or negative change
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'product', 'created_at']),
        ]

    def __str__(self):
        return f"Stock change {self.delta} for {self.product.title}"


class IdempotencyKey(models.Model):
    """
    Tracks processed idempotent requests.
    Ensures repeated requests with the same key are safely ignored.
    """
    key = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
    class Meta:
        indexes = [models.Index(fields=['key'])]


    def __str__(self):
        return self.key
