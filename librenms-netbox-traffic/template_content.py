from netbox.plugins import PluginTemplateExtension

class InterfaceTrafficExtension(PluginTemplateExtension):
    models = ['dcim.interface']

    def full_width_page(self):
        # Retrieve the interface object being rendered in NetBox
        interface = self.context.get('object')
        
        # Defensive type checks to guarantee compatibility with all versions and page views
        if not interface or interface.__class__.__name__ != 'Interface':
            return ""
        if not hasattr(interface, 'device') or not interface.device:
            return ""

        # Render the custom traffic template, passing device and interface identifiers
        return self.render('netbox_zabbix2_traffic/inc/interface_traffic.html', extra_context={
            'device_name': interface.device.name,
            'interface_name': interface.name,
        })

template_extensions = [InterfaceTrafficExtension]
