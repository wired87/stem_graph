import ast
import importlib
import sys
from typing import Union, Optional, Callable, Set

try:
    from graph.local_graph_utils import GUtils
except ImportError:
    GUtils = None


def _get_docstring(node: Union[ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef]) -> str:
    """Extracts docstring from function or class node."""
    return ast.get_docstring(node) or ""


def _get_type_name(node: Optional[ast.expr]) -> str:
    """Extracts type name from annotation or defaults to 'Any'."""
    return ast.unparse(node) if node else 'Any'


def _has_self_param(node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> bool:
    """True if function has 'self' as first parameter (i.e. is a class method)."""
    if node.args.args:
        return node.args.args[0].arg == "self"
    return False

def flatten_payload(payload: dict) -> dict:
    """
    Flatten nested payload {auth: {...}, data: {...}} to top-level dict.
    All keys from auth and data become top-level kwargs for handler methods.
    """
    if not isinstance(payload, dict):
        return {}
    auth = payload.get("auth") or {}
    data = payload.get("data") or {}
    if not isinstance(auth, dict):
        auth = {}
    if not isinstance(data, dict):
        data = {}
    return {**auth, **data}


def _make_direct_callable(
    module_name: str,
    method_name: str,
    class_name: Optional[str] = None,
    has_self: bool = False,
) -> Callable:
    """
    Create a callable that invokes the function/method without requiring the caller
    to pass self or a class instance. Accepts payload (dict) and flattens to **kwargs
    for handler methods. For class methods: instantiates the class (no-arg __init__).
    """
    def invoke(*args, **kwargs):
        mod = importlib.import_module(module_name)
        if class_name and has_self:
            cls = getattr(mod, class_name)
            instance = cls()
            func = getattr(instance, method_name)
            if args and len(args) == 1 and isinstance(args[0], dict) and not kwargs:
                return func(**flatten_payload(args[0]))
            return func(*args, **kwargs)
        else:
            func = getattr(mod, method_name)
            if args and len(args) == 1 and isinstance(args[0], dict) and not kwargs:
                return func(**flatten_payload(args[0]))
            return func(*args, **kwargs)
    return invoke




class StructInspector(ast.NodeVisitor):

    """
    USE FOR SINGLE FILE
    Traverses AST to populate a CodeGraph with classes, methods, and variables.
    The graph stores the entire structure; no redundant internal dicts are kept.
    """

    def __init__(self, G=None, g=None):
        self.current_class: Optional[str] = None
        self.g = g if g is not None else (GUtils(G=G) if GUtils else None)

    def visit_ClassDef(self, node: ast.ClassDef):
        """Add CLASS node, MODULE->CLASS edge; track current class for method resolution."""
        prev = self.current_class
        self.current_class = node.name
        class_id = node.name
        if self.module_name:
            self.g.add_node(attrs=dict(id=class_id, type="CLASS", name=class_id))
            self.g.add_edge(
                src=self.module_name,
                trgt=class_id,
                attrs=dict(rel="has_class", trgt_layer="CLASS", src_layer="MODULE"),
            )
            print(f"CLASS node created: {class_id}", file=sys.stderr)
        self.generic_visit(node)
        self.current_class = prev

    # B. Visit Methods (Sync/Async)
    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._process_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._process_function(node)

    def _process_function(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]):
        """Processes methods (or standalone functions, if not in class).
        Creates a direct callable for each function/method that can be invoked
        without passing self or class instance (for methods, instantiates internally).
        """
        try:
            method_name = node.name
            has_self = _has_self_param(node)
            method_id = f"{self.current_class}.{method_name}" if self.current_class else method_name
            print(f"CREATE METHOD:{self.module_name}: {method_id}", file=sys.stderr)

            if not method_name.startswith("_"):

                print("Get Method Data", file=sys.stderr)
                return_type = _get_type_name(node.returns)
                docstring = _get_docstring(node)

                return_key = self.extract_return_statement_expression(
                    method_node=node,
                )

                print(f"RETURN KEY FOR METHOD {method_name}: {return_key}", file=sys.stderr)
                if len(return_key.split(" ")) == 0:
                    return_key = method_id

                entire_def = ast.unparse(node)

                callable_fn = _make_direct_callable(
                    module_name=self.module_name,
                    method_name=method_name,
                    class_name=self.current_class,
                    has_self=has_self,
                )

                #p_tree = _extract_param_tree(node)
                #p_tree_str = json.dumps(p_tree) if p_tree else "{}"
                # print("METHOD-module edge created", method_id)
                params = self.process_method_params(node, method_id, return_key)

                data = {
                    "id": method_id,
                    "tid": 0,
                    "parent": ["MODULE"],
                    "type": "METHOD",
                    "return_key": return_key,
                    "returns": return_type,
                    "docstring": docstring,
                    "code": entire_def,
                    "module_id": self.module_name,
                    "callable": callable_fn,
                    "params": params,
                }

                # 1. METHOD Node
                self.g.add_node(
                    attrs=data
                )

                print(f"METHOD node created: {method_id}", file=sys.stderr)

                # MODULE -> METHOD
                self.g.add_edge(
                    src=self.module_name,
                    trgt=method_id,
                    attrs=dict(
                        rel='has_method',
                        trgt_layer='METHOD',
                        src_layer='MODULE',
                    )
                )
                # CLASS -> METHOD (when inside a class)
                if self.current_class:
                    self.g.add_edge(
                        src=self.current_class,
                        trgt=method_id,
                        attrs=dict(
                            rel='has_method',
                            trgt_layer='METHOD',
                            src_layer='CLASS',
                        )
                    )

        except Exception as e:
            print("Err _process_function", e, file=sys.stderr)
        self.generic_visit(node)


    def process_method_params(self, node, method_id, return_key):
        # 3. Process Parameters
        #print("process_method_params node", node, type(method_id))
        filtered_args = []
        return_key = return_key.strip()

        for arg in node.args.args:
            try:
                if arg.arg == 'self': continue
                param_name = arg.arg
                param_type = _get_type_name(arg.annotation)

                print(f"ADD PARAM: {param_name}", file=sys.stderr)
                # PARAM
                self.g.add_node(
                    attrs=dict(
                        id=param_name,
                        type='PARAM',
                        param_type=param_type,
                    )
                )

                # METHOD -> PARAM
                self.g.add_edge(
                    src=method_id,
                    trgt=param_name,
                    attrs=dict(
                        rel='requires_param',
                        type=param_type,
                        trgt_layer='PARAM',
                        src_layer='METHOD',
                    ))

                # MODULE -> PARAM
                if not self.g.G.has_edge(self.module_name, param_name):
                    self.g.add_edge(
                        src=self.module_name,
                        trgt=param_name,
                        attrs=dict(
                            rel='requires_param',
                            trgt_layer='PARAM',
                            src_layer='MODULE',
                        ))

                filtered_args.append(arg.arg)
            except Exception as e:
                print("Err node.args.args", e, file=sys.stderr)

        # RETURN PARAM (outside loop - add once per method)
        if return_key:
            self.g.add_node(attrs=dict(id=return_key, type='PARAM'))
            self.g.add_edge(
                src=method_id,
                trgt=return_key,
                attrs=dict(rel='returns_param', trgt_layer='PARAM', src_layer='METHOD'),
            )
            if not self.g.G.has_edge(self.module_name, return_key):
                self.g.add_edge(
                    src=self.module_name,
                    trgt=return_key.strip(),
                    attrs=dict(rel='returns_param', trgt_layer='PARAM', src_layer='MODULE'),
                )
        print("process_method_params... done -> filtered_args", filtered_args, file=sys.stderr)
        return filtered_args

    def extract_return_statement_expression(self, method_node: ast.FunctionDef) -> Optional[str]:
        """
        Extracts the name/identifier of the returned expression, stripped of whitespace.
        """
        for node in ast.walk(method_node):
            try:
                if isinstance(node, ast.Return) and node.value is not None:
                    # ast.unparse converts the AST node back into a string
                    # .strip() removes any leading/trailing whitespace or newlines
                    return ast.unparse(node.value).strip()
            except Exception as e:
                # It's often better to log this or use 'pass' if you want it silent
                print(f"Err extract_return_statement_expression: {e}")
        return ""



    # C. Visit Class Variables
    def visit_Assign(self, node: ast.Assign):
        """Identifies class variables and creates CLASS_VAR nodes."""

        if not self.current_class: return

        for target in node.targets:
            try:
                if isinstance(target, ast.Name):
                    var_name = target.id

                    # Simple type inference (kept simple from original)
                    value_type = 'Unknown'
                    var_id = f"{self.current_class}.{var_name}"

                    # 1. Add CLASS_VAR Node
                    self.g.add_node(
                        dict(
                            id=var_id,
                            type='CLASS_VAR',
                            name=var_name,
                            inferred_type=value_type,
                        )
                    )
                    # CLASS -> CLASS_VAR
                    self.g.add_edge(
                        src=self.current_class,
                        trgt=var_id,
                        attrs=dict(rel='has_var', trgt_layer='CLASS_VAR', src_layer='CLASS'),
                    )
            except Exception as e:
                print("Err Assign:", e, file=sys.stderr)

    def convert_module_to_graph(self, code_content: str, module_name: str):
        """
        Parses code content, runs the inspector, and returns the graph.
        Takes code as a string input, as required by ast.parse.
        """
        self.module_name = module_name
        print("ADD MODULE:", module_name, file=sys.stderr)
        self.g.add_node(attrs=dict(id=module_name, type="MODULE", name=module_name))
        try:
            if not code_content.strip():
                return {"Error": "Input code content is empty."}

            tree = ast.parse(code_content)
            self.visit(tree)
            # Second pass: link usages (METHOD->METHOD calls, PARAM->METHOD passes_to)
            _UsageLinker(self.g, module_name).visit(tree)

        except Exception as e:
            print(f"Error processing code structure for {module_name}: {e}", file=sys.stderr)


