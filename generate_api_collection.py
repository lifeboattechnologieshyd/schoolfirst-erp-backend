"""
Generates one Postman v2.1 collection (importable in Bruno / Postman) with
EVERY API of the project: URL, method, auth, query params and body fields.

It only READS the code (urls.py + views) with Python's ast module.
Nothing is imported or executed, so Django does not need to run.

Usage (from the project root):
    python generate_api_collection.py
        -> writes SchoolFirst_ERP_All_APIs.postman_collection.json (for Import)

    python generate_api_collection.py --bruno ~/Documents/Bruno/SchoolFirst-ERP
        -> ALSO writes a native Bruno collection folder. Open that folder once in
           Bruno ("Open Collection"); after that Bruno reloads it automatically
           every time this script runs. Your environment values are kept, and
           files you create yourself are never touched.

    python generate_api_collection.py /path/to/project output.json --bruno DIR

Re-run it whenever you add or change APIs.
"""
import ast
import json
import os
import re
import argparse
import uuid

_parser = argparse.ArgumentParser(description="Generate the SchoolFirst ERP API collection.")
_parser.add_argument("project", nargs="?", default=os.getcwd(), help="project root (default: current folder)")
_parser.add_argument("output", nargs="?", default="SchoolFirst_ERP_All_APIs.postman_collection.json",
                     help="Postman/Bruno import file to write")
_parser.add_argument("--bruno", metavar="DIR", help="also write a native Bruno collection folder here")
ARGS = _parser.parse_args()

ROOT = os.path.abspath(ARGS.project)
HTTP_METHODS = ["get", "post", "put", "patch", "delete"]


# ---------------------------------------------------------------- utils
_ast_cache = {}


def module_file(module):
    base = os.path.join(ROOT, *module.split("."))
    for candidate in (base + ".py", os.path.join(base, "__init__.py")):
        if os.path.exists(candidate):
            return candidate
    return None


def parse_module(module):
    if module in _ast_cache:
        return _ast_cache[module]
    path = module_file(module)
    tree = ast.parse(open(path).read()) if path else None
    _ast_cache[module] = tree
    return tree


def import_map(tree, current_module):
    """name -> module it was imported from"""
    result = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            module = node.module
            if node.level:  # relative
                parts = current_module.split(".")[: -node.level]
                module = ".".join(parts + [node.module])
            for alias in node.names:
                result[alias.asname or alias.name] = module
    return result


