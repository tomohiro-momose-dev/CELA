import re

with open('cela_main.py', 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.split('\n')

# 1. Read _build_task_scope_context (line 7224)
print("=== _build_task_scope_context (lines 7224-7280) ===")
for i in range(7223, min(7280, len(lines))):
    print(f'{i+1}|{lines[i][:200]}')

# 2. Read _commit_agreement_from_tool UPDATE path (lines 3000-3120)
print("\n=== _commit_agreement_from_tool UPDATE path (lines 3055-3120) ===")
for i in range(3054, min(3120, len(lines))):
    print(f'{i+1}|{lines[i][:250]}')

# 3. Read _write_agreement_impl call to _commit_agreement_from_tool (lines 3295-3310)
print("\n=== _write_agreement_impl calling _commit_agreement_from_tool (lines 3295-3310) ===")
for i in range(3294, min(3310, len(lines))):
    print(f'{i+1}|{lines[i][:250]}')

# 4. Read how Expert node is called in graph (search for "expert" node definition)
print("\n=== Expert node / graph references ===")
for i, line in enumerate(lines):
    if 'expert_node' in line or ('expert' in line.lower() and 'def ' in line and 'node' in line.lower()):
        print(f'{i+1}|{lines[i][:200]}')
    if '"expert"' in line and ('node' in line.lower() or 'add_node' in line.lower() or 'invoke' in line.lower() or 'call_' in line.lower()):
        print(f'{i+1}|{lines[i][:200]}')

# 5. Search for where current_phase is set in state (not just _CURRENT_PHASE_ID global)
print("\n=== state current_phase assignments ===")
for i, line in enumerate(lines):
    if 'state' in line and 'current_phase' in line and ('=' in line and 'get' not in line):
        print(f'{i+1}|{lines[i][:200]}')
    if 'current_phase' in line and 'state[' in line and '=' in line:
        print(f'{i+1}|{lines[i][:200]}')

# 6. Search for where current_task_id is set in state
print("\n=== state current_task_id assignments ===")
for i, line in enumerate(lines):
    if 'current_task_id' in line and 'state[' in line and '=' in line and 'get' not in line:
        print(f'{i+1}|{lines[i][:200]}')
    if '_resolve_task_transition' in line or 'BL-024' in line and 'current_task_id' in lines[i+1] if i+1 < len(lines) else False:
        print(f'{i+1}|{lines[i][:200]}')
