from django.test import TestCase
from unittest.mock import patch, MagicMock
from netbox_librenms_traffic.librenms_api import LibreNMSAPIClient

class LibreNMSAPIClientTests(TestCase):
    def setUp(self):
        self.client = LibreNMSAPIClient(
            url="http://10.26.20.146:8000",
            token="test-token",
            verify_ssl=False
        )

    @patch("requests.get")
    def test_get_device_by_ip_success(self, mock_get):
        # Mock direct device endpoint response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "devices": [
                {
                    "device_id": 42,
                    "hostname": "10.23.51.198",
                    "sysName": "MYA-CAR-CSO-001"
                }
            ]
        }
        mock_get.return_value = mock_response

        device = self.client.get_device_by_ip_or_name("MYA-CAR-CSO-001", "10.23.51.198")
        self.assertIsNotNone(device)
        self.assertEqual(device["device_id"], 42)
        self.assertEqual(device["hostname"], "10.23.51.198")

    @patch("requests.get")
    def test_get_device_by_scan_fallback_ip(self, mock_get):
        # Mock direct endpoints failing (e.g. 404 or exception), but scan succeeds
        mock_error = MagicMock()
        mock_error.status_code = 404
        
        mock_scan = MagicMock()
        mock_scan.status_code = 200
        mock_scan.json.return_value = {
            "status": "ok",
            "devices": [
                {
                    "device_id": 10,
                    "hostname": "10.23.51.200",
                    "sysName": "DeviceA"
                },
                {
                    "device_id": 20,
                    "hostname": "10.23.51.202",
                    "sysName": "DeviceB"
                }
            ]
        }
        
        mock_get.side_effect = [mock_error, mock_error, mock_scan]

        device = self.client.get_device_by_ip_or_name("DeviceB", "10.23.51.202")
        self.assertIsNotNone(device)
        self.assertEqual(device["device_id"], 20)
        self.assertEqual(device["hostname"], "10.23.51.202")

    @patch("requests.get")
    def test_get_port_graph_image_parameters(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake-png-data"
        mock_response.headers = {"content-type": "image/png"}
        mock_get.return_value = mock_response

        content, content_type = self.client.get_port_graph_image(
            device_identifier=42,
            port_name="HundredGigE0/0/0/1",
            time_range="7d"
        )
        
        self.assertEqual(content, b"fake-png-data")
        self.assertEqual(content_type, "image/png")
        
        # Verify correct URL construction & encoding
        # HundredGigE0/0/0/1 -> HundredGigE0%2F0%2F0%2F1
        expected_url = "http://10.26.20.146:8000/api/v0/devices/42/ports/HundredGigE0%2F0%2F0%2F1/port_bits"
        mock_get.assert_called_once_with(
            expected_url,
            headers={"X-Auth-Token": "test-token", "Accept": "application/json"},
            params={"from": "-7d", "width": 1100, "height": 300},
            verify=False,
            timeout=15
        )
