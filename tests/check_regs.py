import re
c = open('tests/bench_heavy.s').read()
funcs = re.findall(r'^([a-z_]+):\n    push rbp\n    mov rbp, rsp\n    and rsp, -16([\s\S]*?)(?=^[a-z_]+:|\Z)', c, re.MULTILINE)
for name, body in funcs:
    pushes = re.findall(r'push (r\d+|rbx)', body)
    callee_saved = set(pushes) & {'rbx', 'r12', 'r13', 'r14', 'r15'}
    non_callee = set(pushes) - {'rbx', 'r12', 'r13', 'r14', 'r15'}
    print(f'{name}: pushes={pushes}, callee={callee_saved}')
