# -*- coding: utf-8 -*-
"""
脚本02：数据摸底检查
功能：扫描原始数据文件夹，统计每个文件的基本信息
输出：摸底检查结果 JSON
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import geopandas as gpd
import rasterio
import json
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTOR_DIR = os.path.join(BASE_DIR, '原始数据', '矢量')
RASTER_DIR = os.path.join(BASE_DIR, '原始数据', '栅格')
REPORT_DIR = os.path.join(BASE_DIR, '质检报告')

os.makedirs(REPORT_DIR, exist_ok=True)


def check_vector(filepath):
    """扫描一个矢量文件，返回基本信息"""
    result = {'文件名': os.path.basename(filepath)}
    try:
        gdf = gpd.read_file(filepath)
        result['类型'] = '矢量'
        result['要素数量'] = len(gdf)
        result['几何类型'] = [t for t in gdf.geometry.geom_type.unique() if t] if len(gdf) > 0 else []
        result['坐标系'] = str(gdf.crs)
        result['字段列表'] = [c for c in gdf.columns if c != 'geometry']

        # NULL 统计
        nulls = {}
        for col in gdf.columns:
            if col == 'geometry':
                continue
            n = int(gdf[col].isna().sum())
            if n > 0:
                nulls[col] = {'数量': n, '比例': f'{n/len(gdf)*100:.1f}%'}
        result['NULL统计'] = nulls

        # 坐标范围
        bounds = gdf.total_bounds
        result['空间范围'] = {
            'xmin': round(float(bounds[0]), 4),
            'ymin': round(float(bounds[1]), 4),
            'xmax': round(float(bounds[2]), 4),
            'ymax': round(float(bounds[3]), 4)
        }
        result['状态'] = '正常'
    except Exception as e:
        result['状态'] = f'读取失败: {e}'

    return result


def check_raster(filepath):
    """扫描一个栅格文件，返回基本信息"""
    result = {'文件名': os.path.basename(filepath)}
    try:
        with rasterio.open(filepath) as src:
            data = src.read(1).astype(float)
            nodata = src.nodata
            valid = data[data != nodata] if nodata else data.flatten()
            result['类型'] = '栅格'
            result['尺寸'] = f'{src.width} x {src.height}'
            result['波段数'] = src.count
            result['坐标系'] = str(src.crs)
            result['分辨率'] = [round(r, 6) for r in src.res]
            result['NoData值'] = nodata
            result['值域'] = {
                '最小值': round(float(valid.min()), 2),
                '最大值': round(float(valid.max()), 2)
            }
            result['状态'] = '正常'
    except Exception as e:
        result['状态'] = f'读取失败: {e}'
    return result


def run():
    print('=' * 60)
    print(f'  脚本02：数据摸底检查')
    print(f'  时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 60)

    all_results = []

    # --- 矢量 ---
    print('\n[1] 矢量数据')
    for fname in sorted(os.listdir(VECTOR_DIR)):
        ext = os.path.splitext(fname)[1].lower()
        if ext in ['.shp', '.geojson', '.kml', '.gpkg']:
            fpath = os.path.join(VECTOR_DIR, fname)
            r = check_vector(fpath)
            all_results.append(r)
            print(f'\n  文件: {r["文件名"]}')
            print(f'    类型: {r.get("类型")} | 要素: {r.get("要素数量")} | '
                  f'几何: {r.get("几何类型")}')
            print(f'    坐标系: {r.get("坐标系")}')
            print(f'    空间范围: {r.get("空间范围")}')
            nulls = r.get('NULL统计', {})
            if nulls:
                for col, info in nulls.items():
                    print(f'    [NULL] {col}: {info["数量"]}个 ({info["比例"]})')
            print(f'    状态: {r["状态"]}')

    # --- 栅格 ---
    print('\n[2] 栅格数据')
    for fname in sorted(os.listdir(RASTER_DIR)):
        if fname.lower().endswith(('.tif', '.tiff', '.img')):
            fpath = os.path.join(RASTER_DIR, fname)
            r = check_raster(fpath)
            all_results.append(r)
            print(f'\n  文件: {r["文件名"]}')
            print(f'    类型: {r.get("类型")} | 尺寸: {r.get("尺寸")} | '
                  f'波段: {r.get("波段数")}')
            print(f'    坐标系: {r.get("坐标系")}')
            print(f'    分辨率: {r.get("分辨率")}')
            print(f'    值域: {r.get("值域")}')
            print(f'    状态: {r["状态"]}')

    # --- 保存 ---
    report_path = os.path.join(REPORT_DIR, '01_摸底检查.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)

    print(f'\n{"=" * 60}')
    print(f'  检查完成: {len(all_results)} 个文件')
    print(f'  报告已保存: {report_path}')
    print(f'{"=" * 60}')
    return all_results


if __name__ == '__main__':
    run()
