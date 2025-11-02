#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "vm.h"

// Test framework macros
static int tests_passed = 0;
static int tests_failed = 0;

#define TEST(name) \
    static void test_##name(void); \
    static void run_##name(void) { \
        printf("  %-40s", #name); \
        test_##name(); \
        tests_passed++; \
        printf("PASSED\n"); \
    } \
    static void test_##name(void)

#define ASSERT_EQ(a, b) \
    do { \
        int _a = (int)(a); \
        int _b = (int)(b); \
        if (_a != _b) { \
            printf("FAILED\n"); \
            printf("    %s:%d: %s != %s (%d != %d)\n", \
                   __FILE__, __LINE__, #a, #b, _a, _b); \
            tests_failed++; \
            return; \
        } \
    } while(0)

#define ASSERT_TRUE(expr) \
    do { \
        if (!(expr)) { \
            printf("FAILED\n"); \
            printf("    %s:%d: %s is false\n", \
                   __FILE__, __LINE__, #expr); \
            tests_failed++; \
            return; \
        } \
    } while(0)

// Helper function to create a test robot
static robot_t *create_test_robot(void) {
    robot_t *robot = malloc(sizeof(robot_t));
    robot->stack = malloc(sizeof(int) * STACK_MAX);
    robot->sp = 0;
    robot->pc = 0;
    robot->running = 1;
    robot->stride = 64;
    return robot;
}

static void destroy_test_robot(robot_t *robot) {
    if (robot) {
        free(robot->stack);
        free(robot);
    }
}

// ==================== Stack Operation Tests ====================

TEST(stack_add) {
    robot_t *robot = create_test_robot();
    robot->stack[robot->sp++] = 10;
    robot->stack[robot->sp++] = 32;

    err_t err = handle_stack_op(robot, ST_ADD);

    ASSERT_EQ(err, ERR_NO_ERROR);
    ASSERT_EQ(robot->sp, 1);
    ASSERT_EQ(robot->stack[0], 42);

    destroy_test_robot(robot);
}

TEST(stack_sub) {
    robot_t *robot = create_test_robot();
    robot->stack[robot->sp++] = 100;
    robot->stack[robot->sp++] = 42;

    err_t err = handle_stack_op(robot, ST_SUB);

    ASSERT_EQ(err, ERR_NO_ERROR);
    ASSERT_EQ(robot->sp, 1);
    ASSERT_EQ(robot->stack[0], 58);

    destroy_test_robot(robot);
}

TEST(stack_mul) {
    robot_t *robot = create_test_robot();
    robot->stack[robot->sp++] = 6;
    robot->stack[robot->sp++] = 7;

    err_t err = handle_stack_op(robot, ST_MUL);

    ASSERT_EQ(err, ERR_NO_ERROR);
    ASSERT_EQ(robot->sp, 1);
    ASSERT_EQ(robot->stack[0], 42);

    destroy_test_robot(robot);
}

TEST(stack_div) {
    robot_t *robot = create_test_robot();
    robot->stack[robot->sp++] = 84;
    robot->stack[robot->sp++] = 2;

    err_t err = handle_stack_op(robot, ST_DIV);

    ASSERT_EQ(err, ERR_NO_ERROR);
    ASSERT_EQ(robot->sp, 1);
    ASSERT_EQ(robot->stack[0], 42);

    destroy_test_robot(robot);
}

TEST(stack_mod) {
    robot_t *robot = create_test_robot();
    robot->stack[robot->sp++] = 50;
    robot->stack[robot->sp++] = 8;

    err_t err = handle_stack_op(robot, ST_MOD);

    ASSERT_EQ(err, ERR_NO_ERROR);
    ASSERT_EQ(robot->sp, 1);
    ASSERT_EQ(robot->stack[0], 2);

    destroy_test_robot(robot);
}

TEST(stack_and) {
    robot_t *robot = create_test_robot();
    robot->stack[robot->sp++] = 0xFF;
    robot->stack[robot->sp++] = 0x0F;

    err_t err = handle_stack_op(robot, ST_AND);

    ASSERT_EQ(err, ERR_NO_ERROR);
    ASSERT_EQ(robot->sp, 1);
    ASSERT_EQ(robot->stack[0], 0x0F);

    destroy_test_robot(robot);
}

TEST(stack_or) {
    robot_t *robot = create_test_robot();
    robot->stack[robot->sp++] = 0xF0;
    robot->stack[robot->sp++] = 0x0F;

    err_t err = handle_stack_op(robot, ST_OR);

    ASSERT_EQ(err, ERR_NO_ERROR);
    ASSERT_EQ(robot->sp, 1);
    ASSERT_EQ(robot->stack[0], 0xFF);

    destroy_test_robot(robot);
}

TEST(stack_not) {
    robot_t *robot = create_test_robot();
    robot->stack[robot->sp++] = 0x00;

    err_t err = handle_stack_op(robot, ST_NOT);

    ASSERT_EQ(err, ERR_NO_ERROR);
    ASSERT_EQ(robot->sp, 1);
    ASSERT_EQ(robot->stack[0], ~0x00);

    destroy_test_robot(robot);
}

TEST(stack_dup) {
    robot_t *robot = create_test_robot();
    robot->stack[robot->sp++] = 42;

    err_t err = handle_stack_op(robot, ST_DUP);

    ASSERT_EQ(err, ERR_NO_ERROR);
    ASSERT_EQ(robot->sp, 2);
    ASSERT_EQ(robot->stack[0], 42);
    ASSERT_EQ(robot->stack[1], 42);

    destroy_test_robot(robot);
}

TEST(stack_swap) {
    robot_t *robot = create_test_robot();
    robot->stack[robot->sp++] = 10;
    robot->stack[robot->sp++] = 20;

    err_t err = handle_stack_op(robot, ST_SWAP);

    ASSERT_EQ(err, ERR_NO_ERROR);
    ASSERT_EQ(robot->sp, 2);
    ASSERT_EQ(robot->stack[0], 20);
    ASSERT_EQ(robot->stack[1], 10);

    destroy_test_robot(robot);
}

TEST(stack_pop) {
    robot_t *robot = create_test_robot();
    robot->stack[robot->sp++] = 42;
    robot->stack[robot->sp++] = 100;

    err_t err = handle_stack_op(robot, ST_POP);

    ASSERT_EQ(err, ERR_NO_ERROR);
    ASSERT_EQ(robot->sp, 1);
    ASSERT_EQ(robot->stack[0], 42);

    destroy_test_robot(robot);
}

// ==================== Error Condition Tests ====================

TEST(stack_underflow_pop) {
    robot_t *robot = create_test_robot();
    robot->sp = 0;

    err_t err = handle_stack_op(robot, ST_POP);

    ASSERT_EQ(err, ERR_RUNTIME_STACK_UNDERFLOW);

    destroy_test_robot(robot);
}

TEST(stack_underflow_add) {
    robot_t *robot = create_test_robot();
    robot->stack[robot->sp++] = 42;

    err_t err = handle_stack_op(robot, ST_ADD);

    ASSERT_EQ(err, ERR_RUNTIME_STACK_UNDERFLOW);

    destroy_test_robot(robot);
}

TEST(stack_underflow_not) {
    robot_t *robot = create_test_robot();
    robot->sp = 0;

    err_t err = handle_stack_op(robot, ST_NOT);

    ASSERT_EQ(err, ERR_RUNTIME_STACK_UNDERFLOW);

    destroy_test_robot(robot);
}

TEST(stack_overflow_dup) {
    robot_t *robot = create_test_robot();
    robot->sp = STACK_MAX;

    err_t err = handle_stack_op(robot, ST_DUP);

    ASSERT_EQ(err, ERR_RUNTIME_STACK_OVERFLOW);

    destroy_test_robot(robot);
}

TEST(division_by_zero) {
    robot_t *robot = create_test_robot();
    robot->stack[robot->sp++] = 42;
    robot->stack[robot->sp++] = 0;

    err_t err = handle_stack_op(robot, ST_DIV);

    ASSERT_EQ(err, ERR_RUNTIME_DIVISION_BY_ZERO);

    destroy_test_robot(robot);
}

TEST(modulo_by_zero) {
    robot_t *robot = create_test_robot();
    robot->stack[robot->sp++] = 42;
    robot->stack[robot->sp++] = 0;

    err_t err = handle_stack_op(robot, ST_MOD);

    ASSERT_EQ(err, ERR_RUNTIME_DIVISION_BY_ZERO);

    destroy_test_robot(robot);
}

// ==================== Memory Operation Tests ====================

TEST(write_byte_basic) {
    robot_t *robot = create_test_robot();
    memset(heap, 0, MEM_MAX);

    // Push write_byte parameters: v, x, y, dx, dy
    robot->stack[robot->sp++] = 0b10101010; // value
    robot->stack[robot->sp++] = 0; // x
    robot->stack[robot->sp++] = 0; // y
    robot->stack[robot->sp++] = 1; // dx (horizontal)
    robot->stack[robot->sp++] = 0; // dy

    err_t err = write_byte(robot);

    ASSERT_EQ(err, ERR_NO_ERROR);
    ASSERT_EQ(robot->sp, 0);
    // Check that bits were written correctly
    ASSERT_EQ(heap[0], 1); // bit 7
    ASSERT_EQ(heap[1], 0); // bit 6
    ASSERT_EQ(heap[2], 1); // bit 5
    ASSERT_EQ(heap[3], 0); // bit 4

    destroy_test_robot(robot);
}

TEST(read_byte_basic) {
    robot_t *robot = create_test_robot();
    memset(heap, 0, MEM_MAX);

    // Set up a pattern in heap
    heap[0] = 1;
    heap[1] = 0;
    heap[2] = 1;
    heap[3] = 0;
    heap[4] = 1;
    heap[5] = 0;
    heap[6] = 1;
    heap[7] = 0;

    // Push read_byte parameters: x, y, dx, dy
    robot->stack[robot->sp++] = 0; // x
    robot->stack[robot->sp++] = 0; // y
    robot->stack[robot->sp++] = 1; // dx
    robot->stack[robot->sp++] = 0; // dy

    err_t err = read_byte(robot);

    ASSERT_EQ(err, ERR_NO_ERROR);
    ASSERT_EQ(robot->sp, 1);
    ASSERT_EQ(robot->stack[0], 0b10101010);

    destroy_test_robot(robot);
}

TEST(write_byte_out_of_bounds_x) {
    robot_t *robot = create_test_robot();
    memset(heap, 0, MEM_MAX);

    robot->stack[robot->sp++] = 0xFF;
    robot->stack[robot->sp++] = 9999; // x out of bounds
    robot->stack[robot->sp++] = 0;
    robot->stack[robot->sp++] = 1;
    robot->stack[robot->sp++] = 0;

    err_t err = write_byte(robot);

    ASSERT_EQ(err, ERR_RUNTIME_OUT_OF_BOUNDS);

    destroy_test_robot(robot);
}

TEST(write_byte_out_of_bounds_y) {
    robot_t *robot = create_test_robot();
    memset(heap, 0, MEM_MAX);

    robot->stack[robot->sp++] = 0xFF;
    robot->stack[robot->sp++] = 0;
    robot->stack[robot->sp++] = 9999; // y out of bounds
    robot->stack[robot->sp++] = 1;
    robot->stack[robot->sp++] = 0;

    err_t err = write_byte(robot);

    ASSERT_EQ(err, ERR_RUNTIME_OUT_OF_BOUNDS);

    destroy_test_robot(robot);
}

TEST(write_byte_negative_coords) {
    robot_t *robot = create_test_robot();
    memset(heap, 0, MEM_MAX);

    robot->stack[robot->sp++] = 0xFF;
    robot->stack[robot->sp++] = -1; // negative x
    robot->stack[robot->sp++] = 0;
    robot->stack[robot->sp++] = 1;
    robot->stack[robot->sp++] = 0;

    err_t err = write_byte(robot);

    ASSERT_EQ(err, ERR_RUNTIME_OUT_OF_BOUNDS);

    destroy_test_robot(robot);
}

TEST(read_byte_out_of_bounds) {
    robot_t *robot = create_test_robot();
    memset(heap, 0, MEM_MAX);

    robot->stack[robot->sp++] = 9999; // x out of bounds
    robot->stack[robot->sp++] = 0;
    robot->stack[robot->sp++] = 1;
    robot->stack[robot->sp++] = 0;

    err_t err = read_byte(robot);

    ASSERT_EQ(err, ERR_RUNTIME_OUT_OF_BOUNDS);

    destroy_test_robot(robot);
}

TEST(write_byte_stack_underflow) {
    robot_t *robot = create_test_robot();
    robot->sp = 4; // Need 5 items

    err_t err = write_byte(robot);

    ASSERT_EQ(err, ERR_RUNTIME_STACK_UNDERFLOW);

    destroy_test_robot(robot);
}

TEST(read_byte_stack_underflow) {
    robot_t *robot = create_test_robot();
    robot->sp = 3; // Need 4 items

    err_t err = read_byte(robot);

    ASSERT_EQ(err, ERR_RUNTIME_STACK_UNDERFLOW);

    destroy_test_robot(robot);
}

// ==================== Main Test Runner ====================

int main(void) {
    printf("=== Running VM Unit Tests ===\n\n");

    printf("Stack Operation Tests:\n");
    run_stack_add();
    run_stack_sub();
    run_stack_mul();
    run_stack_div();
    run_stack_mod();
    run_stack_and();
    run_stack_or();
    run_stack_not();
    run_stack_dup();
    run_stack_swap();
    run_stack_pop();

    printf("\nError Condition Tests:\n");
    run_stack_underflow_pop();
    run_stack_underflow_add();
    run_stack_underflow_not();
    run_stack_overflow_dup();
    run_division_by_zero();
    run_modulo_by_zero();

    printf("\nMemory Operation Tests:\n");
    run_write_byte_basic();
    run_read_byte_basic();
    run_write_byte_out_of_bounds_x();
    run_write_byte_out_of_bounds_y();
    run_write_byte_negative_coords();
    run_read_byte_out_of_bounds();
    run_write_byte_stack_underflow();
    run_read_byte_stack_underflow();

    printf("\n=== Test Summary ===\n");
    printf("Passed: %d\n", tests_passed);
    printf("Failed: %d\n", tests_failed);

    return tests_failed > 0 ? 1 : 0;
}