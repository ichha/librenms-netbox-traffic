from django.urls import path
from .views import ZabbixTrafficDataView

urlpatterns = [
    path('traffic-data/', ZabbixTrafficDataView.as_view(), name='traffic_data'),
]
