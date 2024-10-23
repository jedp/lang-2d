# 2D Language Games

A toy 2D stack-based language (like Befunge) that can perform concurrent work
on shared memory.

Includes:

- [Python interpreter](./robots-interpreter.py)
- [Bytecode compiler and Python VM](./robots-interpreter.py)
- [C VM](./vm.c)

## Background: Interview Question

This started as an innocent interview question. I won't go into the prompt and
detailed steps, but in its essentials, it guides you in creating a make-believe
robot that rolls around on a floor, interpreting and reacting to characters
drawn on the floor as it drives over them. There are arrow-like characters to
make the robot rotate, digits and arithmetic symbols to cause the robot to
perform stack-based arithmetic operations, etc. In the end, you've made
something like an adorable Befunge interpreter.

As an interview question, I like it because it has multiple steps that flow
into each other, getting progressively more complicated. There are no "aha" or
gotcha moments and no special algorithms you have to know. There are many ways
to think about the solution, with more or less functional or object-oriented
patterns, and with architectures ranging from game engines to parsers and
interpreters. In the process, you get to see a lot of the candidate's approach
to a problem, awareness of edge cases, approaches to design and architecture,
modularity and structure, defensive fail-fast programming, etc.

Here's a quick summary of some of the key instructions for the robot:

- `@` means halt

- `>`, `^`, `<`, `v` mean face left, up, etc.

- `0`, `1`, ... `9` mean push a value on the stack

- `-` means do subtraction on the stack

- `_` is a conditional: Pop stack; if popped 0, face right, else face left.

- After interpreting a character, move forward one space (except after halt, of course)


In the  map below, if you start in the upper-left and follow the arrows, you
calculate `8 5 - 1 -` (2), before landing on `@` and halting.

```
> 8     v
  >  @  5
  ^ -1 -<
```

The next one uses the conditional instruction to decide when to break out of loops.
(The program computes 5 factorial.)

```
05 > : 1- : v   v *  _ ! @
   ^        _ ! > $: ^    
```

For an example Python interpreter that goes into more detail, see:

- [robots-interpreter.py](robots-interpreter.py)


## Nerd Sniped: Concurrency

When discussing this question with my friend Chris Hayes, he proposed an
implementation that left room for multiple robots to move about the same room
concurrently.

What a fun idea! And thanks, Chris, for totally nerd-sniping me into writing an
interpreter that handles concurrency.

For the concurrent interpreter, let's first add a few more rules and
instructions.

- The only legal start spaces are `N`, `S`, `E`, and `W`. They act just like
  the arrow symbols, but have the special meaning "a robot starts here, facing
  this way."

- Shared memory. The robot can read or write a "byte" on the floor. Each bit in
  the byte is converted to the character representation of `1` or `0`.
  Delightfully thread-unsafe.

  The functions for these take 4 or 5 stack arguments:

  - `[x] [y] [dx] [dy] ?`: Read the 8 characters on the floor starting at `(x,
    y)`, facing in the direction `(dx, dy)`, and interpret them as a binary
    byte. Push the value of the byte on the stack.

  - `[val] [x] [y] [dx] [dy] #`: Convert `val` to a "byte" and write its bits
    on the floor starting at `(x, y)`, facing in the `(dx, dy)` direction.

  For example, if the eight characters `11001011` were written beginning at
  `(1, 2)` and ending at `(8, 2)`, you would read them with `1 2 1 0 ?`. This
  would push the value 203 on the stack.

  Note that the stack contains ints, not bytes, so you have to mask and shift
  the byte you want using stack arithmetic.

  The `[dx] [dy]` vector leaves open the possibility that you could read/write
  at odd angles and extents, potentially bouncing off the wall upon reaching
  the edge of the room. My interpreter doesn't handle this in a well-defined
  way. It's one more thing you could take in a creative direction.
 
- A comment character `;` that means "ignore everything from here to the right
  edge". These programs are still not easy for me to read quickly, so I wanted
  to be able to leave comments. The downside is that the comment text bloats
  the input size. This will have consequences in the future, but for now let's
  just live with it.

