from setuptools import setup, find_packages

setup(
    name="netbox-zabbix2-traffic",
    version="1.0.0",
    description="A NetBox plugin to display dynamic Zabbix traffic graphs and metrics on interface pages (v2)",
    url="https://github.com/netbox-community/netbox-zabbix2-traffic",
    author="Antigravity",
    license="Apache 2.0",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'netbox_zabbix2_traffic': [
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
