from django.urls import path
from .views import LibreNMSTrafficDataView

urlpatterns = [
    path('traffic-data/', LibreNMSTrafficDataView.as_view(), name='traffic_data'),
]
