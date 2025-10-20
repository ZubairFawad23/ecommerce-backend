from rest_framework import serializers

# Assuming core.models contains all your defined models (Product, Order, etc.)

class OrderItemIngestSerializer(serializers.Serializer):
    """Schema for a single OrderItem payload."""
    # product_id is assumed to be a UUID in the incoming payload
    product_id = serializers.UUIDField(help_text="UUID of the product being ordered.")
    quantity = serializers.IntegerField(min_value=1, help_text="Number of units ordered.")
    price = serializers.DecimalField(max_digits=10, decimal_places=2, help_text="Price per unit at the time of order.")

class BulkOrderIngestSerializer(serializers.Serializer):
    """Schema for a single Order record in the bulk file."""
    # Client may optionally provide a unique UUID for the order
    order_id = serializers.UUIDField(required=False, help_text="Optional client-side unique order ID.") 
    customer_name = serializers.CharField(max_length=255)
    customer_email = serializers.EmailField(required=False, help_text="Used for FTS simulation/customer identification.") 
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, help_text="Total calculated amount of the order.")
    # In a robust system, we would validate this against a list of allowed statuses
    status = serializers.CharField(max_length=50) 
    items = OrderItemIngestSerializer(many=True, help_text="List of line items for the order.")

class BulkIngestRequestSerializer(serializers.Serializer):
    """Wrapper for the entire payload when sending as application/json."""
    orders = BulkOrderIngestSerializer(many=True, help_text="Array of order objects to ingest.")