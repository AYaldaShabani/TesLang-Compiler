from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
from ast_nodes import *
from symbols import Scope, VarSymbol, FuncSymbol, TES_TYPES

@dataclass
class SemanticError:
    message: str
    line: int
    column: int

class SemanticAnalyzer:
    def __init__(self):
        self.errors: List[SemanticError] = []
        self.global_scope = Scope(parent=None)
        self.current_scope = self.global_scope
        self.current_function: Optional[FuncSymbol] = None

        # Define built-in functions
        # print accepts 'null' (any type)
        self.global_scope.define_func(FuncSymbol("print", "null", [("x", "null")], 0, 0))
        self.global_scope.define_func(FuncSymbol("length", "int", [("x", "vector")], 0, 0))
        self.global_scope.define_func(FuncSymbol("scan", "int", [], 0, 0)) 

    def error(self, msg: str, node: Node):
        self.errors.append(SemanticError(msg, node.line, node.column))

    def analyze(self, prog: Program) -> List[SemanticError]:
        # 1) Register top-level function signatures
        for fn in prog.functions:
            if isinstance(fn, FunctionDef):
                self._declare_function(fn, self.global_scope)

        # 2) Analyze each function body
        for fn in prog.functions:
            if isinstance(fn, FunctionDef):
                self._analyze_function(fn)

        # 3) Check for entry point (main function)
        main_fn = self.global_scope.lookup_func("main")
        if not main_fn:
            self.error("Program missing entry point: 'main' function is required.", prog)

        return self.errors

    def _declare_function(self, fn: FunctionDef, scope: Scope):
        if fn.return_type not in TES_TYPES:
            self.error(
                f"function '{fn.name}': wrong type '{fn.return_type}' found. types must be one of {sorted(TES_TYPES)}",
                fn
            )
            fn.return_type = "null"

        params = []
        for p in fn.params:
            if p.type_name not in TES_TYPES:
                self.error(
                    f"function '{fn.name}': wrong type '{p.type_name}' found. types must be one of {sorted(TES_TYPES)}",
                    p
                )
            params.append((p.name, p.type_name))
            
        ok = scope.define_func(FuncSymbol(fn.name, fn.return_type, params, fn.line, fn.column))
        if not ok:
            self.error(f"function '{fn.name}': duplicate function definition.", fn)

    def _push_scope(self):
        self.current_scope = Scope(parent=self.current_scope)

    def _pop_scope(self):
        self.current_scope = self.current_scope.parent

    def _analyze_function(self, fn: FunctionDef):
        self._push_scope()
        f_sym = self.global_scope.lookup_func(fn.name)
        self.current_function = f_sym

        # Define parameters in scope (they are considered assigned)
        for pname, ptype in (f_sym.params if f_sym else []):
            self.current_scope.define_var(VarSymbol(pname, ptype, fn.line, fn.column, assigned=True))

        if fn.arrow_return_expr is not None:
            rtype = self._infer_expr(fn.arrow_return_expr)
            self._check_return_type(fn, rtype, fn.arrow_return_expr)
            self._pop_scope()
            self.current_function = None
            return

        if fn.body is not None:
            self._visit_block(fn.body)

        self._pop_scope()
        self.current_function = None

    def _visit_block(self, block: Block):
        for st in block.statements:
            if isinstance(st, FunctionDef):
                # Nested function: declare in current scope and analyze
                self._declare_function(st, self.current_scope)
                self._analyze_function(st)
            elif isinstance(st, VarDecl):
                self._visit_vardecl(st)
            elif isinstance(st, Return):
                self._visit_return(st)
            elif isinstance(st, ExprStmt):
                self._infer_expr(st.expr)
            elif isinstance(st, IfStmt):
                self._infer_expr(st.cond)
                self._push_scope()
                self._visit_block(st.then_block)
                self._pop_scope()
                if st.else_block:
                    self._push_scope()
                    self._visit_block(st.else_block)
                    self._pop_scope()
            elif isinstance(st, WhileStmt):
                self._infer_expr(st.cond)
                self._push_scope()
                self._visit_block(st.body)
                self._pop_scope()
            elif isinstance(st, DoWhileStmt):
                self._push_scope()
                self._visit_block(st.body)
                self._pop_scope()
                self._infer_expr(st.cond)
            elif isinstance(st, ForStmt):
                self._infer_expr(st.start)
                self._infer_expr(st.end)
                self._push_scope()
                self.current_scope.define_var(VarSymbol(st.var_name, "int", st.line, st.column, assigned=True))
                self._visit_block(st.body)
                self._pop_scope()
            else:
                pass

    def _visit_vardecl(self, vd: VarDecl):
        if vd.type_name not in TES_TYPES:
            self.error(
                f"function '{self.current_function.name if self.current_function else '<?>'}': wrong type '{vd.type_name}' found. types must be one of {sorted(TES_TYPES)}",
                vd
            )
            vd.type_name = "null"

        ok = self.current_scope.define_var(VarSymbol(vd.name, vd.type_name, vd.line, vd.column, assigned=False))
        if not ok:
            self.error(
                f"function '{self.current_function.name if self.current_function else '<?>'}': variable '{vd.name}' already defined in this scope.",
                vd
            )
        if vd.init is not None:
            init_t = self._infer_expr(vd.init)
            self._require_type(vd.type_name, init_t, vd.init, f"variable '{vd.name}'")
            sym = self.current_scope.lookup_var(vd.name)
            if sym:
                sym.assigned = True

    def _visit_return(self, r: Return):
        rtype = "null"
        if r.value is not None:
            rtype = self._infer_expr(r.value)
        if self.current_function:
            expected = self.current_function.return_type
            
            if expected != rtype and not (expected == "null" and rtype == "null"):
                 self._require_type(expected, rtype, r, "return value")

    # ---------- Expression typing ----------
    def _infer_expr(self, e: Expr) -> str:
        if isinstance(e, Number):
            return "int"
        if isinstance(e, (String, MString)):
            return "str" if isinstance(e, String) else "mstr"
        if isinstance(e, Identifier):
            sym = self.current_scope.lookup_var(e.name)
            if not sym:
                self.error(f"function '{self.current_function.name if self.current_function else '<?>'}': variable '{e.name}' is not defined.", e)
                return "null"
            if not sym.assigned:
                self.error(f"function '{self.current_function.name if self.current_function else '<?>'}': Variable '{e.name}' is used before being assigned.", e)
            return sym.type_name

        if isinstance(e, Assign):
            target = e.target
            sym = self.current_scope.lookup_var(target.name)
            if not sym:
                self.error(f"function '{self.current_function.name if self.current_function else '<?>'}': variable '{target.name}' is not defined.", e)
                val_t = self._infer_expr(e.value)
                return val_t
            val_t = self._infer_expr(e.value)
            self._require_type(sym.type_name, val_t, e.value, f"variable '{target.name}'")
            sym.assigned = True
            return sym.type_name

        if isinstance(e, UnaryOp):
            t = self._infer_expr(e.operand)
            if e.op in ("+", "-"):
                self._require_type("int", t, e.operand, "unary arithmetic")
                return "int"
            if e.op == "!":
                self._require_type("bool", t, e.operand, "logical not")
                return "bool"
            return "null"

        if isinstance(e, BinaryOp):
            lt = self._infer_expr(e.left)
            rt = self._infer_expr(e.right)
            
            # Arithmetic
            if e.op in ("+", "-", "*", "/"):
                self._require_type("int", lt, e.left, "arithmetic")
                self._require_type("int", rt, e.right, "arithmetic")
                return "int"
            
            # Comparison
            if e.op in ("<", ">", "<=", ">=", "==", "!="):
                # Allow comparison of same types (or any if unknown)
                if lt != "any" and rt != "any" and lt != rt:
                    self.error(
                        f"function '{self.current_function.name if self.current_function else '<?>'}': comparison types mismatch '{lt}' vs '{rt}'.",
                        e
                    )
                return "bool"
            
            # Logical
            if e.op in ("&&", "||"):
                self._require_type("bool", lt, e.left, "logical")
                self._require_type("bool", rt, e.right, "logical")
                return "bool"
            return "null"

        if isinstance(e, TernaryOp):
            ct = self._infer_expr(e.cond)
            self._require_type("bool", ct, e.cond, "ternary condition")
            tt = self._infer_expr(e.then_expr)
            et = self._infer_expr(e.else_expr)
            if tt != "any" and et != "any" and tt != et:
                self.error(
                    f"function '{self.current_function.name if self.current_function else '<?>'}': ternary branches have different types '{tt}' and '{et}'.",
                    e
                )
            return tt if tt != "any" else et

        if isinstance(e, VectorLiteral):
            if not e.items:
                return "vector"
            # Homogeneity check: all elements should generally be of the same type
            first_t = self._infer_expr(e.items[0])
            for item in e.items[1:]:
                t = self._infer_expr(item)
                if t != "any" and first_t != "any" and t != first_t:
                     self.error(f"Vector literal contains mixed types: '{first_t}' vs '{t}'.", item)
            return "vector"

        if isinstance(e, Index):
            bt = self._infer_expr(e.base)
            it = self._infer_expr(e.index)
            self._require_type("vector", bt, e.base, "index base")
            self._require_type("int", it, e.index, "index")
            
            return "any"

        if isinstance(e, Call):
            fn_name = e.func.name
            f = self.current_scope.lookup_func(fn_name) or self.global_scope.lookup_func(fn_name)
            if not f:
                self.error(f"function '{self.current_function.name if self.current_function else '<?>'}': function '{fn_name}' is not defined.", e)
                for a in e.args:
                    self._infer_expr(a)
                return "null"

            if len(e.args) != len(f.params):
                self.error(
                    f"function '{fn_name}': expects {len(f.params)} arguments but got {len(e.args)}.",
                    e
                )
            
            # Check argument types
            for i, arg in enumerate(e.args[:len(f.params)]):
                expected = f.params[i][1]
                got = self._infer_expr(arg)
                self._require_type(expected, got, arg, f"argument {i+1} of '{fn_name}'")
            return f.return_type

        return "null"

    def _require_type(self, expected: str, got: str, node: Node, ctx: str):
        """
        Validates that 'got' type matches 'expected' type.
        Allows 'null' (void/untyped params) and 'any' (dynamic from vector index) to pass.
        """
        if expected == "null":
            return
        if got == "any": 
            return # 'any' matches everything (safe assumption for array access)
            
        if expected != got:
            self.error(
                f"function '{self.current_function.name if self.current_function else '<?>'}': {ctx} expected to be of type '{expected}', but got '{got}' instead.",
                node
            )

    def _check_return_type(self, fn: FunctionDef, got: str, node: Node):
        expected = fn.return_type
        self._require_type(expected, got, node, "return value")