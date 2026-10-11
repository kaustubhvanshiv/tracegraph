import unittest
from research.ml.data_prep.audit_network_host import summarize


class NetworkHostTests(unittest.TestCase):
    def test_remote_match_does_not_prove_local_host(self):
        rows = [{"type": "RECORD_NET_FLOW_OBJECT", "hostId": "h", "datum": {
            "uuid": "n", "localAddress": "127.0.0.1", "remoteAddress": "128.55.12.55"}}]
        self.assertEqual(summarize(rows, "128.55.12.55")["matching_local_address_references"], [])

    def test_local_address_matches_remain_unlabeled(self):
        rows = [{"type": "RECORD_NET_FLOW_OBJECT", "hostId": "h", "datum": {
            "uuid": "n", "localAddress": "128.55.12.55"}}] * 8
        result = summarize(rows, "128.55.12.55")
        self.assertEqual(result["local_address_counts"][0]["count"], 8)
        self.assertEqual(len(result["matching_local_address_references"]), 5)
        self.assertEqual(result["labels_assigned"], 0)