class _UsageLinker(ast.NodeVisitor):
    """
    Second-pass visitor: links METHOD->METHOD (calls), PARAM->METHOD (passes_to).
    Runs after StructInspector has built the graph.
    """

    def __init__(self, g: GUtils, module_name: str):
        self.g = g
        self.module_name = module_name
        self.current_class: Optional[str] = None
        self.current_method_id: Optional[str] = None
        self.param_names: Set[str] = set()
        self._method_ids: Set[str] = set()

    def _ensure_method_registry(self):
        """Build set of known method/function ids from graph."""
        if self._method_ids:
            return
        for nid, attrs in self.g.G.nodes(data=True):
            if attrs.get("type") == "METHOD":
                self._method_ids.add(nid)

    def _resolve_callee(self, call_node: ast.Call) -> Optional[str]:
        """Resolve call target to method_id if known in graph."""
        self._ensure_method_registry()
        func = call_node.func
        if isinstance(func, ast.Name):
            cand = func.id
            if cand in self._method_ids:
                return cand
            if self.current_class and f"{self.current_class}.{cand}" in self._method_ids:
                return f"{self.current_class}.{cand}"
            return cand if cand in self._method_ids else None
        if isinstance(func, ast.Attribute):
            if isinstance(func.value, ast.Name) and func.value.id == "self":
                cand = f"{self.current_class}.{func.attr}" if self.current_class else func.attr
                return cand if cand in self._method_ids else None
            cand = func.attr
            return cand if cand in self._method_ids else None
        return None

    def _add_link(self, src: str, trgt: str, rel: str, src_layer: str, trgt_layer: str):
        """Add usage edge; skip if target node missing."""
        if not self.g.G.has_node(trgt):
            return
        try:
            self.g.add_edge(
                src=src,
                trgt=trgt,
                attrs=dict(rel=rel, src_layer=src_layer, trgt_layer=trgt_layer),
            )
            print(f"LINK {rel}: {src} -> {trgt}", file=sys.stderr)
        except Exception as e:
            print(f"Err add edge {src}->{trgt}: {e}", file=sys.stderr)

    def visit_ClassDef(self, node: ast.ClassDef):
        prev = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = prev

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._visit_function(node)

    def _visit_function(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]):
        method_id = f"{self.current_class}.{node.name}" if self.current_class else node.name
        self.current_method_id = method_id
        self.param_names = {a.arg for a in node.args.args if a.arg != "self"}
        for child in ast.iter_child_nodes(node):
            self.visit(child)
        self.current_method_id = None
        self.param_names = set()

    def visit_Call(self, node: ast.Call):
        if not self.current_method_id:
            self.generic_visit(node)
            return
        callee = self._resolve_callee(node)
        if callee:
            self._add_link(
                self.current_method_id, callee, "calls", "METHOD", "METHOD"
            )
            for arg in node.args:
                if isinstance(arg, ast.Name) and arg.id in self.param_names:
                    self._add_link(arg.id, callee, "passes_to", "PARAM", "METHOD")
        self.generic_visit(node)


