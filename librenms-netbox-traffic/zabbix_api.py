import requests
import json
import re
import logging
from datetime import datetime

logger = logging.getLogger("netbox.plugins.netbox_zabbix2_traffic")

class ZabbixAPIClient:
    def __init__(self, api_url, token, verify_ssl=True):
        self.api_url = api_url
        self.token = token
        self.verify_ssl = verify_ssl

    def request(self, method, params=None):
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": 1,
            "auth": self.token
        }
        headers = {"Content-Type": "application/json"}
        
        try:
            logger.debug(f"Sending request to Zabbix API: {method}")
            response = requests.post(
                self.api_url,
                data=json.dumps(payload),
                headers=headers,
                verify=self.verify_ssl,
                timeout=60
            )
            response.raise_for_status()
            res_data = response.json()
            if "error" in res_data:
                raise Exception(f"Zabbix API Error: {res_data['error']}")
            return res_data.get("result")
        except Exception as e:
            logger.error(f"Zabbix API Request Failed for method {method}: {str(e)}")
            raise Exception(f"Failed to communicate with Zabbix API: {str(e)}")

    def get_host(self, host_name):
        """
        Attempts to locate a host in Zabbix by Name.
        Also tries mapping by common modifications if exact match fails.
        """
        params = {
            "filter": {
                "host": [host_name]
            },
            "output": ["hostid", "host", "name"]
        }
        result = self.request("host.get", params)
        if result:
            return result[0]
            
        # Fallback to visual name (name)
        params = {
            "filter": {
                "name": [host_name]
            },
            "output": ["hostid", "host", "name"]
        }
        result = self.request("host.get", params)
        if result:
            return result[0]

        # Search for case-insensitive substring
        params = {
            "search": {
                "name": host_name
            },
            "searchWildcardsEnabled": True,
            "output": ["hostid", "host", "name"]
        }
        result = self.request("host.get", params)
        if result:
            return result[0]

        return None

    def get_interface_abbreviation(self, interface_name):
        """
        Helper to convert interface name into typical Zabbix/Cisco abbreviation.
        e.g., HundredGigE0/1/0/0 -> Hu0/1/0/0 or GigabitEthernet1/0/1 -> Gi1/0/1
        """
        match = re.match(r'^([a-zA-Z\-]+)(.*)$', interface_name)
        if not match:
            return None
            
        word, num = match.groups()
        word_lower = word.lower()
        
        abbrevs = {
            "hundredgige": "Hu",
            "hundredgigabitethernet": "Hu",
            "tengigabitethernet": "Te",
            "tengige": "Te",
            "gigabitethernet": "Gi",
            "gige": "Gi",
            "fastethernet": "Fa",
            "ethernet": "Eth",
            "port-channel": "Po",
            "portchannel": "Po",
            "loopback": "Lo",
            "vlan": "Vlan"
        }
        
        for k, v in abbrevs.items():
            if word_lower.startswith(k) or k.startswith(word_lower):
                return f"{v}{num}"
        return None

    def get_interface_items(self, host_id, interface_name):
        """
        Finds corresponding Bits received and Bits sent items for the interface.
        """
        params = {
            "hostids": host_id,
            "output": ["itemid", "name", "key_", "value_type", "lastvalue", "units"],
            "selectTags": ["tag", "value"],
        }
        items = self.request("item.get", params)
        if not items:
            return None, None

        abbrev = self.get_interface_abbreviation(interface_name)
        
        matched_in_item = None
        matched_out_item = None

        for item in items:
            name = item.get("name", "")
            key = item.get("key_", "")
            tags = item.get("tags", [])
            
            # 1. Match by Tag
            tag_match = False
            for t in tags:
                tag_name = t.get("tag", "").lower()
                tag_val = t.get("value", "").lower()
                if tag_name in ["interface", "description"] and (tag_val == interface_name.lower() or (abbrev and tag_val == abbrev.lower())):
                    tag_match = True
                    break

            # 2. Match by substring in name/key
            name_lower = name.lower()
            key_lower = key.lower()
            ifname_lower = interface_name.lower()
            
            is_interface_related = tag_match or (ifname_lower in name_lower) or (ifname_lower in key_lower)
            if abbrev and not is_interface_related:
                abbrev_lower = abbrev.lower()
                is_interface_related = (abbrev_lower in name_lower) or (abbrev_lower in key_lower)

            if is_interface_related:
                # 3. Classify into IN or OUT
                is_in = False
                is_out = False
                
                # Check for bits received / sent or input / output
                if "bits received" in name_lower or "bits recv" in name_lower or "input" in name_lower or "in octets" in name_lower or "rx" in name_lower or "in[" in key_lower:
                    is_in = True
                elif "bits sent" in name_lower or "output" in name_lower or "out octets" in name_lower or "tx" in name_lower or "out[" in key_lower:
                    is_out = True
                
                # If key has standard net.if.in or net.if.out
                if not is_in and not is_out:
                    if "net.if.in" in key_lower or ".in" in key_lower or "rx" in key_lower:
                        is_in = True
                    elif "net.if.out" in key_lower or ".out" in key_lower or "tx" in key_lower:
                        is_out = True

                if is_in:
                    if not matched_in_item or "bits" in name_lower or "traffic" in name_lower:
                        matched_in_item = item
                elif is_out:
                    if not matched_out_item or "bits" in name_lower or "traffic" in name_lower:
                        matched_out_item = item

        return matched_in_item, matched_out_item

    def get_item_history(self, item_id, value_type, time_from, time_till, limit=1000):
        """
        Retrieves history data points for an item.
        """
        params = {
            "output": "extend",
            "history": int(value_type),
            "itemids": [item_id],
            "time_from": int(time_from),
            "time_till": int(time_till),
            "sortfield": "clock",
            "sortorder": "ASC",
            "limit": limit
        }
        return self.request("history.get", params) or []