With this, and ignoring the idea of collisions (blocking? resource contention?)
we can evaluate the following room with two concurrently executing robots:

- [Test Room 4](TEST_ROOM_4.txt)

```
00000000                      ; [REG0] Low byte       ;
00000000                      ; [REG1] High byte      ;
       S<                     ; R1: Poll for IRQ ...  ;
00000000                      ; [IRQ] Bytes available ;
      v_^                                             ;
      >    0 0310#        v   ; ... clear interrupt   ;
 @ + * **488 ?0110 ?0100  <   ; ... Read bytes, exit. ;
                                                      ;
E06 > : 1- : v   v *  _ ! v   ; R2: Calculate 6!      ;
    ^        _ ! > $: ^   :                           ;
                                                      ;
v # 0110 / * * 4 8 8 :    <   ; ... store high byte   ;
> : 8 8 4 * * % 0010 #    v   ; ... store low byte    ;
@ 0           # 0130 1    <   ; ... set IRQ, exit 0.  ;
```

One of the robots starts on the `S`. Call it Robot 0. It spins around and
around, reading the character at `(7, 3)` over and over. If this character ever
turns into a `1`, it quickly sets it back to `0` and then reads the two "bytes"
in the upper left. With some bit-shifting, it combines these into a single
16-bit value, pushes the result, and exits.

Meanwhile, the other robot, Robot 1, has been calculating the value of 6
factorial. Having done so, it writes the 16-bit value into the high and low
"bytes" in the upper left, sets the aforementioned `0` bit to a `1` to signal
that it has completed its computation, and exits.

So Robot 1 sets a flag when it's done, and Robot 0 reads and clears the flag,
gets the shared memory value, and pushes it on its own stack.

Here's how that room plays out on my machine. The interpreter prints the room
every time a robot is done, so you can see how the "bytes" in the upper left
evolve:

```
== Entering room: TEST_ROOM_4.txt
Inserted robot 0 at (7, 2), direction (0, 1)
Inserted robot 1 at (0, 8), direction (1, 0)
Begin execution.

Robot 1 exited. Grid now:

11010000                      
00000010                      
       S<                     
00000001                      
      v_^                                             
      >    0 0310#        v   
 @ + * **488 ?0110 ?0100  <   
                                                      
E06 > : 1- : v   v *  _ ! v   
    ^        _ ! > $: ^   :                           
                                                      
v # 0110 / * * 4 8 8 :    <   
> : 8 8 4 * * % 0010 #    v   
@ 0           # 0130 1    <   

Received 0 from robot 1.

Robot 0 exited. Grid now:

11010000                      
00000010                      
       S<                     
00000000                      
      v_^                                             
      >    0 0310#        v   
 @ + * **488 ?0110 ?0100  <   
                                                      
E06 > : 1- : v   v *  _ ! v   
    ^        _ ! > $: ^   :                           
                                                      
v # 0110 / * * 4 8 8 :    <   
> : 8 8 4 * * % 0010 #    v   
@ 0           # 0130 1    <   

Received 720 from robot 0.

== Done with TEST_ROOM_4.txt in 0.4828ms
```

## More Nerd Sniped: Bytecode Compiler

It's fun to see the interpreter process the room and coordinate the robots, but
could we condense these programs into bytecode and write a virtual machine to
run them on any platform?

One immediate benefit of the bytecode would be to optimize out no-op spaces and
useless turns that are the bulk of the program and largely what the interpreter
spends time processing. For example, consider the following basic room:

```
E       v
  >  @   
  ^     <
```

This should be compiled down to pseudo bytecode like the following:

```
0  HALT
```

The program does nothing but halt.

Likewise, programs that perform calculations should have their paths maximally
shortened. For example, consider the room in which the subtraction operator is
introduced:

```
E8      v
  >  @  5
  ^ -1 -<
```

This should compile to something like the following:

```
0  PUSH 8
1  PUSH 5
2  SUB
3  PUSH 1
4  SUB
5  HALT
```

