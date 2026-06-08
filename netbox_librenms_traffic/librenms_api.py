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

    def get_port_graph_image(self, device_identifier, port_name, time_range, double_encode=False, width=1100, height=300):
        """
        Fetch the raw RRD graph image from LibreNMS.
        """
        range_map = {
            "1d": "-1d",
            "2d": "-2d",
            "7d": "-7d",
            "30d": "-30d",
            "1y": "-1y"
        }
        from_time = range_map.get(time_range, "-1d")
        
        # URL-encode the port name (double-encode if double_encode is True)
        encoded_port = quote(port_name, safe='')
        if double_encode:
            encoded_port = quote(encoded_port, safe='')
            
        url = f"{self.url}/api/v0/devices/{quote(str(device_identifier), safe='')}/ports/{encoded_port}/port_bits"
        
        params = {
            "from": from_time,
            "width": width,
            "height": height
        }
        
        logger.info(f"Requesting graph image from LibreNMS (double_encode={double_encode}): {url} with params {params}")
        r = requests.get(url, headers=self.headers, params=params, verify=self.verify_ssl, timeout=15)
        r.raise_for_status()
        
        # Check if LibreNMS returned a JSON error response instead of an image
        content_type = r.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            try:
                data = r.json()
                message = data.get("message") or data.get("error") or "Unknown LibreNMS API error"
                raise Exception(f"LibreNMS API Error: {message}")
            except ValueError:
                raise Exception(f"LibreNMS API returned JSON with non-JSON body: {r.text[:200]}")
                
        # Validate that the content is a valid image (e.g. image/png or image/svg+xml)
        if not r.content:
            raise Exception("LibreNMS API returned an empty response (0 bytes).")
            
        if "image/" not in content_type:
            # The response is not a valid image (e.g. it might be HTML of a login page or error page)
            snippet = r.text[:250].strip().replace('\n', ' ').replace('\r', '')
            raise Exception(f"LibreNMS did not return a valid image. Content type: {content_type}. Snippet: {snippet}")
            
        return r.content, content_type

    def _normalize_interface_name(self, name):
        if not name:
            return ""
        # Lowercase and strip whitespace
        n = name.lower().strip()
        # Remove all spaces and special punctuation except forward slashes
        n = "".join(c for c in n if c.isalnum() or c == '/')
        
        # Standardize common interface name prefixes to their standard short versions
        prefixes = {
            "hundredgigabitethernet": "hu",
            "hundredgige": "hu",
            "fortygigabitethernet": "fo",
            "fortygige": "fo",
            "tengigabitethernet": "te",
            "tengige": "te",
            "gigabitethernet": "ge",
            "fastethernet": "fa",
            "ethernet": "eth",
            "portchannel": "po",
            "loopback": "lo",
            "vlan": "vl",
            "gi": "ge", # Map gi -> ge for consistency
        }
        for full, short in prefixes.items():
            if n.startswith(full):
                n = short + n[len(full):]
                break
        return n

    def get_port_statistics(self, device_identifier, port_name):
        """
        Fetch port details from LibreNMS and extract traffic rate statistics.
        """
        url = f"{self.url}/api/v0/devices/{quote(str(device_identifier), safe='')}/ports"
        logger.info(f"Fetching port statistics from LibreNMS: {url}")
        r = requests.get(url, headers=self.headers, verify=self.verify_ssl, timeout=15)
        r.raise_for_status()
        data = r.json()
        ports = data.get("ports", [])
        
        # Match port by name
        matched_port = None
        target_norm = self._normalize_interface_name(port_name)
        
        # 1. First pass: exact normalized match on ifName or ifDescr
        for port in ports:
            ifName_norm = self._normalize_interface_name(port.get("ifName"))
            ifDescr_norm = self._normalize_interface_name(port.get("ifDescr"))
            if target_norm == ifName_norm or target_norm == ifDescr_norm:
                matched_port = port
                break
                
        # 2. Second pass: exact normalized match on label or ifAlias
        if not matched_port:
            for port in ports:
                label_norm = self._normalize_interface_name(port.get("label"))
                ifAlias_norm = self._normalize_interface_name(port.get("ifAlias"))
                if target_norm == label_norm or target_norm == ifAlias_norm:
                    matched_port = port
                    break

        # 3. Third pass: prefix match (e.g. database description "hu0/2/0/43-to-pokhara" starts with target "hu0/2/0/43")
        if not matched_port:
            for port in ports:
                ifName_norm = self._normalize_interface_name(port.get("ifName"))
                ifDescr_norm = self._normalize_interface_name(port.get("ifDescr"))
                label_norm = self._normalize_interface_name(port.get("label"))
                
                if ifName_norm and ifName_norm.startswith(target_norm):
                    matched_port = port
                    break
                if ifDescr_norm and ifDescr_norm.startswith(target_norm):
                    matched_port = port
                    break
                if label_norm and label_norm.startswith(target_norm):
                    matched_port = port
                    break
                    
        if not matched_port:
            logger.warning(f"Port '{port_name}' (normalized: '{target_norm}') not found for device '{device_identifier}' in LibreNMS ports list.")
            avail_ports = [
                {
                    "ifName": p.get("ifName"),
                    "ifDescr": p.get("ifDescr"),
                    "ifAlias": p.get("ifAlias"),
                    "label": p.get("label")
                }
                for p in ports
            ]
            return {
                "error": "port_not_found",
                "target_port": port_name,
                "target_norm": target_norm,
                "device_id": device_identifier,
                "ports_count": len(ports),
                "available_ports": avail_ports[:50] # return first 50 ports
            }
            
        # Log port metadata for debugging
        logger.info(
            f"Matched port: port_id={matched_port.get('port_id')}, "
            f"ifName='{matched_port.get('ifName')}', ifDescr='{matched_port.get('ifDescr')}', "
            f"ifSpeed={matched_port.get('ifSpeed')}, "
            f"ifInOctets_rate={matched_port.get('ifInOctets_rate')}, ifOutOctets_rate={matched_port.get('ifOutOctets_rate')}, "
            f"in_rate='{matched_port.get('in_rate')}', out_rate='{matched_port.get('out_rate')}'"
        )

        # Extract traffic statistics
        in_octets_rate = matched_port.get("ifInOctets_rate")
        out_octets_rate = matched_port.get("ifOutOctets_rate")
        
        in_bps = 0.0
        out_bps = 0.0
        
        if in_octets_rate is not None:
            try:
                in_bps = float(in_octets_rate) * 8
            except (ValueError, TypeError):
                pass
        else:
            in_rate_str = matched_port.get("in_rate")
            if in_rate_str:
                in_bps = self._parse_rate_str_to_bps(in_rate_str)
                
        if out_octets_rate is not None:
            try:
                out_bps = float(out_octets_rate) * 8
            except (ValueError, TypeError):
                pass
        else:
            out_rate_str = matched_port.get("out_rate")
            if out_rate_str:
                out_bps = self._parse_rate_str_to_bps(out_rate_str)
                
        logger.info(f"Port '{port_name}' matched. In: {in_bps} bps, Out: {out_bps} bps")
        return {
            "in_bps": in_bps,
            "out_bps": out_bps,
            "port_id": matched_port.get("port_id"),
            "ifSpeed": matched_port.get("ifSpeed")
        }

    def _parse_rate_str_to_bps(self, rate_str):
        """
        Parses rate strings like "4.03 Gbps", "120.5 Mbps", "50 kbps", "10 bps" into bits per second.
        """
        try:
            parts = rate_str.strip().split()
            if not parts:
                return 0.0
            value = float(parts[0])
            if len(parts) > 1:
                unit = parts[1].lower()
                if "gbps" in unit:
                    value *= 1e9
                elif "mbps" in unit:
                    value *= 1e6
                elif "kbps" in unit:
                    value *= 1e3
            return value
        except Exception as e:
            logger.warning(f"Failed to parse rate string '{rate_str}': {str(e)}")
            return 0.0

