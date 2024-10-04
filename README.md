# 2D Language Games

## Background: Interview Question

This started as an innocent interview question. I won't go into the prompt and
detailed steps, but in its essentials, the interview question I've been using
for years guides
you in creating a make-believe robot that rolls around on a floor, interpreting
and reacting to 
characters drawn on the floor as it drives over them. There are arrow characters
to make the robot rotate, digits and arithmetic symbols to cause the robot to
perform stack-based arithmetic operations, etc. In the end, you've made something
like an adorable Befunge interpreter.

I like the question because it has multiple steps that flow into each other,
getting progressively more complicated.
There are no "aha" or gotcha moments and no special algorithms you have to know.
There are many ways to think about the solution, either with functional
or object-oriented patterns, and with architectures ranging 
from game development to parsers and interpreters. In the process, you get to see
a lot of the candidate's approach to a problem, awareness of edge cases, approaches
to design and architecture, modularity and structure, defensive programming, etc.

As a quick example, 

- `@` means halt
- `>`, `^`, `<`, `v` mean rotate
- `0`, `1`, ... `9` mean push a value on the stack
- `-` means do subtraction on the stack
- After interpreting a character, move forward one space (except after halt, of course)

So if you start in the upper-left of the following map,
you follow the arrows and calculate
`8 5 - 1 -` (2), before landing on `@` and halting.

> ```
> > 8     v
>   >  @  5
>   ^ -1 -<
> ```

For inputs, see:

- [Test Room 1](TEST_ROOM_1.txt)
- [Test Room 2](TEST_ROOM_2.txt)
- [Test Room 3](TEST_ROOM_3.txt)

For an interpreter, see:

- [robots-interpreter.py](robots-interpreter.py)

## Nerd Sniped: Concurrency

When discussing this question with my friend Chris Hayes,
he proposed an implementation that left room for multiple 
robots to move about the same room concurrently.

What a fun idea! And thanks, Chris, for totally nerd-sniping
me into writing an interpreter that handles concurrency.

For the concurrent interpreter, let's first add a few more
rules and instructions.

- The only legal start spaces are `N`, `S`, `E`, and `W`. 
  They act just like the arrow symbols, but have the special
  meaning "a robot starts here, facing this way."

- Shared memory. The robot can read or write a "byte" on the floor.
  Each bit in the byte is converted to the character
  representation of `1` or `0`. Delightfully thread-unsafe.

  The functions for these take 4 or 5 stack arguments:

  - `[x] [y] [dx] [dy] ?`: Read the 8 characters on the floor
    starting at `(x, y)`, facing in the direction `(dx, dy)`,
    and interpret them as a binary byte. Push the value of the byte
    on the stack.
  - `[val] [x] [y] [dx] [dy] #`: Convert `val` to a "byte"
    and write its bits on the floor starting at `(x, y)`,
    facing in the `(dx, dy)` direction.

  For example, if the eight characters `11001011` were written
  beginning at `(1, 2)` and ending at `(8, 2)`, you would read
  them with `1 2 1 0 ?`. This would push the value 203 on
  the stack.
 
- A comment character `;` that means "ignore everything from here
  to the right edge". (They have the downsize of bloating the input
  size, which will have consequences in the future, but for now
  let's just live with it.)

With this, we can evaluate the following room with two
concurrently executing robots:

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

The source is in:

- [Test Room 4](TEST_ROOM_4.txt)

One of the robots starts on the `S`. Call it Robot 0.
It spins around and
around, reading the character at `(7, 3)` over and over.
If this character ever turns into a `1`, it quickly sets
it back to `0` and then reads the two "bytes" in the upper
left. With some bit-shifting, it combines these into a 
single 16-bit value, pushes the result, and exits.

Meanwhile, the other robot, Robot 1, has been calculating
the value
of 6 factorial. Having done so, it writes the 16-bit value
into the high and low "bytes" in the upper left, sets the
aforementioned `0` bit to a `1` to signal that it has
completed its computation, and exits.

So Robot 1 sets a flag when it's done, and Robot 0
reads and clears the flag, gets the shared memory value,
and pushes it on its own stack.

Here's how that room plays out on my machine. The interpreter
prints the room every time a robot is done, so you can see
how the "bytes" evolve:

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

It's fun to see the interpreter process the room and coordinate
the robots, but could we condense these programs into bytecode
and write a virtual machine to run them on any platform?

One immediate benefit of the bytecode would be to optimize out
no-op spaces and useless turns. For example, consider the following
basic room:

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

Likewise, programs that perform calculations should have their paths
maximally shortened. For example, consider the room in which the 
subtraction operator is introduced:

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

So this is all looking like bytecode is going to make things so neat
and tidy and portable. Fun!


### Bytecode

The bytecode instruction set ends up being very tidy and compact, with 
just seven instructions.

The opcode can typically be stored in the high four bits of the byte,
with an argument in the lower four bits.

- `HALT`

  Halt execution, but don't delete any state.

