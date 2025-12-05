
import ply.lex as lex
import sys

class TesLangLexer:
    
    tokens = (
        # Keywords
        'FUNK', 'IF', 'ELSE', 'WHILE', 'DO', 'FOR',
        'BEGIN', 'END', 'ENDIF', 'ENDWHILE', 'ENDFOR',
        'RETURN', 'AS', 'TO',
        'INT', 'VECTOR', 'STR', 'MSTR', 'BOOL', 'NULL',
        'LEN', 'PRINT',
        
        # Identifiers and values
        'ID', 'NUMBER', 'STRING', 'MSTRING',
        
        # Two-character operators
        'DBL_COLON', 'ARROW', 'EQ_EQ', 'NOT_EQ',
        'LESS_EQ', 'GREATER_EQ', 'AND', 'OR',
        'DBL_LSQUARE', 'DBL_RSQUARE',
        
        # Single-character operators
        'PLUS', 'MINUS', 'MULT', 'DIV',
        'EQ', 'LESS_THAN', 'GREATER_THAN', 'NOT',
        'QUESTION', 'COLON',
        
        # Parentheses and brackets
        'LPAREN', 'RPAREN',
        'LSQUAREBR', 'RSQUAREBR',
        'LCURLYEBR', 'RCURLYEBR',
        
        # Punctuation
        'SEMI_COLON', 'COMMA',
    )
    
    
    reserved = {
        'funk': 'FUNK',
        'if': 'IF',
        'else': 'ELSE',
        'while': 'WHILE',
        'do': 'DO',
        'for': 'FOR',
        'begin': 'BEGIN',
        'end': 'END',
        'endif': 'ENDIF',
        'endwhile': 'ENDWHILE',
        'endfor': 'ENDFOR',
        'return': 'RETURN',
        'as': 'AS',
        'to': 'TO',
        'int': 'INT',
        'vector': 'VECTOR',
        'str': 'STR',
        'mstr': 'MSTR',
        'bool': 'BOOL',
        'null': 'NULL',
        'length': 'LEN',
        'print': 'PRINT',
    }
    
    # Ignored characters
    t_ignore = ' \t\r'
    
    #  Functions with longer names have higher priority
    t_DBL_COLON = r'::'
    t_ARROW = r'=>'
    t_EQ_EQ = r'=='
    t_NOT_EQ = r'!='
    t_LESS_EQ = r'<='
    t_GREATER_EQ = r'>='
    t_AND = r'&&'
    t_OR = r'\|\|'
    t_DBL_LSQUARE = r'\[\['
    t_DBL_RSQUARE = r'\]\]'
    
    # Single-character operators
    t_PLUS = r'\+'
    t_MINUS = r'-'
    t_MULT = r'\*'
    t_DIV = r'/'
    t_EQ = r'='
    t_LESS_THAN = r'<'
    t_GREATER_THAN = r'>'
    t_NOT = r'!'
    t_QUESTION = r'\?'
    t_COLON = r':'
    
    # Parentheses and brackets
    t_LPAREN = r'\('
    t_RPAREN = r'\)'
    t_LSQUAREBR = r'\['
    t_RSQUAREBR = r'\]'
    t_LCURLYEBR = r'\{'
    t_RCURLYEBR = r'\}'
    
    # Punctuation
    t_SEMI_COLON = r';'
    t_COMMA = r','
    
    def __init__(self):
        self.lexer = None
        self.last_token = None
    
    # Multi-line strings 
    def t_MSTRING(self, t):
        r'"""[\s\S]*?"""'
        t.lexer.lineno += t.value.count('\n')
        return t
    
    # Regular strings 
    def t_STRING(self, t):
        r'"(?:[^"\\]|\\[\s\S])*"|\'(?:[^\'\\]|\\[\s\S])*\''
        return t
    
    # Integer numbers
    def t_NUMBER(self, t):
        r'\d+'
        t.value = int(t.value)
        return t
    
    # Identifiers
    def t_ID(self, t):
        r'[a-zA-Z_][a-zA-Z_0-9]*'
        t.type = self.reserved.get(t.value.lower(), 'ID')
        return t
    
    # Comments 
    def t_COMMENT(self, t):
        r'</'
        depth = 1
        start_line = t.lexer.lineno
        
        while depth > 0:
            
            if t.lexer.lexpos >= len(t.lexer.lexdata):
                print(f" Error: Unclosed comment starting at line {start_line}")
                break
            
            
            next_chars = t.lexer.lexdata[t.lexer.lexpos:t.lexer.lexpos+2]
            if next_chars == '</':
                depth += 1
                t.lexer.lexpos += 2
        
            elif next_chars == '/>':
                depth -= 1
                t.lexer.lexpos += 2
            
            else:
                # Count newlines
                if t.lexer.lexdata[t.lexer.lexpos] == '\n':
                    t.lexer.lineno += 1
                t.lexer.lexpos += 1
        pass
    
    #  line number tracking
    def t_newline(self, t):
        r'\n+'
        t.lexer.lineno += len(t.value)
    
    # Error handling
    def t_error(self, t):
        print(f" Illegal character '{t.value[0]}' at line {t.lineno}")
        t.lexer.skip(1)
    
    def build(self, **kwargs):
        """Build the lexer"""
        self.lexer = lex.lex(module=self, **kwargs)
        return self.lexer
    
    def tokenize(self, data):
        if not self.lexer:
            self.build()
        
        self.lexer.input(data)
        tokens = []
        
        while True:
            tok = self.lexer.token()
            if not tok:
                break
            
            # Calculate column number
            line_start = data.rfind('\n', 0, tok.lexpos) + 1
            column = tok.lexpos - line_start + 1
            
            tokens.append({
                'line': tok.lineno,
                'column': column,
                'type': tok.type,
                'value': tok.value,
                'lexpos': tok.lexpos
            })
            
            self.last_token = tok
        
        return tokens
    
    def tokenize_file(self, filename):
        """Tokenize from file"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = f.read()
            return self.tokenize(data)
        except FileNotFoundError:
            print(f" Error: File '{filename}' not found")
            return []
        except Exception as e:
            print(f"Error reading file: {e}")
            return []


def print_tokens(tokens):
    if not tokens:
        print("No tokens found!")
        return
    
    print(f"{'Line':<6}| {'Column':<7}| {'Token':<20}| Value")
    print("-" * 118)
    
    for tok in tokens:
        value = str(tok['value'])
        # Limit length for display
        if len(value) > 50:
            value = value[:47] + "..."
        # Display escape characters
        value = repr(value)[1:-1] if '\n' in value or '\t' in value else value
        
        print(f"{tok['line']:<6}| {tok['column']:<7}| {tok['type']:<20}| {value}")


def save_tokens(tokens, filename='tokens_output.txt'):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"{'Line':<6}| {'Column':<7}| {'Token':<20}| Value\n")
            f.write("-" * 118 + "\n")
            for tok in tokens:
                f.write(f"{tok['line']:<6}| {tok['column']:<7}| {tok['type']:<20}| {tok['value']}\n")
        print(f"Tokens saved to '{filename}'")
    except Exception as e:
        print(f" Error saving tokens: {e}")


