from __future__ import annotations

import unittest
from tempfile import TemporaryDirectory

from infra.db.supabase_client import FileDatabaseClient


class FileDatabaseClientTests(unittest.TestCase):
    def test_file_database_persists_rows_across_instances(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = f"{temp_dir}/alphaforge_db.json"
            first_client = FileDatabaseClient(path)
            inserted = first_client.insert(
                "strategies",
                {
                    "id": "strategy-1",
                    "name": "Strategy One",
                    "direction": "BUY",
                },
            )

            second_client = FileDatabaseClient(path)
            rows = second_client.select("strategies", filters={"id": "strategy-1"})

        self.assertEqual(inserted["id"], "strategy-1")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Strategy One")

    def test_file_database_updates_rows(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = f"{temp_dir}/alphaforge_db.json"
            client = FileDatabaseClient(path)
            client.insert("mining_campaigns", {"id": "campaign-1", "status": "running"})

            updated = client.update(
                "mining_campaigns",
                filters={"id": "campaign-1"},
                values={"status": "completed"},
            )

            rows = client.select("mining_campaigns", filters={"id": "campaign-1"})

        self.assertEqual(updated[0]["status"], "completed")
        self.assertEqual(rows[0]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
