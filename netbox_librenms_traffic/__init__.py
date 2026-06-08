from netbox.plugins import PluginConfig

class NetBoxLibreNMSTrafficConfig(PluginConfig):
    name = 'netbox_librenms_traffic'
    verbose_name = 'LibreNMS Interface Traffic Graph'
    description = 'Embeds real-time LibreNMS traffic graphs inside NetBox interface detail views'
    version = '1.0.0'
    author = 'Antigravity'
    author_email = 'antigravity@google.com'
    base_url = 'librenms-traffic'
    
    default_settings = {
        'librenms_url': 'http://10.26.20.146:8000',
        'librenms_token': '622035fb484c6962f7be516fb87bef4f',
        'verify_ssl': False,
    }
    
    required_settings = []

config = NetBoxLibreNMSTrafficConfig
