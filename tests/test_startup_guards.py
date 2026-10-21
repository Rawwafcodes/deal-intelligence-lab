"""Task 20.4: ordinary local `python server.py` / `python worker.py` runs
must not be able to silently reach a real hosted database - the same gap
Task 19.7 closed for test runs (a developer's .env.local can carry a real
staging DATABASE_URL even though its own comment says "leave unset
locally"), closed here at the one place each entry point would otherwise
first try that connection.

Each guard's condition is a small pure function main() checks before doing
anything else - tested directly here rather than through main() itself,
which goes on to bind a port / start polling for mandate runs when the
guard doesn't fire.
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server
import store
import worker


class IsLocalDatabaseUrlTests(unittest.TestCase):
    def test_local_hosts_are_local(self):
        # IPv6 needs brackets in a URL authority - a bare "::1" isn't a
        # valid DATABASE_URL and urlsplit correctly can't parse a hostname
        # out of it at all.
        for host in ("localhost", "127.0.0.1", "[::1]"):
            self.assertTrue(store.is_local_database_url(f"postgresql://u:p@{host}/db"))

    def test_remote_host_is_not_local(self):
        self.assertFalse(store.is_local_database_url("postgresql://u:p@staging.example.com/db"))


class ServerStartupGuardTests(unittest.TestCase):
    def setUp(self):
        self._original_database_url = store.DATABASE_URL
        self._original_auth_mode = server.AUTH_MODE

    def tearDown(self):
        store.DATABASE_URL = self._original_database_url
        server.AUTH_MODE = self._original_auth_mode

    def test_refuses_dev_mode_against_a_non_local_database(self):
        server.AUTH_MODE = "dev"
        store.DATABASE_URL = "postgresql://u:p@staging.example.com/db"
        self.assertTrue(server.dev_mode_targets_non_local_database())

    def test_allows_dev_mode_against_a_local_database(self):
        server.AUTH_MODE = "dev"
        store.DATABASE_URL = "postgresql://u:p@localhost/db"
        self.assertFalse(server.dev_mode_targets_non_local_database())

    def test_allows_dev_mode_with_no_database_url_set(self):
        server.AUTH_MODE = "dev"
        store.DATABASE_URL = ""
        self.assertFalse(server.dev_mode_targets_non_local_database())

    def test_allows_hosted_mode_against_a_non_local_database(self):
        server.AUTH_MODE = "clerk"
        store.DATABASE_URL = "postgresql://u:p@staging.example.com/db"
        self.assertFalse(server.dev_mode_targets_non_local_database())

    def test_main_actually_raises_when_the_guard_fires(self):
        server.AUTH_MODE = "dev"
        store.DATABASE_URL = "postgresql://u:p@staging.example.com/db"
        with self.assertRaises(SystemExit) as ctx:
            server.main()
        self.assertIn("DATABASE_URL", str(ctx.exception))


class WorkerStartupGuardTests(unittest.TestCase):
    def setUp(self):
        self._original_database_url = store.DATABASE_URL
        self._original_environment = os.environ.get("DEAL_LAB_ENVIRONMENT")
        os.environ.pop("DEAL_LAB_ENVIRONMENT", None)

    def tearDown(self):
        store.DATABASE_URL = self._original_database_url
        if self._original_environment is None:
            os.environ.pop("DEAL_LAB_ENVIRONMENT", None)
        else:
            os.environ["DEAL_LAB_ENVIRONMENT"] = self._original_environment

    def test_refuses_non_local_database_with_no_environment_set(self):
        store.DATABASE_URL = "postgresql://u:p@staging.example.com/db"
        self.assertTrue(worker.non_local_database_without_environment())

    def test_allows_non_local_database_when_environment_is_set(self):
        store.DATABASE_URL = "postgresql://u:p@staging.example.com/db"
        os.environ["DEAL_LAB_ENVIRONMENT"] = "staging"
        self.assertFalse(worker.non_local_database_without_environment())

    def test_allows_local_database_regardless_of_environment(self):
        store.DATABASE_URL = "postgresql://u:p@localhost/db"
        self.assertFalse(worker.non_local_database_without_environment())

    def test_main_actually_raises_when_the_guard_fires(self):
        store.DATABASE_URL = "postgresql://u:p@staging.example.com/db"
        with self.assertRaises(SystemExit) as ctx:
            worker.main()
        self.assertIn("DATABASE_URL", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
