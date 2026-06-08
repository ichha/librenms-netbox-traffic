# NetBox Zabbix Traffic Plugin (v2)

A custom NetBox plugin that dynamically integrates Zabbix monitoring data directly into NetBox's user interface. It fetches real-time interface throughput metrics and renders interactive line charts directly on the NetBox Interface details page.

## Features

- **Asynchronous Design**: Pages render instantly in NetBox, while Zabbix API traffic queries are executed asynchronously in the background.
- **Dynamic Charting**: Displays 24-hour, 48-hour, 7-day, or 30-day traffic lines for bits received (Inbound) and bits sent (Outbound) with smooth gradient fills using Chart.js.
- **Zabbix-Style Metric Table**: Calculates and formats **Last**, **Min**, **Avg**, and **Max** bandwidth rates (scaled dynamically into `Gbps`, `Mbps`, `kbps`, or `bps`) exactly like Zabbix's native graph legends.
- **Smart Interface Mapping**: Matches NetBox interfaces to Zabbix items automatically using:
  1. Zabbix tags matching `interface: <name>` or `description: <name>`.
  2. Substring patterns in item names or keys matching full names (e.g., `HundredGigE0/1/0/0`) or standard Cisco/industry abbreviations (e.g., `Hu0/1/0/0`).

---

## Installation

### 1. Install the Package
In your NetBox environment, clone this repository and install it in editable mode or via pip:

```bash
pip install -e /path/to/zabbix-netbox-traffic
```

### 2. Enable the Plugin in NetBox
Modify your NetBox `configuration.py` (typically in `/opt/netbox/netbox/netbox/configuration.py` or `/etc/netbox/config/plugins.py`) to register the plugin and specify your Zabbix API parameters:

```python
PLUGINS = [
    'netbox_zabbix2_traffic',
]

PLUGINS_CONFIG = {
    'netbox_zabbix2_traffic': {
        'zabbix_url': 'http://10.26.192.125/zabbix/api_jsonrpc.php',
        'zabbix_token': '7afab3979404434fd9a79841428d2a0cb77dce1cc3b0d4a28161e31259938c61',
        'verify_ssl': False, # Set to False if using internal IPs without trusted TLS certs
    }
}
```

### 3. Restart NetBox
Restart the NetBox service to apply the configuration change:

```bash
sudo systemctl restart netbox
```
*(or rebuild/restart your Docker containers if running in Docker).*

---

## Technical Specifications

### Zabbix API Matching Algorithm
When a user views an interface detail page in NetBox:
1. The plugin extracts the `Device Name` (e.g. `PatanNT-Cisco-ASR-9010-Core`) and the `Interface Name` (e.g. `HundredGigE0/0/0/2`).
2. It calls the Zabbix API `host.get` to locate the host ID.
3. It fetches all items for that host and filters them using a scoring engine to identify the bits received and sent metrics:
   - Matches items tagged with `interface: HundredGigE0/0/0/2` or `interface: Hu0/0/0/2`.
   - Fuzzy-matches item names/keys containing `HundredGigE0/0/0/2` or `Hu0/0/0/2`.
   - Identifies directions based on keywords in name/key: `Bits received`, `Bits sent`, `in`, `out`, `rx`, `tx`, `input`, `output`.
4. It calls `history.get` for the active item IDs and builds coordinates for Chart.js.
