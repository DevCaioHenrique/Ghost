"""Validação e normalização de valores por tipo de campo + exceções do domínio."""
import re
import datetime as dt

FIELD_TYPES = ["text", "short_text", "long_text", "integer", "decimal", "date", "datetime", "boolean",
               "select", "tags", "url", "email", "phone", "file", "reference", "reference_list"]
TEXTUAL = ("text", "short_text", "long_text", "phone", "url", "email")
REFS = ("reference", "reference_list")


class GhostError(Exception):
    pass


class ValidationError(GhostError):
    def __init__(self, msg, fields=None):
        super().__init__(msg)
        self.fields = fields or {}


class NotFound(GhostError):
    pass


class Conflict(GhostError):
    def __init__(self, msg, details=None):
        super().__init__(msg)
        self.details = details or {}


_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL = re.compile(r"^https?://\S+$", re.I)


def normalize(ftype, v, opts=None):
    """Retorna o valor normalizado (ou None se vazio). Levanta ValidationError se inválido."""
    opts = opts or {}
    if v is None or (isinstance(v, (str, list)) and len(v) == 0):
        return None
    bad = lambda m: ValidationError(m)
    if ftype == "text":
        ftype = "short_text"
    try:
        if ftype in ("short_text", "phone", "url", "email"):
            s = str(v).strip()
            if len(s) > 500:
                raise bad("texto longo demais (máx. 500)")
            if ftype == "url" and not _URL.match(s):
                raise bad("URL inválida (use http:// ou https://)")
            if ftype == "email" and not _EMAIL.match(s):
                raise bad("e-mail inválido")
            return s or None
        if ftype == "long_text":
            return str(v)
        if ftype == "integer":
            if isinstance(v, bool):
                raise bad("número inteiro inválido")
            return int(str(v).strip())
        if ftype == "decimal":
            if isinstance(v, bool):
                raise bad("número decimal inválido")
            return float(str(v).strip().replace(",", "."))
        if ftype == "date":
            return dt.date.fromisoformat(str(v)).isoformat()
        if ftype == "datetime":
            return dt.datetime.fromisoformat(str(v)).isoformat()
        if ftype == "boolean":
            if isinstance(v, bool):
                return v
            if str(v).lower() in ("true", "false"):
                return str(v).lower() == "true"
            raise bad("valor booleano inválido")
        if ftype == "select":
            if v not in opts.get("choices", []):
                raise bad("opção não permitida")
            return v
        if ftype == "tags":
            if not isinstance(v, list):
                raise bad("esperada uma lista de tags")
            return list(dict.fromkeys(str(t).strip() for t in v if str(t).strip())) or None
        if ftype in ("file", "reference"):
            if not isinstance(v, str):
                raise bad("identificador inválido")
            return v
        if ftype == "reference_list":
            if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                raise bad("esperada uma lista de identificadores")
            return list(dict.fromkeys(v))
    except ValueError:
        raise bad(f"valor inválido para o tipo {ftype}")
    raise bad(f"tipo desconhecido: {ftype}")
