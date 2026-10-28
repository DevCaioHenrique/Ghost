"""Rotas HTTP/JSON. Apenas tradução de requisições; as regras ficam em services.py."""
from flask import Blueprint, request, jsonify, g
from . import services as s
from .validation import FIELD_TYPES

bp = Blueprint("api", __name__, url_prefix="/api")


def body():
    return request.get_json(silent=True) or {}


def flag(name):
    return request.args.get(name, "").lower() in ("1", "true", "yes")


@bp.get("/field-types")
def field_types():
    return jsonify(FIELD_TYPES)


@bp.get("/collections")
def collections():
    return jsonify(s.list_collections(g.db))


@bp.post("/collections")
def collection_create():
    return jsonify(s.create_collection(g.db, body())), 201


@bp.get("/collections/<cid>")
def collection_get(cid):
    return jsonify(s.get_collection(g.db, cid))


@bp.patch("/collections/<cid>")
def collection_update(cid):
    return jsonify(s.update_collection(g.db, cid, body()))


@bp.delete("/collections/<cid>")
def collection_delete(cid):
    s.delete_collection(g.db, cid, confirm=flag("confirm"))
    return "", 204


@bp.post("/collections/<cid>/fields")
def field_create(cid):
    return jsonify(s.add_field(g.db, cid, body())), 201


@bp.patch("/fields/<fid>")
def field_update(fid):
    return jsonify(s.update_field(g.db, fid, body()))


@bp.delete("/fields/<fid>")
def field_delete(fid):
    s.delete_field(g.db, fid, confirm=flag("confirm"))
    return "", 204


@bp.get("/collections/<cid>/records")
def records(cid):
    a = request.args
    filters = {k[7:-1]: v for k, v in a.items() if k.startswith("filter[") and k.endswith("]")}
    return jsonify(s.list_records(g.db, cid, q=a.get("q"), sort=a.get("sort"), desc=a.get("order") == "desc",
                                  filters=filters, limit=min(int(a.get("limit", 100)), 500), offset=int(a.get("offset", 0))))


@bp.post("/collections/<cid>/records")
def record_create(cid):
    return jsonify(s.create_record(g.db, cid, body())), 201


@bp.get("/records/<rid>")
def record_get(rid):
    return jsonify(s.get_record(g.db, rid))


@bp.patch("/records/<rid>")
def record_update(rid):
    return jsonify(s.update_record(g.db, rid, body()))


@bp.delete("/records/<rid>")
def record_delete(rid):
    s.delete_record(g.db, rid)
    return "", 204


@bp.get("/search")
def search():
    q = request.args.get("q", "").strip()
    return jsonify(s.search_all(g.db, q) if q else [])
