from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
from ast_nodes import *

@dataclass
class GenResult:
    code: str

class TSVMCodeGen:
    def __init__(self):
        self.lines: List[str] = []
        self.temp_reg = 3  # r3, r4, ...

    def new_temp(self) -> str:
        r = f"r{self.temp_reg}"
        self.temp_reg += 1
        return r

    def emit(self, s: str):
        self.lines.append(s)

    def generate(self, prog: Program) -> str:
        self.lines = []
        for fn in prog.functions:
            if isinstance(fn, FunctionDef):
                self.gen_function(fn)
        return "\n".join(self.lines).strip() + "\n"

    def gen_function(self, fn: FunctionDef):
        self.temp_reg = 3
        self.emit(f"proc {fn.name}")
        # simple register mapping:
        # r0 = return, r1.. = params/locals
        env = RegEnv()
        # params start from r1
        for i, p in enumerate(fn.params, start=1):
            env.bind(p.name, f"r{i}")

        if fn.arrow_return_expr is not None:
            r = self.gen_expr(fn.arrow_return_expr, env)
            self.emit(f"    mov r0, {r}")
            self.emit("    ret")
            self.emit("")  # blank line
            return

        if fn.body is not None:
            self.gen_block(fn.body, env)
        # if no explicit return, return 0
        self.emit("    mov r0, 0")
        self.emit("    ret")
        self.emit("")

    def gen_block(self, block: Block, env: "RegEnv"):
        for st in block.statements:
            if isinstance(st, VarDecl):
                # allocate a register for var 
                if not env.has(st.name):
                    env.bind(st.name, env.new_local_reg())
                if st.init is not None:
                    r = self.gen_expr(st.init, env)
                    self.emit(f"    mov {env.get(st.name)}, {r}")
            elif isinstance(st, ExprStmt):
                self.gen_expr(st.expr, env)
            elif isinstance(st, Assign):
             
                self.gen_expr(st, env)
            elif isinstance(st, Return):
                if st.value is None:
                    self.emit("    mov r0, 0")
                else:
                    r = self.gen_expr(st.value, env)
                    self.emit(f"    mov r0, {r}")
                self.emit("    ret")
            elif isinstance(st, IfStmt):
                self.gen_if(st, env)
            elif isinstance(st, WhileStmt):
                self.gen_while(st, env)
            elif isinstance(st, DoWhileStmt):
                self.gen_do_while(st, env)
            elif isinstance(st, ForStmt):
                self.gen_for(st, env)
            elif isinstance(st, FunctionDef):
                # nested function codegen: emit as normal proc
                self.gen_function(st)

    def gen_if(self, st: IfStmt, env: "RegEnv"):
        lbl_else = env.new_label("else")
        lbl_end = env.new_label("endif")
        cond_r = self.gen_expr(st.cond, env)
        self.emit(f"    jz {cond_r}, {lbl_else}" if st.else_block else f"    jz {cond_r}, {lbl_end}")
        self.gen_block(st.then_block, env.child())
        if st.else_block:
            self.emit(f"    jmp {lbl_end}")
            self.emit(f"{lbl_else}:")
            self.gen_block(st.else_block, env.child())
        self.emit(f"{lbl_end}:")

    def gen_while(self, st: WhileStmt, env: "RegEnv"):
        lbl_start = env.new_label("while")
        lbl_end = env.new_label("endwhile")
        self.emit(f"{lbl_start}:")
        cond_r = self.gen_expr(st.cond, env)
        self.emit(f"    jz {cond_r}, {lbl_end}")
        self.gen_block(st.body, env.child())
        self.emit(f"    jmp {lbl_start}")
        self.emit(f"{lbl_end}:")

    def gen_do_while(self, st: DoWhileStmt, env: "RegEnv"):
        lbl_start = env.new_label("do")
        self.emit(f"{lbl_start}:")
        self.gen_block(st.body, env.child())
        cond_r = self.gen_expr(st.cond, env)
        self.emit(f"    jnz {cond_r}, {lbl_start}")

    def gen_for(self, st: ForStmt, env: "RegEnv"):
        # for(i = start to end) ... : i assumed int
        if not env.has(st.var_name):
            env.bind(st.var_name, env.new_local_reg())
        ireg = env.get(st.var_name)
        sreg = self.gen_expr(st.start, env)
        ereg = self.gen_expr(st.end, env)
        self.emit(f"    mov {ireg}, {sreg}")
        lbl_start = env.new_label("for")
        lbl_end = env.new_label("endfor")
        self.emit(f"{lbl_start}:")
        # condition: i < end
        tmp = self.new_temp()
        self.emit(f"    lt {tmp}, {ireg}, {ereg}")
        self.emit(f"    jz {tmp}, {lbl_end}")
        self.gen_block(st.body, env.child())
        # i = i + 1
        one = self.new_temp()
        self.emit(f"    mov {one}, 1")
        tmp2 = self.new_temp()
        self.emit(f"    add {tmp2}, {ireg}, {one}")
        self.emit(f"    mov {ireg}, {tmp2}")
        self.emit(f"    jmp {lbl_start}")
        self.emit(f"{lbl_end}:")

    # -------- expressions ----------
    def gen_expr(self, e: Expr, env: "RegEnv") -> str:
        if isinstance(e, Number):
            r = self.new_temp()
            self.emit(f"    mov {r}, {e.value}")
            return r
        if isinstance(e, Identifier):
            return env.get(e.name, default="r0")
        if isinstance(e, Assign):
            rhs = self.gen_expr(e.value, env)
            target = e.target.name
            if not env.has(target):
                env.bind(target, env.new_local_reg())
            self.emit(f"    mov {env.get(target)}, {rhs}")
            return env.get(target)
        if isinstance(e, BinaryOp):
            l = self.gen_expr(e.left, env)
            r = self.gen_expr(e.right, env)
            out = self.new_temp()
            opmap = {
                "+": "add",
                "-": "sub",
                "*": "mul",
                "/": "div",
                "<": "lt",
                ">": "gt",
                "==": "eq",
                "!=": "neq",
                "<=": "le",
                ">=": "ge",
                "&&": "and",
                "||": "or",
            }
            ins = opmap.get(e.op)
            if not ins:
                self.emit(f"    # unsupported op {e.op}")
                self.emit(f"    mov {out}, {l}")
                return out
            self.emit(f"    {ins} {out}, {l}, {r}")
            return out
        if isinstance(e, UnaryOp):
            x = self.gen_expr(e.operand, env)
            out = self.new_temp()
            if e.op == "-":
                zero = self.new_temp()
                self.emit(f"    mov {zero}, 0")
                self.emit(f"    sub {out}, {zero}, {x}")
            elif e.op == "+":
                self.emit(f"    mov {out}, {x}")
            elif e.op == "!":
                self.emit(f"    not {out}, {x}")
            else:
                self.emit(f"    mov {out}, {x}")
            return out
        if isinstance(e, Call):
            fname = e.func.name
           
            if fname == "scan":
                out = self.new_temp()
                self.emit(f"    call read, {out}")
                return out
            if fname == "print":
                # print(x) => call log, xreg
                if e.args:
                    x = self.gen_expr(e.args[0], env)
                    self.emit(f"    call log, {x}")
                return "r0"
            # normal function call: call fn, out, args...
            out = self.new_temp()
            arg_regs = [self.gen_expr(a, env) for a in e.args]
            args_str = ", ".join([out] + arg_regs)
            self.emit(f"    call {fname}, {args_str}")
            return out

        # minimal fall-back
        out = self.new_temp()
        self.emit(f"    mov {out}, 0")
        return out

class RegEnv:
    def __init__(self):
        self.var2reg: Dict[str, str] = {}
        self.local_next = 1  
        self.label_id = 0

    def bind(self, name: str, reg: str):
        self.var2reg[name] = reg

    def has(self, name: str) -> bool:
        return name in self.var2reg

    def get(self, name: str, default: Optional[str]=None) -> str:
        if name in self.var2reg:
            return self.var2reg[name]
        if default is not None:
            return default
        # allocate on demand
        r = self.new_local_reg()
        self.bind(name, r)
        return r

    def new_local_reg(self) -> str:
        # simplistic: allocate next free register
        self.local_next += 1
        return f"r{self.local_next}"

    def child(self) -> "RegEnv":
        c = RegEnv()
        c.var2reg = dict(self.var2reg)
        c.local_next = self.local_next
        c.label_id = self.label_id
        return c

    def new_label(self, prefix: str) -> str:
        self.label_id += 1
        return f"{prefix}_{self.label_id}"
