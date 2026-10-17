"""TASK-5559 D1: readback = intent per field and board."""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lab'))
import d1_readback as D  # noqa: E402


class D1(unittest.TestCase):
    def test_diff(self):
        intent = {'gs': {'TX_AMP': 8, 'RX_EQA_CKP_OFFSET': 1}, 'm2': {'TX_AMP': 12}}
        self.assertEqual(D.diff(intent, {'gs': {'TX_AMP': 8, 'RX_EQA_CKP_OFFSET': 1}, 'm2': {'TX_AMP': 12}}), {})
        self.assertEqual(D.diff(intent, {'gs': {'TX_AMP': 12, 'RX_EQA_CKP_OFFSET': 1}, 'm2': {}}),
                         {'gs': {'TX_AMP': (8, 12)}, 'm2': {'TX_AMP': (12, None)}})


if __name__ == '__main__':
    unittest.main()
