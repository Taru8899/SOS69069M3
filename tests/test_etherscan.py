"""Etherscan client smoke."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from sos69069_msg.config import DEFAULT_ETHERSCAN_KEY
from sos69069_msg.etherscan import EtherscanClient
from sos69069_msg.rpc import RpcError

class TestEs(unittest.TestCase):
    def test_key_required(self):
        with self.assertRaises(RpcError):
            EtherscanClient("")
    def test_ok(self):
        self.assertIsNotNone(EtherscanClient(DEFAULT_ETHERSCAN_KEY))

if __name__ == "__main__":
    unittest.main()
