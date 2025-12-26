from __future__ import annotations
from typing import List, Optional
from ast_nodes import *

class ParseError(Exception):
    def __init__(self, message: str, line: int, col: int):
        super().__init__(f"ParseError at {line}:{col} - {message}")
        self.message = message
        self.line = line
        self.col = col

class TokenStream:
    def __init__(self, tokens: List[dict]):
        self.tokens = tokens
        self.i = 0

    def peek(self, k: int = 0) -> Optional[dict]:
        j = self.i + k
        if j >= len(self.tokens):
            return None
        return self.tokens[j]

    def at_end(self) -> bool:
        return self.i >= len(self.tokens)

    def advance(self) -> Optional[dict]:
        tok = self.peek()
        if tok is not None:
            self.i += 1
        return tok

    def match(self, *types: str) -> Optional[dict]:
        tok = self.peek()
        if tok and tok["type"] in types:
            return self.advance()
        return None

    def expect(self, ttype: str) -> dict:
        tok = self.peek()
        if not tok or tok["type"] != ttype:
            line = tok["line"] if tok else -1
            col = tok["column"] if tok else -1
            got = tok["type"] if tok else "EOF"
            raise ParseError(f"Expected {ttype}, got {got}", line, col)
        return self.advance()

def _loc(tok: dict):
    return tok["line"], tok["column"]

