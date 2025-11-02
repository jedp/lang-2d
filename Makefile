CC = gcc
CFLAGS = -Wall -Wextra -std=c99 -O2
LDFLAGS =

# Targets
VM = vm
TEST = test_vm

# Source files
VM_SRC = vm.c
TEST_SRC = test_vm.c

.PHONY: all clean test

all: $(VM)

$(VM): $(VM_SRC)
	$(CC) $(CFLAGS) -o $(VM) $(VM_SRC) $(LDFLAGS)

$(TEST): $(TEST_SRC) $(VM_SRC)
	$(CC) $(CFLAGS) -DTEST_BUILD -c $(VM_SRC) -o vm.o
	$(CC) $(CFLAGS) -DTEST_BUILD -o $(TEST) $(TEST_SRC) vm.o $(LDFLAGS)

test: $(TEST)
	./$(TEST)

clean:
	rm -f $(VM) $(TEST) vm.o
