import re

with open('stdlib_asm.txt', 'r') as f:
    content = f.read()

# Define function boundaries and their label prefixes
# I need to know EXACTLY which labels belong to which function.
# Let me define replacement rules manually per function.

# Structure: (function_start, function_end) -> [(old_label, new_label), ...]
# function_end is the start of the next function

# _sys_write_raw labels (lines ~134-202)
content = content.replace("L_loop_1:", "L_wr_loop_1:")
content = content.replace("L_loop_end_2:", "L_wr_end_2:")
content = content.replace("L_loop_1\n", "L_wr_loop_1\n")  # used in jmp

# __sys_is_space labels (lines ~257-306)
content = content.replace("L_sys_else_3:", "L_is_space_else_3:")
content = content.replace("L_sys_end_4:", "L_is_space_end_4:")
content = content.replace("L_sys_else_5:", "L_is_space_else_5:")
content = content.replace("L_sys_end_6:", "L_is_space_end_6:")
# jmp/je references
content = content.replace("je L_is_space_else_3", "je L_is_space_else_3")  # already renamed
content = content.replace("jmp L_is_space_end_4", "jmp L_is_space_end_4")

# __sys_extract_arg labels (lines ~307-506)
content = content.replace("L_sys_else_11:", "L_sext_else_11:")
content = content.replace("L_sys_end_12:", "L_sext_end_12:")
content = content.replace("L_sys_else_9:", "L_sext_else_9:")
content = content.replace("L_sys_end_10:", "L_sext_end_10:")
content = content.replace("L_sys_else_7:", "L_sext_else_7:")
content = content.replace("L_sys_end_8:", "L_sext_end_8:")
content = content.replace("L_loop_13:", "L_sext_loop_13:")
content = content.replace("L_loop_end_14:", "L_sext_end_14:")
# References (jmp/je)
content = content.replace("L_sys_else_11", "L_sext_else_11")
content = content.replace("L_sys_else_9", "L_sext_else_9")
content = content.replace("L_sys_else_7", "L_sext_else_7")
content = content.replace("L_loop_13", "L_sext_loop_13")
content = content.replace("L_loop_end_14", "L_sext_end_14")
# Now fix the labels that were renamed by the L_sys_else replacements
# but need the L_sext_ prefix instead of L_is_space_
content = content.replace("L_is_space_else_11:", "L_sext_else_11:")
content = content.replace("L_is_space_end_12:", "L_sext_end_12:")
content = content.replace("L_is_space_else_9:", "L_sext_else_9:")
content = content.replace("L_is_space_end_10:", "L_sext_end_10:")
content = content.replace("L_is_space_else_7:", "L_sext_else_7:")
content = content.replace("L_is_space_end_8:", "L_sext_end_8:")

# _sys_get_args labels (lines ~507-805)
content = content.replace("L_loop_15:", "L_sga_loop_15:")
content = content.replace("L_loop_17:", "L_sga_loop_17:")
content = content.replace("L_loop_end_18:", "L_sga_end_18:")
content = content.replace("L_sys_else_19:", "L_sga_else_19:")
content = content.replace("L_sys_end_20:", "L_sga_end_20:")
content = content.replace("L_loop_21:", "L_sga_loop_21:")
content = content.replace("L_sys_else_25:", "L_sga_else_25:")
content = content.replace("L_sys_end_26:", "L_sga_end_26:")
content = content.replace("L_sys_else_23:", "L_sga_else_23:")
content = content.replace("L_sys_end_24:", "L_sga_end_24:")
content = content.replace("L_sys_else_29:", "L_sga_else_29:")
content = content.replace("L_sys_end_30:", "L_sga_end_30:")
content = content.replace("L_sys_else_27:", "L_sga_else_27:")
content = content.replace("L_sys_end_28:", "L_sga_end_28:")
content = content.replace("L_loop_end_22:", "L_sga_end_22:")
content = content.replace("L_realloc_ok_32:", "L_sga_ok_32:")
content = content.replace("L_no_realloc_31:", "L_sga_nore_31:")
content = content.replace("L_loop_end_16:", "L_sga_end_16:")
# References in sga
content = content.replace("L_sys_else_19", "L_sga_else_19")
content = content.replace("L_sys_else_23", "L_sga_else_23")
content = content.replace("L_sys_else_25", "L_sga_else_25")
content = content.replace("L_sys_else_27", "L_sga_else_27")
content = content.replace("L_sys_else_29", "L_sga_else_29")
content = content.replace("L_loop_17", "L_sga_loop_17")
content = content.replace("L_loop_end_18", "L_sga_end_18")
content = content.replace("L_loop_21", "L_sga_loop_21")
content = content.replace("L_loop_15", "L_sga_loop_15")
content = content.replace("L_loop_end_22", "L_sga_end_22")
content = content.replace("L_loop_end_16", "L_sga_end_16")
content = content.replace("L_realloc_ok_32", "L_sga_ok_32")
content = content.replace("L_no_realloc_31", "L_sga_nore_31")

# _abs_val labels (lines ~911-945)
content = content.replace("L_sys_else_1:", "L_abs_else_1:")
content = content.replace("L_sys_end_2:", "L_abs_end_2:")
content = content.replace("L_sys_else_1", "L_abs_else_1")
content = content.replace("L_sys_end_2", "L_abs_end_2")

# _max_of labels (lines ~946-978)
# L_sys_else_3 and L_sys_end_4 were already renamed to L_is_space_*
# These need to be L_max_else_3 and L_max_end_4 in the _max_of section
# Since _max_of comes AFTER __sys_is_space, the replacements below
# will only affect the _max_of section because they follow the order in the file
content = content.replace("L_is_space_else_3:", "L_max_else_3:")
content = content.replace("L_is_space_end_4:", "L_max_end_4:")
content = content.replace("L_is_space_else_3\n", "L_max_else_3\n")
content = content.replace("L_is_space_end_4\n", "L_max_end_4\n")

# _min_of labels (lines ~979-1011)
content = content.replace("L_is_space_else_5:", "L_min_else_5:")
content = content.replace("L_is_space_end_6:", "L_min_end_6:")
content = content.replace("L_is_space_else_5\n", "L_min_else_5\n")
content = content.replace("L_is_space_end_6\n", "L_min_end_6\n")

# _factorial labels (lines ~1012-1054)
content = content.replace("L_sext_else_7:", "L_fact_else_7:")
content = content.replace("L_sext_end_8:", "L_fact_end_8:")
content = content.replace("L_sext_else_7\n", "L_fact_else_7\n")
content = content.replace("L_sext_end_8\n", "L_fact_end_8\n")

# _random labels (lines ~2802-end)
content = content.replace("L_sext_else_9:", "L_random_else_9:")
content = content.replace("L_sext_end_10:", "L_random_end_10:")
content = content.replace("L_sext_else_9\n", "L_random_else_9\n")
content = content.replace("L_sext_end_10\n", "L_random_end_10\n")

with open('stdlib_asm.txt', 'w') as f:
    f.write(content)

print("Done! Fixed stdlib_asm.txt labels.")
