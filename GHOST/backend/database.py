"""Persistência: conexão SQLite, esquema orientado a metadados e dados iniciais."""
import json
import os
import shutil
import sqlite3
import tempfile
import uuid
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DATA_DIR, "ghost.db")
FILES_DIR = os.path.join(DATA_DIR, "files")

SCHEMA = """
CREATE TABLE IF NOT EXISTS collections(
  id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT DEFAULT '', icon TEXT DEFAULT '◈',
  color TEXT DEFAULT '#4fd1ff', position INTEGER DEFAULT 0, archived INTEGER DEFAULT 0,
  settings TEXT DEFAULT '{}', created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS fields(
  id TEXT PRIMARY KEY, collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
  name TEXT NOT NULL, description TEXT DEFAULT '', type TEXT NOT NULL, required INTEGER DEFAULT 0,
  default_value TEXT, options TEXT DEFAULT '{}', position INTEGER DEFAULT 0,
  hidden INTEGER DEFAULT 0, is_primary INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS records(
  id TEXT PRIMARY KEY, collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
  created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS record_values(
  record_id TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE,
  field_id TEXT NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
  value TEXT NOT NULL, text_value TEXT, num_value REAL, PRIMARY KEY(record_id, field_id));
CREATE INDEX IF NOT EXISTS idx_rv_field ON record_values(field_id, num_value);
CREATE INDEX IF NOT EXISTS idx_rec_col ON records(collection_id);
CREATE TABLE IF NOT EXISTS relationship_defs(
  id TEXT PRIMARY KEY, name TEXT NOT NULL, source_collection_id TEXT REFERENCES collections(id) ON DELETE CASCADE,
  target_collection_id TEXT REFERENCES collections(id) ON DELETE CASCADE,
  cardinality TEXT NOT NULL, directed INTEGER DEFAULT 1, required INTEGER DEFAULT 0,
  attributes TEXT DEFAULT '[]', created_at TEXT);
CREATE TABLE IF NOT EXISTS relationships(
  id TEXT PRIMARY KEY, def_id TEXT REFERENCES relationship_defs(id) ON DELETE CASCADE,
  source_id TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE,
  target_id TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE,
  label TEXT, start_date TEXT, end_date TEXT, notes TEXT, attributes TEXT DEFAULT '{}', created_at TEXT);
CREATE TABLE IF NOT EXISTS files(
  id TEXT PRIMARY KEY, original_name TEXT, mime TEXT, size INTEGER, stored_name TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS history(
  id INTEGER PRIMARY KEY AUTOINCREMENT, entity TEXT, entity_id TEXT, action TEXT, detail TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
"""

