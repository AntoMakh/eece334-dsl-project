import re
import sys
from collections import namedtuple

Token = namedtuple("Token", ["type", "value", "line", "column"])

TOKEN_SPECIFICATION = [
    ("KEYWORD", r"\b(agent|tool|task|action|system|if|for|in|run|string|int|bool|list|true|false|and|or)\b"),
    
    ("WHITESPACE", r"[ \t\r\n]+"),

    ("ARROW", r"->"),
    ("EQ", r"=="),
    ("NE", r"!="),
    ("GE", r">="),
    ("LE", r"<="),

    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("LBRACE", r"\{"),
    ("RBRACE", r"\}"),
    ("LBRACKET", r"\["),
    ("RBRACKET", r"\]"),
    ("COMMA", r","),
    ("DOT", r"\."),
    ("COLON", r":"),
    ("ASSIGN", r"="),
    ("PLUS", r"\+"),
    ("MINUS", r"-"),
    ("TIMES", r"\*"),
    ("DIV", r"/"),
    ("GT", r">"),
    ("LT", r"<"),

    ("STRING", r'"([^"\\\n]|\\.)*"'),
    ("NUM", r"[0-9]+"),

    ("ID", r"[A-Za-z_][A-Za-z0-9_]*"),

    ("MISMATCH", r"."),
]


MASTER_PATTERN = re.compile(
    "|".join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPECIFICATION)
)

TOKEN_TYPE_MAP = {
    "ARROW": "->",
    "EQ": "==",
    "NE": "!=",
    "GE": ">=",
    "LE": "<=",
    "LPAREN": "(",
    "RPAREN": ")",
    "LBRACE": "{",
    "RBRACE": "}",
    "LBRACKET": "[",
    "RBRACKET": "]",
    "COMMA": ",",
    "DOT": ".",
    "COLON": ":",
    "ASSIGN": "=",
    "PLUS": "+",
    "MINUS": "-",
    "TIMES": "*",
    "DIV": "/",
    "GT": ">",
    "LT": "<",
    "NUM": "num",
    "STRING": "str",
}

def tokenize(code: str):
    """
    Convert source code into a list of Token(type, value, line, column).

    Token types are chosen to align directly with the grammar terminals:
      keywords -> 'agent', 'task', 'if', ...
      identifiers -> 'id'
      integers -> 'num'
      strings -> 'str'
      punctuation/operators -> literal terminal strings like '(', '==', '->'
      EOF -> '$'
    """
    tokens = []
    line_num = 1
    line_start = 0

    for match in MASTER_PATTERN.finditer(code):
        kind = match.lastgroup
        value = match.group()
        column = match.start() - line_start + 1

        if kind == "WHITESPACE":
            if "\n" in value:
                line_num += value.count("\n")
                last_newline = value.rfind("\n")
                line_start = match.start() + last_newline + 1
            continue

        if kind == "MISMATCH":
            if value == '"':
                raise SyntaxError(
                    f"Unterminated or invalid string literal at line {line_num}, column {column}"
                )
            raise SyntaxError(
                f"Unexpected character {value!r} at line {line_num}, column {column}"
            )
    
        if kind == "KEYWORD":
            tokens.append(Token(value, value, line_num, column))
            continue
    
        if kind == "ID":
            tokens.append(Token("id", value, line_num, column))
            continue

        token_type = TOKEN_TYPE_MAP[kind]
        tokens.append(Token(token_type, value, line_num, column))

    eof_column = (len(code) - line_start + 1) if code else 1
    tokens.append(Token("$", "$", line_num, eof_column))
    return tokens


def main():
    if len(sys.argv) != 2:
        print("Usage: python lexer.py <source_file>")
        sys.exit(1)

    filename = sys.argv[1]

    try:
        with open(filename, "r", encoding="utf-8") as f:
            code = f.read()
    except FileNotFoundError:
        print(f"Error: file '{filename}' not found.")
        sys.exit(1)

    try:
        tokens = tokenize(code)
    except SyntaxError as e:
        print("Lexical error:", e)
        sys.exit(1)

    for token in tokens:
        print(f"{token.type:<8} {token.value:<25} (line {token.line}, col {token.column})")


if __name__ == "__main__":
    main()