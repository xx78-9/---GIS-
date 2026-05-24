# -*- coding: utf-8 -*-
"""
脚本06：生成质检报告
功能：汇总所有步骤结果，输出 Excel 格式的质检报告
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['PROJ_LIB'] = os.path.join(sys.prefix, 'Library', 'share', 'proj')

import json
import pandas as pd
import geopandas as gpd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(BASE_DIR, '质检报告')
OUTPUT_DIR = os.path.join(BASE_DIR, '处理中')

os.makedirs(REPORT_DIR, exist_ok=True)


def load_json(name):
    path = os.path.join(REPORT_DIR, name)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def sheet_summary(writer):
    """总览表"""
    rows = [
        ['项目名称', '上海城市地理数据治理平台'],
        ['处理时间', datetime.now().strftime('%Y-%m-%d')],
        ['数据来源', 'OpenStreetMap + 模拟脏数据'],
        ['目标坐标系', 'EPSG:4326 (WGS84)'],
        ['质检标准', '9条规则覆盖属性/几何/拓扑/业务逻辑'],
        ['技术栈', 'Python(geopandas/rasterio/shapely), PostGIS, GeoServer, Leaflet'],
        ['报告生成', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
    ]
    pd.DataFrame(rows, columns=['项目', '内容']).to_excel(
        writer, sheet_name='00_总览', index=False)


def sheet_inventory(writer):
    """摸底检查"""
    data = load_json('01_摸底检查.json')
    if not data:
        return
    rows = [{
        '文件名': d['文件名'],
        '类型': d.get('类型'),
        '要素/像素': d.get('要素数量') or d.get('尺寸'),
        '坐标系': d.get('坐标系', '')[:50],
        '几何类型': str(d.get('几何类型', '')),
        '值域范围': str(d.get('值域', '')),
        '状态': d.get('状态')
    } for d in data]
    pd.DataFrame(rows).to_excel(writer, sheet_name='01_摸底检查', index=False)


def sheet_qc(writer):
    """质检问题"""
    data = load_json('02_质检结果.json')
    if not data:
        return
    rows = []
    for file_rpt in data:
        fname = file_rpt.get('文件名', '')
        for r in file_rpt.get('检查结果', []):
            if not r.get('是否通过', True):
                rows.append({
                    '文件': fname,
                    '规则': r.get('规则编号', ''),
                    '规则名称': r.get('规则名称', ''),
                    '问题说明': r.get('说明', ''),
                    '详细信息': str(r.get('非法值', r.get('重叠详情', ''))),
                })
    if rows:
        pd.DataFrame(rows).to_excel(writer, sheet_name='02_质检问题', index=False)
    else:
        pd.DataFrame([{'结果': '全部通过'}]).to_excel(writer, sheet_name='02_质检问题', index=False)


def sheet_fix(writer):
    """修复记录"""
    data = load_json('03_修复日志.json')
    if not data:
        return
    rows = [{
        '文件': d['文件名'],
        '原始要素数': d.get('原始要素数', '-'),
        '处理记录': '；'.join(d.get('处理记录', [])),
        '输出文件': d.get('输出文件', ''),
        '输出要素数': d.get('输出要素数', '-'),
    } for d in data]
    pd.DataFrame(rows).to_excel(writer, sheet_name='03_修复记录', index=False)


def sheet_import(writer):
    """入库记录"""
    data = load_json('04_入库日志.json')
    if not data:
        return
    rows = [{
        '文件': d['文件'],
        '目标': d.get('目标'),
        '记录数': d.get('记录数', '-'),
        '模式': d.get('模式', '-'),
        '状态': d.get('状态', '-')
    } for d in data]
    pd.DataFrame(rows).to_excel(writer, sheet_name='04_入库记录', index=False)


def sheet_stats(writer):
    """数据统计"""
    rows = []
    for fname in sorted(os.listdir(OUTPUT_DIR)):
        if fname.endswith('.geojson'):
            fpath = os.path.join(OUTPUT_DIR, fname)
            gdf = gpd.read_file(fpath)
            types = gdf.geometry.geom_type.unique()
            bounds = gdf.total_bounds
            rows.append({
                '文件名': fname,
                '要素数': len(gdf),
                '几何类型': ', '.join(types),
                '字段数': len(gdf.columns),
                '经度范围': f'{bounds[0]:.3f}~{bounds[2]:.3f}',
                '纬度范围': f'{bounds[1]:.3f}~{bounds[3]:.3f}',
            })
    if rows:
        pd.DataFrame(rows).to_excel(writer, sheet_name='05_数据统计', index=False)


def run():
    print('=' * 60)
    print(f'  脚本06：生成质检报告')
    print(f'  时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 60)

    report_path = os.path.join(REPORT_DIR, '数据处理报告.xlsx')
    writer = pd.ExcelWriter(report_path, engine='openpyxl')

    sheets = [
        (sheet_summary, '总览'),
        (sheet_inventory, '摸底'),
        (sheet_qc, '质检'),
        (sheet_fix, '修复'),
        (sheet_import, '入库'),
        (sheet_stats, '统计'),
    ]

    for func, name in sheets:
        try:
            func(writer)
            print(f'  [OK] {name}')
        except Exception as e:
            print(f'  [SKIP] {name}: {e}')

    writer.close()
    print(f'\n  报告已保存: {report_path}')
    print(f'{"=" * 60}')


if __name__ == '__main__':
    run()
