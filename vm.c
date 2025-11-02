#include "stdint.h"
#include "stdio.h"
#include "stdlib.h"
#include "time.h"

#define CODE_MAX (1024)
#define MEM_MAX (4096)
#define STACK_MAX (256)

uint8_t magic[] = {'J', 'E', 'D', '?'};
uint8_t version[] = {1, 0};

// Code and heap shared by all processes. Whee!
uint8_t bytecode[CODE_MAX];
uint8_t heap[MEM_MAX];

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

static err_t init_heap(vm_t *vm, int code_sz) {
    for (int i = 0; i < vm->mem_size; i++) {
        heap[i] = 0;
    }

    int i = vm->data_seg;
    while (i < code_sz) {
        uint16_t high = bytecode[i++] << 8;
        uint16_t addr = high | bytecode[i++];
        uint8_t value = bytecode[i++];
        heap[addr] = value;
    }

    return ERR_NO_ERROR;
}

static err_t init_vm(vm_t *vm, int code_sz) {
    err_t err = ERR_NO_ERROR;

    if (!vm) return ERR_BAD_INPUT;
    if (code_sz < 12) { printf("Input buffer too short. Not even worth trying.\n"); return ERR_BAD_INPUT; }
    if (bytecode[0] != magic[0]) { printf("Bad magic.\n"); return ERR_BAD_INPUT; }
    if (bytecode[1] != magic[1]) { printf("Bad magic.\n"); return ERR_BAD_INPUT; }
    if (bytecode[2] != magic[2]) { printf("Bad magic.\n"); return ERR_BAD_INPUT; }
    if (bytecode[3] != magic[3]) { printf("Bad magic.\n"); return ERR_BAD_INPUT; }
    if (bytecode[4] != version[0]) { printf("Bad version.\n"); return ERR_BAD_INPUT; }
    if (bytecode[5] != version[1]) { printf("Bad version.\n"); return ERR_BAD_INPUT; }

    uint16_t data_seg = bytecode[9];
    uint16_t code_size = data_seg - 11 - bytecode[11];
    uint16_t mem_size = (bytecode[6] << 8) | bytecode[7];
    uint8_t mem_stride = bytecode[8];
    vm->code_size = code_size;
    vm->mem_size = mem_size;
    vm->data_seg = bytecode[9];
    vm->n_robots = bytecode[10];

    err = init_heap(vm, code_sz);
    if (err != ERR_NO_ERROR) {
        return err;
    }

    for (int i = 0; i < vm->n_robots; i++) {
        robot_t *robot = malloc(sizeof(robot_t));
        robot->stack = malloc(sizeof(int) * STACK_MAX);
        robot->running = 0;
        robot->entry_point = bytecode[11 + i];
        robot->pc = bytecode[11 + i];
        robot->sp = 0;
        robot->stride = mem_stride;
        vm->robots[i] = robot;
    }

    return err;
}

static err_t destroy(vm_t *vm) {
    if (!vm)
        return ERR_BAD_INPUT;

    for (int i = 0; i < vm->n_robots; i++) {
        robot_t *robot = vm->robots[i];
        if (robot) {
            free(robot->stack);
            free(robot);
        }
    }

    free(vm);
    return ERR_NO_ERROR;
}

