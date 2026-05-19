# -*- coding: utf-8 -*-
"""
脚本04：数据修复与标准化转换
功能：修复质检发现的问题 → 坐标系统一 → 属性规范化 → 输出标准数据
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import geopandas as gpd
import json
import numpy as np
from datetime import datetime
from shapely.validation import make_valid

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTOR_DIR = os.path.join(BASE_DIR, '原始数据', '矢量')
RASTER_DIR = os.path.join(BASE_DIR, '原始数据', '栅格')
OUTPUT_DIR = os.path.join(BASE_DIR, '处理中')
RESULT_DIR = os.path.join(BASE_DIR, '成果数据')
REPORT_DIR = os.path.join(BASE_DIR, '质检报告')

TARGET_CRS = 'EPSG:4326'

for d in [OUTPUT_DIR, RESULT_DIR, REPORT_DIR]:
    os.makedirs(d, exist_ok=True)


def fix_geometry(gdf):
    """修复无效几何"""
    fixed = 0
    for idx in gdf.index:
        geom = gdf.at[idx, 'geometry']
        if geom is not None and not geom.is_empty and not geom.is_valid:
            gdf.at[idx, 'geometry'] = make_valid(geom)
            fixed += 1
    return gdf, fixed


def fix_nulls(gdf):
    """填充NULL值：字符串填'未知'，数值填0"""
    filled = {}
    for col in gdf.columns:
        if col == 'geometry':
            continue
        null_count = int(gdf[col].isna().sum())
        if null_count > 0:
            if gdf[col].dtype == object:
                gdf[col] = gdf[col].fillna('未知')
            else:
                gdf[col] = gdf[col].fillna(0)
            filled[col] = null_count
    return gdf, filled


def standardize_crs(gdf):
    """统一坐标系到 WGS84"""
    current = str(gdf.crs)
    if TARGET_CRS not in current and current != TARGET_CRS:
        gdf = gdf.to_crs(TARGET_CRS)
        return gdf, True, current
    return gdf, False, current


def clean_fields(gdf):
    """清理冗余字段（保留核心字段，去掉 OSM 元数据噪音）"""
    # 保留优先字段
    keep_patterns = ['id', 'name', 'length', 'type', 'highway', 'building', 'category',
                     'geometry', '名称', '类型', '道路名称', '道路类型', '车道数',
                     '学校名称', '区名', '面积', '建校年代', '入库时间', '数据来源',
                     'osm_tag', 'road_name', 'road_type']
    cols_to_keep = []
    for col in gdf.columns:
        for pat in keep_patterns:
            if pat in col.lower() or pat in col:
                cols_to_keep.append(col)
                break
    if 'geometry' not in cols_to_keep:
        cols_to_keep.append('geometry')
    # 保留至少 id, geometry
    cols_to_keep = list(set(cols_to_keep))
    return gdf[cols_to_keep]


def process_raster():
    """处理栅格：统一 NoData 值"""
    records = []
    for fname in sorted(os.listdir(RASTER_DIR)):
        if not fname.lower().endswith(('.tif', '.tiff', '.img')):
            continue
        fpath = os.path.join(RASTER_DIR, fname)

        import rasterio
        with rasterio.open(fpath) as src:
            meta = src.meta.copy()
            data = src.read(1).astype(np.float32)
            nodata = src.nodata

        # 统一 NoData 为 -9999
        if nodata and nodata != -9999:
            data = np.where(np.isclose(data, nodata), -9999, data)

        meta.update({'dtype': 'float32', 'nodata': -9999})
        out_path = os.path.join(OUTPUT_DIR, fname.replace('.img', '.tif'))
        with rasterio.open(out_path, 'w', **meta) as dst:
            dst.write(data, 1)

        records.append({
            '文件': fname,
            '输出': os.path.basename(out_path),
            '处理': 'NoData值统一为-9999'
        })
        print(f'  [OK] 栅格 {fname} -> 处理完成')

    return records


def run():
    print('=' * 60)
    print(f'  脚本04：数据修复与标准化')
    print(f'  时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 60)

    conversion_log = []

    # ---- 矢量处理 ----
    print('\n[1] 矢量数据修复')
    for fname in sorted(os.listdir(VECTOR_DIR)):
        ext = os.path.splitext(fname)[1].lower()
        if ext not in ['.shp', '.geojson', '.gpkg', '.kml']:
            continue

        fpath = os.path.join(VECTOR_DIR, fname)
        print(f'\n  {fname}')

        try:
            gdf = gpd.read_file(fpath)
        except Exception as e:
            print(f'    [FAIL] 无法读取: {e}')
            continue

        log = {'文件名': fname, '原始要素数': len(gdf), '处理记录': []}

        # 1. 几何修复
        gdf, fixed = fix_geometry(gdf)
        if fixed > 0:
            log['处理记录'].append(f'修复无效几何：{fixed}个')
            print(f'    修复无效几何: {fixed}个')

        # 2. NULL填充
        gdf, filled = fix_nulls(gdf)
        if filled:
            fields_str = ', '.join(f'{k}({v})' for k, v in filled.items())
            log['处理记录'].append(f'填充NULL: {fields_str}')
            print(f'    填充NULL: {fields_str}')

        # 3. 坐标系统一
        gdf, converted, orig_crs = standardize_crs(gdf)
        if converted:
            log['处理记录'].append(f'坐标系转换: {orig_crs} -> {TARGET_CRS}')
            print(f'    坐标系转换: {orig_crs} -> {TARGET_CRS}')
        else:
            print(f'    坐标系: {orig_crs} (符合目标)')

        # 4. 字段精简
        gdf = clean_fields(gdf)

        # 5. 添加元数据
        gdf['入库时间'] = datetime.now().strftime('%Y-%m-%d')
        gdf['数据来源'] = fname

        # 6. 保存
        out_name = os.path.splitext(fname)[0] + '_std.geojson'
        out_path = os.path.join(OUTPUT_DIR, out_name)
        gdf.to_file(out_path, driver='GeoJSON')
        log['输出文件'] = out_name
        log['输出要素数'] = len(gdf)

        conversion_log.append(log)
        print(f'    输出: {out_name} ({len(gdf)}要素)')

    # ---- 栅格处理 ----
    print('\n[2] 栅格数据处理')
    raster_logs = process_raster()
    conversion_log.extend(raster_logs)

    # ---- 生成成果数据 ----
    print('\n[3] 生成最终成果数据')
    # 把矢量处理后的文件复制到成果数据
    for fname in sorted(os.listdir(OUTPUT_DIR)):
        if fname.endswith('.geojson'):
            src = os.path.join(OUTPUT_DIR, fname)
            dst = os.path.join(RESULT_DIR, fname.replace('_std', ''))
            gdf = gpd.read_file(src)
            gdf.to_file(dst, driver='GeoJSON')
            print(f'  [OK] {os.path.basename(dst)}')

    # ---- 保存日志 ----
    log_path = os.path.join(REPORT_DIR, '03_修复日志.json')
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(conversion_log, f, ensure_ascii=False, indent=2, default=str)

    print(f'\n{"=" * 60}')
    print(f'  修复完成: {len(conversion_log)} 个文件已标准化')
    print(f'  日志: {log_path}')
    print(f'{"=" * 60}')

    return conversion_log


if __name__ == '__main__':
    run()
