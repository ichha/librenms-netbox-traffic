from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from netbox_zabbix2_traffic.zabbix_api import ZabbixAPIClient
import time
import logging

logger = logging.getLogger("netbox.plugins.netbox_zabbix2_traffic")

class ZabbixTrafficDataView(APIView):
    """
    Asynchronous proxy API view that fetches live history/trends from Zabbix.
    """
    permission_classes = [IsAuthenticated]
    def get(self, request):
        device_name = request.query_params.get("device")
        interface_name = request.query_params.get("interface")
        time_range = request.query_params.get("range", "1d")

        if not device_name or not interface_name:
            return Response(
                {"error": "Missing device or interface query parameters"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Retrieve plugin configuration
        plugin_config = settings.PLUGINS_CONFIG.get("netbox_zabbix2_traffic", {})
        zabbix_url = plugin_config.get("zabbix_url")
        zabbix_token = plugin_config.get("zabbix_token")
        verify_ssl = plugin_config.get("verify_ssl", False)

        if not zabbix_url or not zabbix_token:
            return Response(
                {"error": "Zabbix plugin configuration is missing or incomplete"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        try:
            client = ZabbixAPIClient(zabbix_url, zabbix_token, verify_ssl)
            
            # 1. Get host
            host = client.get_host(device_name)
            if not host:
                logger.warning(f"Device '{device_name}' not found in Zabbix")
                return Response(
                    {"error": f"Device '{device_name}' not found in Zabbix. Please verify hostname naming convention matches exactly."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # 2. Get interface items
            in_item, out_item = client.get_interface_items(host["hostid"], interface_name)
            if not in_item and not out_item:
                logger.warning(f"Traffic items not found for interface '{interface_name}' on Zabbix host '{device_name}'")
                return Response(
                    {"error": f"Interface '{interface_name}' traffic monitoring items not found in Zabbix host '{device_name}'"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # 3. Determine time boundaries
            now = int(time.time())
            if time_range == "2d":
                time_from = now - (2 * 86400)
            elif time_range == "7d":
                time_from = now - (7 * 86400)
            elif time_range == "30d":
                time_from = now - (30 * 86400)
            else:  # '1d' default
                time_from = now - 86400

            # 4. Fetch history for matched items
            in_history = []
            out_history = []

            if in_item:
                in_history = client.get_item_history(
                    in_item["itemid"],
                    in_item["value_type"],
                    time_from,
                    now
                )
            if out_item:
                out_history = client.get_item_history(
                    out_item["itemid"],
                    out_item["value_type"],
                    time_from,
                    now
                )

            # 5. Format datasets for Chart.js (Unix ms timestamp coordinate format)
            in_data = [{"x": int(d["clock"]) * 1000, "y": float(d["value"])} for d in in_history]
            out_data = [{"x": int(d["clock"]) * 1000, "y": float(d["value"])} for d in out_history]

            # 6. Compute statistics (last, min, avg, max)
            in_values = [d["y"] for d in in_data]
            out_values = [d["y"] for d in out_data]

            stats = {
                "in": {
                    "last": in_values[-1] if in_values else 0,
                    "min": min(in_values) if in_values else 0,
                    "max": max(in_values) if in_values else 0,
                    "avg": sum(in_values) / len(in_values) if in_values else 0
                },
                "out": {
                    "last": out_values[-1] if out_values else 0,
                    "min": min(out_values) if out_values else 0,
                    "max": max(out_values) if out_values else 0,
                    "avg": sum(out_values) / len(out_values) if out_values else 0
                }
            }

            return Response({
                "device": device_name,
                "interface": interface_name,
                "in_item": {
                    "name": in_item.get("name") if in_item else None,
                    "key": in_item.get("key_") if in_item else None,
                    "units": in_item.get("units") if in_item else "bps"
                },
                "out_item": {
                    "name": out_item.get("name") if out_item else None,
                    "key": out_item.get("key_") if out_item else None,
                    "units": out_item.get("units") if out_item else "bps"
                },
                "stats": stats,
                "history": {
                    "in": in_data,
                    "out": out_data
                }
            })

        except Exception as e:
            logger.error(f"Failed to fetch traffic data: {str(e)}")
            return Response(
                {"error": f"Failed to retrieve data from Zabbix: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
