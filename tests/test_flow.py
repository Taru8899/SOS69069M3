"""M3 core: self-post, directed post, stores."""
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from sos69069_msg.conversation import ChatTargetStore, MindBind, WalletStore, random_wallet
from sos69069_msg.eip712 import verify_record
from sos69069_msg.message_engine import prepare_and_sign
from sos69069_msg.reader import Inbox, Message


class TestM3Core(unittest.TestCase):
    def test_self_post(self):
        a = random_wallet()
        ph, meta, sig = prepare_and_sign(a, "hello")
        self.assertTrue(verify_record(a.address, a.address, ph, meta, sig))

    def test_directed_post(self):
        a = random_wallet()
        b = random_wallet()
        ph, meta, sig = prepare_and_sign(a, "hi board", intended_to=b.address)
        self.assertTrue(verify_record(a.address, b.address, ph, meta, sig))

    def test_chat_target_persists(self):
        path = os.path.join(tempfile.mkdtemp(), "t.json")
        store = ChatTargetStore(Path := __import__("pathlib").Path(path))
        a = random_wallet()
        store.save(a.address)
        self.assertEqual(store.load().lower(), a.address.lower())

    def test_mind_bind_is_session_only_object(self):
        b = MindBind()
        a = random_wallet()
        b.set(a.address)
        self.assertEqual(b.other.lower(), a.address.lower())
        b.clear()
        self.assertIsNone(b.other)

    def test_wallet_store(self):
        path = os.path.join(tempfile.mkdtemp(), "w.json")
        from pathlib import Path
        store = WalletStore(Path(path))
        kp = random_wallet()
        store.save(kp)
        loaded = store.load()
        self.assertEqual(loaded.address, kp.address)

    def test_inbox_entries_me(self):
        path = os.path.join(tempfile.mkdtemp(), "i.json")
        inbox = Inbox(path)
        my = "0x" + "11" * 20
        other = "0x" + "22" * 20
        inbox.messages = [
            Message(1, 0, "0x" + "aa" * 32, 1700000000, my, my, "from me", "0x" + "11" * 32, my),
            Message(2, 0, "0x" + "bb" * 32, 1700000100, other, other, "from other", "0x" + "22" * 32, other),
        ]
        es = inbox.entries(my)
        self.assertEqual(es[0]["text"], "from other")  # newest first
        self.assertIn(es[1]["who"], ("Me", my))


if __name__ == "__main__":
    unittest.main()