Thinking of turns like jump targets, and the space before a turn as a jump to
that target, we should be able to reduce consecutive jumps that do nothing but
move the program counter forward. (If a turn can be reached from multiple
paths, as for example after a conditional in the room that calculates
factorials, we can't simply reduce it in the same way. This will be relevant
later on.)


### Bytecode

The bytecode instruction set ends up being very tidy and compact, with just
six instructions.

The opcode can typically be stored in the high four bits of the byte, with an
argument in the lower four bits.

- `HALT`

  Halt execution, but don't delete any state.

- `BYTE`

  Read or write a "byte" off the floor, taking its value from the stack or pushing
  it there. Reading takes four stack arguments to compute location and direction
  of writing. Writing takes five stack arguments: The value, and the four
  location/direction parameters. Read vs write is specified by the argument
  half of the byte.

- `STACK`

  Perform an operation on the stack. The operation is encoded in the lower four
  bits of the opcode.

  `POP`, `SWAP`, and `DUP` manipulate the stack directly.

  Other instructions perform computations on the top one or two stack elements:
  `NEG`, `SUB`, `MUL`, `MOD`, `AND`, `OR`, etc.

- `JMP`

  Jump to an offset in the bytecode. If the offset is less than 15, it is
  stored in the lower four bits. If greater, the lower four bits are set to 15
  and the next byte contains the offset.

  (This could be improved: If the offset is less than 15, jump relative to
  current program counter; otherwise jump to the code address of the next
  byte.)

- `JZ`
 
  Same offset encoding as `JMP`. Pops a value from the stack and jumps to one
  target on 0 and another on non-zero.

