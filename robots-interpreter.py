from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from time import perf_counter
from typing import Callable


class TokenType(Enum):
    T_NOP = 0
    T_HALT = 1
    T_TURN = 2
    T_START = 3
    T_STACK_FUNC = 4
    T_COND = 5
    T_READ_BYTE = 6
    T_WRITE_BYTE = 7
    T_DIGIT = 8
    T_COMMENT = 9


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
    elif ch in ['<', '^', '>', 'v']:
        token_type = TokenType.T_TURN
    elif ch in ['W', 'N', 'E', 'S']:
        token_type = TokenType.T_START
    elif ch in ['!', ':', '$', '-', '+', '*', '/', '%']:
        token_type = TokenType.T_STACK_FUNC
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

    def __str__(self):
        return f"({self.x}, {self.y})"

    def add(self, other: 'Vector') -> None:
        self.x += other.x
        self.y += other.y


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


@dataclass
class Result:
    id: int
    location: Vector
    has_value: bool
    value: int


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

    def math(self, op: str) -> None:
        a = self.stack.pop()
        b = self.stack.pop()
        match op:
            case '-':
                self.push(b - a)
            case '+':
                self.push(b + a)
            case '*':
                self.push(b * a)
            case '/':
                self.push(b // a)
            case '%':
                self.push(b % a)
            case _:
                raise ValueError(f"Unhandled stack op: '{op}'")

    def op(self, op: str) -> None:
        match op:
            case '!':  # pop
                self.pop()
            case ':':  # dup
                self.push(self.stack[-1])
            case '$':  # swap
                self.stack[-2:] = self.stack[-1], self.stack[-2]
            case _:
                self.math(op)


@dataclass
class Frame:
    position: Vector
    direction: Vector


class Robot:
    def __init__(self,
                 id: int,
                 position: Vector,
                 direction: Vector,
                 get_token: Callable[[Vector], Token],
                 put_token: Callable[[Vector, Token], None],
                 on_result: Callable[[Result], None]) -> None:
        self.id = id
        self.running = True
        self.position = position
        self.direction = direction
        self.stack = Stack()
        self.frames: list[Frame] = []
        self.get_token = get_token
        self.put_token = put_token
        self.on_result = on_result
        self.writing_bit: int = -1
        self.reading_bit: int = -1

    def get_position(self):
        return self.position

    def halt(self) -> None:
        if self.stack.is_empty():
            self.on_result(Result(self.id, self.position, False, 0))
        else:
            self.on_result(Result(self.id, self.position, True, self.stack.peek()))
        self.running = False

    def jump(self):
        self.frames.append(Frame(self.position, self.direction))
        dy = self.stack.pop()
        dx = self.stack.pop()
        y = self.stack.pop()
        x = self.stack.pop()
        self.position = Vector(x, y)
        self.direction = Vector(dx, dy)

    def unjump(self):
        prev_frame = self.frames.pop()
        self.direction = prev_frame.direction
        self.position = prev_frame.position
        self.position.add(self.direction)

    def read_next_bit(self, token):
        bit = int(token.value) << self.reading_bit
        self.stack.push(self.stack.pop() | bit)
        self.reading_bit -= 1

        if self.reading_bit == -1:
            self.unjump()

    def write_next_bit(self):
        bit = (self.stack.peek() >> self.writing_bit) & 1
        self.put_token(self.position, Token(TokenType.T_DIGIT, str(bit)))
        self.writing_bit -= 1

        if self.writing_bit == -1:
            self.stack.pop()
            self.unjump()

    def next(self) -> None:
        token = self.get_token(self.position)

        if self.writing_bit > -1:
            self.write_next_bit()

        elif self.reading_bit > -1:
            self.read_next_bit(token)

        else:
            match token.type:
                case TokenType.T_NOP:
                    pass
                case TokenType.T_HALT:
                    self.halt()
                case TokenType.T_TURN:
                    self.direction = dir_vec[token.value]
                case TokenType.T_START:
                    self.direction = dir_vec[token.value]
                case TokenType.T_STACK_FUNC:
                    self.stack.op(token.value)
                case TokenType.T_COND:
                    if self.stack.pop() == 0:
                        self.direction = dir_vec['>']
                    else:
                        self.direction = dir_vec['<']
                case TokenType.T_READ_BYTE:
                    self.reading_bit = 7
                    self.jump()
                    self.stack.push(0)  # Push a byte to start adding bits to.
                    return  # jump updates location and direction.
                case TokenType.T_WRITE_BYTE:
                    self.writing_bit = 7
                    self.jump()
                    return  # jump updates location and direction.
                case TokenType.T_DIGIT:
                    self.stack.push(int(token.value))
                case _:
                    raise ValueError(f"Cannot handle token {token}")

        self.position.add(self.direction)


class Room:
    def __init__(self):
        self.grid: list[list[Token]] = []
        self.start_positions: list[tuple[Vector, Vector]] = []
        self.robots: list[Robot] = []

    def init_from_string(self, source: str) -> None:
        """
        Riffing off your idea of having multiple input methods
        (pipe, file, etc.), this parses a string input into
        a standard tokenized grid.
        """
        self.robots = []
        self.grid = []

        # Parse grid into tokens.
        str_grid = source.splitlines()
        for y in range(len(str_grid)):
            self.grid.append([])
            current_row = self.grid[-1]
            for x in range(len(str_grid[y])):
                ch = str_grid[y][x]
                token = lex_char(ch)
                if token.type == TokenType.T_COMMENT:
                    break
                if token.type == TokenType.T_START:
                    self.start_positions.append((Vector(x, y), dir_vec[ch]))
                current_row.append(lex_char(ch))

        self._place_robots()

    def _receive_result(self, result: Result) -> None:
        for robot in self.robots:
            if robot.id == result.id:
                self.robots.remove(robot)
                print(f"Robot {robot.id} exited. Grid now:")
                self._print_grid()
                print(f"Received {result.value} from robot {robot.id}.")

    def _place_robots(self) -> None:
        for position, direction in self.start_positions:
            robot = Robot(id=len(self.robots),
                          position=position,
                          direction=direction,
                          get_token=self._get_token,
                          put_token=self._put_token,
                          on_result=self._receive_result)
            self.robots.append(robot)
            print(f"Inserted robot {robot.id} at {robot.position}, direction {robot.direction}")

    def _get_token(self, pos: Vector) -> Token:
        return self.grid[pos.y][pos.x]

    def _put_token(self, pos: Vector, token: Token) -> None:
        match token.type:
            case TokenType.T_DIGIT:
                self.grid[pos.y][pos.x] = token
            case _:
                raise ValueError(f"Cannot put token of type {token.type}")

    def _print_grid(self):
        for y in range(len(self.grid)):
            print(''.join([x.value for x in self.grid[y]]))

    def start(self) -> float:
        """
        Execute program. Return elapsed time in milliseconds.
        """
        print("Begin execution.")
        start = perf_counter()
        while self.robots:
            for robot in self.robots:
                robot.next()
        return (perf_counter() - start) * 1000


if __name__ == '__main__':
    for room_name in ['TEST_ROOM_1.txt',
                      'TEST_ROOM_2.txt',
                      'TEST_ROOM_3.txt',
                      'TEST_ROOM_4.txt']:
        with open(room_name) as f:
            print(f"== Entering room: {room_name}")
            room = Room()
            room.init_from_string(f.read())
            elapsed = room.start()
            print(f"== Done with {room_name} in {elapsed:0.4f}ms\n\n")