def const_str(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


# ---------------------------------------------------------------- field collection
class Fields:
    def __init__(self):
        self.body = []      # ordered unique
        self.query = []
        self.files = []
        self.headers = []
        self.required_query = set()
        self.list_body = set()
        self.types = {}      # key -> list / bool / dict / int
        self.nested = {}     # list key -> [item keys]

    def add(self, kind, key):
        target = getattr(self, kind)
        if key and key not in target:
            target.append(key)


def literal_strings(node):
    """Strings in a literal tuple/list/set (first element of inner tuples)."""
    out = []
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        for elt in node.elts:
            if const_str(elt):
                out.append(const_str(elt))
            elif isinstance(elt, (ast.Tuple, ast.List)) and elt.elts and const_str(elt.elts[0]):
                out.append(const_str(elt.elts[0]))
    elif isinstance(node, ast.Dict):
        out = [const_str(k) for k in node.keys if const_str(k)]
    return out


def analyze_function(func, request_names, module, fields, visited, class_node=None):
    key = (module, func.name, class_node.name if class_node else None)
    if key in visited:
        return
    visited.add(key)

    tree = parse_module(module)
    imports = import_map(tree, module)
    module_funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    class_methods = {}
    if class_node:
        class_methods = {n.name: n for n in class_node.body if isinstance(n, ast.FunctionDef)}

    aliases = {}            # var -> kind ('body','query','files')
    string_collections = {}  # var -> [strings]
    loop_vars = {}           # var -> [strings]
    query_vars = {}          # var -> query key (for required detection)

    def kind_of(expr):
        """request.data -> body, request.query_params/GET -> query, request.FILES -> files"""
        if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name) and expr.value.id in request_names:
            return {"data": "body", "query_params": "query", "GET": "query", "POST": "body",
                    "FILES": "files", "headers": "headers"}.get(expr.attr)
        if isinstance(expr, ast.Name) and expr.id in aliases:
            return aliases[expr.id]
        return None

    def keys_from_arg(arg):
        if const_str(arg):
            return [const_str(arg)]
        if isinstance(arg, ast.Name):
            return loop_vars.get(arg.id, [])
        return []

    # first pass: aliases, string collections, loops
    for node in ast.walk(func):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            kind = kind_of(node.value)
            if kind:
                aliases[name] = kind
            strings = literal_strings(node.value)
            if strings:
                string_collections[name] = strings
    for node in ast.walk(func):
        if isinstance(node, (ast.For, ast.comprehension)):
            target = node.target
            names = []
            if isinstance(target, ast.Name):
                names = [target.id]
            elif isinstance(target, ast.Tuple) and target.elts and isinstance(target.elts[0], ast.Name):
                names = [target.elts[0].id]
            iterable = node.iter
            strings = literal_strings(iterable)
            if not strings and isinstance(iterable, ast.Name):
                strings = string_collections.get(iterable.id, [])
            if not strings and isinstance(iterable, ast.Call) and isinstance(iterable.func, ast.Attribute) \
                    and iterable.func.attr == "items" and isinstance(iterable.func.value, ast.Name):
                strings = string_collections.get(iterable.func.value.id, [])
            for name in names:
                if strings:
                    loop_vars[name] = strings

    # allowed_fields style sets count as body fields
    for name, strings in string_collections.items():
        if "allowed" in name.lower() and "field" in name.lower():
            for s in strings:
                fields.add("body", s)

    # second pass: reads
    for node in ast.walk(func):
        # x.get("k") / x.getlist("k")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in ("get", "getlist") and node.args:
            kind = kind_of(node.func.value)
            if kind:
                for k in keys_from_arg(node.args[0]):
                    fields.add(kind, k)
                    if node.func.attr == "getlist" and kind == "body":
                        fields.list_body.add(k)
        # x["k"]
        if isinstance(node, ast.Subscript):
            kind = kind_of(node.value)
            if kind:
                k = const_str(node.slice)
                if k:
                    fields.add(kind, k)
        # "k" in request.data
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], (ast.In, ast.NotIn)):
            kind = kind_of(node.comparators[0])
            if kind and const_str(node.left):
                fields.add(kind, const_str(node.left))
        # var = request.query_params.get("k")  (required detection)
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) \
                and node.value.func.attr == "get" and node.value.args and kind_of(node.value.func.value) == "query":
            k = const_str(node.value.args[0])
            if k:
                query_vars[node.targets[0].id] = k

    # ---- types and nested list items ----
    body_vars = {}
    for node in ast.walk(func):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) \
                and node.value.func.attr in ("get", "getlist") and node.value.args \
                and kind_of(node.value.func.value) == "body" and const_str(node.value.args[0]):
            body_vars[node.targets[0].id] = const_str(node.value.args[0])
    type_names = {"list": "list", "tuple": "list", "bool": "bool", "dict": "dict", "int": "int", "float": "int"}
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "isinstance" and len(node.args) == 2 \
                and isinstance(node.args[0], ast.Name) and node.args[0].id in body_vars:
            spec = node.args[1]
            names = [e.id for e in spec.elts if isinstance(e, ast.Name)] if isinstance(spec, ast.Tuple) else \
                [spec.id] if isinstance(spec, ast.Name) else []
            for n in names:
                if n in type_names:
                    fields.types.setdefault(body_vars[node.args[0].id], type_names[n])
                    break
    item_vars = {}
    for node in ast.walk(func):
        if isinstance(node, (ast.For, ast.comprehension)):
            iterable, target = node.iter, node.target
            if isinstance(iterable, ast.Call) and getattr(iterable.func, "id", None) == "enumerate" and iterable.args:
                iterable = iterable.args[0]
                target = target.elts[1] if isinstance(target, ast.Tuple) and len(target.elts) > 1 else target
            if isinstance(iterable, ast.Name) and iterable.id in body_vars and isinstance(target, ast.Name):
                item_vars[target.id] = body_vars[iterable.id]
                fields.types[body_vars[iterable.id]] = "list"
    for node in ast.walk(func):
        sub = None
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get" \
                and isinstance(node.func.value, ast.Name) and node.func.value.id in item_vars and node.args:
            sub, owner = const_str(node.args[0]), item_vars[node.func.value.id]
        elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id in item_vars:
            sub, owner = const_str(node.slice), item_vars[node.value.id]
        if sub:
            fields.nested.setdefault(owner, [])
            if sub not in fields.nested[owner]:
                fields.nested[owner].append(sub)

    for node in ast.walk(func):
        if isinstance(node, ast.If) and isinstance(node.test, ast.UnaryOp) and isinstance(node.test.op, ast.Not) \
                and isinstance(node.test.operand, ast.Name) and node.test.operand.id in query_vars:
            fields.required_query.add(query_vars[node.test.operand.id])
        if isinstance(node, ast.If) and isinstance(node.test, ast.BoolOp):
            for value in node.test.values:
                if isinstance(value, ast.UnaryOp) and isinstance(value.op, ast.Not) \
                        and isinstance(value.operand, ast.Name) and value.operand.id in query_vars:
                    fields.required_query.add(query_vars[value.operand.id])

    # follow calls that receive the request
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        # self.helper(...)
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) \
                and node.func.value.id == "self" and node.func.attr in class_methods:
            target = class_methods[node.func.attr]
            arg_names = [a.arg for a in target.args.args][1:]
            passed = set()
            for i, arg in enumerate(node.args):
                if isinstance(arg, ast.Name) and arg.id in request_names and i < len(arg_names):
                    passed.add(arg_names[i])
            # helpers can also use self.request
            analyze_function(target, (passed or set()) | request_names, module, fields, visited, class_node)
            continue
        # helper(request, ...)
        if isinstance(node.func, ast.Name):
            name = node.func.id
            target, target_module = None, None
            if name in module_funcs:
                target, target_module = module_funcs[name], module
            elif name in imports and imports[name].startswith(("apps.", "shared.")):
                other = parse_module(imports[name])
                if other:
                    for n in other.body:
                        if isinstance(n, ast.FunctionDef) and n.name == name:
                            target, target_module = n, imports[name]
            if target is None:
                continue
            arg_names = [a.arg for a in target.args.args]
            passed = set()
            for i, arg in enumerate(node.args):
                if isinstance(arg, ast.Name) and arg.id in request_names and i < len(arg_names):
                    passed.add(arg_names[i])
            if passed:
                analyze_function(target, passed, target_module, fields, visited, None)


