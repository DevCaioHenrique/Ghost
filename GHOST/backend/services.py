"""Regras de negócio: coleções, campos e registros (modelo genérico orientado a metadados)."""
import json
from .database import new_id, now, log
from .validation import (FIELD_TYPES, TEXTUAL, REFS, ValidationError, NotFound, Conflict, normalize)


def _field(r):
    d = dict(r)
    d["options"] = json.loads(d["options"] or "{}")
    d["default_value"] = json.loads(d["default_value"]) if d["default_value"] is not None else None
    for k in ("required", "hidden", "is_primary"):
        d[k] = bool(d[k])
    return d


def _col(r):
    d = dict(r)
    d["settings"] = json.loads(d["settings"] or "{}")
    d["archived"] = bool(d["archived"])
    return d


def _need_name(data):
    n = str(data.get("name", "")).strip()
    if not n:
        raise ValidationError("O nome é obrigatório.", {"name": "obrigatório"})
    return n


def create_field(conn, cid, data):
    return add_field(conn, cid, data)


# ---------- Coleções ----------
def list_collections(conn):
    cols = [_col(r) for r in conn.execute("SELECT * FROM collections ORDER BY position, created_at")]
    by = {c["id"]: c for c in cols}
    for c in cols:
        c["fields"] = []
    for r in conn.execute("SELECT * FROM fields ORDER BY position"):
        by[r["collection_id"]]["fields"].append(_field(r))
    return cols


def get_fields(conn, cid):
    return [_field(r) for r in conn.execute("SELECT * FROM fields WHERE collection_id=? ORDER BY position", (cid,))]


def get_collection(conn, cid):
    r = conn.execute("SELECT * FROM collections WHERE id=?", (cid,)).fetchone()
    if not r:
        raise NotFound("Coleção não encontrada.")
    c = _col(r)
    c["fields"] = get_fields(conn, cid)
    return c


