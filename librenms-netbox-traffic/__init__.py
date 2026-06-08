from netbox.plugins import PluginConfig

class NetBoxZabbix2TrafficConfig(PluginConfig):
    name = 'netbox_zabbix2_traffic'
    verbose_name = 'Zabbix Interface Traffic Graph v2'
    description = 'Embeds real-time Zabbix traffic graphs and metrics inside NetBox interface detail views'
    version = '1.0.0'
    author = 'Antigravity'
    author_email = 'antigravity@google.com'
    base_url = 'zabbix2-traffic'
    
    default_settings = {
        'zabbix_url': 'http://10.26.192.125/zabbix/api_jsonrpc.php',
        'zabbix_token': '7afab3979404434fd9a79841428d2a0cb77dce1cc3b0d4a28161e31259938c61',
        'verify_ssl': False,
    }
    
    required_settings = []

config = NetBoxZabbix2TrafficConfig
