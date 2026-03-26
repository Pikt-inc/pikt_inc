from __future__ import annotations

import html
import json
import sys
import types
import unittest
from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

DEFAULT_NOW = datetime(2026, 3, 25, 12, 0, 0)
_HARNESS_STATE: dict[str, object] = {}


def ensure_app_root_on_path() -> Path:
    app_root = Path(__file__).resolve().parents[2]
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))
    return app_root


def _to_datetime(value=None):
    if value is None or value == "":
        return DEFAULT_NOW
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())

    text = str(value).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return DEFAULT_NOW


def _to_date(value=None):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return _to_datetime(value).date()


def _add_to_date(value=None, days=0, hours=0, minutes=0, seconds=0, as_string=False, as_datetime=False):
    dt_value = _to_datetime(value) + timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
    if as_datetime:
        return dt_value
    if as_string:
        return dt_value.strftime("%Y-%m-%d %H:%M:%S")
    return dt_value


def _add_days(value, days):
    base = _to_date(value)
    return base + timedelta(days=days)


def _add_months(value, months):
    base = _to_date(value)
    total_months = (base.year * 12 + base.month - 1) + int(months)
    year = total_months // 12
    month = total_months % 12 + 1
    day = min(base.day, monthrange(year, month)[1])
    return date(year, month, day)


def _format_datetime(value):
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _format_date(value):
    if value in (None, ""):
        return ""
    if isinstance(value, (date, datetime)):
        return _to_date(value).isoformat()
    return str(value)


def _escape_html(value):
    return html.escape(str(value or ""))


def _get_url(path=""):
    path = str(path or "")
    if path and not path.startswith("/"):
        path = "/" + path
    return f"https://example.test{path}"


def _get_request_header(_key):
    return ""


def _throw(message, **_kwargs):
    raise Exception(message)


def _whitelist(**_kwargs):
    def decorator(fn):
        return fn

    return decorator


def _parse_json(data):
    if isinstance(data, str):
        return json.loads(data)
    return data


def _build_utils_module():
    utils_module = types.ModuleType("frappe.utils")
    utils_module.add_days = _add_days
    utils_module.add_months = _add_months
    utils_module.add_to_date = _add_to_date
    utils_module.escape_html = _escape_html
    utils_module.format_date = _format_date
    utils_module.format_datetime = _format_datetime
    utils_module.get_datetime = _to_datetime
    utils_module.get_datetime_in_timezone = lambda _tz="UTC": DEFAULT_NOW
    utils_module.get_url = _get_url
    utils_module.getdate = _to_date
    utils_module.now = lambda: DEFAULT_NOW.strftime("%Y-%m-%d %H:%M:%S")
    utils_module.now_datetime = lambda: DEFAULT_NOW
    utils_module.nowdate = lambda: DEFAULT_NOW.date().isoformat()
    utils_module.today = lambda: DEFAULT_NOW.date().isoformat()
    return utils_module


def _ensure_module(name, module_factory):
    module = sys.modules.get(name)
    if module is None:
        module = module_factory()
        sys.modules[name] = module
    return module


def _setdefault_attr(target, attr, value):
    if not hasattr(target, attr):
        setattr(target, attr, value)


def _reset_object_attrs(target, defaults):
    for attr, value in defaults.items():
        setattr(target, attr, value)


def _new_local():
    return SimpleNamespace(
        response={},
        request=SimpleNamespace(get_json=lambda silent=True: None),
        request_ip="127.0.0.1",
    )


def _new_request():
    return SimpleNamespace(headers={}, environ={}, data=None)


def _new_session():
    return SimpleNamespace(user="Guest")


def _new_db():
    return SimpleNamespace()


def _install_unittest_isolation():
    if getattr(unittest.TestCase, "__pikt_frappe_harness_installed__", False):
        return

    original_run = unittest.TestCase.run

    def isolated_run(self, result=None):
        reset_test_frappe()
        try:
            return original_run(self, result)
        finally:
            reset_test_frappe()

    isolated_run.__wrapped__ = original_run
    unittest.TestCase.run = isolated_run
    unittest.TestCase.__pikt_frappe_harness_installed__ = True


