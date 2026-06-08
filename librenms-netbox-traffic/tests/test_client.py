from django.test import TestCase
from unittest.mock import patch, MagicMock
from netbox_zabbix2_traffic.zabbix_api import ZabbixAPIClient

class ZabbixAPIClientTests(TestCase):
    def setUp(self):
        self.client = ZabbixAPIClient(
            api_url="http://10.26.192.125/zabbix/api_jsonrpc.php",
            token="test-token",
            verify_ssl=False
        )

    def test_get_interface_abbreviation(self):
        # Test core abbreviation mapper
        self.assertEqual(self.client.get_interface_abbreviation("HundredGigE0/1/0/0"), "Hu0/1/0/0")
        self.assertEqual(self.client.get_interface_abbreviation("GigabitEthernet1/0/2"), "Gi1/0/2")
        self.assertEqual(self.client.get_interface_abbreviation("TenGigabitEthernet0/2/1/0"), "Te0/2/1/0")
        self.assertEqual(self.client.get_interface_abbreviation("FastEthernet0/0"), "Fa0/0")
        self.assertEqual(self.client.get_interface_abbreviation("Loopback10"), "Lo10")
        self.assertEqual(self.client.get_interface_abbreviation("Vlan100"), "Vlan100")
        self.assertIsNone(self.client.get_interface_abbreviation("unknown"))

    @patch("requests.post")
    def test_api_request_success(self, mock_post):
        # Mock successful JSON-RPC response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "result": [{"hostid": "10050", "name": "PatanNT-Cisco-ASR-9010-Core"}],
            "id": 1
        }
        mock_post.return_value = mock_response

        res = self.client.get_host("PatanNT-Cisco-ASR-9010-Core")
        self.assertIsNotNone(res)
        self.assertEqual(res["hostid"], "10050")
        self.assertEqual(res["name"], "PatanNT-Cisco-ASR-9010-Core")

    @patch("requests.post")
    def test_get_interface_items_heuristics(self, mock_post):
        # Mock item query result
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "result": [
                {
                    "itemid": "101",
                    "name": "Interface *** 2nd Link to Hetuada Cisco 9010 HundredGigE0/1/0/2 ***: Bits received",
                    "key_": "net.if.in[HundredGigE0/1/0/2]",
                    "value_type": "0",
                    "tags": [{"tag": "interface", "value": "HundredGigE0/1/0/2"}]
                },
                {
                    "itemid": "102",
                    "name": "Interface *** 2nd Link to Hetuada Cisco 9010 HundredGigE0/1/0/2 ***: Bits sent",
                    "key_": "net.if.out[HundredGigE0/1/0/2]",
                    "value_type": "0",
                    "tags": [{"tag": "interface", "value": "HundredGigE0/1/0/2"}]
                }
            ],
            "id": 1
        }
        mock_post.return_value = mock_response

        in_item, out_item = self.client.get_interface_items("10050", "HundredGigE0/1/0/2")
        self.assertIsNotNone(in_item)
        self.assertIsNotNone(out_item)
        self.assertEqual(in_item["itemid"], "101")
        self.assertEqual(out_item["itemid"], "102")
