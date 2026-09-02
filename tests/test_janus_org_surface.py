import unittest
from unittest import mock

from janus_model.extensions import org_surface as osurf


class OrgSurfaceTests(unittest.TestCase):
    def test_all_discovered_public_repositories_are_bound_without_authority(self):
        repos = [
            {"full_name": "Hawkar-usls/A", "owner": {"login": "Hawkar-usls"}, "default_branch": "main", "clone_url": "https://github.com/Hawkar-usls/A.git", "archived": False, "fork": False, "size": 1},
            {"full_name": "Hawkar-usls/B", "owner": {"login": "Hawkar-usls"}, "default_branch": "master", "clone_url": "https://github.com/Hawkar-usls/B.git", "archived": False, "fork": False, "size": 2},
        ]

        def bind(repo, timeout):
            return {
                "repository": repo["full_name"],
                "visibility": "public",
                "default_branch": repo["default_branch"],
                "status": "BOUND_PUBLIC_READ_ONLY",
                "head_sha": "a" * 40,
                "training_inclusion": False,
                "authority": False,
                "source_execution": False,
            }

        with mock.patch.object(osurf, "discover_public_repositories", return_value=repos), mock.patch.object(osurf, "_bind_head", side_effect=bind):
            obj = osurf.build_org_surface(private_unmounted_count=3, baseline_inventory_total=5, workers=2)
        self.assertEqual(obj["status"], "READY_PUBLIC_ALL_BOUND_PRIVATE_UNMOUNTED")
        self.assertEqual(obj["public_discovered_count"], 2)
        self.assertEqual(obj["public_bound_count"], 2)
        self.assertEqual(obj["baseline_inventory"]["represented_minimum_now"], 5)
        self.assertFalse(obj["capabilities"]["cross_repository_write"])
        self.assertFalse(obj["firewalls"]["private_repository_names_may_be_published"])
        self.assertEqual(len(obj["surface_digest"]), 64)

    def test_unbound_public_repository_degrades_surface(self):
        repos = [{"full_name": "Hawkar-usls/A", "owner": {"login": "Hawkar-usls"}, "default_branch": "main"}]
        with mock.patch.object(osurf, "discover_public_repositories", return_value=repos), mock.patch.object(osurf, "_bind_head", return_value={"repository": "Hawkar-usls/A", "status": "UNBOUND_HEAD"}):
            obj = osurf.build_org_surface(workers=1)
        self.assertEqual(obj["status"], "DEGRADED")
        self.assertFalse(obj["all_public_repositories_bound"])


if __name__ == "__main__":
    unittest.main()