def find_class(module, class_name):
    tree = parse_module(module)
    if tree is None:
        return None, None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node, module
    # re-exported?
    imports = import_map(tree, module)
    if class_name in imports and imports[class_name] != module:
        return find_class(imports[class_name], class_name)
    return None, None


def class_info(class_node, module):
    info = {"methods": {}, "permission": None, "allow_any": False, "doc": ast.get_docstring(class_node)}
    for node in class_node.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "required_permission" and const_str(node.value):
                    info["permission"] = const_str(node.value)
                if isinstance(target, ast.Name) and target.id == "permission_classes":
                    if "AllowAny" in ast.dump(node.value):
                        info["allow_any"] = True
    # methods incl. inherited from classes in same module
    method_nodes = {}
    for base in class_node.bases:
        if isinstance(base, ast.Name):
            base_node, base_module = find_class(module, base.id)
            if base_node is not None:
                for n in base_node.body:
                    if isinstance(n, ast.FunctionDef) and n.name in HTTP_METHODS:
                        method_nodes[n.name] = (n, base_node, base_module)
    for n in class_node.body:
        if isinstance(n, ast.FunctionDef) and n.name in HTTP_METHODS:
            method_nodes[n.name] = (n, class_node, module)
    for name, (func, owner, owner_module) in method_nodes.items():
        fields = Fields()
        request_name = func.args.args[1].arg if len(func.args.args) > 1 else "request"
        analyze_function(func, {request_name}, owner_module, fields, set(), owner)
        info["methods"][name] = fields
    return info


