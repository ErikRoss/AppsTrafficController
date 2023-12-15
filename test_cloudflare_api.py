from pprint import pprint
import unittest

from cloudflare_api import CloudflareApi
from config import DNS_HOST


class TESTCloudflareApi(unittest.TestCase):
    def setUp(self):
        self.cloudflare = CloudflareApi()

    def test_create_zone(self):
        domain_name = "testdomain.online"
        result = self.cloudflare.create_zone(domain_name)
        try:
            self.assertEqual(result["success"], True)
        except AssertionError:
            self.assertIsNotNone(result["error"])
            print("Got error: ", result["error"], sep="\n")
        else:
            self.assertIsNotNone(result["nameservers"])
            self.assertIsNotNone(result["zone_id"])
            self.assertEqual(len(result["nameservers"]), 2)

    def test_get_zone(self):
        domain_name = "testdomain.online"
        result = self.cloudflare.get_zone(domain_name)
        self.assertEqual(result["success"], True)
        self.assertEqual(len(result["nameservers"]), 2)

    def test_set_dns_records(self):
        domain_name = "testdomain.online"
        result = self.cloudflare.get_zone(domain_name)
        zone_id = result["zone_id"]
        ip = DNS_HOST
        name = "www"
        result = self.cloudflare.set_dns_records(zone_id, ip, name)
        pprint(result)
        self.assertEqual(result["success"], True)
