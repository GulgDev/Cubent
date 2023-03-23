from lexer import LexemeType, Lexer, Position
from dataclasses import dataclass, field
from enum import Enum
from typing import Union, Any
from zipfile import ZipFile
from io import TextIOWrapper, BytesIO
import os, shutil, glob, uuid, json, http.client

class Operation(Enum):
    LOAD = 0

    DECLARE_VAR = 1
    GET_VAR = 2
    SET_VAR = 3

    GET_PROP = 4
    SET_PROP = 5

    CALL = 6
    GET_ARG = 7

    DO_IF = 8

    ADD = 11
    SUB = 12
    DIV = 13
    MUL = 14

    EQ = 15
    NEQ = 16

    OR = 17
    AND = 18

@dataclass
class Context:
    file_name: str
    source_code: str
    function_path: str
    position: Position
    
    def in_function(self, function_path):
        return Context(self.file_name, self.source_code, function_path, self.position)

    def at_position(self, position):
        return Context(self.file_name, self.source_code, self.function_path, position)

@dataclass
class Command:
    context: Context
    operation: Operation
    data: list = field(default_factory=list)

class CompilationError:
    def __init__(self, context: Context, message: str):
        self.position = context.position
        self.line = context.source_code.splitlines()[context.position.line]
        self.file_name = context.file_name
        self.function_path = context.function_path
        self.message = message

cache_directory = os.path.join(os.environ["localappdata"], "cubent", "cache")
if not os.path.exists(cache_directory):
    os.makedirs(cache_directory)

def cache(url: str, filename: str, no_cache: bool = False) -> BytesIO:
    cache_file_path = os.path.join(cache_directory, filename)

    if os.path.isfile(cache_file_path) and not no_cache:
        with open(cache_file_path, "rb") as cache_file:
            return BytesIO(cache_file.read())
    else:
        if url[:5] == "https":
            without_protocol = url[8:]
            cls = http.client.HTTPSConnection
        else:
            without_protocol = url[7:]
            cls = http.client.HTTPConnection
        
        hostname = without_protocol[:without_protocol.find("/")]
        path = without_protocol[len(hostname):]

        conn = cls(hostname)
        conn.request("GET", path)

        data = conn.getresponse().read()

        with open(cache_file_path, "wb") as cache_file:
            cache_file.write(data)

        return BytesIO(data)

@dataclass
class MinecraftVersion:
    major: int
    minor: int
    phase: int

    _version_info: dict[str, Any] = field(default=None, init=False)

    def _load_version_info(self) -> dict[str, Any]:
        if self._version_info == None:
            version_url = self._find_version_url()
            if version_url == None:
                self._load_manifest(True)
                version_url = self._find_version_url()

            jar_url = json.load(cache(version_url, f"{self}.json"))["downloads"]["client"]["url"]

            with ZipFile(cache(jar_url, f"{self}.jar")) as jar_file:
                self._version_info = json.load(jar_file.open("version.json"))
        
        return self._version_info
        
    def _find_version_url(self) -> None:
        try:
            return next(filter(lambda version: version["id"] == str(self), self._versions_manifest["versions"]))["url"]
        except:
            return None
    
    def get_datapack_version(self) -> int:
        pack_version = self._load_version_info()["pack_version"]
        if isinstance(pack_version, int):
            return pack_version
        return pack_version["data"]
    
    def __lt__(self, other: "MinecraftVersion") -> bool:
        return self.major < other.major or self.minor < other.minor or self.phase < other.phase

    def __le__(self, other: "MinecraftVersion") -> bool:
        return self == other or self < other
    
    def __eq__(self, other: "MinecraftVersion") -> bool:
        return self.major == other.major and self.minor == other.minor and self.phase == other.phase

    def __ne__(self, other: "MinecraftVersion") -> bool:
        return self.major != other.major or self.minor != other.minor or self.phase != other.phase
    
    def __ge__(self, other: "MinecraftVersion") -> bool:
        return self == other or self > other

    def __gt__(self, other: "MinecraftVersion") -> bool:
        return self.major > other.major or self.minor > other.minor or self.phase > other.phase
    
    def __str__(self) -> str:
        return "%d.%d.%d" % (self.major, self.minor, self.phase) if self.phase else "%d.%d" % (self.major, self.minor)
    
    _versions_manifest: dict[str, Any] = field(init=False)

    latest: "MinecraftVersion" = field(init=False)

    @classmethod
    def _load_manifest(cls, no_cache: bool) -> None:
        cls._versions_manifest = json.load(cache("https://piston-meta.mojang.com/mc/game/version_manifest_v2.json", "versions.json", no_cache))

    @classmethod
    def parse(cls, version: str) -> Union["MinecraftVersion", None]:
        if version == "latest":
            return MinecraftVersion.latest

        parts = version.split(".")

        numbers = []
        for part in parts:
            if not part.isdigit():
                return
            
            numbers.append(int(part))

        if len(numbers) == 2:
            numbers.append(0)
        elif len(numbers) != 3:
            return None

        return cls(*numbers)

