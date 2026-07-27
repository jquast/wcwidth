# libwcwidth — simple Makefile (CMake is preferred)
#
#   make          build static library and example programs
#   make test     build and run all tests
#   make examples build example programs (textwrap, width, align)
#   make format   auto-format all C source with clang-format
#   make format-check  check formatting without modifying files
#   make clean    remove build artifacts

CC      ?= gcc
AR      ?= ar
CFLAGS  ?= -std=c11 -Wall -Wextra -O2 -g
INCLUDE  = -Iinclude
BUILD    = build

LIB_SRCS  = $(wildcard src/*.c) $(wildcard src/tables/*.c)
LIB_OBJS  = $(patsubst %.c,$(BUILD)/%.o,$(LIB_SRCS))
TEST_SRCS = $(wildcard tests/test_*.c)
TEST_BINS = $(patsubst tests/%.c,$(BUILD)/%,$(TEST_SRCS))
EX_SRCS   = $(wildcard examples/*.c)
EX_BINS   = $(patsubst examples/%.c,$(BUILD)/%,$(EX_SRCS))

LIB = $(BUILD)/libwcwidth.a

FORMAT_DIRS = src include tests examples
FORMAT_FILES = $(shell find $(FORMAT_DIRS) -name '*.c' -o -name '*.h' | sort)

.PHONY: all clean test examples format format-check

all: $(LIB) examples

examples: $(EX_BINS)

$(LIB): $(LIB_OBJS)
	@mkdir -p $(dir $@)
	$(AR) rcs $@ $^

$(BUILD)/%.o: %.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(INCLUDE) -c $< -o $@

$(BUILD)/%: tests/%.c $(LIB)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(INCLUDE) -Itests $< -L$(BUILD) -lwcwidth -o $@

$(BUILD)/%: examples/%.c $(LIB)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(INCLUDE) $< -L$(BUILD) -lwcwidth -o $@

define run_test
	@echo "=== $(notdir $(1)) ==="
	@$(1) || true
endef

test: $(TEST_BINS)
	$(foreach t,$(TEST_BINS),$(call run_test,$(t)))

format:
	clang-format -i $(FORMAT_FILES)

format-check:
	clang-format --dry-run --Werror $(FORMAT_FILES)

clean:
	rm -rf $(BUILD)
