from enum import Enum

class LexemeType(Enum):
    EOF = 0
    
    KEYWORD = 1
    TYPE = 2
    IDENTIFIER = 3

    BYTE = 4
    BOOLEAN = 5
    SHORT = 6
    INT = 7
    LONG = 8
    FLOAT = 9
    DOUBLE = 10
    STRING = 11

class Position:
    def __init__(self, offset: int, line: int, column: int) -> None:
        self.offset = offset
        self.line = line
        self.column = column
    
    def __str__(self):
        return f"line {self.line + 1}, column {self.column + 1}"

class Lexeme:
    def __init__(self, lexemeType: LexemeType, position: Position, body: str = None) -> None:
        self.type = lexemeType
        self.position = position
        self.body = body
    
    def __str__(self):
        return f"'{self.body}'"

class Lexer:
    keywords = ["namespace", "import", "as", "function", "mcfunction", "var", "if", "else"]
    types = ["Void", "Any", "Byte", "Boolean", "Short", "Int", "Long", "Float", "Double", "String", "List", "Compound", "ByteArray", "IntArray", "LongArray"]
    
    def __init__(self, text: str) -> None:
        self.offset = 0
        self.line = 0
        self.column = 0
        self.text = text
    
    def skip_space(self) -> None:
        while self.peekch().isspace():
            self.consume()
    
    def peekch(self) -> str:
        return self.text[self.offset] if self.offset < len(self.text) else "\0"
    
    def consume(self) -> None:
        if self.peekch() == "\n":
            self.line += 1
            self.column = 0
        else:
            self.column += 1
        self.offset += 1
    
    def position(self) -> Position:
        return Position(self.offset, self.line, self.column)
    
    def lookahead(self) -> Lexeme:
        offset, line, column = self.offset, self.line, self.column
        lexeme = self.next()
        self.offset, self.line, self.column = offset, line, column
        return lexeme
    
    def next(self) -> Lexeme:
        self.skip_space()
        ch = self.peekch()
        if ch == "\0":
            return Lexeme(LexemeType.EOF, self.position())
        elif ch == "/":
            self.consume()
            ch = self.peekch()
            if ch == "/":
                self.consume()
                while self.peekch() not in "\r\n\0":
                    self.consume()
                return self.next()
            elif ch == "*":
                self.consume()
                while self.peekch() != "\0":
                    ch = self.peekch()
                    self.consume()
                    if ch == "*":
                        if self.peekch() == "/":
                            self.consume()
                            break
                return self.next()
        elif ch == "=":
            position = self.position()
            body = ch
            self.consume()
            ch = self.peekch()
            if ch == "=":
                body += ch
                self.consume()
            return Lexeme(None, position, body)
        elif ch.isdigit() or ch == ".":
            return self.read_number()
        elif ch in "\"'":
            return self.read_string()
        elif ch.isalpha():
            return self.read_identifier()
        else:
            position = self.position()
            self.consume()
            return Lexeme(None, position, ch)
    
    def read_number(self) -> Lexeme:
        position = self.position()
        body = ""
        while self.peekch().isdigit():
            body += self.peekch()
            self.consume()
        if self.peekch() == ".":
            body += self.peekch()
            self.consume()
            while self.peekch().isdigit():
                body += self.peekch()
                self.consume()
        ch = self.peekch().lower()
        if ch == "b":
            if "." in body or int(body) + 128 > 255:
                return Lexeme(None, position, body)
            body += ch
            self.consume()
            return Lexeme(LexemeType.BYTE, position, body)
        elif ch == "s":
            if "." in body or int(body) + 32768 > 65535:
                return Lexeme(None, position, body)
            body += ch
            self.consume()
            return Lexeme(LexemeType.SHORT, position, body)
        elif ch == "l":
            if "." in body or int(body) + 9223372036854775808 > 18446744073709551615:
                return Lexeme(None, position, body)
            body += ch
            self.consume()
            return Lexeme(LexemeType.LONG, position, body)
        elif ch == "f":
            if float(body) + 3.4E38 > 6.8E38:
                return Lexeme(None, position, body)
            body += ch
            self.consume()
            return Lexeme(LexemeType.FLOAT, position, body)
        elif ch == "d":
            body += ch
            self.consume()
            return Lexeme(LexemeType.DOUBLE, position, body)
        else:
            if "." in body:
                return Lexeme(LexemeType.DOUBLE, position, body)
            elif int(body) + 2147483648 <= 4294967295:
                return Lexeme(LexemeType.INT, position, body)
            return Lexeme(None, position, body)

    def read_string(self) -> Lexeme:
        position = self.position()
        body = delimiter = self.peekch()
        self.consume()

        while self.peekch() != delimiter:
            ch = self.peekch()
            if ch in "\r\n\0":
                return Lexeme(None, position, body)
            else:
                self.consume()
                body += ch
                if ch == "\\":
                    ch = self.peekch()
                    if ch in "\\\"'":
                        self.consume()
                        body += ch
                    else:
                        return Lexeme(None, position, body)
        
        body += self.peekch()
        self.consume()

        return Lexeme(LexemeType.STRING, position, body)
    
    def read_identifier(self) -> Lexeme:
        position = self.position()
        body = ""
        while self.peekch().isalnum():
            body += self.peekch()
            self.consume()
        
        if body in self.keywords:
            lexemeType = LexemeType.KEYWORD
        elif body in self.types:
            lexemeType = LexemeType.TYPE
        elif body == "true" or body == "false":
            lexemeType = LexemeType.BOOLEAN
        else:
            lexemeType = LexemeType.IDENTIFIER
        
        return Lexeme(lexemeType, position, body)