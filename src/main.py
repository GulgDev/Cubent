from compiler import MinecraftVersion, Compiler
from argparse import ArgumentParser
import os, sys

RESOURCES = os.path.join(os.path.dirname(__file__), "resources")
DEFAULT_ICON = os.path.join(RESOURCES, "pack.png")

parser = ArgumentParser(
            prog="cubent",
            description="Compiles Cubent code to Minecraft datapack")

parser.add_argument("out",
                    help="output datapack folder")
parser.add_argument("version",
                    help="target Minecraft version")
parser.add_argument("-i", "--icon",
                    help="change output datapack icon",
                    default=DEFAULT_ICON)
parser.add_argument("-d", "--description",
                    help="change output datapack description",
                    default="Cubent datapack")
parser.add_argument("-s", "--source",
                    help="append path to compile files from",
                    action="append",
                    default=[])

args = parser.parse_args()

mcversion = MinecraftVersion.parse(args.version)
if mcversion is None:
    sys.stderr.write("Invalid target version\n")
    exit(-1)

if os.path.isfile(args.icon):
    icon = args.icon
else:
    icon = DEFAULT_ICON
    sys.stderr.write(f"Icon file '{args.icon}' doesn't exists\n")

for directory in args.source:
    if not os.path.isdir(directory):
        sys.stderr.write(f"Directory '{directory}' doesn't exists\n")
        exit(-1)

compiler = Compiler()
if not compiler.compile(args.source, args.out, mcversion, icon, args.description):
    error = compiler.error

    if error == None:
        sys.stderr.write(f"Unexpected error\n")
        exit(-1)
    
    if isinstance(error, str):
        sys.stderr.write(f"Error: {error}\n")
        exit(-1)
    
    context = f"at {error.position} in file '{os.path.abspath(error.file_name)}'"
    if error.function_path != None:
        context += f", function '{error.function_path}'"
    
    sys.stderr.write(f"Error {context}: {error.message}\n")
    line = error.line.strip()
    sys.stderr.write("    " + line + "\n")
    sys.stderr.write("    " + " " * (error.position.column - len(error.line) + len(line)) + "^\n")
    exit(-1)

sys.stdout.write(f"Sucessfuly compiled datapack to '{os.path.abspath(args.out)}'\n")