static err_t handle_stack_op(robot_t *robot, stack_op_t op) {
    err_t err = ERR_NO_ERROR;

    if (op == ST_POP) {
        if (robot->sp <= 0) {
            return ERR_RUNTIME_STACK_UNDERFLOW;
        }
        --robot->sp;
        return ERR_NO_ERROR;
    }

    // Remaining ops require one thing on the stack.
    if (robot->sp <= 0) {
        return ERR_RUNTIME_STACK_UNDERFLOW;
    }

    if (op == ST_DUP) {
        if (robot->sp >= STACK_MAX) {
            return ERR_RUNTIME_STACK_OVERFLOW;
        }
        int top = robot->stack[robot->sp - 1];
        robot->stack[robot->sp++] = top;
        return ERR_NO_ERROR;
    } else if (op == ST_NOT) {
        robot->stack[robot->sp - 1] = ~robot->stack[robot->sp - 1];
        return ERR_NO_ERROR;
    }

    // Remaining ops require two things on the stack.
    if (robot->sp < 2) {
        return ERR_RUNTIME_STACK_UNDERFLOW;
    }

    int a = robot->stack[--robot->sp];
    int b = robot->stack[--robot->sp];

    if (robot->sp >= STACK_MAX) {
        return ERR_RUNTIME_STACK_OVERFLOW;
    }

    switch (op) {
        case ST_SWAP:
            if (robot->sp + 1 >= STACK_MAX) {
                return ERR_RUNTIME_STACK_OVERFLOW;
            }
            robot->stack[robot->sp++] = a;
            robot->stack[robot->sp++] = b;
            break;
        case ST_SUB:
            robot->stack[robot->sp++] = b - a;
            break;
        case ST_ADD:
            robot->stack[robot->sp++] = b + a;
            break;
        case ST_MUL:
            robot->stack[robot->sp++] = b * a;
            break;
        case ST_DIV:
            if (a == 0) {
                return ERR_RUNTIME_DIVISION_BY_ZERO;
            }
            robot->stack[robot->sp++] = b / a;
            break;
        case ST_MOD:
            if (a == 0) {
                return ERR_RUNTIME_DIVISION_BY_ZERO;
            }
            robot->stack[robot->sp++] = b % a;
            break;
        case ST_AND:
            robot->stack[robot->sp++] = b & a;
            break;
        case ST_OR:
            robot->stack[robot->sp++] = b | a;
            break;
        default:
            return ERR_BAD_INPUT;
    }

    return err;
}

static err_t write_byte(robot_t *robot) {
    if (robot->sp < 5) {
        return ERR_RUNTIME_STACK_UNDERFLOW;
    }

    int dy = robot->stack[--robot->sp];
    int dx = robot->stack[--robot->sp];
    int y = robot->stack[--robot->sp];
    int x = robot->stack[--robot->sp];
    int v = robot->stack[--robot->sp];

    for (int i = 0; i < 8; i++) {
        // Strict bounds check - error on out-of-bounds access
        if (x < 0 || y < 0 || x >= robot->stride || y >= (MEM_MAX / robot->stride)) {
            return ERR_RUNTIME_OUT_OF_BOUNDS;
        }

        uint16_t offset = x + y * robot->stride;
        if (offset >= MEM_MAX) {
            return ERR_RUNTIME_OUT_OF_BOUNDS;
        }

        heap[offset] = (v >> (7 - i)) & 0x1;
        y += dy;
        x += dx;
    }

    return ERR_NO_ERROR;
}

static err_t read_byte(robot_t *robot) {
    if (robot->sp < 4) {
        return ERR_RUNTIME_STACK_UNDERFLOW;
    }

    int dy = robot->stack[--robot->sp];
    int dx = robot->stack[--robot->sp];
    int y = robot->stack[--robot->sp];
    int x = robot->stack[--robot->sp];
    int v = 0;

    for (int i = 0; i < 8; i++) {
        // Strict bounds check - error on out-of-bounds access
        if (x < 0 || y < 0 || x >= robot->stride || y >= (MEM_MAX / robot->stride)) {
            return ERR_RUNTIME_OUT_OF_BOUNDS;
        }

        uint16_t offset = x + y * robot->stride;
        if (offset >= MEM_MAX) {
            return ERR_RUNTIME_OUT_OF_BOUNDS;
        }

        uint8_t bit = heap[offset];
        v |= (bit << (7 - i));
        y += dy;
        x += dx;
    }

    if (robot->sp >= STACK_MAX) {
        return ERR_RUNTIME_STACK_OVERFLOW;
    }
    robot->stack[robot->sp++] = v;

    return ERR_NO_ERROR;
}

