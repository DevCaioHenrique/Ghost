import os, sqlite3, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app


class T(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "t.db")
        self.c = create_app(self.path).test_client()

    def test_fluxo(self):
        c = self.c
        cols = c.get("/api/collections").get_json()
        self.assertEqual([x["name"] for x in cols][:2], ["Pessoas", "Diário"])
        pessoas = cols[0]; nome = pessoas["fields"][0]["id"]
        livros = c.post("/api/collections", json={"name": "Livros"}).get_json()
        lid = livros["fields"][0]["id"]
        nota = c.post(f"/api/collections/{livros['id']}/fields", json={"name": "Nota", "type": "integer"}).get_json()
        r = c.post(f"/api/collections/{livros['id']}/records", json={"values": {lid: "Dune", nota["id"]: "5"}})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()["values"][nota["id"]], 5)
        self.assertEqual(c.post(f"/api/collections/{livros['id']}/records", json={"values": {}}).status_code, 422)
        self.assertEqual(c.post(f"/api/collections/{livros['id']}/records", json={"values": {lid: "A", nota["id"]: "x"}}).status_code, 422)
        self.assertEqual(c.get(f"/api/collections/{livros['id']}/records?sort={nota['id']}&order=desc").get_json()["total"], 1)
        self.assertEqual(len(c.get("/api/search?q=dun").get_json()), 1)
        self.assertEqual(c.patch(f"/api/fields/{nota['id']}", json={"type": "date"}).status_code, 409)
        self.assertEqual(c.patch(f"/api/fields/{nota['id']}", json={"type": "short_text"}).status_code, 200)
        ref = c.post(f"/api/collections/{livros['id']}/fields", json={"name": "Indicado por", "type": "reference_list", "options": {"target": pessoas["id"]}}).get_json()
        p = c.post(f"/api/collections/{pessoas['id']}/records", json={"values": {nome: "Ana"}}).get_json()
        l = c.post(f"/api/collections/{livros['id']}/records", json={"values": {lid: "Emma", ref["id"]: [p["id"]]}}).get_json()
        self.assertEqual(c.post(f"/api/collections/{livros['id']}/records", json={"values": {lid: "X", ref["id"]: ["rec_fake"]}}).status_code, 422)
        self.assertEqual(c.delete(f"/api/collections/{pessoas['id']}").status_code, 409)
        c.delete(f"/api/records/{p['id']}")
        self.assertNotIn(ref["id"], c.get(f"/api/records/{l['id']}").get_json()["values"])
        self.assertEqual(c.delete(f"/api/fields/{nota['id']}").status_code, 409)
        self.assertEqual(c.delete(f"/api/fields/{nota['id']}?confirm=true").status_code, 204)

    def test_persistencia(self):
        self.c.post("/api/collections", json={"name": "Lugares"})
        n = len(create_app(self.path).test_client().get("/api/collections").get_json())
        self.assertEqual(n, 5)

    def test_migracao_banco_antigo(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "ghost.db")
            conn = sqlite3.connect(path)
            conn.executescript("""
                CREATE TABLE collections(
                    id INTEGER PRIMARY KEY, name TEXT, description TEXT, icon TEXT, color TEXT,
                    archived INTEGER, created_at TEXT);
                CREATE TABLE fields(
                    id INTEGER PRIMARY KEY, collection_id INTEGER, name TEXT, type TEXT, required INTEGER,
                    default_value TEXT, options_json TEXT, ref_collection_id INTEGER, order_index INTEGER,
                    hidden INTEGER, description TEXT);
                CREATE TABLE records(
                    id INTEGER PRIMARY KEY, collection_id INTEGER, created_at TEXT, updated_at TEXT);
                CREATE TABLE record_values(
                    id INTEGER PRIMARY KEY, record_id INTEGER, field_id INTEGER,
                    value_text TEXT, value_number REAL, value_json TEXT);
                INSERT INTO collections VALUES(1, 'Arquivo', '', '◈', '#4fd1ff', 0, '2024-01-01');
                INSERT INTO fields VALUES(2, 1, 'Título', 'text', 1, NULL, '{}', NULL, 0, 0, '');
                INSERT INTO records VALUES(3, 1, '2024-01-01', '2024-01-01');
                INSERT INTO record_values VALUES(4, 3, 2, 'Preservado', NULL, '"Preservado"');
            """)
            conn.close()

            client = create_app(path).test_client()
            collections = client.get("/api/collections").get_json()
            self.assertEqual(collections[0]["name"], "Arquivo")
            result = client.get(f"/api/collections/{collections[0]['id']}/records").get_json()
            field_id = collections[0]["fields"][0]["id"]
            self.assertEqual(result["items"][0]["values"][field_id], "Preservado")
            self.assertTrue(os.path.exists(os.path.join(temp_dir, "ghost.legacy.db")))


if __name__ == "__main__":
    unittest.main()
