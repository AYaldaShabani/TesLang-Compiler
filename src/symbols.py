from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional, List

TES_TYPES = {"int", "vector", "str", "mstr", "bool", "null"}

@dataclass
class VarSymbol:
    name: str
    type_name: str
    defined_line: int
    defined_col: int
    assigned: bool = False

@dataclass
class FuncSymbol:
    name: str
    return_type: str
    params: List[tuple]  
    defined_line: int
    defined_col: int

@dataclass
class Scope:
    parent: Optional["Scope"] = None
    vars: Dict[str, VarSymbol] = field(default_factory=dict)
    funcs: Dict[str, FuncSymbol] = field(default_factory=dict)

    def define_var(self, sym: VarSymbol) -> bool:
        if sym.name in self.vars:
            return False
        self.vars[sym.name] = sym
        return True

    def define_func(self, sym: FuncSymbol) -> bool:
        if sym.name in self.funcs:
            return False
        self.funcs[sym.name] = sym
        return True

    def lookup_var(self, name: str) -> Optional[VarSymbol]:
        cur = self
        while cur:
            if name in cur.vars:
                return cur.vars[name]
            cur = cur.parent
        return None

    def lookup_func(self, name: str) -> Optional[FuncSymbol]:
        cur = self
        while cur:
            if name in cur.funcs:
                return cur.funcs[name]
            cur = cur.parent
        return None
