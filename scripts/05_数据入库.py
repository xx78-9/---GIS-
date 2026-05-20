# -*- coding: utf-8 -*-
"""
脚本05：数据入库
功能：将标准化后的数据导入 PostGIS 数据库
说明：需先安装 PostgreSQL + PostGIS 扩展，并创建数据库
      如果数据库不可用，自动降级为本地文件模式
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import geopandas as gpd
import json
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DIR = os.path.join(BASE_DIR, '处理中')
RESULT_DIR = os.path.join(BASE_DIR, '成果数据')
REPORT_DIR = os.path.join(BASE_DIR, '质检报告')

os.makedirs(REPORT_DIR, exist_ok=True)

# 改这里为你的 PostgreSQL 配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'gis_practice',
    'user': 'postgres',
    'password': '123456'
}

TABLE_MAPPING = {
    'shanghai_roads_std.geojson': 'tb_上海道路',
    'shanghai_buildings_std.geojson': 'tb_上海建筑',
    'shanghai_poi_std.geojson': 'tb_上海POI',
    'corrupt_crs_std.geojson': 'tb_学校_已修复',
    'corrupt_geometry_std.geojson': 'tb_行政区_已修复',
    'corrupt_nulls_std.geojson': 'tb_道路_已修复',
}


def try_postgis_import():
    """尝试导入到 PostGIS，如果不可用则返回False"""
    try:
        from sqlalchemy import create_engine, text
        url = (f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
               f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
        engine = create_engine(url)

        # 测试连接
        with engine.connect() as conn:
            result = conn.execute(text("SELECT PostGIS_Full_Version()"))
            version = result.scalar()
            print(f'  [OK] PostGIS 连接成功: {version[:80]}')

        return engine
    except Exception as e:
        print(f'  [INFO] PostGIS 不可用 ({e})，切换到本地文件模式')
        return None


def import_to_postgis(filepath, table_name, engine):
    """导入矢量到PostGIS"""
    gdf = gpd.read_file(filepath)
    gdf['入库时间'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    gdf.to_postgis(table_name, engine, if_exists='replace', index=False)
    return len(gdf)


def import_local_mode(filepath, table_name):
    """本地文件模式：直接保存到成果目录"""
    gdf = gpd.read_file(filepath)
    out_name = table_name + '.geojson'
    out_path = os.path.join(RESULT_DIR, out_name)
    gdf.to_file(out_path, driver='GeoJSON')
    return len(gdf), out_name


def run():
    print('=' * 60)
    print(f'  脚本05：数据入库')
    print(f'  时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 60)

    engine = try_postgis_import()
    use_postgis = engine is not None
    mode_text = 'PostGIS' if use_postgis else '本地文件'

    print(f'\n  入库模式: {mode_text}')
    print()

    import_log = []

    for fname, table_name in TABLE_MAPPING.items():
        fpath = os.path.join(INPUT_DIR, fname)
        if not os.path.exists(fpath):
            print(f'  [SKIP] {fname} 不存在')
            continue

        try:
            if use_postgis:
                count = import_to_postgis(fpath, table_name, engine)
                print(f'  [OK] {fname} -> {table_name}: {count}条')
                import_log.append({
                    '文件': fname, '目标': table_name, '记录数': count,
                    '模式': 'PostGIS', '状态': '成功'
                })
            else:
                count, out_name = import_local_mode(fpath, table_name)
                print(f'  [OK] {fname} -> {out_name}: {count}条')
                import_log.append({
                    '文件': fname, '目标': out_name, '记录数': count,
                    '模式': '本地文件', '状态': '成功'
                })
        except Exception as e:
            print(f'  [FAIL] {fname}: {e}')
            import_log.append({
                '文件': fname, '目标': table_name,
                '状态': f'失败: {e}'
            })

    # 如果是 PostGIS 模式，验证入库
    if use_postgis:
        print('\n  验证入库结果:')
        from sqlalchemy import text
        with engine.connect() as conn:
            for log in import_log:
                if log.get('状态') == '成功':
                    try:
                        result = conn.execute(text(f"SELECT COUNT(*) FROM \"{log['目标']}\""))
                        count = result.scalar()
                        print(f'    表 {log["目标"]}: {count} 条 [OK]')
                    except Exception as e:
                        print(f'    表 {log["目标"]}: 验证失败 - {e}')

    # 保存日志
    log_path = os.path.join(REPORT_DIR, '04_入库日志.json')
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(import_log, f, ensure_ascii=False, indent=2, default=str)

    ok_count = sum(1 for l in import_log if l.get('状态') == '成功')
    print(f'\n{"=" * 60}')
    print(f'  入库完成: {ok_count}/{len(import_log)} 成功 ({mode_text})')
    print(f'  日志: {log_path}')
    print(f'{"=" * 60}')

    return import_log


if __name__ == '__main__':
    run()