def install_test_frappe():
    ensure_app_root_on_path()

    utils_module = _HARNESS_STATE.get("utils_module")
    if utils_module is None:
        utils_module = _build_utils_module()
        _HARNESS_STATE["utils_module"] = utils_module

    pdf_module = _HARNESS_STATE.get("pdf_module")
    if pdf_module is None:
        pdf_module = types.ModuleType("frappe.utils.pdf")
        pdf_module.get_pdf = lambda html_value: str(html_value).encode("utf-8")
        _HARNESS_STATE["pdf_module"] = pdf_module

    document_module = _HARNESS_STATE.get("document_module")
    if document_module is None:
        document_module = types.ModuleType("frappe.model.document")
        document_module.Document = object
        _HARNESS_STATE["document_module"] = document_module

    model_module = _HARNESS_STATE.get("model_module")
    if model_module is None:
        model_module = types.ModuleType("frappe.model")
        model_module.document = document_module
        _HARNESS_STATE["model_module"] = model_module

    frappe_module = sys.modules.get("frappe")
    if frappe_module is None:
        frappe_module = types.ModuleType("frappe")
        frappe_module.__pikt_test_double__ = True
        sys.modules["frappe"] = frappe_module

    db_namespace = _HARNESS_STATE.get("db_namespace")
    if db_namespace is None:
        db_namespace = _new_db()
        _HARNESS_STATE["db_namespace"] = db_namespace

    local_namespace = _HARNESS_STATE.get("local_namespace")
    if local_namespace is None:
        local_namespace = _new_local()
        _HARNESS_STATE["local_namespace"] = local_namespace

    request_namespace = _HARNESS_STATE.get("request_namespace")
    if request_namespace is None:
        request_namespace = _new_request()
        _HARNESS_STATE["request_namespace"] = request_namespace

    session_namespace = _HARNESS_STATE.get("session_namespace")
    if session_namespace is None:
        session_namespace = _new_session()
        _HARNESS_STATE["session_namespace"] = session_namespace

    db_defaults = {
        "sql": lambda *args, **kwargs: [],
        "exists": lambda *args, **kwargs: False,
        "get_value": lambda *args, **kwargs: None,
        "set_value": lambda *args, **kwargs: None,
        "get_single_value": lambda *args, **kwargs: None,
        "set_single_value": lambda *args, **kwargs: None,
        "count": lambda *args, **kwargs: 0,
        "commit": lambda: None,
        "rollback": lambda: None,
    }
    _HARNESS_STATE["db_defaults"] = db_defaults
    _reset_object_attrs(db_namespace, db_defaults)

    defaults = {
        "attach_print": lambda *args, **kwargs: b"",
        "clear_cache": lambda: None,
        "delete_doc": lambda *args, **kwargs: None,
        "enqueue": lambda *args, **kwargs: None,
        "form_dict": {},
        "get_all": lambda *args, **kwargs: [],
        "get_doc": lambda *args, **kwargs: None,
        "get_print": lambda *args, **kwargs: "<html></html>",
        "get_request_header": _get_request_header,
        "get_roles": lambda _user=None: [],
        "get_traceback": lambda: "traceback",
        "local": local_namespace,
        "log_error": lambda *args, **kwargs: None,
        "new_doc": lambda *args, **kwargs: None,
        "parse_json": _parse_json,
        "publish_realtime": lambda *args, **kwargs: None,
        "request": request_namespace,
        "sendmail": lambda *args, **kwargs: None,
        "session": session_namespace,
        "throw": _throw,
        "utils": utils_module,
        "whitelist": _whitelist,
        "db": db_namespace,
    }
    _HARNESS_STATE["frappe_defaults"] = defaults

    _reset_object_attrs(frappe_module, defaults)
    _reset_object_attrs(local_namespace, {"response": {}, "request": SimpleNamespace(get_json=lambda silent=True: None), "request_ip": "127.0.0.1"})
    _reset_object_attrs(request_namespace, {"headers": {}, "environ": {}, "data": None})
    _reset_object_attrs(session_namespace, {"user": "Guest"})

    sys.modules["frappe.utils"] = utils_module
    sys.modules["frappe.utils.pdf"] = pdf_module
    sys.modules["frappe.model"] = model_module
    sys.modules["frappe.model.document"] = document_module
    _install_unittest_isolation()
    return frappe_module


def reset_test_frappe():
    frappe_module = install_test_frappe()
    return frappe_module
