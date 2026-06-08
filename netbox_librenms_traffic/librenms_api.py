import requests
import urllib3
import logging
from urllib.parse import quote

logger = logging.getLogger("netbox.plugins.netbox_librenms_traffic")

class LibreNMSAPIClient:
    """
    Client for interacting with the LibreNMS API.
    """
    def __init__(self, url, token, verify_ssl=False):
        self.url = url.rstrip('/')
        self.token = token
        self.verify_ssl = verify_ssl
        self.headers = {
            "X-Auth-Token": self.token,
            "Accept": "application/json"
        }
        if not self.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def get_device_by_ip_or_name(self, device_name, ip_address):
        """
        Look up a device in LibreNMS using the IP address or name.
        """
        # 1. Try querying by IP directly first
        if ip_address:
            try:
                url = f"{self.url}/api/v0/devices/{ip_address}"
                logger.info(f"Querying LibreNMS device directly by IP: {url}")
                r = requests.get(url, headers=self.headers, verify=self.verify_ssl, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    devices = data.get("devices", [])
                    if devices:
                        logger.info(f"Found LibreNMS device directly by IP: {ip_address}")
                        return devices[0]
            except Exception as e:
                logger.warning(f"Failed direct lookup by IP {ip_address}: {str(e)}")

        # 2. Try querying by name directly
        if device_name:
            try:
                url = f"{self.url}/api/v0/devices/{quote(device_name, safe='')}"
                logger.info(f"Querying LibreNMS device directly by name: {url}")
                r = requests.get(url, headers=self.headers, verify=self.verify_ssl, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    devices = data.get("devices", [])
                    if devices:
                        logger.info(f"Found LibreNMS device directly by name: {device_name}")
                        return devices[0]
            except Exception as e:
                logger.warning(f"Failed direct lookup by name {device_name}: {str(e)}")

        # 3. Fallback: Retrieve all devices and scan them
        try:
            url = f"{self.url}/api/v0/devices"
            logger.info(f"Scanning all LibreNMS devices from: {url}")
            r = requests.get(url, headers=self.headers, verify=self.verify_ssl, timeout=15)
            r.raise_for_status()
            data = r.json()
            devices = data.get("devices", [])
            
            for dev in devices:
                hostname = dev.get("hostname", "")
                sysname = dev.get("sysName", "")
                display = dev.get("display", "")
                
                # Match IP address
                if ip_address and hostname == ip_address:
                    logger.info(f"Matched LibreNMS device by IP scan: {hostname}")
                    return dev
                    
                # Match device name (case-insensitive)
                if device_name:
                    name_lower = device_name.lower()
                    if (hostname.lower() == name_lower or 
                        sysname.lower() == name_lower or 
                        display.lower() == name_lower):
                        logger.info(f"Matched LibreNMS device by name scan: {hostname} ({sysname})")
                        return dev
                        
        except Exception as e:
            logger.error(f"Failed to scan LibreNMS devices: {str(e)}")
            
        return None

    def get_port_graph_image(self, device_identifier, port_name, time_range, width=1100, height=300):
        """
        Fetch the raw RRD graph image from LibreNMS.
        """
        # Map range to LibreNMS 'from' style
        range_map = {
            "1d": "-1d",
            "2d": "-2d",
            "7d": "-7d",
            "30d": "-30d"
        }
        from_time = range_map.get(time_range, "-1d")
        
        # Double URL-encode the port name to be completely safe with slashes
        # Standard: /api/v0/devices/:device/ports/:port/port_bits
        encoded_port = quote(port_name, safe='')
        url = f"{self.url}/api/v0/devices/{quote(str(device_identifier), safe='')}/ports/{encoded_port}/port_bits"
        
        params = {
            "from": from_time,
            "width": width,
            "height": height
        }
        
        logger.info(f"Requesting graph image from LibreNMS: {url} with params {params}")
        r = requests.get(url, headers=self.headers, params=params, verify=self.verify_ssl, timeout=15)
        r.raise_for_status()
        return r.content
