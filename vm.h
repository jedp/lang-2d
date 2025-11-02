#ifndef VM_H
#define VM_H

#include "stdint.h"

#define CODE_MAX (1024)
#define MEM_MAX (4096)
#define STACK_MAX (256)

typedef enum {
    OP_HALT = 0,
    OP_BYTE = 1,
    OP_STACK = 2,
    OP_JMP = 3,
    OP_JZ = 4,
    OP_PUSH = 8,
} op_t;

typedef enum {
    ST_SUB = 0,
    ST_ADD = 1,
    ST_MUL = 2,
    ST_DIV = 3,
    ST_MOD = 4,
    ST_AND = 5,
    ST_OR = 6,
    ST_NOT = 7,
    ST_POP = 8,
    ST_SWAP = 9,
    ST_DUP = 10,
} stack_op_t;

typedef enum {
    ERR_NO_ERROR,
    ERR_INVALID_ARGUMENT,
    ERR_BAD_INPUT,
    ERR_NOT_SUPPORTED,
    ERR_NOT_RUNNING,
    ERR_RUNTIME_STACK_UNDERFLOW,
    ERR_RUNTIME_STACK_OVERFLOW,
    ERR_RUNTIME_DIVISION_BY_ZERO,
    ERR_RUNTIME_OUT_OF_BOUNDS,
} err_t;

typedef struct {
    int running;
    int entry_point;
    int pc;
    int sp;
    int stride;
    int *stack;
} robot_t;

typedef struct {
    uint16_t code_size;
    uint16_t data_seg;
    uint16_t mem_size;
    uint8_t n_robots;
    robot_t *robots[16];
} vm_t;

// External declarations for testing
extern uint8_t bytecode[CODE_MAX];
extern uint8_t heap[MEM_MAX];

// Function declarations for testing
err_t handle_stack_op(robot_t *robot, stack_op_t op);

err_t write_byte(robot_t *robot);

err_t read_byte(robot_t *robot);

#endif // VM_H