static void disassemble_instruction(int pc, uint8_t opcode) {
    uint8_t op = (opcode >> 4) & 0xf;
    uint8_t arg = opcode & 0xf;

    printf("  %04d: 0x%02x ", pc, opcode);

    if (op & OP_PUSH) {
        uint16_t addr = ((opcode & 0x7f) << 8) | (bytecode[pc + 1]);
        printf("PUSH [0x%04x]\n", addr);
    } else {
        switch (op) {
            case OP_HALT:
                printf("HALT\n");
                break;
            case OP_BYTE:
                printf("BYTE %s\n", (arg == 0x1) ? "WRITE" : "READ");
                break;
            case OP_STACK:
                printf("STACK ");
                switch (arg) {
                    case ST_SUB: printf("SUB\n"); break;
                    case ST_ADD: printf("ADD\n"); break;
                    case ST_MUL: printf("MUL\n"); break;
                    case ST_DIV: printf("DIV\n"); break;
                    case ST_MOD: printf("MOD\n"); break;
                    case ST_AND: printf("AND\n"); break;
                    case ST_OR: printf("OR\n"); break;
                    case ST_NOT: printf("NOT\n"); break;
                    case ST_POP: printf("POP\n"); break;
                    case ST_SWAP: printf("SWAP\n"); break;
                    case ST_DUP: printf("DUP\n"); break;
                    default: printf("UNKNOWN(%d)\n", arg); break;
                }
                break;
            case OP_JMP:
                if (arg != 0xf) {
                    printf("JMP %d\n", arg);
                } else {
                    printf("JMP %d\n", bytecode[pc + 1]);
                }
                break;
            case OP_JZ:
                if (arg != 0xf) {
                    printf("JZ %d\n", arg);
                } else {
                    printf("JZ %d\n", bytecode[pc + 1]);
                }
                break;
            default:
                printf("UNKNOWN_OP(0x%02x)\n", op);
                break;
        }
    }
}

static err_t next_tick(robot_t *robot) {
    err_t err = ERR_NO_ERROR;
    if (!robot->running) {
        return ERR_NOT_RUNNING;
    }

    if (robot->pc < 0 || robot->pc >= CODE_MAX) {
        return ERR_BAD_INPUT;
    }

    uint8_t opcode = bytecode[robot->pc];
    uint8_t op = (opcode >> 4) & 0xf;
    uint8_t arg = opcode & 0xf;

    if (op & OP_PUSH) {
        if (robot->pc + 1 >= CODE_MAX) {
            return ERR_BAD_INPUT;
        }
        if (robot->sp >= STACK_MAX) {
            return ERR_RUNTIME_STACK_OVERFLOW;
        }
        uint16_t addr = ((opcode & 0x7f) << 8) | (bytecode[robot->pc + 1]);
        if (addr >= MEM_MAX) {
            return ERR_BAD_INPUT;
        }
        robot->stack[robot->sp++] = heap[addr];
        // Skip over next byte.
        robot->pc++;
    } else {
        switch (op) {
            case OP_HALT:
                robot->running = 0;
                break;
            case OP_BYTE:
                if (arg == 0x1) {
                    err = write_byte(robot);
                } else {
                    err = read_byte(robot);
                }
                break;
            case OP_STACK:
                err |= handle_stack_op(robot, arg);
                break;
            case OP_JMP: {
                uint16_t target;
                if (arg != 0xf) {
                    target = arg;
                } else {
                    if (robot->pc + 1 >= CODE_MAX) {
                        return ERR_BAD_INPUT;
                    }
                    target = bytecode[++robot->pc];
                }

                // -1 because incremented after the loop.
                robot->pc = target - 1;
                break;
            }
            case OP_JZ: {
                if (robot->sp <= 0) {
                    return ERR_RUNTIME_STACK_UNDERFLOW;
                }
                uint16_t target;
                if (arg != 0xf) {
                    target = arg;
                } else {
                    if (robot->pc + 1 >= CODE_MAX) {
                        return ERR_BAD_INPUT;
                    }
                    target = bytecode[++robot->pc];
                }
                if (robot->stack[--robot->sp] == 0) {
                    // -1 because incremented after the loop.
                    robot->pc = target - 1;
                }
                break;
            }
            default:
                printf("Unknown opcode: 0x%02x\n", op);
                return ERR_BAD_INPUT;
        }
    }

    robot->pc++;

    return err;
}

