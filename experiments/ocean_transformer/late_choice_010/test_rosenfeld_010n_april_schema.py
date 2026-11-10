import hashlib
import io
import unittest
import zipfile
import rosenfeld_010n_april_schema as q

class SourceProbeTest(unittest.TestCase):
 def test_archive_inventory(self):
  b=io.BytesIO()
  with zipfile.ZipFile(b,"w") as z:
   z.writestr("measurement.csv","a,b,local\n0,1,+1\n")
  x=q.inventory(b.getvalue())
  self.assertEqual(x[0]["name"],"measurement.csv")
  self.assertEqual(x[0]["line_count"],2)
  self.assertEqual(x[0]["first_four_original_text_lines"][0],"a,b,local")

 def test_path_traversal_rejected(self):
  b=io.BytesIO()
  with zipfile.ZipFile(b,"w") as z:z.writestr("../override.dat","corrupt")
  with self.assertRaisesRegex(ValueError,"UNSAFE_ZIP_PATH"):
   q.inventory(b.getvalue())

 def test_authoritative_april_only(self):
  self.assertIn("2016-04-15",q.URL)
  self.assertNotIn("2016-06-14",q.URL)
  self.assertEqual(q.MD5,"53544819317d4dcfbe5c63e039a8aa38")

if __name__=="__main__":unittest.main()
