"""Inbox pagination entries."""
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from sos69069_msg.config import DEFAULT_ETHERSCAN_KEY
from sos69069_msg.reader import Inbox, Message

class TestList(unittest.TestCase):
    def test_key(self):
        self.assertTrue(len(DEFAULT_ETHERSCAN_KEY) > 10)
    def test_entries(self):
        inbox = Inbox(os.path.join(tempfile.mkdtemp(), "i.json"))
        my = "0x" + "11" * 20
        inbox.messages = [
            Message(1, 0, "0x" + "aa" * 32, 1, my, my, "a", "0x" + "11" * 32, my),
        ]
        es = inbox.entries(my)
        self.assertEqual(len(es), 1)
        self.assertTrue(len(es[0]["code"]) >= 4)

if __name__ == "__main__":
    unittest.main()
