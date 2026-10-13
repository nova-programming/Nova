"""Opcode definitions for the custom Nova Virtual Machine"""

from enum import Enum, auto

class OpCode(Enum):
    # Constants
    LOAD_CONST = auto()   # Push constant onto stack
    LOAD_STR = auto()     # Push string onto stack
    LOAD_BOOL = auto()    # Push boolean onto stack

    # Variables
    LOAD_NAME = auto()    # Load variable from environment
    STORE_NAME = auto()   # Store top of stack to variable

    # Operations
    ADD = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    MOD = auto()
    NEG = auto()

    # Comparisons
    CMP_EQ = auto()
    CMP_NEQ = auto()
    CMP_LT = auto()
    CMP_GT = auto()
    CMP_LE = auto()
    CMP_GE = auto()

    # Logic
    AND = auto()
    OR = auto()

    # Bitwise
    BIT_AND = auto()
    BIT_OR = auto()
    BIT_XOR = auto()
    BIT_NOT = auto()
    SHL = auto()
    SAR = auto()
    HAS = auto()
    NOT = auto()

    # Control Flow
    JUMP = auto()         # Unconditional jump
    JUMP_IF_FALSE = auto()# Jump if top of stack is false
    CALL = auto()         # Call function
    RETURN = auto()       # Return from function

    # Memory / System
    ALLOC = auto()        # Allocate memory on heap
    FREE = auto()         # Free memory from heap
    LOAD_PTR = auto()     # Load value from pointer address
    LOAD_PTR_BYTE = auto()# Load single byte from pointer address
    LOAD_PTR_WORD = auto()# Load 16-bit word from pointer address
    STORE_PTR = auto()    # Store value to pointer address
    PTR_OFFSET = auto()   # Calculate pointer offset (for arrays/structs)
    LOAD_INDEX = auto()   # Load from array index
    STORE_INDEX = auto()  # Store to array index

    # Built-ins
    PRINT = auto()
    SIZEOF = auto()
    LEN = auto()
    OPEN_FILE = auto()
    READ_FILE = auto()
    WRITE_FILE = auto()
    CLOSE_FILE = auto()

    # FFI
    LOAD_LIB = auto()
    CALL_LIB = auto()

    # OOP
    NEW = auto()          # Instantiate a class
    LOAD_ATTR = auto()    # Load property from object
    STORE_ATTR = auto()   # Store property to object
    CALL_METHOD = auto()  # Call method on object
    LOAD_SELF = auto()    # Load 'self' context
    NEW_LIST = auto()     # Create a new dynamic list
    STR_CONVERT = auto()  # Convert value to string

    # Dictionaries
    BUILD_DICT = auto()

    # Slicing
    SLICE = auto()

    # Exception handling
    PUSH_HANDLER = auto()  # Push exception handler (arg = catch address)
    POP_HANDLER = auto()   # Pop current exception handler
    THROW = auto()         # Throw exception with top-of-stack value

    # Multi-value return (MultiReturn/UnpackAssign). RETURN's own frame cleanup collapses
    # the operand stack down to a single value (see _vm_run's "garbage above the return
    # value is dropped" comment), so values[1:] ride in a side stash instead of the main
    # stack; values[0] stays the normal single RETURN value.
    CLEAR_RETURN_STASH = auto()  # Clear the stash (start of a MultiReturn)
    STASH_RETURN = auto()        # Pop top-of-stack, append to the stash
    UNSTASH_RETURN = auto()      # Pop front of the stash, push onto the stack