- `PUSH`

  Based on experience, this is the most-commonly used instruction, so it makes
  sense to try to optimize a bit on space here. This is the only opcode with
  the high bit set: The address in memory of the value to push is the remaining
  7 bits from the PUSH opcode (high byte) and the following opcode (low byte).

  For example the opcode sequence `0xe1 0x64` means "PUSH value at memory
  address `0x0164`".

  (When I first put this together, I tried saving a byte of opcodes by using
  all pointer references to the stack. Saving a byte is nice, but requiring
  pointer indirection for all memory lookups is a pretty high cost. For this
  reason, I've added an extra address byte for all PUSHes.)


### Further Room for Improvement

Looking back at the subtraction map (the one that computes `8 5 - 1 -`) You
might push further and say, Well, since it's clear at compile time that this
expression never changes, it should ideally compile down to:

```
0  PUSH 2
1  HALT
```

I agree. I'm not sure how to go about this, though. There might be a way to
optimize constant expressions out, but more "realistic" programs have
conditionals and memory value mutations. And since all expressions can be
computed at runtime, it's challenging to figure out which expressions will be
constant and which will be mutable. Too big a challenge for me right now.

Another problem that arises when we compile down to bytecode is that we lose
the geometric information of the original grid. How do we know where `(1,1)` is
in the compiled code?

The quick and dirty solution for this is to create a memory array the same size
as the program and record each value at its location offset in this array. We
additionally store a pointer to that offset. Why? Because the robots can stomp
all over each other's memory and symbols, and it's necessary to re-read a value
every time we land on one.

### Bytecode Example

Here's a compiler and virtual machine:

- [robots-bytecode.py](robots-bytecode.py)

Compile the room that computes 5 factorial:

```
E05 > : 1- : v   v *  _ ! @
    ^        _ ! > $: ^    
```

Get this bytecode:

```
	:magic
0000	74
0001	69
0002	68
0003	63
	:version
0004	01
0005	00
	:memory length (int16)
0006	00
0007	36
	:memory stride
0008	1b
	:data segment offset
0009	27
	:entry points
000a	01
	:entry point offsets
000b	0c

	:code
000c	[80] PUSH 00 01
000e	[80] PUSH 00 02
0011	[3f] JUMP 12
0012	[2a] DUP
0013	[80] PUSH 00 08
0015	[20] SUB
0016	[2a] DUP
0018	[4f] JZ 1b
001a	[3f] JUMP 12
001b	[28] POP
001d	[3f] JUMP 1e
001e	[29] SWAP
001f	[2a] DUP
0021	[4f] JZ 25
0022	[22] MUL
0024	[3f] JUMP 1e
0025	[28] POP
0026	[00] HALT

	:data
0027	0001 = 00
002a	0002 = 05
002d	0008 = 01
```

(Hmm ... It looks like that `JUMP 1e` at address `1d` can be optimized out. I
guess there's room for improvement in the path-reduction logic.)

You can read the generated bytecode for each room and compare with the
interpreter in the attached `output` files.

The header includes some bytecode-y information, like a magic number and
version number.

Then it reports the following crucial values:

- Memory length: How many bytes long the input was, which is the number of
  bytes we have to allocate as our memory.

- Memory stride: This is the length of the x direction in the input. In the
  array memory model, your offset when going "up" or "down" is `x + y *
  stride`.

- Data segment offset: After the program ends, where initial state values are
  recorded.

- Entry points: The number of entry points and their offsets in the bytecode.
 
Looking at the data segment here, it contains three-byte group, each holding a
16-bit address value and a byte value:

```
00 01 08
00 11 05
00 17 01
```

The 16-bit address is the location of a value in the memory array; the next
byte is its initial value. This shows where the initial `8`, `5`, and `1` of
the text input are located.

When the virtual machine reads the bytecode, it initializes the room memory
with the values specified at each 15-bit address. For example, memory for the
segment above will be initialized as:

```
0x00  00 08 00 00 00 00 00 00
0x08  00 00 00 00 00 00 00 00
0x10  00 05 00 00 00 00 00 01
...
```

Values can change, but the memory address associated with a value location in
the input cannot change.

The python [Virtual Machine](./robots-bytecode.py) output for
[Room 4](./TEST_ROOM_4.txt):

```
== Executing bytecode for TEST_ROOM_4.txt
Loaded 327 bytes: 74 69 68 63 1 0 3 2 55 138 2 92 13 129 185 129 186 63 19 42 129 192 32 42 79 28 63 19 40 63 31 41 42 79 38 34 63 31 40 42 42 130 112 130 110 130 108 34 34 35 130 100 130 99 130 98 130 97 17 42 130 152 130 154 130 156 34 34 36 130 164 130 165 130 166 130 167 17 130 224 130 222 130 221 130 220 130 219 17 130 205 0 128 172 79 136 129 30 129 32 129 33 129 34 129 35 17 129 97 129 96 129 95 129 94 16 129 91 129 90 129 89 129 88 16 129 85 129 84 129 83 34 34 34 33 0 63 92 0 0 0 0 1 0 0 2 0 0 3 0 0 4 0 0 5 0 0 6 0 0 7 0 0 55 0 0 56 0 0 57 0 0 58 0 0 59 0 0 60 0 0 61 0 0 62 0 0 165 0 0 166 0 0 167 0 0 168 0 0 169 0 0 170 0 0 171 0 0 172 0 1 30 0 1 32 0 1 33 3 1 34 1 1 35 0 1 83 4 1 84 8 1 85 8 1 88 0 1 89 1 1 90 1 1 91 0 1 94 0 1 95 1 1 96 0 1 97 0 1 185 0 1 186 6 1 192 1 2 97 0 2 98 1 2 99 1 2 100 0 2 108 4 2 110 8 2 112 8 2 152 8 2 154 8 2 156 4 2 164 0 2 165 0 2 166 1 2 167 0 2 205 0 2 219 0 2 220 1 2 221 3 2 222 0 2 224 1
VM Starting. Processes: 2.
[proc1] 005b Halt after 204 ticks.
[proc1] Stack top: 0
[proc0] 0087 Halt after 230 ticks.
[proc0] Stack top: 720
== Done with TEST_ROOM_4.txt in 0.2011ms
```

The value we want (720) is on top of the stack of process 0.

That's 0.2011ms on my old-ish 2.4GHz Intel Mac.

### Another Bytecode Example

I also threw together a VM in C, [vm.c](./vm.c). (Why write a bytecode compiler
without writing a VM in a different language?) I didn't try to optimize
anything, but it still runs over an order of magnitude faster than the Python
version.

Simply compiles with gcc. No special flags or std lib version.

Be sure to run the Python [robots-bytecode.py](./robots-bytecode.py) first, as
that contains the compiler that compiles and writes all the bytecode files
(they end in `.oof`).

Same example as in the previous section. Here's the full bytecode listing. More
than half of it is initial memory state.

```
>  hexdump -C test_room_4.oof
00000000  4a 45 44 3f 01 00 03 02  37 8a 02 5c 0d 81 b9 81  |JED?....7..\....|
00000010  ba 3f 13 2a 81 c0 20 2a  4f 1c 3f 13 28 3f 1f 29  |.?.*.. *O.?.(?.)|
00000020  2a 4f 26 22 3f 1f 28 2a  2a 82 70 82 6e 82 6c 22  |*O&"?.(**.p.n.l"|
00000030  22 23 82 64 82 63 82 62  82 61 11 2a 82 98 82 9a  |"#.d.c.b.a.*....|
00000040  82 9c 22 22 24 82 a4 82  a5 82 a6 82 a7 11 82 e0  |..""$...........|
00000050  82 de 82 dd 82 dc 82 db  11 82 cd 00 80 ac 4f 88  |..............O.|
00000060  81 1e 81 20 81 21 81 22  81 23 11 81 61 81 60 81  |... .!.".#..a.`.|
00000070  5f 81 5e 10 81 5b 81 5a  81 59 81 58 10 81 55 81  |_.^..[.Z.Y.X..U.|
00000080  54 81 53 22 22 22 21 00  3f 5c 00 00 00 00 01 00  |T.S"""!.?\......|
00000090  00 02 00 00 03 00 00 04  00 00 05 00 00 06 00 00  |................|
000000a0  07 00 00 37 00 00 38 00  00 39 00 00 3a 00 00 3b  |...7..8..9..:..;|
000000b0  00 00 3c 00 00 3d 00 00  3e 00 00 a5 00 00 a6 00  |..<..=..>.......|
000000c0  00 a7 00 00 a8 00 00 a9  00 00 aa 00 00 ab 00 00  |................|
000000d0  ac 00 01 1e 00 01 20 00  01 21 03 01 22 01 01 23  |...... ..!.."..#|
000000e0  00 01 53 04 01 54 08 01  55 08 01 58 00 01 59 01  |..S..T..U..X..Y.|
000000f0  01 5a 01 01 5b 00 01 5e  00 01 5f 01 01 60 00 01  |.Z..[..^.._..`..|
00000100  61 00 01 b9 00 01 ba 06  01 c0 01 02 61 00 02 62  |a...........a..b|
00000110  01 02 63 01 02 64 00 02  6c 04 02 6e 08 02 70 08  |..c..d..l..n..p.|
00000120  02 98 08 02 9a 08 02 9c  04 02 a4 00 02 a5 00 02  |................|
00000130  a6 01 02 a7 00 02 cd 00  02 db 00 02 dc 01 02 dd  |................|
00000140  03 02 de 00 02 e0 01                              |.......|
00000147

> gcc vm.c -o vm

> ./vm test_room_4.oof
Exec bytecode: 327 bytes.
Robot 1 halted at tick 204. Last value: 0
Robot 0 halted at tick 230. Last value: 720
Elapsed CPU time: 12 µs.
```

## More to do?

This was fun. And really captivated my mind. Thanks again, Chris. I guess.

There are probably plenty of other ways to make other optimizations and
elaborations, in addition to the ones suggested above. It would be interesting
to explore what happens when robots don't only modify each other's data but
mutate each other's source code directly. This would pose some very interesting
challenges to a bytecode compiler! I'm going to take a break from this for now,
though. Perhaps in the future we can play more with it.

- Jed
 