MinecraftVersion._load_manifest(False)

MinecraftVersion.latest = MinecraftVersion.parse(MinecraftVersion._versions_manifest["latest"]["release"])

@dataclass
class CubentFunction:
    path: list[str]
    parameters: list[tuple[str, "CubentType"]]
    return_type: "CubentType"
    commands: list[Command]

@dataclass
class MCFunction:
    path: list[str]
    parameters: list[tuple[str, "CubentType"]]
    return_type: "CubentType"
    location: str

@dataclass
class CubentType:
    path: list[str]
    properties: dict[str, "CubentType"]
    methods: dict[str, CubentFunction]

    Void: "CubentType" = field(init=False)
    Any: "CubentType" = field(init=False)
    Byte: "CubentType" = field(init=False)
    Boolean: "CubentType" = field(init=False)
    Short: "CubentType" = field(init=False)
    Int: "CubentType" = field(init=False)
    Long: "CubentType" = field(init=False)
    Float: "CubentType" = field(init=False)
    Double: "CubentType" = field(init=False)
    String: "CubentType" = field(init=False)

CubentType.Void = CubentType(["Void"], {}, {}),
CubentType.Any = CubentType(["Any"], {}, {})
CubentType.Byte = CubentType(["Byte"], {}, {})
CubentType.Boolean = CubentType(["Boolean"], {}, {})
CubentType.Short = CubentType(["Short"], {}, {})
CubentType.Int = CubentType(["Int"], {}, {})
CubentType.Long = CubentType(["Long"], {}, {})
CubentType.Float = CubentType(["Float"], {}, {})
CubentType.Double = CubentType(["Double"], {}, {})
CubentType.String = CubentType(["String"], {}, {})

class Scope:
    def __init__(self, parent: Union["Scope", None] = None) -> None:
        self.parent = parent
        self.variables: dict[str, CubentType] = {}
    
    def declare_variable(self, variable_name: str, variable_type: CubentType) -> bool:
        if variable_name in self.variables:
            return False
        self.variables[variable_name] = variable_type
        return True
    
    def get_variable(self, variable_name: str) -> CubentType | None:
        scope = self
        while scope:
            if variable_name in scope.variables:
                return scope.variables[variable_name]
            scope = scope.parent

MINIMAL_VERSION = MinecraftVersion(1, 14, 1)

CUBENT_STORAGE = "cubent:storage"
CUBENT_SCOREBOARD = "cubent.scoreboard"