- `LOAD`

  Read a "byte" off the floor and push its value on the stack. Takes
  Four stack arguments to compute location and direction of writing.

- `STORE`
 
  Pop a value from the stack and write it as a "byte" on the floor.
  Takes five stack arguments: The value, and the location/direction
  parameters.

  I guess `LOAD` and `STORE` could be folded into a single opcode as well.

- `STACK`

  Perform an operation on the stack. The operation is encoded in the 
  lower four bits of the opcode.

  `POP`, `SWAP`, and `DUP` manipulate the stack directly.

  Other instructions perform computations on the top one or two 
  stack elements: `NEG`, `SUB`, `MUL`, `MOD`, `AND`, `OR`, etc.

- `JMP`

  Jump to an offset in the bytecode. If the offset is less than 15,
  it is stored in the lower four bits. If greater, the lower four bits
  are set to 15 and the next byte contains the offset.

- `JZ`
 
  Same offset encoding as `JMP`. Pops a value from the stack and jumps
  to one target on 0 and another on non-zero.

- `PUSH`

  This is the only opcode with the high bit set. The pointer index of
  the value to load from memory and push on to the stack is encoded in
  the lower 7 bits.

  for example the opcode `0xe4` has high bit set; lower 7 bits are
  `0xe4 & 0x7f` which is `0x64` (decimal 100). The opcode `0xe4` therefore 
  means "Get the memory address recorded at offset 100 in the data segment;
  load the value at that address and push it onto the stack." 


### Further Room for Improvement

Looking back at the subtraction map (the one that computes `8 5 - 1 -`)
You might push further and say,
Well, since it's clear at compile time that this expression
never changes, it should ideally compile down to:

```
0  PUSH 2
1  HALT
```

I agree. But I haven't made it that far yet. There might be a way to
optimize constant expressions out (I'm not sure, tbh, because I haven't
tried yet), but more
"realistic" programs have conditionals and memory value mutations. And since
all expressions can be computed at runtime, it's going to be challenging
to know what expression will be constant and what will be mutable.

Another problem that arises when we compile down to bytecode is that we
lose the geometric information of the original grid. How do we know where
`(1,1)` is in the compiled code?

The quick and dirty solution for this is to create a memory array the same
size as the program and record each value at its location offset in this
array. We additionally store a pointer to that offset. Why? Because the
robots can stomp all over each other's memory and symbols, and it's
necessary to re-read a value every time we land on one.

### Bytecode Example

At this point, it'll be easier just to show the compiled bytecode.

Here's a compiler and virtual machine:

- [robots-bytecode.py](robots-bytecode.py)

Compile this room:

```
E8      v
  >  @  5
  ^ -1 -<
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
0007	1b
	:memory stride
0008	09
	:data segment offset
0009	12
	:entry points
000a	01
	:entry point offsets
000b	0c

	:code
000c	[80] PUSH @00
000d	[81] PUSH @01
000e	[30] SUB
000f	[82] PUSH @02
0010	[30] SUB
0011	[00] HALT

	:data
0012	0001 = 08
0015	0011 = 05
0018	0017 = 01
```

You can read the generated bytecode for each room and compare with the interpreter
in the attached `output` files.

The header includes some bytecode-y information, like a magic number and version
number.

Then it reports the following crucial values:

- Memory length: How many bytes long the input was, which is the number
  of bytes we have to allocate as our memory.
- Memory stride: This is the length of the x direction in the input. In the
  array memory model, your offset when going "up" or "down" is `x + y * stride`.
- Data segment offset: After the program ends, where initial state values
  are recorded.
- Entry points: The number of entry points and their offsets in the bytecode.
 
Looking at the data segment here, it contains three-byte group, each holding 
a 16-bit address value and a byte value:

```
00 01 08
00 11 05
00 17 01
```

The 16-bit address is the location of a value in the memory array; the 
next byte is its initial value. This shows where the initial `8`, `5`, and
`1` of the text input are located.

These values can in turn be referenced by their offset in the data segment,
which, for example, is what `PUSH @01` is doing: "Look at offset 1 in the 
data segment; get its memory location (`0011`); now get the value
at location `0011` and push that on the stack. This indirection is necessary
because any robot can change those memory values, which is what happens
with the concurrent room in which one robot polls for data written by another.

The initial values `8`, `5`, and `1` are only used when initializing memory
from the bytecode. Values can change, but the memory address associated 
with a value location in the input cannot change.

An obviously undesirable feature here is that *every* memory access requires
a pointer dereference, which is a gross thing to see. It performs better 
than the interpreted version (about 2.5x faster in the python version here),
which isn't a great improvement, but it's a start.

My impulse was to make the bytecode compact, but doing so necessitated this
pointer approach. I think the next iteration should just put the 16-bit
memory addresses inline after each `PUSH` instruction and get on with life.
It will take a few more instructions, but spare a lot of computation.

There are probably plenty of other ways to make further optimizations with further
pre-processing passes
but I'm not
going to try to figure them out because I'm done being nerd-sniped by this.

For now.

- Jed
 

