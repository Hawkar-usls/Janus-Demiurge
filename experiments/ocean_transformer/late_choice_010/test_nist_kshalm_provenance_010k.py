#!/usr/bin/env python3
"""Offline provenance gate tests: code never executes; no cloud science claim."""
import unittest
import nist_kshalm_provenance_010k as q

P={
"process":"def find_ttag_offset(timeTaggers, rawData):\n    return timeTaggers.find_sync_offset2(.2,rawData=rawData)\n",
"tt":"def find_sync_offset2(self,intTime,rawData=None):\n    return cl.calc_offset(rawData,{},1)\n",
"coinc":"""def calc_offset(data, params, divider):
    coincArray=[1,2,3]
    value=find_offset_coinc(data,1,2)
    idx=np.argmax(coincArray)
    ttagOffset=np.mean(value)
    return {"ttagOffset":ttagOffset}
"""
}

class ProvenanceChecks(unittest.TestCase):
    def test_detect_coincidence_tuned_clock(self):
        result=q.audit_source_triplet(P)
        self.assertTrue(all(result["gates"].values()))
        self.assertFalse(result["independent_UTC_clock_anchor_from_this_algorithm"])

    def test_reject_looking_like_independent_clock(self):
        alt=dict(P)
        alt["coinc"]="def calc_offset(data,params,divider):\n    return GPS_PPS_ONLY(data)\n"
        with self.assertRaisesRegex(ValueError,"PROVENANCE_CHAIN_INCOMPLETE"):
            q.audit_source_triplet(alt)

    def test_reject_missing_function(self):
        alt=dict(P)
        alt["process"]="def other_func():\n    pass\n"
        with self.assertRaisesRegex(ValueError,"MISSING_OR_DUPLICATE"):
            q.audit_source_triplet(alt)

    def test_original_2015_not_substituted(self):
        self.assertEqual(len(q.REPOS),2)
        for repo,spec in q.REPOS.items():
            self.assertTrue(spec["repo_created_utc"].startswith("202"))
            self.assertIn(repo,("kshalm/bellhelpers","kshalm/bellanalysishelper"))
            self.assertEqual(len(spec["commit"]),40)

if __name__=="__main__":unittest.main()
