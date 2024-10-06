from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
from enum import IntEnum
from os import path
from time import perf_counter

magic: bytearray = bytearray(map(ord, "JED?"))
version = [1, 0]

header_sections = {
    'magic': 0,
    'version': 4,
    'mem_length': 6,
    'mem_stride': 8,
    'data_segment': 9,
    'entry_points': 10,
}


class TokenType(IntEnum):
    T_NOP = 0
    T_HALT = 1
    T_START = 2
    T_TURN = 3
    T_STACK_OP = 4
    T_COND = 5
    T_READ_BYTE = 6
    T_WRITE_BYTE = 7
    T_DIGIT = 8
    T_COMMENT = 9

    def is_path_terminal(self):
        return self in (
            TokenType.T_HALT,
            TokenType.T_START,
            TokenType.T_TURN,
            TokenType.T_COND)


class ByteCode(IntEnum):
    OP_HALT = 0
    OP_LOAD = 1
    OP_STORE = 2
    OP_STACK = 3
    OP_JMP = 4
    OP_JZ = 5
    OP_PUSH = 8  # Create no opcodes with higher number


jump_bytes = [
    (ByteCode.OP_JMP << 4) | 0x0f,
    (ByteCode.OP_JZ << 4) | 0x0f
]


class StackOp(IntEnum):
    STACK_SUB = 0
    STACK_ADD = 1
    STACK_MUL = 2
    STACK_DIV = 3
    STACK_MOD = 4
    STACK_AND = 5
    STACK_OR = 6
    STACK_NOT = 7
    STACK_POP = 8
    STACK_SWAP = 9
    STACK_DUP = 10


class PlaceholderType(IntEnum):
    FOR_PATH_END = 0
    FOR_PATH_START = 1


@dataclass
class Token:
    type: TokenType
    value: str


def lex_char(ch: str) -> Token:
    if ch == ' ':
        token_type = TokenType.T_NOP
    elif ch == ';':
        token_type = TokenType.T_COMMENT
    elif ch == '@':
        token_type = TokenType.T_HALT
    elif ch in ['N', 'S', 'E', 'W']:
        token_type = TokenType.T_START
    elif ch in ['<', '^', '>', 'v']:
        token_type = TokenType.T_TURN
    elif ch in ['-', '+', '*', '/', '%', '&', '|', '~', '!', ':', '$']:
        token_type = TokenType.T_STACK_OP
    elif ch == '_':
        token_type = TokenType.T_COND
    elif '0' <= ch <= '9':
        token_type = TokenType.T_DIGIT
    elif ch == '?':
        token_type = TokenType.T_READ_BYTE
    elif ch == '#':
        token_type = TokenType.T_WRITE_BYTE
    else:
        raise ValueError(f"Cannot parse token: '{ch}")

    return Token(token_type, ch)


@dataclass
class Vector:
    x: int
    y: int

    def copy(self) -> 'Vector':
        return Vector(self.x, self.y)

    def add(self, other: 'Vector') -> None:
        self.x += other.x
        self.y += other.y


# (0, 0) is at upper left.
@dataclass
class Label:
    location: Vector
    direction: Vector
    refcount: int = 0


dir_vec: Mapping[str, Vector] = {
    '^': Vector(0, -1),
    'v': Vector(0, 1),
    '<': Vector(-1, 0),
    '>': Vector(1, 0),
    'N': Vector(0, -1),
    'S': Vector(0, 1),
    'W': Vector(-1, 0),
    'E': Vector(1, 0),
}


