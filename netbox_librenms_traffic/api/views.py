from django.views import View
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from dcim.models import Device
from netbox_librenms_traffic.librenms_api import LibreNMSAPIClient
import logging

logger = logging.getLogger("netbox.plugins.netbox_librenms_traffic")

class LibreNMSTrafficDataView(View):
    """
    Proxy API view that fetches live interface graphs from LibreNMS and serves them as PNG.
    """
    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        device_name = request.GET.get("device")
        interface_name = request.GET.get("interface")
        time_range = request.GET.get("range", "1d")

        width_str = request.GET.get("width")
        height_str = request.GET.get("height")
        try:
            width = int(width_str) if width_str else 1350
        except ValueError:
            width = 1350
        try:
            height = int(height_str) if height_str else 350
        except ValueError:
            height = 350

        if not device_name or not interface_name:
            return JsonResponse(
                {"error": "Missing device or interface query parameters"},
                status=400
            )

        # Retrieve plugin configuration
        plugin_config = settings.PLUGINS_CONFIG.get("netbox_librenms_traffic", {})
        librenms_url = plugin_config.get("librenms_url")
        librenms_token = plugin_config.get("librenms_token")
        verify_ssl = plugin_config.get("verify_ssl", False)

        if not librenms_url or not librenms_token:
            return JsonResponse(
                {"error": "LibreNMS plugin configuration is missing or incomplete"},
                status=500
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
                return JsonResponse(
                    {"error": f"Device '{device_name}' (IP: {ip_address or 'None'}) not found in LibreNMS"},
                    status=404
                )

            # We use device_id (numeric) which is much more reliable in API endpoints
            device_id = device.get("device_id")
            if not device_id:
                # fallback to hostname (which is IP in LibreNMS)
                device_id = device.get("hostname")

            logger.info(f"Resolved LibreNMS device ID: {device_id} for '{device_name}'")

            # Check if the user is requesting JSON metadata instead of an image
            accept_header = request.headers.get("Accept", "")
            wants_json = request.GET.get("format") == "json" or "application/json" in accept_header

            if wants_json:
                try:
                    stats = client.get_port_statistics(device_id, interface_name)
                    if not stats:
                        # Return empty/zero stats if interface statistics are not found
                        stats = {
                            "in_bps": 0.0,
                            "out_bps": 0.0,
                            "port_id": None,
                            "ifSpeed": None
                        }
                    elif isinstance(stats, dict) and stats.get("error") == "port_not_found":
                        return JsonResponse(stats, status=404)
                    in_bps = stats["in_bps"]
                    out_bps = stats["out_bps"]
                    
                    response_data = {
                        "device": device_name,
                        "interface": interface_name,
                        "stats": {
                            "in": { "last": in_bps, "avg": in_bps, "max": in_bps },
                            "out": { "last": out_bps, "avg": out_bps, "max": out_bps }
                        },
                        "history": { "in": [], "out": [] }
                    }
                    return JsonResponse(response_data)
                except Exception as e:
                    logger.error(f"Failed to get port statistics for {device_name}/{interface_name}: {str(e)}")
                    return JsonResponse(
                        {"error": f"Failed to retrieve port statistics: {str(e)}"},
                        status=500
                    )

            # 3. Retrieve graph image from LibreNMS (try single-encoding first, fallback to double-encoding if needed)
            image_content = None
            content_type = "image/png"
            try:
                logger.info(f"Attempting single-encoded port graph query for: {interface_name}")
                image_content, content_type = client.get_port_graph_image(
                    device_identifier=device_id,
                    port_name=interface_name,
                    time_range=time_range,
                    double_encode=False,
                    width=width,
                    height=height
                )
            except Exception as single_err:
                logger.warning(f"Single encoded port graph query failed: {str(single_err)}. Retrying with double-encoding...")
                try:
                    image_content, content_type = client.get_port_graph_image(
                        device_identifier=device_id,
                        port_name=interface_name,
                        time_range=time_range,
                        double_encode=True,
                        width=width,
                        height=height
                    )
                except Exception as double_err:
                    err_msg = f"LibreNMS API failed for both single and double encoded routes. Single error: {str(single_err)}. Double error: {str(double_err)}"
                    logger.error(err_msg)
                    return JsonResponse(
                        {"error": err_msg},
                        status=500
                    )

            # 4. Return raw image response with correct content-type (e.g. image/png or image/svg+xml)
            return HttpResponse(image_content, content_type=content_type)

        except Exception as e:
            logger.exception(f"Failed to fetch LibreNMS graph: {str(e)}")
            return JsonResponse(
                {"error": f"Failed to retrieve graph from LibreNMS: {str(e)}"},
                status=500
            )