class Parser:
    def __init__(self, tokens: List[dict]):
        self.ts = TokenStream(tokens)

    def parse_program(self) -> Program:
        prog = Program()
        while not self.ts.at_end():
            # allow stray semicolons/newlines already ignored by lexer
            func = self.parse_function()
            prog.functions.append(func)
        return prog

    def parse_function(self) -> FunctionDef:
        t_funk = self.ts.expect("FUNK")
        line, col = _loc(t_funk)
        self.ts.expect("LESS_THAN")
        ret_type_tok = self.ts.expect_any(("INT","VECTOR","STR","MSTR","BOOL","NULL"))
        self.ts.expect("GREATER_THAN")
        name_tok = self.ts.expect("ID")
        self.ts.expect("LPAREN")
        params = self.parse_param_list_opt()
        self.ts.expect("RPAREN")

        fn = FunctionDef(
            name=name_tok["value"],
            return_type=ret_type_tok["value"].lower() if isinstance(ret_type_tok["value"], str) else ret_type_tok["type"].lower(),
            params=params,
            line=line,
            column=col,
        )

        if self.ts.match("LCURLYEBR"):
            body = self.parse_body_until("RCURLYEBR")
            self.ts.expect("RCURLYEBR")
            fn.body = body
            return fn

        if self.ts.match("ARROW"):
            self.ts.expect("RETURN")
            expr = self.parse_expr()
            # arrow form ends with SEMI_COLON in grammar
            if self.ts.match("SEMI_COLON") is None:
                # tolerate missing ; but report strictness in semantic if you want
                pass
            fn.arrow_return_expr = expr
            fn.body = None
            return fn

        tok = self.ts.peek()
        raise ParseError("Expected '{' or '=>'", tok["line"], tok["column"])

    def parse_param_list_opt(self) -> List[Param]:
        params: List[Param] = []
        tok = self.ts.peek()
        if not tok or tok["type"] == "RPAREN":
            return params
        while True:
            name_tok = self.ts.expect("ID")
            self.ts.expect("AS")
            type_tok = self.ts.expect_any(("INT","VECTOR","STR","MSTR","BOOL","NULL"))
            params.append(Param(
                name=name_tok["value"],
                type_name=type_tok["value"].lower() if isinstance(type_tok["value"], str) else type_tok["type"].lower(),
                line=name_tok["line"],
                column=name_tok["column"]
            ))
            if self.ts.match("COMMA") is None:
                break
        return params

    # ---------------- BODY----------------
    def parse_body_until(self, end_token: str) -> Block:
        block = Block()
        while True:
            tok = self.ts.peek()
            if tok is None or tok["type"] == end_token:
                break
            stmt = self.parse_stmt()
            block.statements.append(stmt)
        return block

    def parse_stmt(self) -> Stmt:
        tok = self.ts.peek()
        if not tok:
            raise ParseError("Unexpected EOF", -1, -1)

        ttype = tok["type"]

        # Nested function definition allowed per spec
        if ttype == "FUNK":
            fn = self.parse_function()
            return fn  # treat as stmt node
        if ttype == "RETURN":
            t = self.ts.advance()
            expr = None
            # return expr ;
            if self.ts.peek() and self.ts.peek()["type"] != "SEMI_COLON":
                expr = self.parse_expr()
            self.ts.match("SEMI_COLON")
            return Return(value=expr, line=t["line"], column=t["column"])

        if ttype == "IF":
            return self.parse_if()

        if ttype == "WHILE":
            return self.parse_while()

        if ttype == "DO":
            return self.parse_do_while()

        if ttype == "FOR":
            return self.parse_for()

        # BEGIN body END  (block statement)
        if ttype == "BEGIN":
            t = self.ts.advance()
            body = self.parse_body_until("END")
            self.ts.expect("END")
            return body

        # variable definition: id :: type (= expr)? ;
        # lookahead: ID DBL_COLON
        if ttype == "ID" and self.ts.peek(1) and self.ts.peek(1)["type"] == "DBL_COLON":
            return self.parse_vardecl()

        # Otherwise: expression statement
        expr = self.parse_expr()
        self.ts.match("SEMI_COLON")
        return ExprStmt(expr=expr, line=expr.line, column=expr.column)

    def parse_vardecl(self) -> VarDecl:
        name_tok = self.ts.expect("ID")
        self.ts.expect("DBL_COLON")
        type_tok = self.ts.expect_any(("INT","VECTOR","STR","MSTR","BOOL","NULL"))
        init = None
        if self.ts.match("EQ"):
            init = self.parse_expr()
        self.ts.match("SEMI_COLON")
        return VarDecl(
            name=name_tok["value"],
            type_name=type_tok["value"].lower() if isinstance(type_tok["value"], str) else type_tok["type"].lower(),
            init=init,
            line=name_tok["line"],
            column=name_tok["column"],
        )

    def parse_if(self) -> IfStmt:
        t = self.ts.expect("IF")
        self.ts.expect("DBL_LSQUARE")
        cond = self.parse_expr()
        self.ts.expect("DBL_RSQUARE")
        self.ts.expect("BEGIN")
        then_block = self.parse_body_until("ENDIF" if self._next_has_else() is False else "ELSE")
        else_block = None
        if self.ts.match("ELSE"):
            else_block = self.parse_body_until("ENDIF")
        self.ts.expect("ENDIF")
        return IfStmt(cond=cond, then_block=then_block, else_block=else_block, line=t["line"], column=t["column"])

    def _next_has_else(self) -> bool:
        # crude: scan ahead until ENDIF/ELSE at same nesting level
        depth = 0
        j = self.ts.i
        while j < len(self.ts.tokens):
            tt = self.ts.tokens[j]["type"]
            if tt == "IF":
                depth += 1
            elif tt == "ENDIF":
                if depth == 0:
                    return False
                depth -= 1
            elif tt == "ELSE" and depth == 0:
                return True
            j += 1
        return False

    def parse_while(self) -> WhileStmt:
        t = self.ts.expect("WHILE")
        self.ts.expect("DBL_LSQUARE")
        cond = self.parse_expr()
        self.ts.expect("DBL_RSQUARE")
        self.ts.expect("BEGIN")
        body = self.parse_body_until("ENDWHILE")
        self.ts.expect("ENDWHILE")
        return WhileStmt(cond=cond, body=body, line=t["line"], column=t["column"])

    def parse_do_while(self) -> DoWhileStmt:
        t = self.ts.expect("DO")
        self.ts.expect("BEGIN")
        body = self.parse_body_until("WHILE")
        self.ts.expect("WHILE")
        self.ts.expect("DBL_LSQUARE")
        cond = self.parse_expr()
        self.ts.expect("DBL_RSQUARE")
        self.ts.expect("ENDWHILE")
        return DoWhileStmt(body=body, cond=cond, line=t["line"], column=t["column"])

    def parse_for(self) -> ForStmt:
        t = self.ts.expect("FOR")
        self.ts.expect("LPAREN")
        var_tok = self.ts.expect("ID")
        self.ts.expect("EQ")
        start = self.parse_expr()
        self.ts.expect("TO")
        end = self.parse_expr()
        self.ts.expect("RPAREN")
        self.ts.expect("BEGIN")
        body = self.parse_body_until("ENDFOR")
        self.ts.expect("ENDFOR")
        return ForStmt(var_name=var_tok["value"], start=start, end=end, body=body, line=t["line"], column=t["column"])

    # ---------------- EXPRESSIONS (precedence) ----------------
    def parse_expr(self) -> Expr:
        return self.parse_assignment()

    def parse_assignment(self) -> Expr:
        expr = self.parse_ternary()
        if isinstance(expr, Identifier) and self.ts.match("EQ"):
            value = self.parse_expr()
            return Assign(target=expr, value=value, line=expr.line, column=expr.column)
        return expr

    def parse_ternary(self) -> Expr:
        cond = self.parse_or()
        if self.ts.match("QUESTION"):
            then_e = self.parse_expr()
            self.ts.expect("COLON")
            else_e = self.parse_expr()
            return TernaryOp(cond=cond, then_expr=then_e, else_expr=else_e, line=cond.line, column=cond.column)
        return cond

    def parse_or(self) -> Expr:
        expr = self.parse_and()
        while self.ts.match("OR"):
            op_tok = self.ts.tokens[self.ts.i-1]
            rhs = self.parse_and()
            expr = BinaryOp(op="||", left=expr, right=rhs, line=op_tok["line"], column=op_tok["column"])
        return expr

    def parse_and(self) -> Expr:
        expr = self.parse_equality()
        while self.ts.match("AND"):
            op_tok = self.ts.tokens[self.ts.i-1]
            rhs = self.parse_equality()
            expr = BinaryOp(op="&&", left=expr, right=rhs, line=op_tok["line"], column=op_tok["column"])
        return expr

    def parse_equality(self) -> Expr:
        expr = self.parse_relational()
        while True:
            if self.ts.match("EQ_EQ"):
                op_tok = self.ts.tokens[self.ts.i-1]
                rhs = self.parse_relational()
                expr = BinaryOp(op="==", left=expr, right=rhs, line=op_tok["line"], column=op_tok["column"])
            elif self.ts.match("NOT_EQ"):
                op_tok = self.ts.tokens[self.ts.i-1]
                rhs = self.parse_relational()
                expr = BinaryOp(op="!=", left=expr, right=rhs, line=op_tok["line"], column=op_tok["column"])
            else:
                break
        return expr

    def parse_relational(self) -> Expr:
        expr = self.parse_additive()
        while True:
            if self.ts.match("LESS_THAN"):
                op_tok = self.ts.tokens[self.ts.i-1]
                rhs = self.parse_additive()
                expr = BinaryOp(op="<", left=expr, right=rhs, line=op_tok["line"], column=op_tok["column"])
            elif self.ts.match("GREATER_THAN"):
                op_tok = self.ts.tokens[self.ts.i-1]
                rhs = self.parse_additive()
                expr = BinaryOp(op=">", left=expr, right=rhs, line=op_tok["line"], column=op_tok["column"])
            elif self.ts.match("LESS_EQ"):
                op_tok = self.ts.tokens[self.ts.i-1]
                rhs = self.parse_additive()
                expr = BinaryOp(op="<=", left=expr, right=rhs, line=op_tok["line"], column=op_tok["column"])
            elif self.ts.match("GREATER_EQ"):
                op_tok = self.ts.tokens[self.ts.i-1]
                rhs = self.parse_additive()
                expr = BinaryOp(op=">=", left=expr, right=rhs, line=op_tok["line"], column=op_tok["column"])
            else:
                break
        return expr

    def parse_additive(self) -> Expr:
        expr = self.parse_multiplicative()
        while True:
            if self.ts.match("PLUS"):
                op_tok = self.ts.tokens[self.ts.i-1]
                rhs = self.parse_multiplicative()
                expr = BinaryOp(op="+", left=expr, right=rhs, line=op_tok["line"], column=op_tok["column"])
            elif self.ts.match("MINUS"):
                op_tok = self.ts.tokens[self.ts.i-1]
                rhs = self.parse_multiplicative()
                expr = BinaryOp(op="-", left=expr, right=rhs, line=op_tok["line"], column=op_tok["column"])
            else:
                break
        return expr

    def parse_multiplicative(self) -> Expr:
        expr = self.parse_unary()
        while True:
            if self.ts.match("MULT"):
                op_tok = self.ts.tokens[self.ts.i-1]
                rhs = self.parse_unary()
                expr = BinaryOp(op="*", left=expr, right=rhs, line=op_tok["line"], column=op_tok["column"])
            elif self.ts.match("DIV"):
                op_tok = self.ts.tokens[self.ts.i-1]
                rhs = self.parse_unary()
                expr = BinaryOp(op="/", left=expr, right=rhs, line=op_tok["line"], column=op_tok["column"])
            else:
                break
        return expr

    def parse_unary(self) -> Expr:
        tok = self.ts.peek()
        if tok and tok["type"] in ("NOT","PLUS","MINUS"):
            op_tok = self.ts.advance()
            operand = self.parse_unary()
            op_map = {"NOT":"!", "PLUS":"+", "MINUS":"-"}
            return UnaryOp(op=op_map[op_tok["type"]], operand=operand, line=op_tok["line"], column=op_tok["column"])
        return self.parse_postfix()

    def parse_postfix(self) -> Expr:
        expr = self.parse_primary()
        while True:
            if self.ts.match("LPAREN"):
                # call
                args = self.parse_arg_list_opt()
                self.ts.expect("RPAREN")
                if not isinstance(expr, Identifier):
                    raise ParseError("Call target must be identifier", expr.line, expr.column)
                expr = Call(func=expr, args=args, line=expr.line, column=expr.column)
            elif self.ts.match("LSQUAREBR"):
                idx = self.parse_expr()
                self.ts.expect("RSQUAREBR")
                expr = Index(base=expr, index=idx, line=expr.line, column=expr.column)
            else:
                break
        return expr

    def parse_arg_list_opt(self) -> List[Expr]:
        args: List[Expr] = []
        tok = self.ts.peek()
        if not tok or tok["type"] == "RPAREN":
            return args
        while True:
            args.append(self.parse_expr())
            if self.ts.match("COMMA") is None:
                break
        return args

    def parse_primary(self) -> Expr:
        tok = self.ts.peek()
        if not tok:
            raise ParseError("Unexpected EOF in expression", -1, -1)

        if self.ts.match("NUMBER"):
            t = self.ts.tokens[self.ts.i-1]
            return Number(value=t["value"], line=t["line"], column=t["column"])

        if self.ts.match("STRING"):
            t = self.ts.tokens[self.ts.i-1]
            return String(value=t["value"], line=t["line"], column=t["column"])

        if self.ts.match("MSTRING"):
            t = self.ts.tokens[self.ts.i-1]
            return MString(value=t["value"], line=t["line"], column=t["column"])

        if self.ts.match("ID"):
            t = self.ts.tokens[self.ts.i-1]
            return Identifier(name=t["value"], line=t["line"], column=t["column"])

        if self.ts.match("LSQUAREBR"):
            # [ clist ]  => vector literal
            items = []
            if self.ts.peek() and self.ts.peek()["type"] != "RSQUAREBR":
                items = self.parse_arg_list_opt()
            self.ts.expect("RSQUAREBR")
            start_tok = tok
            return VectorLiteral(items=items, line=start_tok["line"], column=start_tok["column"])

        if self.ts.match("LPAREN"):
            expr = self.parse_expr()
            self.ts.expect("RPAREN")
            return expr

        raise ParseError(f"Unexpected token {tok['type']} in expression", tok["line"], tok["column"])

# helper: expect_any
def _expect_any(self, types):
    tok = self.peek()
    if not tok or tok["type"] not in types:
        line = tok["line"] if tok else -1
        col = tok["column"] if tok else -1
        got = tok["type"] if tok else "EOF"
        raise ParseError(f"Expected one of {types}, got {got}", line, col)
    return self.advance()

TokenStream.expect_any = _expect_any
