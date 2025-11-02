# VM Test Suite

A zero-dependency test suite for the virtual machine.

## Quick Start

```bash
make test
```

## Overview

The test suite uses a simple assert-based framework built into `test_vm.c` 
with no external dependencies. It's completely portable standard C.

## Running Tests

```bash
# Build and run all tests
make test

# Or compile and run manually
gcc -Wall -Wextra -std=c99 -o test_vm test_vm.c vm.c
./test_vm
```

## Architecture

### Files

- `test_vm.c` - Test suite with all test cases
- `vm.h` - Header exposing VM internals for testing
- `vm.c` - The VM implementation (modified to expose test functions)

### Test Framework

Simple macro-based framework:

```c
TEST(test_name) {
    // Test code
    ASSERT_EQ(actual, expected);
    ASSERT_TRUE(condition);
}
```

### Adding New Tests

1. Add a `TEST(name)` function in `test_vm.c`
2. Add `run_name();` call in `main()`
3. Run `make test`

Example:

```c
TEST(my_new_test) {
    robot_t *robot = create_test_robot();
    
    // Setup
    robot->stack[robot->sp++] = 42;
    
    // Execute
    err_t err = handle_stack_op(robot, ST_DUP);
    
    // Verify
    ASSERT_EQ(err, ERR_NO_ERROR);
    ASSERT_EQ(robot->sp, 2);
    
    destroy_test_robot(robot);
}
```