def create_collection(conn, data):
    name, t = _need_name(data), now()
    cid = new_id("col")
    with conn:
        pos = conn.execute("SELECT COALESCE(MAX(position),-1)+1 FROM collections").fetchone()[0]
        conn.execute("INSERT INTO collections(id,name,description,icon,color,position,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                     (cid, name, data.get("description", ""), data.get("icon", "◈"), data.get("color", "#4fd1ff"), pos, t, t))
        # campo principal inicial: a coleção funciona imediatamente
        conn.execute("INSERT INTO fields(id,collection_id,name,type,position,is_primary,required) VALUES(?,?,?,?,0,1,1)",
                     (new_id("fld"), cid, "Nome", "short_text"))
        log(conn, "collection", cid, "create", name)
    return get_collection(conn, cid)


def update_collection(conn, cid, data):
    get_collection(conn, cid)
    sets = {k: data[k] for k in ("name", "description", "icon", "color", "position", "archived") if k in data}
    if "name" in sets:
        sets["name"] = _need_name(sets)
    if "settings" in data:
        sets["settings"] = json.dumps(data["settings"])
    if sets:
        with conn:
            cols = ", ".join(f"{k}=?" for k in sets)  # chaves vêm da lista fixa acima
            conn.execute(f"UPDATE collections SET {cols}, updated_at=? WHERE id=?", (*sets.values(), now(), cid))
            log(conn, "collection", cid, "update", ",".join(sets))
    return get_collection(conn, cid)


def delete_collection(conn, cid, confirm=False):
    get_collection(conn, cid)
    deps = [dict(r) for r in conn.execute(
        "SELECT f.id, f.name, c.name AS collection FROM fields f JOIN collections c ON c.id=f.collection_id "
        "WHERE f.type IN ('reference','reference_list') AND f.collection_id<>? AND json_extract(f.options,'$.target')=?", (cid, cid))]
    if deps:
        raise Conflict("Outras coleções possuem campos de referência para esta. Remova-os antes.", {"fields": deps})
    n = conn.execute("SELECT COUNT(*) FROM records WHERE collection_id=?", (cid,)).fetchone()[0]
    if not confirm:
        raise Conflict(f"Esta coleção possui {n} registro(s), que serão excluídos.", {"records": n})
    with conn:
        conn.execute("DELETE FROM collections WHERE id=?", (cid,))
        log(conn, "collection", cid, "delete", f"{n} registros")


# ---------- Campos ----------
def _check_options(conn, ftype, opts):
    if ftype == "select" and not isinstance(opts.get("choices", []), list):
        raise ValidationError("As opções devem ser uma lista.", {"options": "inválido"})
    if ftype in REFS and not conn.execute("SELECT 1 FROM collections WHERE id=?", (opts.get("target"),)).fetchone():
        raise ValidationError("Campo de referência exige uma coleção de destino existente.", {"options": "target inválido"})


def get_field(conn, fid):
    r = conn.execute("SELECT * FROM fields WHERE id=?", (fid,)).fetchone()
    if not r:
        raise NotFound("Campo não encontrado.")
    return _field(r)


def add_field(conn, cid, data):
    get_collection(conn, cid)
    name, ftype, opts = _need_name(data), data.get("type"), data.get("options") or {}
    if ftype not in FIELD_TYPES:
        raise ValidationError("Tipo de campo inválido.", {"type": "inválido"})
    _check_options(conn, ftype, opts)
    default = normalize(ftype, data.get("default_value"), opts)
    fid = new_id("fld")
    with conn:
        pos = conn.execute("SELECT COALESCE(MAX(position),-1)+1 FROM fields WHERE collection_id=?", (cid,)).fetchone()[0]
        conn.execute("INSERT INTO fields(id,collection_id,name,description,type,required,default_value,options,position,hidden) VALUES(?,?,?,?,?,?,?,?,?,?)",
                     (fid, cid, name, data.get("description", ""), ftype, int(bool(data.get("required"))),
                      None if default is None else json.dumps(default), json.dumps(opts), pos, int(bool(data.get("hidden")))))
        log(conn, "field", fid, "create", name)
    return get_field(conn, fid)


def _convert(v, new_type, opts):
    if new_type in TEXTUAL:
        v = ", ".join(map(str, v)) if isinstance(v, list) else ("sim" if v is True else "não" if v is False else str(v))
    elif new_type == "tags" and isinstance(v, str):
        v = [x.strip() for x in v.split(",")]
    elif new_type == "reference_list" and isinstance(v, str):
        v = [v]
    elif new_type == "reference" and isinstance(v, list) and len(v) == 1:
        v = v[0]
    return normalize(new_type, v, opts)


def update_field(conn, fid, data):
    f = get_field(conn, fid)
    sets = {k: data[k] for k in ("description", "required", "hidden", "position", "is_primary") if k in data}
    if "name" in data:
        sets["name"] = _need_name(data)
    new_type, opts = data.get("type", f["type"]), data.get("options", f["options"])
    if "default_value" in data:
        d = normalize(new_type, data["default_value"], opts)
        sets["default_value"] = None if d is None else json.dumps(d)
    with conn:
        if new_type != f["type"] or "options" in data:
            if new_type not in FIELD_TYPES:
                raise ValidationError("Tipo de campo inválido.", {"type": "inválido"})
            _check_options(conn, new_type, opts)
            plan, failed = [], []
            for r in conn.execute("SELECT record_id, value FROM record_values WHERE field_id=?", (fid,)).fetchall():
                try:
                    if new_type in REFS and f["type"] not in REFS:
                        raise ValidationError("incompatível")
                    plan.append((r["record_id"], _convert(json.loads(r["value"]), new_type, opts)))
                except ValidationError:
                    failed.append(r["record_id"])
            if failed and not data.get("confirm"):
                raise Conflict(f"{len(failed)} valor(es) não podem ser convertidos e serão removidos.",
                               {"affected_records": failed[:50], "count": len(failed)})
            for rid in failed:
                conn.execute("DELETE FROM record_values WHERE record_id=? AND field_id=?", (rid, fid))
            for rid, v in plan:
                _store(conn, rid, fid, new_type, v)
            sets["type"], sets["options"] = new_type, json.dumps(opts)
        if sets:
            cols = ", ".join(f"{k}=?" for k in sets)  # chaves vêm de lista fixa
            conn.execute(f"UPDATE fields SET {cols} WHERE id=?", (*sets.values(), fid))
            if sets.get("is_primary"):
                conn.execute("UPDATE fields SET is_primary=0 WHERE collection_id=? AND id<>?", (f["collection_id"], fid))
            log(conn, "field", fid, "update", ",".join(sets))
    return get_field(conn, fid)


def delete_field(conn, fid, confirm=False):
    f = get_field(conn, fid)
    if f["is_primary"]:
        raise Conflict("Este é o campo principal. Defina outro campo como principal antes de excluí-lo.")
    n = conn.execute("SELECT COUNT(*) FROM record_values WHERE field_id=?", (fid,)).fetchone()[0]
    if not confirm:
        raise Conflict(f"{n} valor(es) armazenado(s) neste campo serão removidos.", {"values": n})
    with conn:
        conn.execute("DELETE FROM fields WHERE id=?", (fid,))
        log(conn, "field", fid, "delete", f["name"])


# ---------- Registros ----------
def _store(conn, rid, fid, ftype, v):
    text = ", ".join(map(str, v)) if isinstance(v, list) else str(v)
    num = float(v) if ftype in ("integer", "decimal") else None
    conn.execute("INSERT OR REPLACE INTO record_values(record_id,field_id,value,text_value,num_value) VALUES(?,?,?,?,?)",
                 (rid, fid, json.dumps(v, ensure_ascii=False), text, num))


def _validate(conn, fields, values, partial):
    out, errors = {}, {}
    for u in set(values) - {f["id"] for f in fields}:
        errors[u] = "campo desconhecido"
    if not values and not partial:
        for f in fields:
            if f["required"]:
                errors[f["id"]] = "campo obrigatório"
        if errors:
            raise ValidationError("Dados inválidos.", errors)
    for f in fields:
        if f["id"] in values:
            raw = values[f["id"]]
        elif partial:
            continue
        else:
            raw = f["default_value"]
        try:
            v = normalize(f["type"], raw, f["options"])
            if v is None and f["required"] and not values:
                raise ValidationError("campo obrigatório")
            if v is not None and f["type"] in REFS:
                for ref in (v if isinstance(v, list) else [v]):
                    if not conn.execute("SELECT 1 FROM records WHERE id=? AND collection_id=?", (ref, f["options"].get("target"))).fetchone():
                        raise ValidationError(f"referência inexistente: {ref}")
            out[f["id"]] = v
        except ValidationError as e:
            errors[f["id"]] = str(e)
    if errors:
        raise ValidationError("Dados inválidos.", errors)
    return out


def _load(conn, ids):
    recs = {}
    for rid in ids:
        r = conn.execute("SELECT * FROM records WHERE id=?", (rid,)).fetchone()
        if r:
            recs[rid] = {**dict(r), "values": {}}
            for v in conn.execute("SELECT field_id, value FROM record_values WHERE record_id=?", (rid,)):
                recs[rid]["values"][v["field_id"]] = json.loads(v["value"])
    return [recs[i] for i in ids if i in recs]


def get_record(conn, rid):
    r = _load(conn, [rid])
    if not r:
        raise NotFound("Registro não encontrado.")
    return r[0]


def create_record(conn, cid, data):
    get_collection(conn, cid)
    fields = get_fields(conn, cid)
    payload = data.get("values") if isinstance(data, dict) and "values" in data else data
    values = _validate(conn, fields, payload or {}, partial=False)
    ft = {f["id"]: f["type"] for f in fields}
    rid, t = new_id("rec"), now()
    with conn:
        conn.execute("INSERT INTO records(id,collection_id,created_at,updated_at) VALUES(?,?,?,?)", (rid, cid, t, t))
        for fid, v in values.items():
            if v is not None:
                _store(conn, rid, fid, ft[fid], v)
        log(conn, "record", rid, "create", cid)
    return get_record(conn, rid)


def update_record(conn, rid, data):
    rec = get_record(conn, rid)
    fields = get_fields(conn, rec["collection_id"])
    payload = data.get("values") if isinstance(data, dict) and "values" in data else data
    values = _validate(conn, fields, payload or {}, partial=True)
    ft = {f["id"]: f["type"] for f in fields}
    with conn:
        for fid, v in values.items():
            if v is None:
                conn.execute("DELETE FROM record_values WHERE record_id=? AND field_id=?", (rid, fid))
            else:
                _store(conn, rid, fid, ft[fid], v)
        conn.execute("UPDATE records SET updated_at=? WHERE id=?", (now(), rid))
        log(conn, "record", rid, "update", ",".join(values))
    return get_record(conn, rid)


def delete_record(conn, rid):
    get_record(conn, rid)
    with conn:
        # remove apenas a referência ao registro excluído; os demais dados são preservados
        for r in conn.execute("SELECT v.record_id, v.field_id, v.value, f.type FROM record_values v JOIN fields f ON f.id=v.field_id "
                              "WHERE f.type IN ('reference','reference_list') AND v.text_value LIKE ?", (f"%{rid}%",)).fetchall():
            val = json.loads(r["value"])
            new = [x for x in val if x != rid] if isinstance(val, list) else (None if val == rid else val)
            if new:
                _store(conn, r["record_id"], r["field_id"], r["type"], new)
            else:
                conn.execute("DELETE FROM record_values WHERE record_id=? AND field_id=?", (r["record_id"], r["field_id"]))
        conn.execute("DELETE FROM records WHERE id=?", (rid,))
        log(conn, "record", rid, "delete")


def _like(s):
    return "%" + s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def list_records(conn, cid, q=None, sort=None, desc=False, filters=None, limit=100, offset=0):
    get_collection(conn, cid)
    fields = {f["id"] for f in get_fields(conn, cid)}
    sql, args = "FROM records r WHERE r.collection_id=?", [cid]
    if q:
        sql += " AND EXISTS(SELECT 1 FROM record_values v WHERE v.record_id=r.id AND v.text_value LIKE ? ESCAPE '\\')"
        args.append(_like(q))
    for fid, term in (filters or {}).items():
        if fid not in fields:
            raise ValidationError("Filtro por campo desconhecido.", {fid: "desconhecido"})
        sql += " AND EXISTS(SELECT 1 FROM record_values v WHERE v.record_id=r.id AND v.field_id=? AND v.text_value LIKE ? ESCAPE '\\')"
        args += [fid, _like(str(term))]
    total = conn.execute("SELECT COUNT(*) " + sql, args).fetchone()[0]
    order, oargs = "r.created_at", []
    if sort:
        if sort not in fields:
            raise ValidationError("Ordenação por campo desconhecido.", {sort: "desconhecido"})
        d = "DESC" if desc else "ASC"
        order = (f"(SELECT num_value FROM record_values WHERE record_id=r.id AND field_id=?) {d}, "
                 f"(SELECT text_value FROM record_values WHERE record_id=r.id AND field_id=?) {d}, r.created_at")
        oargs = [sort, sort]
    ids = [r[0] for r in conn.execute(f"SELECT r.id {sql} ORDER BY {order} LIMIT ? OFFSET ?", [*args, *oargs, limit, offset])]
    return {"items": _load(conn, ids), "total": total}


def search_all(conn, q, limit=50):
    """Busca global: registros de qualquer coleção cujo texto contenha q."""
    rows = conn.execute("SELECT DISTINCT r.id FROM records r JOIN record_values v ON v.record_id=r.id "
                        "WHERE v.text_value LIKE ? ESCAPE '\\' LIMIT ?", (_like(q), limit)).fetchall()
    return _load(conn, [r[0] for r in rows])
