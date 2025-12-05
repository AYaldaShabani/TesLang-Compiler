import sys
from lexer import TesLangLexer, print_tokens, save_tokens


def main():
    lexer = TesLangLexer()
    if len(sys.argv) == 2:
        input_filename = sys.argv[1]
        tokens = lexer.tokenize_file(input_filename)
        print_tokens(tokens)

    elif len(sys.argv) == 1:
        data = sys.stdin.read()
        tokens = lexer.tokenize(data)
        print_tokens(tokens)

    else:
        print("Usage:")
        print("  python main.py <input_file>")
        print("  or")
        print("  python main.py < input_file")
        sys.exit(1)


if __name__ == "__main__":
    main()