"""



def _extract_param_tree(method_node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> Dict[str, Any]:

    param_names = {arg.arg for arg in method_node.args.args if arg.arg != "self"}
    var_to_path: Dict[str, Tuple[str, ...]] = {}
    tree: Dict[str, Any] = {}

    def _get_path(expr) -> Optional[Tuple[str, ...]]:
        if isinstance(expr, ast.Name):
            if expr.id in param_names:
                return (expr.id,)
            return var_to_path.get(expr.id)
        return None

    def _get_key_from_call(call_node) -> Optional[str]:
        if not isinstance(call_node, ast.Call) or not call_node.args:
            return None
        first_arg = call_node.args[0]
        if isinstance(first_arg, ast.Constant):
            return first_arg.value
        if isinstance(first_arg, ast.Str):
            return first_arg.s
        return None

    def _set_in_tree(path: Tuple[str, ...], value: Any = "Any", required: bool = False):
        if not path:
            return
        d = tree
        for key in path[:-1]:
            d = d.setdefault(key, {})
        d[path[-1]] = {"_type": value, "_required": required}

    def _ensure_branch(path: Tuple[str, ...]):
        d = tree
        for key in path:
            d = d.setdefault(key, {})

    def _extract_get_call(value) -> Optional[ast.Call]:
        if isinstance(value, ast.Call):
            return value
        if isinstance(value, ast.IfExp):
            if isinstance(value.body, ast.Call):
                return value.body
        return None

    class BodyVisitor(ast.NodeVisitor):
        def visit_Assign(self, node: ast.Assign):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                self.generic_visit(node)
                return
            lhs = node.targets[0].id
            value = node.value

            call_node = _extract_get_call(value)
            if call_node is not None:
                func = call_node.func
                if isinstance(func, ast.Attribute) and func.attr == "get":
                    obj_path = _get_path(func.value)
                    key = _get_key_from_call(call_node)
                    if obj_path is not None and key:
                        new_path = obj_path + (key,)
                        var_to_path[lhs] = new_path
                        _ensure_branch(new_path)
            elif isinstance(value, ast.Subscript):
                slice_val = getattr(value.slice, "value", value.slice) if hasattr(value.slice, "value") else value.slice
                key = slice_val.value if isinstance(slice_val, ast.Constant) else None
                if key is not None:
                    obj_path = _get_path(value.value)
                    if obj_path is not None:
                        new_path = obj_path + (str(key),)
                        var_to_path[lhs] = new_path
                        _ensure_branch(new_path)
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "get":
                obj_path = _get_path(func.value)
                key = _get_key_from_call(node)
                if obj_path is not None and key:
                    _ensure_branch(obj_path + (key,))
            elif isinstance(func, ast.Name):
                if func.id in ("require_param", "require_param_truthy") and len(node.args) >= 2:
                    val_arg = node.args[0]
                    key_arg = node.args[1]
                    key_str = None
                    if isinstance(key_arg, ast.Constant):
                        key_str = key_arg.value
                    elif isinstance(key_arg, ast.Str):
                        key_str = key_arg.s
                    if key_str:
                        val_path = _get_path(val_arg)
                        inferred_type = "dict" if func.id == "require_param_truthy" else "str"
                        if val_path:
                            _set_in_tree(val_path, inferred_type, required=True)
                        else:
                            for param in param_names:
                                _ensure_branch((param, key_str))
            self.generic_visit(node)

    try:
        visitor = BodyVisitor()
        for _ in range(3):
            prev_len = len(var_to_path)
            visitor.visit(method_node)
            if len(var_to_path) == prev_len:
                break
    except Exception:
        pass

    def _to_clean_tree(d: dict) -> dict:
        out = {}
        for k, v in d.items():
            if k.startswith("_"):
                continue
            if isinstance(v, dict) and "_type" in v:
                out[k] = v.get("_type", "Any")
            elif isinstance(v, dict):
                out[k] = _to_clean_tree(v)
            else:
                out[k] = v
        return out

    return _to_clean_tree(tree) if tree else {}


"""