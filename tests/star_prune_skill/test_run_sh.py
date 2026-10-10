"""star-prune's run.sh: the shared bootstrap behind a second wrapper, and its scope rules.

Every check the star-lists wrapper passes runs again here, against star-prune's
wrapper, so the shared bootstrap is proven through both entry points.
"""

from __future__ import annotations

import unittest

from star_lists_skill import test_run_sh as base

from star_prune_skill.helpers import SCRIPTS


class PruneRunShTests(base.RunShTests):
    RUN_SH = SCRIPTS / "run.sh"

    def test_unstarring_needs_repo_as_well_as_user(self) -> None:
        self.with_python()
        self.with_gh(scopes="user, read:org")
        doctor = self.run_sh("doctor")
        self.assertEqual(doctor.returncode, 1)
        self.assertIn("writing needs: repo", doctor.stdout)
        for command in ("apply", "restore"):
            result = self.run_sh(command, "file.json", "--yes")
            self.assertEqual(result.returncode, 1)
            self.assertIn("--scopes repo", result.stderr)

    def test_public_repo_satisfies_the_repo_requirement(self) -> None:
        self.with_python()
        self.with_gh(scopes="user, public_repo")
        self.assertEqual(self.run_sh("doctor").returncode, 0)

    def test_login_hint_asks_for_both_scopes(self) -> None:
        self.with_python()
        self.with_gh(authed=False)
        self.assertIn("--scopes user,repo", self.run_sh("doctor").stdout)


if __name__ == "__main__":
    unittest.main()
