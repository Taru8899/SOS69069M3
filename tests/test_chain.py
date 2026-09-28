"""RLP / ABI smoke."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from sos69069_msg import rlp
from sos69069_msg.abi import RECORD_SIGNATURE_SELECTOR, encode_record_signature, decode_signature_recorded
from sos69069_msg.rpc import RpcError, _check_url

class TestRlp(unittest.TestCase):
    def test_spec_vectors(self):
        self.assertEqual(rlp.encode(b"dog").hex(), "83646f67")
        self.assertEqual(rlp.encode(0).hex(), "80")

class TestAbi(unittest.TestCase):
    def test_calldata(self):
        data = encode_record_signature(
            "0x" + "11" * 20, "0x" + "22" * 20, b"\x33" * 32, b"\x44" * 65, "hi")
        self.assertEqual(data[:4], RECORD_SIGNATURE_SELECTOR)

class TestRpc(unittest.TestCase):
    def test_url(self):
        with self.assertRaises(RpcError):
            _check_url("http://example.com")
        _check_url("https://example.com")

if __name__ == "__main__":
    unittest.main()
