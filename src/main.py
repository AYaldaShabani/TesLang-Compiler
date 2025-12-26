# import sys
# from lexer import TesLangLexer, print_tokens, save_tokens


# def main():
#     lexer = TesLangLexer()
#     if len(sys.argv) == 2:
#         input_filename = sys.argv[1]
#         tokens = lexer.tokenize_file(input_filename)
#         print_tokens(tokens)

#     elif len(sys.argv) == 1:
#         data = sys.stdin.read()
#         tokens = lexer.tokenize(data)
#         print_tokens(tokens)

#     else:
#         print("Usage:")
#         print("  python main.py <input_file>")
#         print("  or")
#         print("  python main.py < input_file")
#         sys.exit(1)


# if __name__ == "__main__":
#     main()
# phase 2 and 3 
import sys
from lexer import TesLangLexer, print_tokens
from parser import Parser, ParseError
from semantic import SemanticAnalyzer
from codegen_tsvm import TSVMCodeGen

def read_input(argv):
    if len(argv) == 2:
        with open(argv[1], "r", encoding="utf-8") as f:
            return f.read()
    return sys.stdin.read()

def usage():
    print("Usage:")
    print("  python main.py lex < input.tes")
    print("  python main.py check < input.tes")
    print("  python main.py gen < input.tes")
    print("  or:")
    print("  python main.py lex file.tes")
    print("  python main.py check file.tes")
    print("  python main.py gen file.tes")

def main():
    if len(sys.argv) < 2:
        usage()
        sys.exit(1)

    mode = sys.argv[1].lower()
    data = read_input(sys.argv[1:])

    lexer = TesLangLexer()
    tokens = lexer.tokenize(data)

    if mode == "lex":
        print_tokens(tokens)
        return

    # parse
    try:
        parser = Parser(tokens)
        program = parser.parse_program()
    except ParseError as e:
        print(str(e))
        return

    # semantic
    sema = SemanticAnalyzer()
    errors = sema.analyze(program)
    if mode == "check":
        if not errors:
            print("OK: no syntax/semantic errors found.")
        else:
            for er in errors:
                print(f"Error at {er.line}:{er.column} - {er.message}")
        return

    if mode == "gen":
        if errors:
            for er in errors:
                print(f"Error at {er.line}:{er.column} - {er.message}")
            print("\nCode generation skipped due to errors.")
            return
        gen = TSVMCodeGen()
        out = gen.generate(program)
        print(out)
        return

    usage()

if __name__ == "__main__":
    main()
