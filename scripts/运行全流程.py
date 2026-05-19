# -*- coding: utf-8 -*-
"""一键运行全部数据处理流程"""

import os
import sys
import subprocess
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable

STEPS = [
    ('1/6', '01_获取数据.py',   '获取OSM数据 + 构造脏数据'),
    ('2/6', '02_数据摸底.py',   '扫描文件基本信息'),
    ('3/6', '03_质量检查.py',   '9条质检规则检查'),
    ('4/6', '04_数据修复.py',   '修复几何/填充NULL/坐标系统一'),
    ('5/6', '05_数据入库.py',   '数据入库/本地文件模式'),
    ('6/6', '06_生成报告.py',   '生成Excel质检报告'),
]

print('=' * 64)
print('  GIS数据处理自动化流水线')
print('  上海城市地理数据治理平台')
print('=' * 64)
print()

total_start = time.time()
results = []

for step_id, script, desc in STEPS:
    step_start = time.time()
    print(f'  [{step_id}] {desc}')
    print(f'       运行: {script}')

    script_path = os.path.join(SCRIPTS_DIR, script)
    try:
        cp = subprocess.run(
            [PYTHON, script_path],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=600,
            encoding='utf-8',
            errors='replace'
        )
        elapsed = time.time() - step_start
        if cp.returncode == 0:
            # 只显示最后几行关键输出
            lines = [l for l in cp.stdout.strip().split('\n') if l.strip()]
            for line in lines[-5:]:
                if line.strip():
                    print(f'       {line.strip()[:100]}')
            results.append((desc, 'OK', elapsed))
            print(f'       -> 完成 ({elapsed:.1f}s)')
        else:
            err_lines = [l for l in cp.stderr.strip().split('\n') if l.strip()]
            for line in err_lines[-3:]:
                print(f'       [ERR] {line.strip()[:100]}')
            results.append((desc, f'FAIL (exit {cp.returncode})', elapsed))
            print(f'       -> 失败 ({elapsed:.1f}s)')
            print('  [WARN] 流水线中断')
            break
    except subprocess.TimeoutExpired:
        elapsed = time.time() - step_start
        results.append((desc, 'TIMEOUT', elapsed))
        print(f'       -> 超时 ({elapsed:.1f}s)')
        break
    except Exception as e:
        elapsed = time.time() - step_start
        results.append((desc, f'ERROR: {e}', elapsed))
        print(f'       -> 异常 ({elapsed:.1f}s)')
        break

    print()

# 汇总
total_elapsed = time.time() - total_start
print('=' * 64)
print('  执行结果汇总')
print('=' * 64)
for name, status, elapsed in results:
    icon = '[OK]' if status == 'OK' else '[FAIL]'
    print(f'  {icon} {name:30s}  {elapsed:6.1f}s')

ok_count = sum(1 for _, s, _ in results if s == 'OK')
print(f'  {"-" * 48}')
print(f'  通过: {ok_count}/{len(results)}  总耗时: {total_elapsed:.1f}s')
print('=' * 64)

print()
print('  生成的文件:')
for folder, label in [
    ('成果数据', '成果数据'),
    ('质检报告', '质检报告'),
    ('成果展示', '成果展示'),
    ('处理中', '处理中')
]:
    path = os.path.join(BASE_DIR, folder)
    if os.path.exists(path):
        print(f'    [{label}]')
        for f in sorted(os.listdir(path)):
            size = os.path.getsize(os.path.join(path, f))
            print(f'      {f:45s} {size/1024:8.0f} KB')

print()
print(f'  在浏览器中打开查看成果: ')
print(f'    成果展示/index.html')
print('=' * 64)
