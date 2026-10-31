import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from pnp_policy0a_cleanroom_replay import explicit_n3, symbolic_sink_inequality

class TestDeepReplay(unittest.TestCase):
    def test_cleanroom_n3(self):
        data=explicit_n3()
        self.assertEqual(data['total_literals'],31140)
        self.assertEqual(data['sink_pairs_checked'],331776)
        self.assertTrue(data['both_branch_projections_checked'])
        self.assertFalse(data['full_asymptotic_lower_bound_proved'])
    def test_symbolic_budget(self):
        data=symbolic_sink_inequality()
        self.assertTrue(data['positive_for_n_ge_3'])
        self.assertFalse(data['full_policy0a_asymptotic_result_independently_proved'])

if __name__=='__main__':
    unittest.main()