class Compiler:
    operators = [
        ["+", "-"],
        ["*", "/"],
        ["==", "!="],
        ["||", "&&"]
    ]

    operations = {
        "+": Operation.ADD,
        "-": Operation.SUB,
        "*": Operation.MUL,
        "/": Operation.DIV,
        "==": Operation.EQ,
        "!=": Operation.NEQ,
        "||": Operation.OR,
        "&&": Operation.AND
    }

    def __init__(self) -> None:
        self.functions: list[CubentFunction] = []
        self.error: Union[CompilationError, str, None] = None
    
    def compile(self, source_path: str, out: str, mcversion: MinecraftVersion, icon: str, description: str) -> bool:
        if mcversion < MINIMAL_VERSION:
            self.error = f"Minimal Minecraft version for Cubent is {MINIMAL_VERSION}"
            return False

        if os.path.exists(out):
            shutil.rmtree(out)
        os.makedirs(out)

        for directory in source_path:
            if not os.path.isdir(directory):
                return False
            for filename in glob.glob("**.cubent", dir_fd=directory, recursive=True):
                if not self.compile_file(os.path.join(directory, os.path.basename(filename))):
                    return False

        build_uuid = uuid.uuid4().hex

        with open(os.path.join(out, "pack.mcmeta"), "w") as pack_meta:
            json.dump({
                "pack": {
                    "pack_format": mcversion.get_datapack_version(),
                    "description": description
                }
            }, pack_meta)
        
        shutil.copyfile(icon, os.path.join(out, "pack.png"))
        
        internal_directory = os.path.join(out, "data", build_uuid, "functions")
        os.makedirs(internal_directory)
        
        for function in self.functions:
            if type(function) == CubentFunction:
                function_directory = os.path.join(out, "data", ".".join(function.path[:-1]), "functions")
                os.makedirs(function_directory)
                if not self.write_cubent_function(build_uuid, function, os.path.join(function_directory, function.path[-1] + ".mcfunction"), internal_directory, Scope()):
                    return False
            elif type(function) == MCFunction:
                namespace, path = function.location.split(":", 2)
                path = path.split("/")
                function_directory = os.path.join(out, "data", namespace, "functions", *path[:-1])
                os.makedirs(function_directory)
                for directory in source_path:
                    function_file = os.path.join(directory, namespace, *path) + ".mcfunction"
                    if os.path.exists(function_file):
                        shutil.copyfile(function_file, os.path.join(function_directory, path[-1] + ".mcfunction"))
        
        return True
    
    def compile_file(self, filename: str) -> bool:
        with open(filename, "r") as source:
            lexer = Lexer(source.read())
        
        context = Context(filename, lexer.text, None, None)

        imports = {}
        if not self.parse_imports(lexer, context, imports):
            return False
        
        while lexer.lookahead().type != LexemeType.EOF:
            if not self.compile_block(lexer, context, imports):
                return False
        
        return True
    
    def parse_imports(self, lexer: Lexer, context: Context, imports: dict[str, list[str]]) -> bool:
        while lexer.lookahead().body == "import":
            lexer.next()

            path = []
            
            lexeme = lexer.next()
            if lexeme.type != LexemeType.IDENTIFIER:
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected identifier, got {lexeme}")
                return False
            path.append(lexeme.body)
            
            lexeme = lexer.next()
            if lexeme.body != ".":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected '.', got {lexeme}")
                return False
            while lexeme.body == ".":
                lexeme = lexer.next()
                
                if lexeme.type != LexemeType.IDENTIFIER:
                    self.error = CompilationError(context.at_position(lexeme.position), f"Expected identifier, got {lexeme}")
                    return False
                path.append(lexeme.body)
                
                lexeme = lexer.next()
            
            if lexeme.body == "as":
                lexeme = lexer.next()
                if lexeme.type != LexemeType.IDENTIFIER:
                    self.error = CompilationError(context.at_position(lexeme.position), f"Expected identifier, got {lexeme}")
                    return False
                name = lexeme.body
                
                lexeme = lexer.next()
            else:
                name = path[-1]
                
            if lexeme.body != ";":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected end of statement, got {lexeme}")
                return False

            imports[name] = path
        
        return True
    
    def compile_block(self, lexer: Lexer, context: Context, imports: dict[str, list[str]]) -> bool:
        lexeme = lexer.next()
        if lexeme.body == "namespace":
            namespace = []

            lexeme = lexer.next()
            if lexeme.type == LexemeType.IDENTIFIER:
                namespace.append(lexeme.body)
            else:
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected identifier, got {lexeme}")
                return False
            while lexer.lookahead().body == ".":
                lexer.next()
                if lexeme.type == LexemeType.IDENTIFIER:
                    namespace.append(lexeme.body)
                else:
                    self.error = CompilationError(context.at_position(lexeme.position), f"Expected identifier, got {lexeme}")
                    return False
            
            if lexer.next().body != "{":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected '{{', got {lexeme}")
                return False
            
            while lexer.lookahead().body != "}":
                if not self.compile_structure(lexer, context, namespace, imports):
                    return False
            
            if lexer.next().body != "}":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected '}}', got {lexeme}")
                return False
        elif lexeme.body == "load":
            if lexer.next().body != "{":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected '{{', got {lexeme}")
                return False
            
            if lexer.next().body != "}":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected '}}', got {lexeme}")
                return False
        elif lexeme.body == "tick":
            pass
        else:
            self.error = CompilationError(context.at_position(lexeme.position), f"Unexpected {lexeme}")
            return False
        
        return True

    def compile_structure(self, lexer: Lexer, context: Context, namespace: list[str], imports: dict[str, list[str]]) -> bool:
        lexeme = lexer.next()
        if lexeme.body == "function":
            lexeme = lexer.next()
            if lexeme.type != LexemeType.IDENTIFIER:
                self.error = CompilationError(context.at_position(lexeme.position), lexer.text, f"Expected function name, got {lexeme}")
                return False
            name = lexeme.body
            
            if lexer.next().body != "(":
                self.error = CompilationError(context.at_position(lexeme.position), lexer.text, f"Expected '(', got {lexeme}")
                return False

            parameters = {}
            while lexer.lookahead().body != ")":
                lexeme = lexer.next()
                if lexeme.type != LexemeType.IDENTIFIER:
                    self.error = CompilationError(context.at_position(lexeme.position), lexer.text, f"Expected parameter name, got {lexeme}")
                    return False
                parameter_name = lexeme.body

                if lexer.next().body != ":":
                    self.error = CompilationError(context.at_position(lexeme.position), lexer.text, f"Expected ':', got {lexeme}")
                    return False
                
                lexeme = lexer.next()
                if lexeme.type != LexemeType.TYPE:
                    self.error = CompilationError(context.at_position(lexeme.position), lexer.text, f"Expected parameter type, got {lexeme}")
                    return False
                parameter_type = lexeme.body

                parameters[parameter_name] = getattr(CubentType, parameter_type)

                if lexer.lookahead().body == ",":
                    lexer.next()
                else:
                    break

            lexeme = lexer.next()
            if lexeme.body != ")":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected ')', got {lexeme}")
                return False
            
            lexeme = lexer.next()
            if lexeme.body != ":":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected ':', got {lexeme}")
                return False
            
            lexeme = lexer.next()
            if lexeme.type != LexemeType.TYPE:
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected return type, got {lexeme}")
                return False
            return_type = lexeme.body

            lexeme = lexer.next()
            if lexeme.body != "{":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected '{{', got {lexeme}")
                return False

            commands = []

            while lexer.lookahead().body != "}":
                if not self.compile_statement(lexer, context.in_function(".".join(namespace) + "." + name), namespace, imports, parameters, commands):
                    return False
            
            if lexer.next().body != "}":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected '}}', got {lexeme}")
                return False

            self.functions.append(CubentFunction([*namespace, name], parameters, getattr(CubentType, return_type), commands))
        elif lexeme.body == "mcfunction":
            lexeme = lexer.next()
            if lexeme.type != LexemeType.STRING:
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected function location, got {lexeme}")
                return False
            
            location = ""
            offset = 1
            while offset < len(lexeme.body) - 1:
                if lexeme.body[offset] == "\\":
                    location += lexeme.body[offset + 1]
                    offset += 1
                else:
                    location += lexeme.body[offset]
                offset += 1
            
            if ":" in location:
                mcfunction_namespace, mcfunction_path = location.split(":", 2)
            else:
                mcfunction_namespace, mcfunction_path = "minecraft", location

            lexeme = lexer.next()
            if lexeme.type != LexemeType.IDENTIFIER:
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected function name, got {lexeme}")
                return False
            name = lexeme.body
            
            if lexer.next().body != "(":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected '(', got {lexeme}")
                return False

            parameters = {}
            while lexer.lookahead().body != ")":
                lexeme = lexer.next()
                if lexeme.type != LexemeType.IDENTIFIER:
                    self.error = CompilationError(context.at_position(lexeme.position), lexer.text, f"Expected parameter name, got {lexeme}")
                    return False
                parameter_name = lexeme.body

                if lexer.next().body != ":":
                    self.error = CompilationError(context.at_position(lexeme.position), lexer.text, f"Expected ':', got {lexeme}")
                    return False
                
                lexeme = lexer.next()
                if lexeme.type != LexemeType.TYPE:
                    self.error = CompilationError(context.at_position(lexeme.position), lexer.text, f"Expected parameter type, got {lexeme}")
                    return False
                parameter_type = lexeme.body

                parameters[parameter_name] = getattr(CubentType, parameter_type)

                if lexer.lookahead().body == ",":
                    lexer.next()
                else:
                    break

            lexeme = lexer.next()
            if lexeme.body != ")":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected ')', got {lexeme}")
                return False
            
            lexeme = lexer.next()
            if lexeme.body != ":":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected ':', got {lexeme}")
                return False
            
            lexeme = lexer.next()
            if lexeme.type != LexemeType.TYPE:
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected return type, got {lexeme}")
                return False
            return_type = lexeme.body

            lexeme = lexer.next()
            if lexeme.body != ";":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected ';', got {lexeme}")
                return False

            self.functions.append(MCFunction([*namespace, name], parameters, getattr(CubentType, return_type), mcfunction_namespace + ":" + mcfunction_path))
        else:
            self.error = CompilationError(context.at_position(lexeme.position), f"Unexpected {lexeme}")
            return False
        
        return True
    
    def compile_statement(self, lexer: Lexer, context: Context, namespace: list[str], imports: dict[str, list[str]], parameters: dict[str, CubentType], commands: list[Command]) -> bool:
        lexeme = lexer.lookahead()
        if lexeme.type == LexemeType.IDENTIFIER and lexeme.body in imports:
            if not self.compile_function_call(lexer, context, namespace, imports, parameters, commands):
                return False
            
            lexeme = lexer.next()
            if lexeme.body != ";":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected end of statement, got {lexeme}")
                return False
        elif lexeme.type == LexemeType.IDENTIFIER:
            lexer.next()

            path = [lexeme]

            while lexer.lookahead().body == ".":
                lexer.next()

                lexeme = lexer.next()
                if lexeme.type != LexemeType.IDENTIFIER:
                    self.error = CompilationError(context.at_position(lexeme.position), f"Expected identifier, got {lexeme}")
                    return False
                path.append(lexeme)

            lexeme = lexer.next()
            if lexeme.body != "=":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected '=', got {lexeme}")
                return False
            
            if not self.compile_expression(lexer, context, namespace, imports, parameters, commands):
                return False
            
            lexeme = lexer.next()
            if lexeme.body != ";":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected end of statement, got {lexeme}")
                return False

            if len(path) > 1:
                commands.append(Command(context.at_position(path[0].position), Operation.GET_VAR, [path[0].body]))
                for lexeme in path[1:-1]:
                    commands.append(Command(context.at_position(lexeme.position), Operation.GET_PROP, [lexeme.body]))
                commands.append(Command(context.at_position(path[-1].position), Operation.SET_PROP, [path[-1].body]))
            else:
                commands.append(Command(context.at_position(path[0].position), Operation.SET_VAR, [path[0].body]))
        elif lexeme.body == "var":
            lexer.next()

            name = lexer.next()
            if name.type != LexemeType.IDENTIFIER:
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected identifier, got {lexeme}")
                return False
            
            lexeme = lexer.next()
            if lexeme.body != "=":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected '=', got {lexeme}")
                return False
            
            if not self.compile_expression(lexer, context, namespace, imports, parameters, commands):
                return False
            
            lexeme = lexer.next()
            if lexeme.body != ";":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected end of statement, got {lexeme}")
                return False

            commands.append(Command(context.at_position(name.position), Operation.DECLARE_VAR, [name.body]))
        elif lexeme.body == "if":
            keyword = lexer.next()

            lexeme = lexer.next()
            if lexeme.body != "(":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected '(', got {lexeme}")
                return False
            
            if not self.compile_expression(lexer, context, namespace, imports, parameters, commands):
                return False

            lexeme = lexer.next()
            if lexeme.body != ")":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected ')', got {lexeme}")
                return False
            
            lexeme = lexer.next()
            if lexeme.body != "{":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected '{{', got {lexeme}")
                return False

            block_commands = []

            while lexer.lookahead().body != "}":
                if not self.compile_statement(lexer, context, namespace, imports, parameters, block_commands):
                    return False

            lexeme = lexer.next()
            if lexeme.body != "}":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected '}}', got {lexeme}")
                return False

            commands.append(Command(context.at_position(keyword.position), Operation.DO_IF, [block_commands]))
        else:
            self.error = CompilationError(context.at_position(lexeme.position), f"Unexpected {lexeme}")
            return False
        
        return True
    
    def compile_function_call(self, lexer: Lexer, context: Context, namespace: list[str], imports: dict[str, list[str]], parameters: dict[str, CubentType], commands: list[Command]) -> bool:
        lexeme = lexer.next()

        name = lexeme.body
        if name in imports:
            path = imports[name]

            position = lexeme.position

            lexeme = lexer.next()
            if lexeme.body != "(":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected '(' when calling function, got {lexeme}")
                return False

            argc = 0
            while lexer.lookahead().body != ")":
                if not self.compile_expression(lexer, context, namespace, imports, parameters, commands):
                    return False
                argc += 1

                if lexer.lookahead().body == ",":
                    lexer.next()
                else:
                    break

            lexeme = lexer.next()
            if lexeme.body != ")":
                self.error = CompilationError(context.at_position(lexeme.position), f"Expected ')', got {lexeme}")
                return False
            
            commands.append(Command(context.at_position(position), Operation.CALL, [path, argc]))

            return True
        else:
            self.error = CompilationError(context.at_position(lexeme.position), f"Expected function name, got {lexeme}")
            return False

    def compile_expression(self, lexer: Lexer, context: Context, namespace: list[str], imports: dict[str, list[str]], parameters: list[tuple[str, CubentType]], commands: list[Command]):
        if not self.compile_primary(lexer, context, namespace, imports, parameters, commands):
            return False
        
        return self.compile_operation(lexer, context, namespace, imports, parameters, commands, 0)

    def compile_operation(self, lexer: Lexer, context: Context, namespace: list[str], imports: dict[str, list[str]], parameters: list[tuple[str, CubentType]], commands: list[Command], precedence: int) -> bool:
        lexeme = lexer.lookahead()
        while lexeme.body in [operator for operators in self.operators[precedence:] for operator in operators]:
            operator = lexer.next()

            if not self.compile_primary(lexer, context, namespace, imports, parameters, commands):
                return False
            
            commands.append(Command(context.at_position(operator.position), self.operations[operator.body]))
        
            if not self.compile_operation(lexer, context, namespace, imports, parameters, commands, precedence + (1 if [operator for operators in self.operators[precedence + 1:] for operator in operators] else 0)):
                return False

            lexeme = lexer.lookahead()
        
        return True

    def compile_primary(self, lexer: Lexer, context: Context, namespace: list[str], imports: dict[str, list[str]], parameters: list[tuple[str, CubentType]], commands: list[Command]) -> bool:
        lexeme = lexer.lookahead()
        if lexeme.type == LexemeType.IDENTIFIER:
            if lexeme.body in imports:
                return self.compile_function_call(lexer, context, namespace, imports, parameters, commands)
            elif any([lexeme.body == name for name in parameters]):
                commands.append(Command(context.at_position(lexeme.position), Operation.GET_ARG, [next(index for index, (name, _) in enumerate(parameters) if name == lexeme.body)]))
            else:
                commands.append(Command(context.at_position(lexeme.position), Operation.GET_VAR, [lexeme.body]))
        elif lexeme.type == LexemeType.BOOLEAN:
            commands.append(Command(context.at_position(lexeme.position), Operation.LOAD, [CubentType.Boolean, lexeme.body == "true"]))
        elif lexeme.type == LexemeType.BYTE:
            commands.append(Command(context.at_position(lexeme.position), Operation.LOAD, [CubentType.Byte, int(lexeme.body.rstrip("Bb"))]))
        elif lexeme.type == LexemeType.SHORT:
            commands.append(Command(context.at_position(lexeme.position), Operation.LOAD, [CubentType.Short, int(lexeme.body.rstrip("Ss"))]))
        elif lexeme.type == LexemeType.INT:
            commands.append(Command(context.at_position(lexeme.position), Operation.LOAD, [CubentType.Int, int(lexeme.body)]))
        elif lexeme.type == LexemeType.LONG:
            commands.append(Command(context.at_position(lexeme.position), Operation.LOAD, [CubentType.Long, int(lexeme.body.rstrip("Ll"))]))
        elif lexeme.type == LexemeType.FLOAT:
            commands.append(Command(context.at_position(lexeme.position), Operation.LOAD, [CubentType.Float, float(lexeme.body.rstrip("Ff"))]))
        elif lexeme.type == LexemeType.DOUBLE:
            commands.append(Command(context.at_position(lexeme.position), Operation.LOAD, [CubentType.Double, float(lexeme.body.rstrip("Dd"))]))
        elif lexeme.type == LexemeType.STRING:
            body = ""
            offset = 1
            while offset < len(lexeme.body) - 1:
                if lexeme.body[offset] == "\\":
                    body += lexeme.body[offset + 1]
                    offset += 1
                else:
                    body += lexeme.body[offset]
                offset += 1
            commands.append(Command(context.at_position(lexeme.position), Operation.LOAD, [CubentType.String, body]))
        else:
            self.error = CompilationError(context.at_position(lexeme.position), f"Unexpected {lexeme}")
            return False
        
        lexer.next()

        return True

    def write_cubent_function(self, build_uuid: str, cubent_function: CubentFunction, mcfunction_filename: str, internal_directory: str, scope: Scope) -> bool:
        with open(mcfunction_filename, "w") as mcfunction_file:
            return self.write_commands(build_uuid, cubent_function.path, cubent_function.commands, cubent_function.parameters, mcfunction_file, internal_directory, scope)
    
    def write_commands(self, build_uuid: str, path: list[str], commands: list[Command], parameters: dict[str, CubentType], mcfunction_file: TextIOWrapper, internal_directory: str, scope: Scope) -> bool:
        stack: list[CubentType] = []

        function_storage = build_uuid + "." + ".".join(path[:-1]) + ":" + path[-1]

        mcfunction_file.write(f"scoreboard objectives add {CUBENT_SCOREBOARD} dummy\ndata modify storage {function_storage} Stack set value []\nexecute unless data storage {function_storage} Variables run data modify storage {function_storage} Variables set value {{}}\n")

        for command in commands:
            if command.operation == Operation.LOAD:
                cubent_type = command.data[0]
                stack.append(cubent_type)

                if cubent_type == CubentType.String:
                    body = command.data[1].replace("\\", "\\\\")
                    if body.find("'") != -1 and body.find("'") > body.find('"'):
                        raw = '"' + body.replace('"', '\\"') + '"'
                    else:
                        raw = "'" + body.replace("'", "\\'") + "'"
                elif cubent_type == CubentType.Byte:
                    raw = f"{command.data[1]}B"
                elif cubent_type == CubentType.Boolean:
                    raw = "true" if command.data[1] else "false"
                elif cubent_type == CubentType.Short:
                    raw = f"{command.data[1]}S"
                elif cubent_type == CubentType.Long:
                    raw = f"{command.data[1]}L"
                elif cubent_type == CubentType.Float:
                    raw = f"{command.data[1]}F"
                else:
                    raw = command.data[1]
                mcfunction_file.write(f"data modify storage {function_storage} Stack append value {{Value:{raw}}}\n")
            elif command.operation == Operation.DECLARE_VAR:
                name = command.data[0]
                variable_type = stack.pop()
                if not scope.declare_variable(name, variable_type):
                    self.error = CompilationError(command.context, f"Can't declare existing variable '{name}'")
                    return False
            elif command.operation == Operation.SET_VAR:
                name = command.data[0]
                object_type = stack.pop()
                variable_type = scope.get_variable(name)
                if not variable_type:
                    self.error = CompilationError(command.context, f"Undefined variable '{name}'")
                    return False
                if variable_type != object_type:
                    self.error = CompilationError(command.context, f"Can't put {'.'.join(object_type.path)} object to {'.'.join(variable_type.path)} variable '{name}'")
                    return False
                mcfunction_file.write(f"data modify storage {function_storage} Variables.{name} set from storage {function_storage} Stack[-1]\ndata remove storage {function_storage} Stack[-1]\n")
            elif command.operation == Operation.GET_VAR:
                name = command.data[0]
                variable_type = scope.get_variable(name)
                if variable_type:
                    stack.append(variable_type)
                    mcfunction_file.write(f"data modify storage {function_storage} Stack append from storage {function_storage} Variables.{name}\n")
                else:
                    self.error = CompilationError(command.context, f"Undefined variable '{name}'")
                    return False
            elif command.operation == Operation.GET_PROP:
                name = command.data[0]
                object_type = stack.pop()
                if object_type.has_property(name):
                    stack.append(object_type.get_property_type(name))
                    mcfunction_file.write(f"data modify storage {function_storage} Stack append from storage {function_storage} Stack[-1].Value.{name}\ndata remove storage {function_storage} Stack[-2]\n")
                else:
                    self.error = CompilationError(command.context, f"Undefined property '{name}' of object")
                    return False
            elif command.operation == Operation.SET_PROP:
                name = command.data[0]
                object_type = stack.pop()
                if object_type.has_property(name):
                    stack.append(object_type.get_property_type(name))
                    mcfunction_file.write(f"data modify storage {function_storage} Stack[-1].Value.{name} set from storage {function_storage} Stack[-2].Value\ndata remove storage {function_storage} Stack[-1]\ndata remove storage {function_storage} Stack[-1]\n")
                else:
                    self.error = CompilationError(command.context, f"Undefined property '{name}' of object")
                    return False
            elif command.operation == Operation.GET_ARG:
                index = command.data[0]
                stack.append(parameters[index])
                mcfunction_file.write(f"data modify storage {function_storage} Stack append from storage {CUBENT_STORAGE} Arguments[{index}]\n")
            elif command.operation == Operation.CALL:
                mcfunction_file.write(f"data modify storage {CUBENT_STORAGE} Arguments set value []\n")
                
                path = command.data[0]
                namespace = ".".join(path[:-1])

                for target_function in self.functions:
                    if target_function.path == path:
                        for parameter_name, parameter_type in target_function.parameters.items():
                            argument_type = stack.pop()
                            if not self.write_type_conversion(argument_type, parameter_type, function_storage, mcfunction_file):
                                self.error = CompilationError(command.context, f"Expected argument '{parameter_name}' of type {parameter_type.path[-1]}, but got {argument_type.path[-1]}")
                                return False
                            
                            mcfunction_file.write(f"data modify storage {CUBENT_STORAGE} Arguments append from storage {function_storage} Stack[-1]\ndata remove storage {function_storage} Stack[-1]\n")
                        
                        if type(target_function) == CubentFunction:
                            mcfunction_file.write(f"function {namespace}:{path[-1]}\n")
                        elif type(target_function) == MCFunction:
                            mcfunction_file.write(f"function {target_function.location}\n")
                        break
                else:
                    self.error = CompilationError(command.context, f"Undefined function '{'.'.join(path)}'")
                    return False
            elif command.operation == Operation.DO_IF:
                object_type = stack.pop()

                if not self.write_type_conversion(object_type, CubentType.Boolean, function_storage, mcfunction_file):
                    return False

                internal_function_location = self.write_internal_function(build_uuid, path, command.data[0], parameters, internal_directory, scope)
                if not internal_function_location:
                    return False
                
                mcfunction_file.write(f"execute store result score 1 {CUBENT_SCOREBOARD} run data get storage {function_storage} Stack[-1].Value\ndata remove storage {function_storage} Stack[-1]\nexecute if score 1 {CUBENT_SCOREBOARD} matches 1 run function {internal_function_location}\n")
            elif command.operation == Operation.ADD:
                second_type, first_type = stack.pop(), stack.pop()

                first_type_path, second_type_path = ".".join(first_type.path), ".".join(second_type.path)

                if first_type_path not in ["Byte", "Short", "Int", "Long"] or \
                    second_type_path not in ["Byte", "Short", "Int", "Long"]:
                    self.error = CompilationError(command.context, f"Can't add {second_type.path[-1]} to {first_type.path[-1]}")
                    return False
                
                stack.append(CubentType.Int)
                
                mcfunction_file.write(f"execute store result score 1 {CUBENT_SCOREBOARD} run data get storage {function_storage} Stack[-1].Value\ndata remove storage {function_storage} Stack[-1]\nexecute store result score 2 {CUBENT_SCOREBOARD} run data get storage {function_storage} Stack[-1].Value\ndata remove storage {function_storage} Stack[-1]\nscoreboard players operation 1 {CUBENT_SCOREBOARD} += 2 {CUBENT_SCOREBOARD}\ndata modify storage {function_storage} Stack append value {{}}\nexecute store result storage {function_storage} Stack[-1].Value {first_type_path.lower()} 1.0 run scoreboard players get 1 {CUBENT_SCOREBOARD}\n")
            elif command.operation == Operation.EQ:
                stack.pop()
                stack.pop()
                mcfunction_file.write(f"execute store success score 1 {CUBENT_SCOREBOARD} run data modify storage {function_storage} Stack[-1] set from storage {function_storage} Stack[-2]\ndata remove storage {function_storage} Stack[-1]\nexecute if score 1 {CUBENT_SCOREBOARD} matches 0 run data modify storage {function_storage} Stack[-1].Value set value true\nexecute if score 1 {CUBENT_SCOREBOARD} matches 1 run data modify storage {function_storage} Stack[-1].Value set value false\n")
                stack.append(CubentType.Boolean)
        
        return True
    
    def write_internal_function(self, build_uuid: str, path: list[str], commands: list[Command], parameters: dict[str, CubentType], internal_directory: str, scope: Scope) -> Union[str, None]:
        internal_function_name = uuid.uuid4().hex
        with open(os.path.join(internal_directory, internal_function_name + ".mcfunction"), "w") as mcfunction_file:
            if not self.write_commands(build_uuid, path, commands, parameters, mcfunction_file, internal_directory, Scope(scope)):
                return None
        return internal_directory.split(os.path.sep)[-2] + ":" + internal_function_name

    def write_type_conversion(self, current_type: CubentType, target_type: CubentType, function_storage: str, mcfunction_file: TextIOWrapper) -> bool:
        current_type_path, target_type_path = ".".join(current_type.path), ".".join(target_type.path)

        if current_type_path == target_type_path or current_type_path == "Any" or target_type_path == "Any":
            return True

        if current_type_path in ["Boolean", "Byte", "Short", "Int", "Long", "Float", "Double"]:
            if target_type_path in ["Byte", "Short", "Int", "Long", "Float", "Double"]:
                mcfunction_file.write(f"execute store result storage {function_storage} Stack[-1].Value {target_type.path[0].lower()} 1.0 run data get storage {function_storage} Stack[-1].Value\n")
                return True
            elif target_type_path == "Boolean":
                mcfunction_file.write(f"execute store result score 1 {CUBENT_SCOREBOARD} run data get storage {function_storage} Stack[-1].Value\nexecute if score 1 {CUBENT_SCOREBOARD} matches 1.. run data modify storage {function_storage} Stack[-1].Value set value true\nexecute if score 1 {CUBENT_SCOREBOARD} matches ..0 run data modify storage {function_storage} Stack[-1].Value set value false\n")
                return True
        
        return False