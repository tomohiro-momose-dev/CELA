import re

with open('cela_main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("=== _CURRENT_PHASE_ID assignments ===")
for i, line in enumerate(lines):
    if '_CURRENT_PHASE_ID' in line and ('global' in line or '=' in line):
        print(f'{i+1}|{lines[i].rstrip()[:200]}')

print("\n=== current_phase set in state ===")
for i, line in enumerate(lines):
    if '_CURRENT_PHASE_ID' in line and ('global' in line.lower() or 'state' in line.lower()):
        print(f'{i+1}|{lines[i].rstrip()[:200]}')

print("\n=== _phase_id_from function ===")
for i, line in enumerate(lines):
    if '_phase_id_from' in line and 'def ' in line:
        for j in range(i, min(i+5, len(lines))):
            print(f'{j+1}|{lines[j].rstrip()}')
        print('---')

print("\n=== call_expert: global declarations and _CURRENT_ assignments ===")
in_call_expert = False
for i, line in enumerate(lines):
    if 'def call_expert(' in line:
        in_call_expert = True
    if in_call_expert and ('_CURRENT_' in line and '=' in line):
        print(f'{i+1}|{lines[i].rstrip()[:200]}')
    if in_call_expert and i > 8340:
        break
