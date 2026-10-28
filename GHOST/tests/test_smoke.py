import os
import tempfile
import unittest

from backend import database, services

class GhostSmokeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        database.DATA_DIR = self.tmp.name
        database.DB_PATH = os.path.join(self.tmp.name, "ghost.db")
        database.FILES_DIR = os.path.join(self.tmp.name, "files")
        database.init_db()
        self.conn = database.get_db()

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_create_collection_field_and_record(self):
        collection = services.create_collection(
            self.conn,
            {"name": "Livros", "description": "Leituras"},
        )
        field = services.create_field(
            self.conn,
            collection["id"],
            {"name": "Título", "type": "text", "required": True},
        )
        record = services.create_record(
            self.conn,
            collection["id"],
            {str(field["id"]): "Duna"},
        )
        self.assertEqual(record["values"][str(field["id"])], "Duna")

if __name__ == "__main__":
    unittest.main()