class Stack:
    def __init__(self):
        self.stack: list[int] = []

    def is_empty(self) -> bool:
        return len(self.stack) == 0

    def push(self, val: int) -> None:
        self.stack.append(val)

    def pop(self) -> int:
        return self.stack.pop()

    def peek(self) -> int:
        return self.stack[-1]

    def math(self, op: StackOp) -> None:
        # Unary operator.
        if op == StackOp.STACK_NOT:
            self.push(~self.pop())

        # Binary operators.
        else:
            a = self.pop()
            b = self.pop()
            match op:
                case StackOp.STACK_SUB:
                    self.push(b - a)
                case StackOp.STACK_ADD:
                    self.push(b + a)
                case StackOp.STACK_MUL:
                    self.push(b * a)
                case StackOp.STACK_DIV:
                    self.push(b // a)
                case StackOp.STACK_MOD:
                    self.push(b % a)
                case StackOp.STACK_AND:
                    self.push(b & a)
                case StackOp.STACK_OR:
                    self.push(b | a)
                case _:
                    raise ValueError(f"Unhandled stack math op: {op}")

    def op(self, op: StackOp) -> None:
        match op:
            case StackOp.STACK_POP:
                self.pop()
            case StackOp.STACK_SWAP:
                self.stack[-2:] = self.stack[-1], self.stack[-2]
            case StackOp.STACK_DUP:
                self.push(self.stack[-1])
            case _:
                self.math(op)


def make_byte(op: ByteCode, arg: int = 0) -> int:
    if arg < 0 or arg > 15:
        raise ValueError(f"Invalid op for bytecode: {arg}")
    return (op.value << 4) | (arg & 0xff)


def fmt_line(offset: int, text: any) -> str:
    return f"{offset:04x}\t{text}\n"


def bytecode_name(byte: int, next_byte: int = -1) -> str:
    op = (byte >> 4) & 0xf
    arg = byte & 0xf

    if op & 0x8:
        return f"[{byte:02x}] PUSH {byte & 0x7f:02x} {next_byte:02x}"

    match op:
        case ByteCode.OP_HALT:
            return f"[{byte:02x}] HALT"
        case ByteCode.OP_LOAD:
            return f"[{byte:02x}] LOAD"
        case ByteCode.OP_STORE:
            return f"[{byte:02x}] STORE"
        case ByteCode.OP_STACK:
            match arg:
                case StackOp.STACK_SUB:
                    return f"[{byte:02x}] SUB"
                case StackOp.STACK_ADD:
                    return f"[{byte:02x}] ADD"
                case StackOp.STACK_MUL:
                    return f"[{byte:02x}] MUL"
                case StackOp.STACK_DIV:
                    return f"[{byte:02x}] DIV"
                case StackOp.STACK_MOD:
                    return f"[{byte:02x}] MOD"
                case StackOp.STACK_AND:
                    return f"[{byte:02x}] AND"
                case StackOp.STACK_OR:
                    return f"[{byte:02x}] MOD"
                case StackOp.STACK_NOT:
                    return f"[{byte:02x}] NOT"
                case StackOp.STACK_SWAP:
                    return f"[{byte:02x}] SWAP"
                case StackOp.STACK_DUP:
                    return f"[{byte:02x}] DUP"
                case StackOp.STACK_POP:
                    return f"[{byte:02x}] POP"
        case ByteCode.OP_JMP:
            if next_byte > -1:
                return f"[{byte:02x}] JUMP {next_byte:02x}"
            else:
                return f"[{byte:02x}] JUMP"
        case ByteCode.OP_JZ:
            if next_byte > -1:
                return f"[{byte:02x}] JZ {next_byte:02x}"
            else:
                return f"[{byte:02x}] JZ"
        case _:
            raise ValueError(f"Don't know how to disassemble byte {hex(byte)}")


def format_header(octets: bytearray) -> str:
    header = ""
    header += "\t:magic\n"
    header += fmt_line(0, octets[0])
    header += fmt_line(1, octets[1])
    header += fmt_line(2, octets[2])
    header += fmt_line(3, octets[3])

    header += "\t:version\n"
    header += fmt_line(4, f"{octets[4]:02x}")
    header += fmt_line(5, f"{octets[5]:02x}")

    header += "\t:memory length (int16)\n"
    header += fmt_line(6, f"{octets[6]:02x}")
    header += fmt_line(7, f"{octets[7]:02x}")

    header += "\t:memory stride\n"
    header += fmt_line(8, f"{octets[8]:02x}")

    header += "\t:data segment offset\n"
    header += fmt_line(9, f"{octets[9]:02x}")

    offset = 10
    header += "\t:entry points\n"
    header += fmt_line(offset, f"{octets[offset]:02x}")
    offset += 1
    header += "\t:entry point offsets\n"
    for addr in octets[offset:]:
        header += fmt_line(offset, f"{addr:02x}")
        offset += 1

    return header


def format_footer(opcodes: bytearray, offset=0) -> str:
    footer = ""
    index = 0
    while index < len(opcodes):
        high = opcodes[index]
        low = opcodes[index + 1]
        value = opcodes[index + 2]
        footer += fmt_line(index + offset, f"{high:02x}{low:02x} = {value:02x}")
        index += 3

    return footer


def dis(opcodes: bytearray, offset=0) -> str:
    i = 0
    result = ""
    while i < len(opcodes):
        byte = opcodes[i]
        op = (byte & 0xf0) >> 4
        arg = byte & 0x0f
        if op & ByteCode.OP_PUSH:
            result += fmt_line(i + offset, bytecode_name(byte, opcodes[i+1]))
            i += 1
        else:
            match op:
                case ByteCode.OP_JMP:
                    if arg < 15:
                        result += fmt_line(i + offset, bytecode_name(byte))
                    else:
                        i += 1
                        result += fmt_line(i + offset, bytecode_name(byte, opcodes[i]))
                case ByteCode.OP_JZ:
                    if arg < 15:
                        result += fmt_line(i + offset, bytecode_name(byte))
                    else:
                        i += 1
                        result += fmt_line(i + offset, bytecode_name(byte, opcodes[i]))
                case _:
                    result += fmt_line(i + offset, bytecode_name(byte))
        i += 1

    return result


class Compiler:
    def __init__(self):
        self.dim: Vector = Vector(0, 0)
        self.mem_addrs: OrderedDict[int, int] = OrderedDict()
        self.jumps = dict[int, Vector]
        self.input_grid: list[list[Token]] = []
        self.entry_points: list[int] = []
        self.jump_labels: list[Label] = []
        self.paths: dict[int, bytearray] = {}
        self.return_addresses: list[int] = []

    def init_mem(self) -> None:
        if not self.input_grid:
            raise ValueError("Must load grid before initializing memory.")
        for y in range(len(self.input_grid)):
            for x in range(len(self.input_grid[y])):
                token = self.input_grid[y][x]
                if token.type == TokenType.T_DIGIT:
                    addr16 = x + y * self.dim.x
                    strval = token.value
                    if strval in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']:
                        self.mem_addrs[addr16] = int(strval)
                    else:
                        raise ValueError(f"Digit token contains non-digit value: 0x{ord(token.value):2x}")

    def load_string(self, source: str) -> None:
        """
        Riffing off your idea of having multiple input methods
        (pipe, file, etc.), this parses a string input into
        a standard tokenized grid.
        """
        self.input_grid = []

        # Parse grid into tokens.
        str_grid = source.splitlines()
        self.dim = Vector(len(str_grid[0]), len(str_grid))
        for y in range(len(str_grid)):
            self.input_grid.append([])
            current_row = self.input_grid[-1]
            if len(str_grid[y]) != self.dim.x:
                raise ValueError(f"Row {y}: Malformed input: Must be rectangular grid.")
            for x in range(len(str_grid[y])):
                ch = str_grid[y][x]
                token = lex_char(ch)
                if token.type == TokenType.T_COMMENT:
                    break
                current_row.append(token)

        self.init_mem()

    def get_label_index(self, label: Label) -> int:
        for i in range(len(self.jump_labels)):
            existing = self.jump_labels[i]
            if label.direction == existing.direction and label.location == existing.location:
                return i
        raise ValueError(f"Label not found: {label}")

    def find_path_heads(self) -> None:
        """
        Find all the symbols that begin code paths. These are the START,
        TURN, and COND tokens.

        This doesn't find computed jump targets like registers.

        "E  >  @"

        Path heads: E, >
        Targets / Paths:
            E: [Jump >]
            >: [Halt]

        Path head stores info about how to parse the path (location, direction, refcount)
        Path contains the compiled bytecodes.
        """
        for y in range(len(self.input_grid)):
            for x in range(len(self.input_grid[0])):
                token = self.input_grid[y][x]
                location = Vector(x, y)
                match token.type:
                    case TokenType.T_START:
                        # Save entry points separately, as these tell us where to set the PC(s).
                        self.jump_labels.append(Label(location=location, direction=dir_vec[token.value], refcount=1))
                        self.entry_points.append(len(self.jump_labels) - 1)
                    case TokenType.T_TURN:
                        self.jump_labels.append(Label(location=location, direction=dir_vec[token.value]))
                    case TokenType.T_COND:
                        # Both paths for conditional
                        # Set refcount for JZ so it doesn't get optimized out.
                        self.jump_labels.append(Label(location=location, direction=dir_vec["<"], refcount=0))
                        self.jump_labels.append(Label(location=location, direction=dir_vec[">"], refcount=1))

                if len(self.jump_labels) >= 255:
                    raise ValueError(f"Too many labels!")

    def comp_jump_target(self, jump_op: ByteCode, label: Label) -> list[int]:
        """
        Side effect: Increase refcount of target label.
        """
        target_index = self.get_label_index(label)
        self.jump_labels[target_index].refcount += 1
        return [
            make_byte(jump_op, 0xf),
            target_index
        ]

    def parse_paths(self) -> None:
        """
        Beginning with each label (path head), parse the path it points to.

        This is a first pass. Generated code may be altered in subsequent steps.
        """
        for label_index in range(len(self.jump_labels)):
            label = self.jump_labels[label_index]
            location = label.location.copy()
            direction = label.direction
            # Begin with the first instruction after the label.
            location.add(direction)
            path = bytearray()
            while True:
                x = location.x
                y = location.y

                token = self.input_grid[y][x]

                # Paths can end with HALT, TURN, START, or COND.

                if token.type == TokenType.T_HALT:
                    path.append(make_byte(ByteCode.OP_HALT))
                    break

                # Jump targets
                elif token.type in [TokenType.T_TURN, TokenType.T_START]:
                    path.extend(self.comp_jump_target(ByteCode.OP_JMP, Label(Vector(x, y), dir_vec[token.value])))
                    break

                elif token.type == TokenType.T_COND:
                    # Zero and non-zero branches.
                    # These labels were created in find_path_heads.
                    jz_target = Label(Vector(x, y), dir_vec[">"])
                    jnz_target = Label(Vector(x, y), dir_vec["<"])
                    path.extend(self.comp_jump_target(ByteCode.OP_JZ, jz_target))
                    path.extend(self.comp_jump_target(ByteCode.OP_JMP, jnz_target))
                    break

                elif token.type == TokenType.T_DIGIT:
                    addr16 = x + y * self.dim.x
                    if addr16 > 32767:
                        raise ValueError(f"Only support 15-bit addressing. Address {addr16} too big!")
                    # High seven bits in opcode byte; low eight bits in next byte.
                    path.append((ByteCode.OP_PUSH << 4) | ((addr16 >> 8) & 0x7f))
                    path.append(addr16 & 0xff)

                elif token.type == TokenType.T_STACK_OP:
                    match token.value:
                        case '-':
                            stack_op = StackOp.STACK_SUB
                        case '+':
                            stack_op = StackOp.STACK_ADD
                        case '*':
                            stack_op = StackOp.STACK_MUL
                        case '/':
                            stack_op = StackOp.STACK_DIV
                        case '%':
                            stack_op = StackOp.STACK_MOD
                        case '&':
                            stack_op = StackOp.STACK_AND
                        case '|':
                            stack_op = StackOp.STACK_OR
                        case '~':
                            stack_op = StackOp.STACK_NOT
                        case '!':
                            stack_op = StackOp.STACK_POP
                        case '$':
                            stack_op = StackOp.STACK_SWAP
                        case ':':
                            stack_op = StackOp.STACK_DUP
                        case _:
                            raise ValueError(f"Unhandled stack op token: '{token.value}'")
                    path.append(make_byte(ByteCode.OP_STACK, stack_op.value))

                elif token.type == TokenType.T_READ_BYTE:
                    path.append(make_byte(ByteCode.OP_LOAD))

                elif token.type == TokenType.T_WRITE_BYTE:
                    path.append(make_byte(ByteCode.OP_STORE))

                elif token.type == TokenType.T_NOP:
                    pass

                else:
                    raise ValueError(f"Unhandled token: {token}")

                # Read next token.
                location.add(direction)
            self.paths[label_index] = path

    def build_header(self) -> bytearray:
        header = bytearray()
        header.extend(magic)
        header.extend(version)

        # mem length - fill in after compilation.
        header.extend([0xff, 0xff])
        # mem stride
        header.extend([0xff])
        # mem offset - fill in after compilation.
        header.extend([0xff])

        # code entry points
        header.extend([len(self.entry_points)])
        for label_index in self.entry_points:
            # Index of label; will be resolved in a subsequent step.
            header.extend([label_index])

        return header

    def maximally_extend_path(self, path_index: int) -> bytearray:
        """
        Coalesce jumps with targets that have no other references.
        """
        path = self.paths[path_index]

        i = 0
        while i < len(path):
            if path[i] & 0x80:
                # Skip over PUSH and subsequent addr byte
                i += 2
                continue
            if path[i] in jump_bytes:
                target = path[i + 1]
                if self.jump_labels[target].refcount < 2:
                    path[i:i + 2] = self.maximally_extend_path(target)
            i += 1

        return path

    def resolve_entry_addresses(self, header: bytearray, entry_points_offset: int, label_offsets: dict) -> None:
        for entry_point in self.entry_points:
            header[entry_points_offset] = label_offsets[entry_point]
            entry_points_offset += 1

    def resolve_jump_addresses(self, code: bytearray, label_offsets: dict) -> None:
        i = 0
        print(label_offsets)
        while i < len(code):
            if code[i] & 0x80:
                # Skip over PUSH and subsequent addr byte
                i += 2
                continue
            if code[i] in jump_bytes:
                # Curious that you can't do this assignment in one line.
                temp_index = code[i + 1]
                new_offset = label_offsets[temp_index]
                code[i + 1] = new_offset
                i += 1
            i += 1

    def build_footer(self) -> bytearray:
        footer = bytearray()
        for addr16 in self.mem_addrs.keys():
            value = self.mem_addrs[addr16]
            footer.extend([(addr16 >> 8) & 0xff, addr16 & 0xff, value])
        return footer

    def compile(self) -> bytes:
        code = bytearray()
        output = bytearray()
        label_offsets: dict[int, int] = {}
        path_stack: list[int] = []
        seen: set[int] = set()

        self.find_path_heads()
        self.parse_paths()

        header = self.build_header()
        code_offset = len(header)
        offset = code_offset

        for label in self.jump_labels:
            # This does a little extra pointless work.
            self.maximally_extend_path(self.get_label_index(label))

        path_stack.extend(self.entry_points)

        while path_stack:
            next_path_index = path_stack.pop()
            seen.add(next_path_index)
            label_offsets[next_path_index] = offset

            path = self.paths[next_path_index]

            # scan path for next paths to follow
            i = 0
            while i < len(path):
                if path[i] & 0x80:
                    # Skip over PUSH and subsequent addr byte
                    i += 2
                    continue
                if path[i] in jump_bytes:
                    # Prevent infinite loops.
                    if path[i + 1] not in seen:
                        path_stack.append(path[i + 1])
                i += 1

            code.extend(path)
            offset += len(path)

        # TODO refactor and hide all this
        header_len = len(header)
        code_len = len(code)
        data_offset = header_len + code_len
        # memory size and offset
        mem_length = self.dim.x * self.dim.y
        header[header_sections['mem_length']] = (mem_length >> 8) & 0xff
        header[header_sections['mem_length'] + 1] = mem_length & 0xff
        header[header_sections['mem_stride']] = self.dim.x
        header[header_sections['data_segment']] = data_offset & 0xff

        self.resolve_entry_addresses(header, 11, label_offsets)

        self.resolve_jump_addresses(code, label_offsets)

        footer = self.build_footer()

        print(format_header(header))
        print("\t:code")
        print(dis(code, code_offset))
        print("\t:data")
        print(format_footer(footer, data_offset))

        output.extend(header)
        output.extend(code)
        output.extend(footer)
        return output


class Process:
    def __init__(self, id: int, pc: int):
        self.id: int = id
        self.stopped: bool = False
        self.pc: int = pc
        self.stack: Stack = Stack()

    def __str__(self) -> str:
        if self.stack.is_empty():
            return f"Process {self.id} halted at {self.pc}"
        else:
            return f"Process {self.id} halted at {self.pc}. Stack top: {self.stack.peek()}"


class VirtualMachine:
    supports_version = bytearray([1, 0])

    def __init__(self):
        self.bytecode: bytearray = bytearray()
        self.size: int = 0
        self.processes: list[Process] = []
        self.memory: bytearray = bytearray()
        self.mem_stride: int = 0
        self.ticks = 0

    def _load_byte(self, proc: Process) -> None:
        """
        Read a "byte" off the map, converting the ascii string of '1's
        and '0's to binary. Push the result on the stack.
        """
        dy = proc.stack.pop()
        dx = proc.stack.pop()
        y = proc.stack.pop()
        x = proc.stack.pop()
        value = 0
        for i in range(8):
            offset = x + y * self.mem_stride
            # TODO bounds checking
            bit = self.memory[offset]
            value |= (bit << (7 - i))
            y += dy
            x += dx
        proc.stack.push(value)

    def _store_byte(self, proc: Process) -> None:
        """
        Store the value on the top of the stack as a "byte" written
        on the map in binary, with ascii '0' and '1' representing
        binary bits.
        """
        dy = proc.stack.pop()
        dx = proc.stack.pop()
        y = proc.stack.pop()
        x = proc.stack.pop()
        value = proc.stack.pop()
        for i in range(8):
            offset = x + y * self.mem_stride
            # TODO bounds checking
            # Store in memory as the parsed value. I.e., '1' -> 1.
            self.memory[offset] = (value >> (7 - i)) & 0x1
            y += dy
            x += dx

    def run(self) -> float:
        """
        Execute the program. Return elapsed time in milliseconds.
        """
        start = perf_counter()
        running_processes = [p for p in self.processes]
        while running_processes:
            for proc in running_processes:
                self.ticks += 1
                bytecode = self.bytecode[proc.pc]
                op = (bytecode >> 4) & 0xf
                arg = bytecode & 0xf

                # Uncomment if you want to see the play-by-play.
                # if bytecode in jump_bytes:
                #     print(f"[proc{proc.id}] {proc.pc:04x} {bytecode_name(bytecode, self.bytecode[proc.pc + 1])}")
                # else:
                #     print(f"[proc{proc.id}] {proc.pc:04x} {bytecode_name(bytecode)}")
                if op & 0x8:
                    # Special-case for PUSH
                    high7 = bytecode & 0x7f
                    low8 = self.bytecode[proc.pc + 1]
                    addr16 = (high7 << 8) | low8
                    proc.stack.push(self.memory[addr16])
                    proc.pc += 1
                else:
                    match op:
                        case ByteCode.OP_HALT:
                            print(f"[proc{proc.id}] {proc.pc:04x} Halt after {self.ticks} ticks.")
                            if not proc.stack.is_empty():
                                print(f"[proc{proc.id}] Stack top: {proc.stack.peek()}")
                            proc.stopped = True
                            running_processes.remove(proc)

                        case ByteCode.OP_LOAD:
                            self._load_byte(proc)

                        case ByteCode.OP_STORE:
                            self._store_byte(proc)

                        case ByteCode.OP_STACK:
                            proc.stack.op(arg)

                        case ByteCode.OP_JZ:
                            target: int
                            if arg != 0xf:
                                target = arg
                            else:
                                proc.pc += 1
                                target = self.bytecode[proc.pc]

                            if proc.stack.pop() == 0:
                                proc.pc = target - 1

                        case ByteCode.OP_JMP:
                            target: int
                            if arg != 0xf:
                                target = arg
                            else:
                                proc.pc += 1
                                target = self.bytecode[proc.pc]

                            proc.pc = target - 1

                        case _:
                            raise ValueError(
                                f"[proc{proc.id}] Unhandled bytecode: 0x{op << 4:02x} {arg} at addr {proc.pc:02x}")

                proc.pc += 1
        return (perf_counter() - start) * 1000

    def _init_mem(self, mem_length, data_offset):
        self.memory = bytearray(mem_length)
        i = data_offset
        while i < len(self.bytecode):
            addr16 = ((self.bytecode[i] << 8) | self.bytecode[i + 1])
            self.memory[addr16] = self.bytecode[i + 2]
            i += 3

    def load(self, bytecode: bytearray) -> None:
        self.bytecode = bytecode
        if self.bytecode[header_sections['magic']:header_sections['magic'] + 4] != magic:
            raise ValueError("Wrong kind of file.")

        if self.bytecode[header_sections['version']:header_sections['version'] + 2] != self.supports_version:
            raise ValueError("Incompatible syntax version.")

        mem_length = ((self.bytecode[header_sections['mem_length']] & 0xff) << 8)
        mem_length |= ((self.bytecode[header_sections['mem_length'] + 1] & 0xff) << 8)
        self.mem_stride = self.bytecode[header_sections['mem_stride']]
        data_offset = self.bytecode[header_sections['data_segment']]
        self._init_mem(mem_length, data_offset)

        offset = header_sections['entry_points']
        entry_point_count = self.bytecode[offset]
        offset += 1
        for i in range(entry_point_count):
            self.processes.append(Process(id=i, pc=self.bytecode[offset]))
            offset += 1

        print(f"Loaded {len(bytecode)} bytes: {' '.join([str(b) for b in self.bytecode])}")
        print(f"VM Starting. Processes: {len(self.processes)}.")


def test_compiler():
    for room_name in ['TEST_ROOM_1.txt',
                      'TEST_ROOM_2.txt',
                      'TEST_ROOM_3.txt',
                      'TEST_ROOM_4.txt']:
        with open(room_name) as f:
            outfile_name = path.splitext(room_name)[0].lower() + '.oof'
            print(f"== Compiling {room_name} -> {outfile_name}")
            c = Compiler()
            c.load_string(f.read())
            bytecode = c.compile()

            open(outfile_name, 'wb').write(bytecode)

            print(f"== Executing bytecode for {room_name}")
            v = VirtualMachine()
            v.load(bytecode)
            elapsed = v.run()

            print(f"== Done with {room_name} in {elapsed:0.4f}ms\n\n")


if __name__ == '__main__':
    test_compiler()
