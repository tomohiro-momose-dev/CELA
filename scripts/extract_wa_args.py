import os, re, json

for log_dir in ['log/2026-08-10/2100', 'log/2026-08-10/1905']:
    print(f'=== {log_dir} ===')
    for fname in os.listdir(log_dir):
        if 'log_no_prompt' in fname:
            fpath = os.path.join(log_dir, fname)
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
            # Find all write_agreement tool calls
            for m in re.finditer(r'write_agreement\s+実行\s*\(iter=(\d+)\)\s*:\s*(\{.*?\})\s*\n', content, re.DOTALL):
                iter_num = m.group(1)
                args_str = m.group(2)
                try:
                    args = json.loads(args_str)
                except:
                    # Try to find the closing bracket
                    print(f'  iter={iter_num}: PARSE FAILED, raw: ...{args_str[:200]}...')
                    continue
                has_phase = 'phase_id' in args
                has_task = 'task_id' in args
                has_edits = 'edits' in args
                at = args.get('action_type', '?')
                et = args.get('entry_type', '?')
                tid = args.get('task_id', 'NOT_PROVIDED')
                pid = args.get('phase_id', 'NOT_PROVIDED')
                print(f'  iter={iter_num}: action={at}, entry_type={et}, task_id={tid}, phase_id={pid}, edits={has_edits}')
                if has_edits:
                    for e in args.get('edits', []):
                        ot = e.get('old_text', '')[:100]
                        print(f'    old_text[:100]: {ot}')
                print()
