# -*- coding: utf-8 -*-
"""
脚本03：数据质量检查（9条规则）
规则覆盖三大维度：属性完整度、空间几何、业务逻辑一致性
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import geopandas as gpd
import json
import pandas as pd
from datetime import datetime
from shapely.validation import explain_validity

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTOR_DIR = os.path.join(BASE_DIR, '原始数据', '矢量')
REPORT_DIR = os.path.join(BASE_DIR, '质检报告')

TARGET_CRS = 'EPSG:4326'

# === 域值配置：定义每个字段允许的取值范围 ===
DOMAIN_RULES = {
    'highway': ['primary', 'secondary', 'tertiary', 'residential', 'unclassified',
                'motorway', 'trunk', 'motorway_link', 'trunk_link', 'primary_link',
                'secondary_link', 'tertiary_link', 'living_street', 'service', 'pedestrian'],
    'road_type': ['主干道', '次干道', '支路'],
    'building': ['yes', 'apartments', 'house', 'commercial', 'industrial', 'school',
                 'hospital', 'office', 'retail', 'warehouse', 'church', 'hotel', 'dormitory'],
    'category': ['学校', '医院', '餐厅'],
    '类型': ['商业', '住宅', '工业', '绿地']
}

os.makedirs(REPORT_DIR, exist_ok=True)


def check_null_ratio(gdf, filename):
    """规则1：每个字段的NULL比例"""
    results = []
    for col in gdf.columns:
        if col == 'geometry':
            continue
        count = int(gdf[col].isna().sum())
        ratio = count / len(gdf) if len(gdf) > 0 else 0
        results.append({
            '规则': 'R1-NULL检查',
            '字段': col,
            'NULL数': count,
            'NULL比例': f'{ratio*100:.1f}%',
            '是否通过': ratio < 0.5,
            '说明': f'字段"{col}"NULL值占比{ratio*100:.1f}%'
        })
    return results


def check_domain_values(gdf, filename):
    """规则2：字段值是否在合法域值范围内"""
    results = []
    for col in gdf.columns:
        if col == 'geometry' or col not in DOMAIN_RULES:
            continue
        valid_set = set(DOMAIN_RULES[col])
        actual_vals = gdf[col].dropna().unique()
        invalid = [v for v in actual_vals if v not in valid_set]
        if invalid:
            results.append({
                '规则': 'R2-域值检查',
                '字段': col,
                '问题': f'发现{len(invalid)}个不在允许范围内的值',
                '非法值': invalid[:10],  # 只列前10个
                '是否通过': False,
                '说明': f'字段"{col}"有{len(invalid)}个非法值'
            })
        else:
            results.append({
                '规则': 'R2-域值检查',
                '字段': col,
                '问题': '无',
                '是否通过': True,
                '说明': f'字段"{col}"所有值合法'
            })
    return results


def check_geometry_validity(gdf, filename):
    """规则3：几何有效性"""
    invalid_mask = ~gdf.geometry.is_valid
    invalid_count = int(invalid_mask.sum())
    problems = []
    if invalid_count > 0:
        invalid_ids = gdf.index[invalid_mask].tolist()
        for idx in invalid_ids[:5]:  # 取前5个样本
            problems.append({
                '要素ID': gdf.iloc[idx].get('id', idx),
                '原因': explain_validity(gdf.iloc[idx].geometry)
            })
    return [{
        '规则': 'R3-几何有效性',
        '无效数量': invalid_count,
        '无效比例': f'{invalid_count/len(gdf)*100:.1f}%' if len(gdf) > 0 else 'N/A',
        '问题样本': problems,
        '是否通过': invalid_count == 0,
        '说明': f'{invalid_count}个无效几何，共{len(gdf)}个要素'
    }]


def check_polygon_overlap(gdf, filename):
    """规则4：面图层重叠检查（超过1000个要素跳过以避免性能问题）"""
    geom_types = gdf.geometry.geom_type.unique()
    if 'Polygon' not in geom_types and 'MultiPolygon' not in geom_types:
        return [{
            '规则': 'R4-面重叠检查',
            '是否通过': True,
            '说明': '非面图层，跳过拓扑检查'
        }]

    if len(gdf) > 1000:
        # 采样检查：取前100个面做抽查
        sample = gdf.iloc[:100]
        return check_overlap_sample(sample, f'全量{len(gdf)}个要素过多，仅抽样前100个检查')

    return check_overlap_sample(gdf, '')


def check_overlap_sample(gdf, note):
    """重叠检查的实际实现"""
    overlaps = []
    for i in range(len(gdf)):
        for j in range(i + 1, len(gdf)):
            try:
                if gdf.iloc[i].geometry.intersects(gdf.iloc[j].geometry):
                    overlap_area = gdf.iloc[i].geometry.intersection(gdf.iloc[j].geometry).area
                    if overlap_area > 1e-10:
                        overlaps.append({
                            '要素A': gdf.iloc[i].get('id', i),
                            '要素B': gdf.iloc[j].get('id', j),
                            '重叠面积': round(overlap_area, 8)
                        })
            except Exception:
                continue

    note_suffix = f' ({note})' if note else ''
    return [{
        '规则': 'R4-面重叠检查',
        '重叠对数': len(overlaps),
        '重叠详情': overlaps[:10],
        '是否通过': len(overlaps) == 0,
        '说明': (f'发现{len(overlaps)}对面重叠' if overlaps else '无重叠') + note_suffix
    }]


def check_line_self_intersection(gdf, filename):
    """规则5：线图层自相交检查"""
    geom_types = gdf.geometry.geom_type.unique()
    if 'LineString' not in geom_types and 'MultiLineString' not in geom_types:
        return [{
            '规则': 'R5-线自相交检查',
            '是否通过': True,
            '说明': '非线图层，跳过'
        }]

    self_intersections = 0
    for i, geom in enumerate(gdf.geometry):
        if geom is None or geom.is_empty:
            continue
        try:
            # 检查是否为简单线（不自相交）
            if geom.geom_type == 'LineString':
                is_simple = geom.is_simple
            else:
                is_simple = all(segment.is_simple for segment in geom.geoms)
            if not is_simple:
                self_intersections += 1
        except Exception:
            self_intersections += 1

    return [{
        '规则': 'R5-线自相交检查',
        '问题数量': self_intersections,
        '是否通过': self_intersections == 0,
        '说明': f'{self_intersections}条线自相交' if self_intersections else '所有线合法'
    }]


def check_road_length_consistency(gdf, filename):
    """规则6：道路长度与几何长度一致性"""
    if 'length' not in gdf.columns or 'LineString' not in str(gdf.geometry.geom_type.unique()):
        return [{'规则': 'R6-长度一致性', '是否通过': True, '说明': '不适用'}]

    deviations = []
    for i, row in gdf.iterrows():
        try:
            declared = float(row['length']) if pd.notna(row['length']) else None
            actual = row.geometry.length * 111320  # 近似转米
            if declared and actual:
                ratio = declared / max(actual, 1)
                if ratio > 1.05 or ratio < 0.95:
                    deviations.append({
                        '要素ID': i,
                        '声明长度': round(declared, 1),
                        '几何长度': round(actual, 1),
                        '差异': f'{(ratio-1)*100:+.1f}%'
                    })
        except Exception:
            continue

    return [{
        '规则': 'R6-长度一致性',
        '异常数量': len(deviations),
        '异常详情': deviations[:10],
        '是否通过': len(deviations) < len(gdf) * 0.1,
        '说明': f'{len(deviations)}条道路声明的长度与几何长度偏差>5%'
    }]


def check_crs_correctness(gdf, filename):
    """规则7：坐标系是否符合目标"""
    current = str(gdf.crs)
    is_target = TARGET_CRS in current or current == TARGET_CRS
    return [{
        '规则': 'R7-坐标系检查',
        '当前坐标系': current,
        '目标坐标系': TARGET_CRS,
        '是否需要转换': not is_target,
        '是否通过': is_target,
        '说明': f'当前{current}' + ('，符合' if is_target else '，不符合，需转换')
    }]


def check_unique_ids(gdf, filename):
    """规则8：ID字段唯一性"""
    id_col = None
    for col in ['id', 'fid', 'osm_id', 'osmid']:
        if col in gdf.columns:
            id_col = col
            break

    if id_col is None:
        return [{'规则': 'R8-ID唯一性', '是否通过': True, '说明': '无ID字段'}]

    n_unique = gdf[id_col].dropna().nunique()
    n_total = len(gdf)
    has_dupes = n_unique < n_total
    return [{
        '规则': 'R8-ID唯一性',
        '字段': id_col,
        '唯一值数': int(n_unique),
        '总记录数': n_total,
        '是否通过': not has_dupes,
        '说明': f'ID字段"{id_col}"{"有" if has_dupes else "无"}重复'
    }]


def check_attribute_logic(gdf, filename):
    """规则9：属性逻辑一致性（如道路类型与速度上限关系等）"""
    results = [{'规则': 'R9-业务逻辑', '检查项': [], '是否通过': True}]
    # 如果是POI数据，检查category和osm_tag是否一致
    if 'category' in gdf.columns and 'amenity' in gdf.columns:
        food_has_cuisine = 0
        for _, row in gdf.iterrows():
            if row.get('category') == '餐厅' and pd.isna(row.get('cuisine')):
                food_has_cuisine += 1
        if food_has_cuisine > 0:
            results[0]['检查项'].append(f'餐厅中{food_has_cuisine}个缺少cuisine字段')
            results[0]['是否通过'] = False

    if not results[0]['检查项']:
        results[0]['检查项'].append('无异常')

    return results


def run():
    print('=' * 60)
    print(f'  脚本03：数据质量检查（9条规则）')
    print(f'  时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 60)

    all_qc = []
    checked_files = 0
    total_issues = 0

    for fname in sorted(os.listdir(VECTOR_DIR)):
        ext = os.path.splitext(fname)[1].lower()
        if ext not in ['.shp', '.geojson', '.gpkg', '.kml']:
            continue
        try:
            gdf = gpd.read_file(os.path.join(VECTOR_DIR, fname))
        except Exception as e:
            print(f'\n  文件: {fname} | 状态: 无法读取 - {e}')
            all_qc.append({
                '文件名': fname,
                '状态': f'读取失败: {e}',
                '总体通过': False
            })
            continue

        checked_files += 1
        file_result = {
            '文件名': fname,
            '要素数量': len(gdf),
            '几何类型': [t for t in gdf.geometry.geom_type.unique()],
            '检查时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            '检查结果': []
        }

        print(f'\n  {fname} ({len(gdf)} 个要素)')
        print('  ' + '-' * 50)

        # 执行9条规则
        rules = [
            ('R1', 'NULL比例', check_null_ratio),
            ('R2', '域值范围', check_domain_values),
            ('R3', '几何有效性', check_geometry_validity),
            ('R4', '面重叠检查', check_polygon_overlap),
            ('R5', '线自相交检查', check_line_self_intersection),
            ('R6', '长度一致性', check_road_length_consistency),
            ('R7', '坐标系检查', check_crs_correctness),
            ('R8', 'ID唯一性', check_unique_ids),
            ('R9', '业务逻辑', check_attribute_logic),
        ]

        for rid, rname, func in rules:
            results = func(gdf, fname)
            for r in results:
                status = 'PASS' if r.get('是否通过') else 'FAIL'
                print(f'    [{status}] {rid} {rname}: {r.get("说明", "")}')
                r['规则编号'] = rid
                r['规则名称'] = rname
                file_result['检查结果'].append(r)
                if not r.get('是否通过'):
                    total_issues += 1

        # 汇总
        fails = sum(1 for r in file_result['检查结果'] if not r.get('是否通过'))
        file_result['未通过规则数'] = fails
        file_result['总体通过'] = fails == 0
        print(f'  {"=" * 50}')
        print(f'  {"[PASS] 全部通过" if fails == 0 else f"[FAIL] {fails}条规则未通过"}')

        all_qc.append(file_result)

    # 保存报告
    report_path = os.path.join(REPORT_DIR, '02_质检结果.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(all_qc, f, ensure_ascii=False, indent=2, default=str)

    # 打印汇总
    passed = sum(1 for r in all_qc if r.get('总体通过'))
    print(f'\n{"=" * 60}')
    print(f'  质检完成: {checked_files}个文件, {passed}/{checked_files}通过')
    print(f'  发现{total_issues}个质量问题')
    print(f'  报告: {report_path}')
    print(f'{"=" * 60}')

    return all_qc


if __name__ == '__main__':
    run()
