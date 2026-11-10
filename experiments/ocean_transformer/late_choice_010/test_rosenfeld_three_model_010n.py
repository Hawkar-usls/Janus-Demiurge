import io
import unittest
import zipfile
import rosenfeld_three_model_010n as q

def toy_archive():
    header1="time (Unix time in ms);setting;result; local timestamp;Bell-state;excluded from evaluation; comment"
    header2="time (Unix time in ms);setting;result;local timestamp;excluded from evaluation;comment;"
    header3="timestamp lab 1 (unix time ms)\tBell-state\tsetting lab 1\tresult lab 1\tsetting lab 2\tresult lab 2\tline in lab 1 file\tline in lab 2 file"
    a=[header1];b=[header2];pairs=[header3]
    for i in range(32):
        own=i//16
        remote=(i//8)%2
        A=(i//4)%2
        # Every own+remote cell sees both A outcomes; B=A XOR remote,
        # and conditioning on B==1 creates correlation not in unfiltered A.
        B=A^remote
        utc=1460729997000+1000*i
        a.append(f"{utc};{own};{A};{8700000+i*10};Psi-;no;")
        b.append(f"{utc+1};{remote};{B};{6800000+i*10};no;")
        pairs.append(f"{utc}\tPsi-\t{own}\t{A}\t{remote}\t{B}\t{i}\t{i}")
    f=io.BytesIO()
    with zipfile.ZipFile(f,"w") as z:
        z.writestr("Bell_2016-04-15_9_lab_1.csv","\n".join(a)+"\n")
        z.writestr("Bell_2016-04-15_9_lab_2.csv","\n".join(b)+"\n")
        z.writestr("Bell_2016-04-15_9_pairs.csv","\n".join(pairs)+"\n")
        z.writestr("Readme.txt","Author valid Bell events as pair file")
    return f.getvalue()

class RosenfeldOriginalAudit(unittest.TestCase):
    def test_canonical_original_schema(self):
        inv,rows=q.extract_zip(toy_archive())
        self.assertEqual(inv["all_attempts"],{"Alice":32,"Bob":32})
        self.assertEqual(inv["author_valid_pairs"],32)
        self.assertEqual(len(rows),32)

    def test_m0_no_signal_but_b_selected_false_signal(self):
        _,rows=q.extract_zip(toy_archive())
        base,selection=q.tables(rows)
        for own in (0,1):
            self.assertEqual(q.contrast(base,"Alice",own)["delta_Pplus_remote1_minus0"],0)
            self.assertEqual(q.contrast(selection,"Alice",own)["delta_Pplus_remote1_minus0"],-1)
        scored=q.comparison(base,base)
        self.assertIsInstance(scored["Alice"]["Mjanus_minus_M0_bits_per_pair"],float)

    def test_holm_fixed_four(self):
        base,_=q.tables(q.extract_zip(toy_archive())[1])
        vals=q.holm([q.contrast(base,w,o) for w in ("Alice","Bob") for o in (0,1)])
        self.assertEqual(len(vals),4)
        self.assertEqual(vals[0]["holm_p_descriptive"],1)

    def test_malformed_pair_bad_time_rejected(self):
        b=toy_archive()
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            a=z.read("Bell_2016-04-15_9_lab_1.csv")
            second=z.read("Bell_2016-04-15_9_lab_2.csv")
            pair=z.read("Bell_2016-04-15_9_pairs.csv").decode()
        pair=pair.replace("1460729997000\t","1460729997400\t",1)
        with self.assertRaisesRegex(ValueError,"PAIR_TIME_OUTSIDE"):
            q.author_pairs(pair.encode(),q.lab_rows(a,1),q.lab_rows(second,2))

    def test_bad_pair_not_silently_selected(self):
        b=toy_archive()
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            a=z.read("Bell_2016-04-15_9_lab_1.csv")
            second=z.read("Bell_2016-04-15_9_lab_2.csv")
            pair=z.read("Bell_2016-04-15_9_pairs.csv").decode()
        pair=pair.replace("\t0\t0\t0\t0\n","\t0\t1\t0\t0\n",1)
        with self.assertRaisesRegex(ValueError,"PAIR_OUTCOME_SETTING_DIFFERS"):
            q.author_pairs(pair.encode(),q.lab_rows(a,1),q.lab_rows(second,2))

    def test_original_zenodo_source_hash_pinned(self):
        self.assertEqual(q.SOURCES["june"]["md5"],"030ce1a0c6c6cc7f1107e1cd608cce77")
        self.assertEqual(q.FAMILY_ALPHA,0.001)
        self.assertEqual(q.SOURCES["april"]["md5"],"53544819317d4dcfbe5c63e039a8aa38")

if __name__=="__main__":unittest.main()
