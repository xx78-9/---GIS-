# -*- coding: utf-8 -*-
"""
脚本01：获取真实数据 + 构造脏数据
数据源：OpenStreetMap（上海中心城区）
脏数据：用于后续质检展示——坐标系错误、几何无效、属性NULL
如果数据已存在则跳过耗时下载
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point, Polygon, LineString
import osmnx as ox
import shutil
import random

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTOR_OUT = os.path.join(BASE_DIR, '原始数据', '矢量')
RASTER_OUT = os.path.join(BASE_DIR, '原始数据', '栅格')

for d in [VECTOR_OUT, RASTER_OUT]:
    os.makedirs(d, exist_ok=True)

print('=' * 60)
print('  脚本01：获取数据')
print('=' * 60)

# ============================================================
# 1. 从 OSM 拉取上海中心城区数据（使用指定bbox，避免超时）
# ============================================================
print('\n[1] 从 OpenStreetMap 下载上海中心城区数据...')

# 上海中心城区范围（黄浦江沿线，约 12km x 10km）
NORTH, SOUTH, EAST, WEST = 31.30, 31.17, 121.55, 121.40
bbox = (WEST, SOUTH, EAST, NORTH)

try:
    print('  下载路网...')
    roads_graph = ox.graph_from_bbox(bbox=(WEST, SOUTH, EAST, NORTH), network_type='drive')
    roads_gdf = ox.convert.graph_to_gdfs(roads_graph, nodes=False, edges=True)
    roads_gdf = roads_gdf.reset_index(drop=True)
    roads_gdf.to_file(os.path.join(VECTOR_OUT, 'shanghai_roads.geojson'), driver='GeoJSON')
    print(f'  [OK] 道路：{len(roads_gdf)} 条 -> shanghai_roads.geojson')
except Exception as e:
    print(f'  [FAIL] 道路下载失败: {e}')
    # 创建备用数据
    print('  使用备用模拟数据...')
    lines = []
    for _ in range(200):
        x = random.uniform(121.40, 121.55)
        y = random.uniform(31.17, 31.30)
        lines.append(LineString([(x,y), (x+random.uniform(0.001,0.01), y+random.uniform(0.001,0.01))]))
    roads_gdf = gpd.GeoDataFrame({
        'id': range(200),
        'name': [f'上海路_{i}' for i in range(200)],
        'highway': [random.choice(['primary','secondary','tertiary','residential']) for _ in range(200)],
        'length': [round(l.length*111320, 2) for l in lines],
        'geometry': lines
    }, crs='EPSG:4326')
    roads_gdf.to_file(os.path.join(VECTOR_OUT, 'shanghai_roads.geojson'), driver='GeoJSON')
    print(f'  [OK] 备用道路数据：{len(roads_gdf)} 条')

try:
    print('  下载建筑物...')
    buildings = ox.features_from_bbox(bbox=(WEST, SOUTH, EAST, NORTH), tags={'building': True})
    if len(buildings) > 0:
        buildings = buildings.reset_index(drop=True)
        buildings.to_file(os.path.join(VECTOR_OUT, 'shanghai_buildings.geojson'), driver='GeoJSON')
        print(f'  [OK] 建筑物：{len(buildings)} 个 -> shanghai_buildings.geojson')
    else:
        raise Exception('无建筑物数据')
except Exception as e:
    print(f'  [FAIL] 建筑物下载失败: {e}')
    print('  使用备用模拟数据...')
    polys = []
    for _ in range(500):
        x, y = random.uniform(121.40, 121.55), random.uniform(31.17, 31.30)
        s = random.uniform(0.0005, 0.003)
        polys.append(Polygon([(x,y),(x+s,y),(x+s,y+s),(x,y+s)]))
    buildings = gpd.GeoDataFrame({
        'id': range(500),
        'name': [f'建筑_{i}' for i in range(500)],
        'building': ['yes'] * 500,
        'geometry': polys
    }, crs='EPSG:4326')
    buildings.to_file(os.path.join(VECTOR_OUT, 'shanghai_buildings.geojson'), driver='GeoJSON')
    print(f'  [OK] 备用建筑物数据：{len(buildings)} 个')

try:
    print('  下载POI数据...')
    all_pois = []
    # 学校
    schools = ox.features_from_bbox(bbox=(WEST, SOUTH, EAST, NORTH), tags={'amenity': 'school'})
    if len(schools) > 0:
        schools = schools.reset_index(drop=True)
        schools['category'] = '学校'
        all_pois.append(schools)
        print(f'    学校：{len(schools)} 个')

    # 医院
    hospitals = ox.features_from_bbox(bbox=(WEST, SOUTH, EAST, NORTH), tags={'amenity': 'hospital'})
    if len(hospitals) > 0:
        hospitals = hospitals.reset_index(drop=True)
        hospitals['category'] = '医院'
        all_pois.append(hospitals)
        print(f'    医院：{len(hospitals)} 个')

    # 餐馆
    restaurants = ox.features_from_bbox(bbox=(WEST, SOUTH, EAST, NORTH), tags={'amenity': 'restaurant'})
    if len(restaurants) > 0:
        restaurants = restaurants.reset_index(drop=True)
        restaurants['category'] = '餐厅'
        all_pois.append(restaurants)
        print(f'    餐厅：{len(restaurants)} 个')

    if all_pois:
        poi_gdf = gpd.GeoDataFrame(pd.concat(all_pois, ignore_index=True), crs=all_pois[0].crs)
        poi_gdf.to_file(os.path.join(VECTOR_OUT, 'shanghai_poi.geojson'), driver='GeoJSON')
        print(f'  [OK] POI总计：{len(poi_gdf)} 个 -> shanghai_poi.geojson')
    else:
        raise Exception('无POI数据')
except Exception as e:
    print(f'  [FAIL] POI下载失败: {e}')
    print('  使用备用模拟数据...')
    points = [Point(random.uniform(121.40, 121.55), random.uniform(31.17, 31.30)) for _ in range(100)]
    poi_gdf = gpd.GeoDataFrame({
        'id': range(100),
        'name': [f'POI_{i}' if i%5!=0 else None for i in range(100)],
        'category': [random.choice(['学校','医院','餐厅']) for _ in range(100)],
        'geometry': points
    }, crs='EPSG:4326')
    poi_gdf.to_file(os.path.join(VECTOR_OUT, 'shanghai_poi.geojson'), driver='GeoJSON')
    print(f'  [OK] 备用POI数据：{len(poi_gdf)} 个')

# ============================================================
# 2. 复制高程数据
# ============================================================
print('\n[2] 复制栅格数据...')
dem_src = os.path.join(BASE_DIR, '..', 'xx', 'dem_上海.tif')
if os.path.exists(dem_src):
    shutil.copy(dem_src, os.path.join(RASTER_OUT, 'shanghai_dem.tif'))
    print(f'  [OK] 高程数据 -> shanghai_dem.tif')
else:
    # 创建一个简单的假DEM
    import rasterio
    from rasterio.transform import from_bounds
    arr = np.random.randint(0, 100, (500, 500)).astype('float32')
    dem_path = os.path.join(RASTER_OUT, 'shanghai_dem.tif')
    transform = from_bounds(WEST, SOUTH, EAST, NORTH, 500, 500)
    with rasterio.open(dem_path, 'w', driver='GTiff', width=500, height=500,
                       count=1, dtype='float32', crs='EPSG:4326', transform=transform, nodata=-9999) as dst:
        dst.write(arr, 1)
    print(f'  [WARN] 未找到真实DEM，使用模拟数据 -> shanghai_dem.tif')

# ============================================================
# 3. 构造脏数据（故意带问题，质检展示用）
# ============================================================
print('\n[3] 构造带问题的测试数据...')

# 3.1 坐标系错了的学校（北京54坐标系）
print('  造：坐标系错误的学校数据...')
dirty_schools = gpd.GeoDataFrame({
    'id': [1, 2, 3, 4, 5],
    'name': ['同济大学', '复旦大学', '上海交大', None, '华东师大'],  # 故意NULL
    '建校年代': [1907, 1905, 1896, 1951, 1951],
    '面积_m2': [2500000, 3000000, 2800000, 1800000, 1200000],
    'geometry': [
        Point(121.506, 31.286), Point(121.502, 31.298),
        Point(121.437, 31.027), Point(121.218, 31.237),
        Point(121.453, 31.230)
    ]
}, crs='EPSG:4214')
dirty_schools.to_file(os.path.join(VECTOR_OUT, 'corrupt_crs.geojson'), driver='GeoJSON')
print(f'  [OK] 5个学校，坐标系为北京54（应转换为WGS84）')

# 3.2 有自相交面的行政区
print('  造：包含自相交面的行政区数据...')
polys = []
for i in range(6):
    x = random.uniform(121.0, 121.5)
    y = random.uniform(31.0, 31.3)
    s = random.uniform(0.02, 0.05)
    polys.append(Polygon([(x,y), (x+s,y), (x+s,y+s), (x,y+s)]))

# 自相交蝴蝶结
bowtie = Polygon([(121.5, 31.2), (121.6, 31.3), (121.5, 31.3), (121.6, 31.2)])
polys.append(bowtie)

dirty_districts = gpd.GeoDataFrame({
    'id': list(range(7)),
    '区名': [f'区域_{i}' for i in range(7)],
    '类型': [random.choice(['商业', '住宅', '工业', '绿地']) for _ in range(7)],
    'geometry': polys
}, crs='EPSG:4326')
dirty_districts.to_file(os.path.join(VECTOR_OUT, 'corrupt_geometry.geojson'), driver='GeoJSON')
print(f'  [OK] 7个面，第7个为自相交（蝴蝶结形状）')

# 3.3 大量NULL的道路数据
print('  造：大量NULL的道路数据...')
lines = []
for i in range(20):
    x1, y1 = random.uniform(121.40, 121.55), random.uniform(31.17, 31.30)
    x2, y2 = x1 + random.uniform(0.005, 0.03), y1 + random.uniform(0.005, 0.03)
    lines.append(LineString([(x1, y1), (x2, y2)]))

dirty_roads = gpd.GeoDataFrame({
    'id': range(20),
    'road_name': [f'道路_{i}' if i % 3 != 0 else None for i in range(20)],
    'road_type': [random.choice(['主干道', '次干道', '支路']) if i % 4 != 0 else None for i in range(20)],
    '车道数': [random.choice([2, 4, 6]) if i % 5 != 0 else None for i in range(20)],
    'geometry': lines
}, crs='EPSG:4326')
dirty_roads.to_file(os.path.join(VECTOR_OUT, 'corrupt_nulls.geojson'), driver='GeoJSON')
print(f'  [OK] 20条道路，name/type/车道数有大量NULL')

# ============================================================
# 4. 汇总
# ============================================================
print('\n' + '=' * 60)
print('  数据准备完成！')
print('=' * 60)
print(f'\n原始数据/矢量/ 包含：')
for f in sorted(os.listdir(VECTOR_OUT)):
    size_kb = os.path.getsize(os.path.join(VECTOR_OUT, f)) / 1024
    print(f'  {f:40s} ({size_kb:6.0f} KB)')

print(f'\n原始数据/栅格/ 包含：')
if os.path.exists(RASTER_OUT):
    for f in sorted(os.listdir(RASTER_OUT)):
        size_kb = os.path.getsize(os.path.join(RASTER_OUT, f)) / 1024
        print(f'  {f:40s} ({size_kb:6.0f} KB)')
