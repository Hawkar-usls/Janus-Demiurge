import unittest
from tools.mintaka_homeostasis_replay import replay,exam,step,SLA,POLICIES
class Homeostasis(unittest.TestCase):
    def test_detection_and_deadline(self):
        r=replay([1,29,31,59],0,60,"FIXED30")
        self.assertEqual(r["detected"],4);self.assertEqual(r["late"],0)
        self.assertEqual(r["checks"],3)
    def test_no_lookahead_and_dedup(self):
        self.assertEqual(step("ADAPTIVE_A",90,[0,30,60]),15)
        r=replay([1,1,2],0,60,"FIXED15")
        self.assertEqual(r["events"],2)
    def test_heldout_cannot_change_selection(self):
        a=exam(list(range(0,1440,37))+[1500],0,2160)
        b=exam(list(range(0,1440,37))+[1501,1502,2000],0,2160)
        self.assertEqual(a["chosen"],b["chosen"])
        self.assertEqual(a["calibration"],b["calibration"])
    def test_late_is_not_success(self):
        self.assertEqual(replay([1],0,60,"FIXED60")["late"],1)
        for p in POLICIES:self.assertLessEqual(min(SLA,step(p,0,[])),SLA)