static err_t exec(int sz) {
    err_t err = ERR_NO_ERROR;
    vm_t *vm = malloc(sizeof(vm_t));

    printf("Exec bytecode: %d bytes.\n", sz);
    err = init_vm(vm, sz);
    if (err) {
        printf("Error initializing VM.\n");
        goto done;
    }

    if (vm->n_robots > 16) {
        printf("Sadly, VM can't handle that many robots.\n");
        err = ERR_NOT_SUPPORTED;
        goto done;
    }

    // Max 16 robots; Bit flag for each robot that's running.
    uint16_t running_robots = 0;
    for (int i = 0; i < vm->n_robots; i++) {
        vm->robots[i]->running = 1;
        running_robots |= 1 << i;
    }

    // Time execution.
    struct timespec start_ts, end_ts;
    clock_gettime(CLOCK_REALTIME, &start_ts);

    int ticks = 0;
    while (running_robots) {
        for (int i = 0; i < vm->n_robots; i++) {
            if (!((running_robots >> i) & 1)) {
                continue;
            }
            robot_t *robot = vm->robots[i];
            if (robot->running) {
                err = next_tick(robot);
                if (err != ERR_NO_ERROR) {
                    printf("Robot %d: Error %d! pc=%d, sp=%d\n", i, err, robot->pc, robot->sp);
                    printf("Instruction causing error:\n");
                    if (robot->pc >= 0 && robot->pc < CODE_MAX) {
                        disassemble_instruction(robot->pc, bytecode[robot->pc]);
                    }
                    goto done;
                }
                ticks++;
            }

            // If robot halted, remove it from the running list.
            if (!robot->running) {
                if (robot->sp > 0) {
                    printf("Robot %d halted at tick %d. Last value: %d\n", i, ticks, robot->stack[robot->sp - 1]);
                } else {
                    printf("Robot %d halted at tick %d.\n", i, ticks);
                }
                running_robots &= ~(1 << i);
            }
        }
    }

done:
    clock_gettime(CLOCK_REALTIME, &end_ts);
    printf("Elapsed CPU time: %ld µs.\n", (end_ts.tv_nsec - start_ts.tv_nsec) / 1000);
    err |= destroy(vm);

    return err;
}

int main(int argc, char **argv) {
    err_t err = ERR_NO_ERROR;
    size_t sz;

    if (argc < 2) {
        printf("Usage: vm <filename>\n");
        return ERR_INVALID_ARGUMENT;
    }

    FILE *fp = fopen(argv[1], "rb");
    if (!fp) {
        printf("Failed to open: %s\n", argv[1]);
        return ERR_INVALID_ARGUMENT;
    }

    fseek(fp, 0L, SEEK_END);
    sz = ftell(fp);
    if (sz > CODE_MAX) {
        printf("Program too large.\n");
        fclose(fp);
        return ERR_BAD_INPUT;
    }
    fseek(fp, 0L, SEEK_SET);

    size_t bytes_read = fread(bytecode, 1, sz, fp);
    fclose(fp);

    if (bytes_read != sz) {
        printf("Failed to read complete file.\n");
        return ERR_BAD_INPUT;
    }

    err = exec((int) sz);

    return err;
}
