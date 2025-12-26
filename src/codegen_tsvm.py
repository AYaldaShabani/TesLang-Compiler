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

    def emit(self, s: str):
        self.lines.append(s)

    def generate(self, prog: Program) -> str:
        self.lines = []
        for fn in prog.functions:
            if isinstance(fn, FunctionDef):
                self.gen_function(fn)
        return "\n".join(self.lines).strip() + "\n"

    def gen_function(self, fn: FunctionDef):
        self.emit(f"proc {fn.name}")
        
        # Initialize environment with a shared register counter starting at 1
        # r0 is reserved for return values.
        env = RegEnv(start_reg=1)
        
        # Bind parameters to registers (r1, r2, ...)
        for i, p in enumerate(fn.params, start=1):
            reg = env.new_reg() 
            env.bind(p.name, reg)

        # Handle arrow functions (single expression return)
        if fn.arrow_return_expr is not None:
            r = self.gen_expr(fn.arrow_return_expr, env)
            self.emit(f"    mov r0, {r}")
            self.emit("    ret")
            self.emit("") 
            return

        # Pre-scan for nested functions to hoist them later
        nested_functions = []
        if fn.body is not None:
            for st in fn.body.statements:
                if isinstance(st, FunctionDef):
                    nested_functions.append(st)

        # Generate body code
        if fn.body is not None:
            self.gen_block(fn.body, env)

        # Default return 0  , if no explicit return found 
        self.emit("    mov r0, 0")
        self.emit("    ret")
        self.emit("")

        # Generate nested functions AFTER the parent function has closed
        for nested in nested_functions:
            self.gen_function(nested)

    def gen_block(self, block: Block, env: "RegEnv"):
        for st in block.statements:
            if isinstance(st, VarDecl):
                # Allocate a register for the variable if not already bound
                if not env.has(st.name):
                    env.bind(st.name, env.new_reg())
                
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
                # Nested function already handled in generate()
                pass

    def gen_if(self, st: IfStmt, env: "RegEnv"):
        lbl_else = env.new_label("else")
        lbl_end = env.new_label("endif")
        cond_r = self.gen_expr(st.cond, env)
        
        target = lbl_else if st.else_block else lbl_end
        self.emit(f"    jz {cond_r}, {target}")
        
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
            env.bind(st.var_name, env.new_reg())
            
        ireg = env.get(st.var_name)
        sreg = self.gen_expr(st.start, env)
        ereg = self.gen_expr(st.end, env)
        
        self.emit(f"    mov {ireg}, {sreg}")
        
        lbl_start = env.new_label("for")
        lbl_end = env.new_label("endfor")
        
        self.emit(f"{lbl_start}:")
        
        # condition: i < end
        tmp = env.new_reg()
        self.emit(f"    lt {tmp}, {ireg}, {ereg}")
        self.emit(f"    jz {tmp}, {lbl_end}")
        
        self.gen_block(st.body, env.child())
        
        # i = i + 1
        one = env.new_reg()
        self.emit(f"    mov {one}, 1")
        tmp2 = env.new_reg()
        self.emit(f"    add {tmp2}, {ireg}, {one}")
        self.emit(f"    mov {ireg}, {tmp2}")
        self.emit(f"    jmp {lbl_start}")
        
        self.emit(f"{lbl_end}:")

    # -------- expressions ----------
    def gen_expr(self, e: Expr, env: "RegEnv") -> str:
        if isinstance(e, Number):
            r = env.new_reg()
            self.emit(f"    mov {r}, {e.value}")
            return r
            
        if isinstance(e, Identifier):
            return env.get(e.name, default="r0")
            
        if isinstance(e, Assign):
            rhs = self.gen_expr(e.value, env)
            target = e.target.name
            if not env.has(target):
                env.bind(target, env.new_reg())
            self.emit(f"    mov {env.get(target)}, {rhs}")
            return env.get(target)
            
        if isinstance(e, BinaryOp):
            l = self.gen_expr(e.left, env)
            r = self.gen_expr(e.right, env)
            out = env.new_reg()
            
            opmap = {
                "+": "add", "-": "sub", "*": "mul", "/": "div",
                "<": "lt", ">": "gt", "==": "eq", "!=": "neq",
                "<=": "le", ">=": "ge", "&&": "and", "||": "or",
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
            out = env.new_reg()
            
            if e.op == "-":
                zero = env.new_reg()
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
                out = env.new_reg()
                self.emit(f"    call read, {out}")
                return out
                
            if fname == "print":
                # print(x) => call log, xreg
                if e.args:
                    x = self.gen_expr(e.args[0], env)
                    self.emit(f"    call log, {x}")
                return "r0"
                
            
            out = env.new_reg()
            arg_regs = [self.gen_expr(a, env) for a in e.args]
            args_str = ", ".join([out] + arg_regs)
            self.emit(f"    call {fname}, {args_str}")
            return out

        
        out = env.new_reg()
        self.emit(f"    mov {out}, 0")
        return out

class RegEnv:
    def __init__(self, start_reg=1, shared_counter=None):
        self.var2reg: Dict[str, str] = {}
        # Use a list to simulate a mutable integer reference shared across scopes
        if shared_counter is None:
            self.reg_counter = [start_reg]
        else:
            self.reg_counter = shared_counter
            
        self.label_id = 0

    def new_reg(self) -> str:
        # Allocate next free register from the shared counter
        r = f"r{self.reg_counter[0]}"
        self.reg_counter[0] += 1
        return r

    def bind(self, name: str, reg: str):
        self.var2reg[name] = reg
        
        if reg.startswith('r') and reg[1:].isdigit():
            val = int(reg[1:])
            if val >= self.reg_counter[0]:
                self.reg_counter[0] = val + 1

    def has(self, name: str) -> bool:
        return name in self.var2reg

    def get(self, name: str, default: Optional[str]=None) -> str:
        if name in self.var2reg:
            return self.var2reg[name]
        if default is not None:
            return default
        # Allocate on demand
        r = self.new_reg()
        self.bind(name, r)
        return r

    def child(self) -> "RegEnv":
        # Create a child scope that shares the same register counter
        # but has its own variable mapping
        c = RegEnv(shared_counter=self.reg_counter)
        c.var2reg = dict(self.var2reg)
        c.label_id = self.label_id
        return c

    def new_label(self, prefix: str) -> str:
        self.label_id += 1
        return f"{prefix}_{self.label_id}"