# ---------------------------------------------------------------- urls
def parse_urls(module):
    tree = parse_module(module)
    imports = import_map(tree, module)
    routes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) in ("path", "re_path") and len(node.args) >= 2:
            route = const_str(node.args[0])
            view = node.args[1]
            if route is None:
                continue
            if isinstance(view, ast.Call) and isinstance(view.func, ast.Attribute) and view.func.attr == "as_view":
                target = view.func.value
                class_name = target.id if isinstance(target, ast.Name) else getattr(target, "attr", None)
                view_module = imports.get(class_name, module)
                routes.append((route, class_name, view_module, getattr(node, "lineno", 0)))
            elif isinstance(view, ast.Call) and getattr(view.func, "id", None) == "include":
                inc = const_str(view.args[0]) if view.args else None
                if inc:
                    routes.append((route, ("INCLUDE", inc), None, getattr(node, "lineno", 0)))
    routes.sort(key=lambda r: r[3])
    return routes


# ---------------------------------------------------------------- examples
VAR_ALIASES = {
    "kid_id": "kidId", "student_id": "kidId", "school_id": "schoolId",
}


def camel(name):
    parts = name.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


def example_value(key, method):
    k = key.lower()
    if k in VAR_ALIASES:
        return "{{%s}}" % VAR_ALIASES[k]
    if k.endswith("_ids"):
        return ["{{%s}}" % camel(k[:-4] + "_id")]
    if k.endswith("_id") or k == "id":
        return "{{%s}}" % camel(k)
    if k in ("mobile", "phone", "contact_phone") or k.endswith("_mobile") or k.endswith("_phone"):
        return "9876543210"
    if "email" in k:
        return "test@example.com"
    if k == "otp":
        return "{{otp}}"
    if k.startswith(("is_", "has_", "allow_", "send_", "notify")) or k.endswith(("_used", "_required", "_enabled")) \
            or k in ("active", "enabled", "published"):
        return False
    if any(w in k.split("_") for w in ("seconds", "minutes", "duration", "count")) or k.startswith("number_of"):
        return 1
    if k.endswith(("_from", "_to")) and any(w in k for w in ("available", "time", "hour")):
        return "08:00" if k.endswith("_from") else "16:00"
    if k.endswith("_days") or k in ("days",):
        return [0, 1, 2, 3, 4]
    if "date" in k or k in ("dob", "date_of_birth", "start", "end", "from_date", "to_date"):
        return "2026-11-26"
    if "time" in k or k in ("check_in", "check_out", "late_after"):
        return "09:00"
    if k in ("page",):
        return 1
    if k in ("page_size", "limit"):
        return 20
    tokens = set(k.split("_"))
    numeric_words = {"amount", "marks", "fee", "fees", "percentage", "price", "count", "number", "order",
                     "sequence", "serial", "capacity", "duration", "minutes", "seconds", "radius", "latitude",
                     "longitude", "year", "age", "score", "total", "rate", "limit", "quantity", "qty",
                     "distance", "km", "experience", "points", "xp", "level_int"}
    if tokens & numeric_words:
        return 1
    if k in ("status",):
        return "ACTIVE"
    if k in ("image", "image_url", "photo", "photo_url", "logo", "thumbnail", "thumbnail_image", "cover_image",
             "file_url", "attachment_url", "video_url", "url", "profile_image"):
        return "https://example.com/file.png"
    if k.endswith("s") and k not in ("status", "address", "remarks", "notes", "class", "news", "details",
                                     "description", "reason", "progress", "access", "bus", "is_class"):
        return []
    return "Sample " + k.replace("_", " ")