# Coleções iniciais: (nome, ícone, cor, [(campo, tipo, opções)]). O primeiro campo é o principal.
SEED = [
    ("Pessoas", "◉", "#4fd1ff", [("Nome", "short_text", {}), ("Apelidos", "tags", {}), ("Aniversário", "date", {}),
                                 ("Ocupação", "short_text", {}), ("Redes sociais", "long_text", {}),
                                 ("Foto", "file", {}), ("Observações", "long_text", {})]),
    ("Diário", "✎", "#7aa2ff", [("Título", "short_text", {}), ("Conteúdo", "long_text", {}),
                                ("Data do acontecimento", "date", {}), ("Categoria", "select", {"choices": []})]),
    ("Interesses", "✦", "#9be7c4", [("Nome", "short_text", {}), ("Descrição", "long_text", {})]),
    ("Grupos", "⬡", "#c9a7ff", [("Nome", "short_text", {}), ("Descrição", "long_text", {})]),
]


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path=None):
    target = path or DB_PATH
    os.makedirs(os.path.dirname(target), exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_db():
    return connect(DB_PATH)


def log(conn, entity, entity_id, action, detail=""):
    conn.execute("INSERT INTO history(entity,entity_id,action,detail,at) VALUES(?,?,?,?,?)",
                 (entity, entity_id, action, detail, now()))


def _columns(conn, table):
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _legacy_database(conn):
    return "position" not in _columns(conn, "collections") and bool(_columns(conn, "collections"))


def _legacy_json(value, default):
    if value is None or value == "":
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def _migrate_legacy_database(path):
    directory = os.path.dirname(path)
    backup = os.path.splitext(path)[0] + ".legacy.db"
    if os.path.exists(backup):
        backup = os.path.splitext(path)[0] + f".legacy-{datetime.now().strftime('%Y%m%d%H%M%S')}.db"
    fd, staged_path = tempfile.mkstemp(prefix="ghost-migrate-", suffix=".db", dir=directory)
    os.close(fd)
    source = connect(path)
    target = connect(staged_path)
    try:
        target.executescript(SCHEMA)
        collections = {}
        for position, row in enumerate(source.execute("SELECT * FROM collections ORDER BY id")):
            cid = new_id("col")
            collections[row["id"]] = cid
            target.execute(
                "INSERT INTO collections(id,name,description,icon,color,position,archived,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (cid, row["name"], row["description"] or "", row["icon"] or "◈",
                 row["color"] or "#4fd1ff", position, row["archived"] or 0,
                 row["created_at"], row["created_at"]),
            )

        fields = {}
        field_types = {}
        primary_assigned = set()
        for row in source.execute("SELECT * FROM fields ORDER BY collection_id, order_index, id"):
            fid = new_id("fld")
            cid = collections[row["collection_id"]]
            ftype = {"text": "short_text", "longtext": "long_text"}.get(row["type"], row["type"])
            options = _legacy_json(row["options_json"], {})
            if not isinstance(options, dict):
                options = {}
            if row["ref_collection_id"] is not None:
                options["target"] = collections[row["ref_collection_id"]]
            default = _legacy_json(row["default_value"], None)
            fields[row["id"]] = fid
            field_types[fid] = ftype
            is_primary = cid not in primary_assigned
            primary_assigned.add(cid)
            target.execute(
                "INSERT INTO fields(id,collection_id,name,description,type,required,default_value,options,position,hidden,is_primary) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (fid, cid, row["name"], row["description"] or "", ftype, row["required"] or 0,
                 None if default is None else json.dumps(default), json.dumps(options),
                 row["order_index"] or 0, row["hidden"] or 0, int(is_primary)),
            )

        records = {}
        for row in source.execute("SELECT * FROM records ORDER BY id"):
            rid = new_id("rec")
            records[row["id"]] = rid
            target.execute(
                "INSERT INTO records(id,collection_id,created_at,updated_at) VALUES(?,?,?,?)",
                (rid, collections[row["collection_id"]], row["created_at"], row["updated_at"]),
            )

        if "record_values" in {row["name"] for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}:
            for row in source.execute("SELECT * FROM record_values"):
                value = _legacy_json(row["value_json"], None)
                if value is None:
                    value = row["value_number"] if row["value_number"] is not None else row["value_text"]
                if value is None:
                    continue
                ftype = field_types[fields[row["field_id"]]]
                text = ", ".join(map(str, value)) if isinstance(value, list) else str(value)
                number = float(value) if ftype in ("integer", "decimal") else None
                target.execute(
                    "INSERT INTO record_values(record_id,field_id,value,text_value,num_value) VALUES(?,?,?,?,?)",
                    (records[row["record_id"]], fields[row["field_id"]],
                     json.dumps(value, ensure_ascii=False), text, number),
                )

        relationships = {}
        if "relationships" in {row["name"] for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}:
            for row in source.execute("SELECT * FROM relationships"):
                rel_id = new_id("rel")
                relationships[row["id"]] = rel_id
                attributes = _legacy_json(row["attributes_json"], [])
                target.execute(
                    "INSERT INTO relationship_defs(id,name,source_collection_id,target_collection_id,cardinality,directed,required,attributes,created_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?)",
                    (rel_id, row["name"], collections[row["source_collection_id"]],
                     collections[row["target_collection_id"]], row["cardinality"], row["directed"],
                     row["required"], json.dumps(attributes), row["created_at"]),
                )
        if "record_links" in {row["name"] for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}:
            for row in source.execute("SELECT * FROM record_links"):
                target.execute(
                    "INSERT INTO relationships(id,def_id,source_id,target_id,attributes,created_at) VALUES(?,?,?,?,?,?)",
                    (new_id("link"), relationships[row["relationship_id"]],
                     records[row["source_record_id"]], records[row["target_record_id"]],
                     json.dumps(_legacy_json(row["attributes_json"], {})), row["created_at"]),
                )

        if "files" in {row["name"] for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}:
            for row in source.execute("SELECT * FROM files"):
                target.execute(
                    "INSERT INTO files(id,original_name,mime,stored_name,created_at) VALUES(?,?,?,?,?)",
                    (new_id("file"), row["filename"], row["mimetype"], row["path"], row["created_at"]),
                )
        if "settings" in {row["name"] for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}:
            target.executemany("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
                               source.execute("SELECT key,value FROM settings"))
        if "history" in {row["name"] for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}:
            for row in source.execute("SELECT * FROM history"):
                target.execute(
                    "INSERT INTO history(entity,entity_id,action,detail,at) VALUES(?,?,?,?,?)",
                    ("legacy", "", row["action"], row["details"] or "", row["created_at"]),
                )

        target.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('seeded','1')")
        target.commit()
        source.close()
        target.close()
        shutil.copy2(path, backup)
        os.replace(staged_path, path)
    except Exception:
        source.close()
        target.close()
        if os.path.exists(staged_path):
            os.remove(staged_path)
        raise


class InitHandle:
    def close(self):
        return None


def init_db(path=None):
    """Cria tabelas e dados iniciais na primeira execução; nunca apaga dados existentes."""
    p = path or DB_PATH
    os.makedirs(os.path.dirname(p), exist_ok=True)
    files_dir = FILES_DIR if path is None else os.path.join(os.path.dirname(p), "files")
    os.makedirs(files_dir, exist_ok=True)
    if os.path.exists(p):
        conn = connect(p)
        try:
            if _legacy_database(conn):
                conn.close()
                _migrate_legacy_database(p)
        finally:
            try:
                conn.close()
            except sqlite3.ProgrammingError:
                pass
    conn = connect(p)
    try:
        with conn:
            conn.executescript(SCHEMA)
            if conn.execute("SELECT 1 FROM settings WHERE key='seeded'").fetchone():
                return InitHandle()
            t = now()
            for pos, (name, icon, color, fields) in enumerate(SEED):
                cid = new_id("col")
                conn.execute("INSERT INTO collections(id,name,icon,color,position,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                             (cid, name, icon, color, pos, t, t))
                for i, (fname, ftype, opts) in enumerate(fields):
                    conn.execute("INSERT INTO fields(id,collection_id,name,type,options,position,is_primary,required) VALUES(?,?,?,?,?,?,?,?)",
                                 (new_id("fld"), cid, fname, ftype, json.dumps(opts), i, int(i == 0), int(i == 0)))
            conn.execute("INSERT INTO settings(key,value) VALUES('seeded','1')")
    finally:
        conn.close()
    return InitHandle()
