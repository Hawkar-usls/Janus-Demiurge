#!/usr/bin/env python3
"""Tests of bounded NIST HDF5 introspection and scientific non-promotion."""
import pathlib
import tempfile
import unittest
import h5py
import numpy as np
import nist_hdf5_clock_010h as n


class NISTHDF5ProvenanceTests(unittest.TestCase):
    def test_clock_candidate_extraction_but_no_claim(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/"toy.h5"
            with h5py.File(p,"w") as f:
                f.attrs["site"]="NIST toy"
                obj=f.create_group("sync")
                obj.attrs["skip_A"]=np.int64(215)
                obj.attrs["skip_B"]=np.int64(223)
                obj.create_dataset("clock_offset_in_ticks",data=np.int64(17))
                obj.create_dataset("raw_photon_times",data=np.arange(5000,dtype="i8"))
            meta=n.collect_metadata(p)
        paths={x["path"] for x in meta["clock_or_sync_named_fields"]}
        self.assertIn("/sync/clock_offset_in_ticks",paths)
        self.assertEqual(next(x for x in meta["clock_or_sync_named_fields"]
                              if x["path"]=="/sync/clock_offset_in_ticks")["small_dataset_value"],17)
        self.assertTrue(meta["candidate_fields_are_not_a_verified_clock_alignment"])
        self.assertTrue(meta["values_stored_in_authors_HDF5_are_not_independent_measurements_by_JANUS"])

    def test_large_arrays_never_loaded_as_data(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/"toy.h5"
            with h5py.File(p,"w") as f:
                f.create_dataset("gps_event_record",data=np.arange(4000,dtype="i8"))
            meta=n.collect_metadata(p)
        found=next(x for x in meta["clock_or_sync_named_fields"] if x["path"]=="/gps_event_record")
        self.assertEqual(found["shape"],[4000])
        self.assertNotIn("small_dataset_value",found)

    def test_safe_numeric_attributes(self):
        self.assertEqual(n.safe_scalar(np.int64(88)),88)
        self.assertEqual(n.safe_scalar(np.float64(1.5)),1.5)
        self.assertEqual(n.safe_scalar(b"gps"),"gps")

    def test_sources_are_official_and_bounded(self):
        self.assertTrue(all(x["download_cap_bytes"]<900000000 for x in n.DATASETS.values()))
        self.assertIn("nist-belltestdata",n.BASE)
        self.assertEqual(set(n.DATASETS),{"training","corrected"})


if __name__=="__main__":
    unittest.main()
