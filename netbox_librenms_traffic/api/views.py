from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse
from django.conf import settings
from dcim.models import Device
from netbox_librenms_traffic.librenms_api import LibreNMSAPIClient
import logging

logger = logging.getLogger("netbox.plugins.netbox_librenms_traffic")

class LibreNMSTrafficDataView(APIView):
    """
    Proxy API view that fetches live interface graphs from LibreNMS and serves them as PNG.
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
        plugin_config = settings.PLUGINS_CONFIG.get("netbox_librenms_traffic", {})
        librenms_url = plugin_config.get("librenms_url")
        librenms_token = plugin_config.get("librenms_token")
        verify_ssl = plugin_config.get("verify_ssl", False)

        if not librenms_url or not librenms_token:
            return Response(
                {"error": "LibreNMS plugin configuration is missing or incomplete"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # 1. Look up NetBox device to extract primary IPv4 address
        ip_address = None
        try:
            nb_device = Device.objects.get(name=device_name)
            if nb_device.primary_ip4:
                ip_address = str(nb_device.primary_ip4.address.ip)
                logger.info(f"Resolved NetBox device '{device_name}' to primary IP: {ip_address}")
            else:
                logger.warning(f"NetBox device '{device_name}' has no primary IPv4 address configured")
        except Device.DoesNotExist:
            logger.warning(f"Device '{device_name}' not found in NetBox database")

        try:
            client = LibreNMSAPIClient(librenms_url, librenms_token, verify_ssl)
            
            # 2. Match device in LibreNMS using NetBox IP or device name
            device = client.get_device_by_ip_or_name(device_name, ip_address)
            if not device:
                logger.error(f"Device '{device_name}' (IP: {ip_address}) could not be resolved in LibreNMS")
                return Response(
                    {"error": f"Device '{device_name}' (IP: {ip_address or 'None'}) not found in LibreNMS"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # We use device_id (numeric) which is much more reliable in API endpoints
            device_id = device.get("device_id")
            if not device_id:
                # fallback to hostname (which is IP in LibreNMS)
                device_id = device.get("hostname")

            logger.info(f"Resolved LibreNMS device ID: {device_id} for '{device_name}'")

            # 3. Retrieve graph image from LibreNMS (try single-encoding first, fallback to double-encoding if needed)
            image_content = None
            try:
                logger.info(f"Attempting single-encoded port graph query for: {interface_name}")
                image_content = client.get_port_graph_image(
                    device_identifier=device_id,
                    port_name=interface_name,
                    time_range=time_range,
                    double_encode=False,
                    width=1100,
                    height=300
                )
            except Exception as single_err:
                logger.warning(f"Single encoded port graph query failed: {str(single_err)}. Retrying with double-encoding...")
                try:
                    image_content = client.get_port_graph_image(
                        device_identifier=device_id,
                        port_name=interface_name,
                        time_range=time_range,
                        double_encode=True,
                        width=1100,
                        height=300
                    )
                except Exception as double_err:
                    err_msg = f"LibreNMS API failed for both single and double encoded routes. Single error: {str(single_err)}. Double error: {str(double_err)}"
                    logger.error(err_msg)
                    return Response(
                        {"error": err_msg},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

            # 4. Return raw PNG image response
            return HttpResponse(image_content, content_type="image/png")

        except Exception as e:
            logger.exception(f"Failed to fetch LibreNMS graph: {str(e)}")
            return Response(
                {"error": f"Failed to retrieve graph from LibreNMS: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
