from setuptools import setup, find_packages

setup(
    name="netbox-librenms-traffic",
    version="1.0.0",
    description="A NetBox plugin to display dynamic LibreNMS traffic graphs on interface pages",
    url="https://github.com/netbox-community/netbox-librenms-traffic",
    author="Antigravity",
    license="Apache 2.0",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'netbox_librenms_traffic': [
            'templates/**/*.html',
            'static/**/*.js',
            'static/**/*.css',
        ]
    },
    zip_safe=False,
    install_requires=[
        "requests"
    ],
)
