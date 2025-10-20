from django.urls import path
from .views import OrderIngestView # Import the view you just created

urlpatterns = [
    # API 1: Bulk ingest - chunked, idempotent
    # POST /api/v1/ingest/orders/
    path('ingest/orders/', OrderIngestView.as_view(), name='bulk-ingest-orders'),
    
    # Other APIs (Search, Metrics, etc.) will be added here
]
