from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Union, Any

@dataclass
class Node:
    line: int = 0
    column: int = 0

# ---------- Program / Function ----------
@dataclass
class Program(Node):
    functions: List["FunctionDef"] = field(default_factory=list)

@dataclass
class Param(Node):
    name: str = ""
    type_name: str = "null"

@dataclass
class FunctionDef(Node):
    name: str = ""
    return_type: str = "null"
    params: List[Param] = field(default_factory=list)
    body: Optional["Block"] = None  # None => arrow form
    arrow_return_expr: Optional["Expr"] = None

# ---------- Statements ----------
class Stmt(Node): ...

@dataclass
class Block(Stmt):
    statements: List[Stmt] = field(default_factory=list)

@dataclass
class VarDecl(Stmt):
    name: str = ""
    type_name: str = "null"
    init: Optional["Expr"] = None

@dataclass
class Return(Stmt):
    value: Optional["Expr"] = None

@dataclass
class ExprStmt(Stmt):
    expr: "Expr" = None

@dataclass
class IfStmt(Stmt):
    cond: "Expr" = None
    then_block: Block = None
    else_block: Optional[Block] = None

@dataclass
class WhileStmt(Stmt):
    cond: "Expr" = None
    body: Block = None

@dataclass
class DoWhileStmt(Stmt):
    body: Block = None
    cond: "Expr" = None

@dataclass
class ForStmt(Stmt):
    var_name: str = ""
    start: "Expr" = None
    end: "Expr" = None
    body: Block = None

# ---------- Expressions ----------
class Expr(Node): ...

@dataclass
class Number(Expr):
    value: int = 0

@dataclass
class String(Expr):
    value: str = ""

@dataclass
class MString(Expr):
    value: str = ""

@dataclass
class Identifier(Expr):
    name: str = ""

@dataclass
class Assign(Expr):
    target: Identifier = None
    value: Expr = None

@dataclass
class UnaryOp(Expr):
    op: str = ""
    operand: Expr = None

@dataclass
class BinaryOp(Expr):
    op: str = ""
    left: Expr = None
    right: Expr = None

@dataclass
class TernaryOp(Expr):
    cond: Expr = None
    then_expr: Expr = None
    else_expr: Expr = None

@dataclass
class Call(Expr):
    func: Identifier = None
    args: List[Expr] = field(default_factory=list)

@dataclass
class VectorLiteral(Expr):
    items: List[Expr] = field(default_factory=list)

@dataclass
class Index(Expr):
    base: Expr = None
    index: Expr = None