def typed_example(key, method, fields):
    value = example_value(key, method)
    kind = fields.types.get(key)
    if key in fields.nested:
        item = {sub: example_value(sub, method) for sub in fields.nested[key]}
        return [item]
    if kind == "list" or key in fields.list_body:
        return value if isinstance(value, list) else ([] if str(value).startswith("Sample") else [value])
    if kind == "bool":
        return False
    if kind == "int":
        return value if isinstance(value, int) and not isinstance(value, bool) else 1
    if kind == "dict":
        return {}
    return value


def route_to_path(route):
    """<uuid:attempt_id> -> :attempt_id"""
    variables = re.findall(r"<(?:\w+:)?(\w+)>", route)
    path = re.sub(r"<(?:\w+:)?(\w+)>", r":\1", route)
    return path, variables


# ---------------------------------------------------------------- build
def title_from_class(class_name):
    name = re.sub(r"APIView$|View$", "", class_name)
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", name)
    return name.strip()


def build():
    root_routes = parse_urls("settings.urls")
    collection_vars = {"baseUrl": "http://localhost:8000", "token": "", "parentToken": "", "schoolId": "",
                       "branchId": "", "mobile": "", "otp": "", "parentMobile": "", "parentOtp": "", "kidId": ""}
    folders = []
    stats = {"endpoints": 0, "requests": 0}

    for prefix, target, _, _ in root_routes:
        if not (isinstance(target, tuple) and target[0] == "INCLUDE" and target[1].startswith("apps.")):
            continue
        urls_module = target[1]
        app = urls_module.split(".")[1]
        is_backoffice = app == "backoffice"
        sub_folders = {}

        for route, class_name, view_module, _ in parse_urls(urls_module):
            if isinstance(class_name, tuple):
                continue
            class_node, found_module = find_class(view_module, class_name)
            if class_node is None:
                continue
            info = class_info(class_node, found_module)
            if not info["methods"]:
                continue
            stats["endpoints"] += 1
            full_route = prefix + route
            path, path_vars = route_to_path(full_route)
            folder_name = (
                "Backoffice - " + found_module.split(".")[-1].replace("_", " ").title()
                if is_backoffice
                else "App - " + app.replace("_", " ").title()
            )
            for method, fields in info["methods"].items():
                stats["requests"] += 1
                headers = [{"key": "X-School-Id", "value": "{{schoolId}}", "type": "text"}]
                if any(h.lower() == "x-branch-id" for h in fields.headers):
                    headers.append({"key": "X-Branch-Id", "value": "{{branchId}}", "type": "text", "disabled": True})

                url = {
                    "raw": "{{baseUrl}}/" + path,
                    "host": ["{{baseUrl}}"],
                    "path": path.strip("/").split("/"),
                }
                if path_vars:
                    url["variable"] = []
                    for v in path_vars:
                        var_name = VAR_ALIASES.get(v, camel(v))
                        collection_vars.setdefault(var_name, "")
                        url["variable"].append({"key": v, "value": "{{%s}}" % var_name})

                query_keys = fields.query
                if query_keys:
                    url["query"] = []
                    for qk in query_keys:
                        value = example_value(qk, method)
                        if isinstance(value, list):
                            value = value[0] if value else ""
                        url["query"].append({
                            "key": qk,
                            "value": str(value).lower() if isinstance(value, bool) else str(value),
                            "disabled": method == "get" and qk not in fields.required_query and qk not in ("page", "page_size"),
                        })
                    enabled = [q for q in url["query"] if not q["disabled"]]
                    if enabled:
                        url["raw"] += "?" + "&".join(f"{q['key']}={q['value']}" for q in enabled)

                request = {"method": method.upper(), "header": headers, "url": url}

                body_keys = [k for k in fields.body if k not in fields.files]
                if fields.files and method != "get":
                    form = [{"key": f, "type": "file", "src": ""} for f in fields.files]
                    for bk in body_keys:
                        value = typed_example(bk, method, fields)
                        form.append({"key": bk, "value": json.dumps(value) if isinstance(value, (list, bool, int)) else value,
                                     "type": "text"})
                    request["body"] = {"mode": "formdata", "formdata": form}
                elif body_keys and method != "get":
                    payload = {}
                    for bk in body_keys:
                        payload[bk] = typed_example(bk, method, fields)
                    request["body"] = {"mode": "raw", "raw": json.dumps(payload, indent=2),
                                       "options": {"raw": {"language": "json"}}}
                    headers.append({"key": "Content-Type", "value": "application/json", "type": "text"})

                # collect {{vars}} used in examples
                for found in re.findall(r"\{\{(\w+)\}\}", json.dumps(request)):
                    collection_vars.setdefault(found, "")

                if info["allow_any"]:
                    request["auth"] = {"type": "noauth"}
                elif not is_backoffice:
                    request["auth"] = {"type": "bearer", "bearer": [{"key": "token", "value": "{{parentToken}}", "type": "string"}]}

                description = [f"View: {class_name} ({found_module})"]
                if info["permission"]:
                    description.append(f"Permission: {info['permission']}")
                if info["allow_any"]:
                    description.append("Public (no token).")
                elif not is_backoffice:
                    description.append("App API: uses {{parentToken}}.")
                if fields.required_query:
                    description.append("Required query params: " + ", ".join(sorted(fields.required_query)))
                if info["doc"]:
                    description.append(info["doc"])
                description.append("Body/query fields are read from the code; example values are placeholders.")
                request["description"] = "\n".join(description)

                item = {"name": f"{title_from_class(class_name)} [{method.upper()}]", "request": request}

                # login helpers
                if full_route == "user/admin/verify-otp":
                    request["body"]["raw"] = json.dumps({"mobile": "{{mobile}}", "otp": "{{otp}}"}, indent=2)
                    item["event"] = [{"listen": "test", "script": {"type": "text/javascript", "exec": [
                        "const body = pm.response.json();",
                        "if (body && body.success) { pm.collectionVariables.set('token', body.data.tokens.access); }"]}}]
                    item["name"] = "Admin verify OTP (saves token)"
                if full_route == "user/admin/send-otp":
                    request["body"]["raw"] = json.dumps({"mobile": "{{mobile}}"}, indent=2)
                if full_route == "user/send-otp":
                    request["body"]["raw"] = json.dumps({"mobile": "{{parentMobile}}"}, indent=2)
                if full_route == "user/verify-otp":
                    payload = json.loads(request["body"]["raw"])
                    payload.update({"mobile": "{{parentMobile}}", "otp": "{{parentOtp}}"})
                    request["body"]["raw"] = json.dumps(payload, indent=2)
                    item["event"] = [{"listen": "test", "script": {"type": "text/javascript", "exec": [
                        "const body = pm.response.json();",
                        "if (body && body.success) {",
                        "  pm.collectionVariables.set('parentToken', body.data.access);",
                        "  try { pm.collectionVariables.set('kidId', body.data.students[0].student_id); pm.collectionVariables.set('schoolId', body.data.students[0].school.id); } catch (e) {}",
                        "}"]}}]
                    item["name"] = "Parent verify OTP (saves parentToken, kidId)"

                sub_folders.setdefault(folder_name, []).append(item)

        for name, items in sub_folders.items():
            folders.append({"name": name, "item": items})

    # Auth folder first, then app folders, then backoffice folders
    def order(folder):
        name = folder["name"]
        return (0 if name == "App - Core" else 1 if name.startswith("App") else 2, name)

    folders.sort(key=order)
    for folder in folders:
        if folder["name"] == "App - Core":
            folder["name"] = "Auth & Profile (user/)"

    collection = {
        "info": {
            "_postman_id": str(uuid.uuid4()),
            "name": "SchoolFirst ERP - All APIs",
            "description": (
                "Generated from the project's urls.py and views (every endpoint, method, query and body field).\n"
                "1. Fill baseUrl, mobile/otp (admin or staff), parentMobile/parentOtp (parent).\n"
                "2. Run 'Auth & Profile > Admin verify OTP' -> saves token (backoffice APIs).\n"
                "3. Run 'Parent verify OTP' -> saves parentToken, kidId, schoolId (app APIs).\n"
                "4. Optional query params are included but disabled; enable what you need.\n"
                "Example values are placeholders - replace with real data."
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{token}}", "type": "string"}]},
        "item": folders,
        "variable": [{"key": k, "value": v, "type": "string"} for k, v in collection_vars.items()],
    }
    return collection, stats, folders


# ---------------------------------------------------------------- native Bruno writer
MANIFEST = ".generated-files"


def _safe_name(text):
    return re.sub(r'[\\/:*?"<>|]', "", text).strip()[:90] or "request"


def _indent(text, spaces=2):
    pad = " " * spaces
    return "\n".join(pad + line if line else line for line in text.splitlines())


def _bru_script(item):
    """Postman test script -> Bruno post-response script (only the set-variable lines we generate)."""
    lines = []
    for event in item.get("event", []):
        for line in event["script"]["exec"]:
            line = line.replace("pm.response.json()", "res.getBody()")
            line = line.replace("pm.collectionVariables.set(", "bru.setEnvVar(")
            lines.append(line)
    return "\n".join(lines)


def _request_to_bru(item, seq):
    request = item["request"]
    method = request["method"].lower()
    url = request["url"]["raw"]
    body = request.get("body") or {}
    mode = {"raw": "json", "formdata": "multipartForm"}.get(body.get("mode"), "none")

    auth = request.get("auth")
    if auth is None:
        auth_mode = "inherit"
    elif auth.get("type") == "noauth":
        auth_mode = "none"
    else:
        auth_mode = "bearer"

    out = [f"meta {{\n  name: {item['name']}\n  type: http\n  seq: {seq}\n}}\n",
           f"{method} {{\n  url: {url}\n  body: {mode}\n  auth: {auth_mode}\n}}\n"]

    query = request["url"].get("query") or []
    if query:
        out.append("params:query {\n" + "\n".join(
            f"  {'~' if q.get('disabled') else ''}{q['key']}: {q['value']}" for q in query) + "\n}\n")

    path_vars = request["url"].get("variable") or []
    if path_vars:
        out.append("params:path {\n" + "\n".join(f"  {v['key']}: {v['value']}" for v in path_vars) + "\n}\n")

    headers = [h for h in request.get("header", []) if h["key"] not in ("X-School-Id", "Content-Type")]
    if headers:
        out.append("headers {\n" + "\n".join(
            f"  {'~' if h.get('disabled') else ''}{h['key']}: {h['value']}" for h in headers) + "\n}\n")

    if auth_mode == "bearer":
        token = auth["bearer"][0]["value"]
        out.append(f"auth:bearer {{\n  token: {token}\n}}\n")

    if mode == "json":
        out.append("body:json {\n" + _indent(body["raw"]) + "\n}\n")
    elif mode == "multipartForm":
        fields = []
        for field in body["formdata"]:
            value = "@file()" if field.get("type") == "file" else str(field.get("value", ""))
            fields.append(f"  {field['key']}: {value}")
        out.append("body:multipart-form {\n" + "\n".join(fields) + "\n}\n")

    script = _bru_script(item)
    if script:
        out.append("script:post-response {\n" + _indent(script) + "\n}\n")

    if request.get("description"):
        out.append("docs {\n" + _indent(request["description"]) + "\n}\n")

    return "\n".join(out)


def write_bruno(collection, target):
    target = os.path.abspath(os.path.expanduser(target))
    os.makedirs(target, exist_ok=True)

    manifest_path = os.path.join(target, MANIFEST)
    previous = set()
    if os.path.exists(manifest_path):
        previous = {line.strip() for line in open(manifest_path) if line.strip()}

    written = set()

    def write(relative, content):
        path = os.path.join(target, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # only rewrite when changed, so Bruno reloads just what changed
        if not os.path.exists(path) or open(path).read() != content:
            with open(path, "w") as handle:
                handle.write(content)
        written.add(relative)

    write("bruno.json", json.dumps({"version": "1", "name": collection["info"]["name"], "type": "collection",
                                    "ignore": ["node_modules", ".git"]}, indent=2) + "\n")

    write("collection.bru", (
        "headers {\n  X-School-Id: {{schoolId}}\n}\n\n"
        "auth {\n  mode: bearer\n}\n\n"
        "auth:bearer {\n  token: {{token}}\n}\n\n"
        "docs {\n" + _indent(collection["info"]["description"]) +
        "\n\n  Select the 'Local' environment (top right) before sending requests.\n}\n"
    ))

    for folder_seq, folder in enumerate(collection["item"], start=1):
        folder_dir = _safe_name(folder["name"])
        write(os.path.join(folder_dir, "folder.bru"), f"meta {{\n  name: {folder['name']}\n  seq: {folder_seq}\n}}\n")
        used = set()
        for seq, item in enumerate(folder["item"], start=1):
            name = _safe_name(item["name"])
            while name in used:
                name += " 2"
            used.add(name)
            write(os.path.join(folder_dir, name + ".bru"), _request_to_bru(item, seq))

    # environment: keep the values you already filled in, add new variables
    env_relative = os.path.join("environments", "Local.bru")
    env_path = os.path.join(target, env_relative)
    existing = {}
    if os.path.exists(env_path):
        for line in open(env_path):
            match = re.match(r"\s*([A-Za-z_][\w]*)\s*:\s?(.*)$", line)
            if match and match.group(1) != "vars":
                existing[match.group(1)] = match.group(2).rstrip("\n")
    defaults = {v["key"]: v["value"] for v in collection["variable"]}
    merged = dict(existing)
    for key, value in defaults.items():
        merged.setdefault(key, value)
    os.makedirs(os.path.dirname(env_path), exist_ok=True)
    env_content = "vars {\n" + "\n".join(f"  {k}: {v}" for k, v in merged.items()) + "\n}\n"
    if not os.path.exists(env_path) or open(env_path).read() != env_content:
        with open(env_path, "w") as handle:
            handle.write(env_content)

    # remove requests that no longer exist in the code (only ones we generated)
    removed = 0
    for relative in previous - written:
        path = os.path.join(target, relative)
        if os.path.exists(path):
            os.remove(path)
            removed += 1
            parent = os.path.dirname(path)
            if parent != target and os.path.isdir(parent) and not os.listdir(parent):
                os.rmdir(parent)

    with open(manifest_path, "w") as handle:
        handle.write("\n".join(sorted(written)) + "\n")

    return target, len(written), removed


if __name__ == "__main__":
    collection, stats, folders = build()
    out = ARGS.output
    json.dump(collection, open(out, "w"), indent=2)
    if ARGS.bruno:
        folder, files, removed = write_bruno(collection, ARGS.bruno)
        print(f"Bruno collection updated: {folder} ({files} files, {removed} removed)")
    print(stats, "folders:", len(folders), "variables:", len(collection["variable"]))
    for f in folders:
        print(f"  {len(f['item']):4d}  {f['name']}")
