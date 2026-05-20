# -*- coding: utf-8 -*-
"""
GeoServer REST API 批量发布脚本
扫描成果数据/shp/ 目录，自动创建数据存储 + 发布图层
"""

import os
import sys
import requests

# GeoServer 连接
GEOSERVER_URL = "http://localhost:8080/geoserver"
USER = "admin"
PASS = "geoserver"
WORKSPACE = "auto_publish"

SHAPE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         '成果数据', 'shp')

session = requests.Session()
session.auth = (USER, PASS)
session.headers['Content-Type'] = 'text/xml; charset=utf-8'


def gs_post(url, data):
    """POST 请求，处理错误"""
    r = session.post(url, data=data.encode('utf-8'))
    if r.status_code not in (200, 201, 202):
        print(f'  [FAIL] {r.status_code}: {r.text[:200]}')
        return None
    return r


def gs_get(url):
    """GET 请求"""
    return session.get(url)


def gs_delete(url):
    """DELETE 请求"""
    return session.delete(url)


def create_workspace():
    """创建工作区"""
    print(f'[1] 创建工作区: {WORKSPACE}')
    # 先检查是否已存在
    r = gs_get(f'{GEOSERVER_URL}/rest/workspaces/{WORKSPACE}')
    if r.status_code == 200:
        print(f'  工作区已存在，跳过')
        return True

    xml = f'''<workspace>
      <name>{WORKSPACE}</name>
    </workspace>'''
    r = gs_post(f'{GEOSERVER_URL}/rest/workspaces', xml)
    if r is None:
        return False
    print(f'  [OK] 工作区创建成功')
    return True


def create_datastore(shp_name):
    """为 shapefile 创建数据存储"""
    ds_name = shp_name.replace('.shp', '')
    shp_path = os.path.join(SHAPE_DIR, shp_name).replace('\\', '/')

    print(f'   数据存储: {ds_name}')

    # 检查是否已存在
    r = gs_get(f'{GEOSERVER_URL}/rest/workspaces/{WORKSPACE}/datastores/{ds_name}')
    if r.status_code == 200:
        print(f'    已存在，先删除')
        gs_delete(f'{GEOSERVER_URL}/rest/workspaces/{WORKSPACE}/datastores/{ds_name}?recurse=true')

    xml = f'''<dataStore>
      <name>{ds_name}</name>
      <type>Shapefile</type>
      <enabled>true</enabled>
      <connectionParameters>
        <entry key="url">file://{shp_path}</entry>
        <entry key="charset">UTF-8</entry>
        <entry key="create spatial index">true</entry>
      </connectionParameters>
    </dataStore>'''

    r = gs_post(f'{GEOSERVER_URL}/rest/workspaces/{WORKSPACE}/datastores', xml)
    if r is None:
        return False
    print(f'    [OK] 数据存储已创建')
    return True


def publish_layer(shp_name):
    """发布图层（数据存储创建时自动发现图层，这里补全配置）"""
    layer_name = shp_name.replace('.shp', '')

    # 自动计算 BBox
    print(f'   发布图层: {layer_name}')

    xml = f'''<featureType>
      <name>{layer_name}</name>
      <title>{layer_name}</title>
      <enabled>true</enabled>
    </featureType>'''

    url = (f'{GEOSERVER_URL}/rest/workspaces/{WORKSPACE}'
           f'/datastores/{layer_name}/featuretypes')
    r = gs_post(url, xml)
    if r is None:
        # 可能图层已存在（Shapefile 数据存储会自动创建）
        existing = gs_get(url + f'/{layer_name}')
        if existing.status_code == 200:
            print(f'    图层已存在（数据存储自动创建），更新 BBox...')
            # PUT 更新配置
            r = session.put(f'{url}/{layer_name}', data=xml.encode('utf-8'))
            if r.status_code not in (200, 201):
                print(f'    [WARN] 更新返回 {r.status_code}')
            else:
                print(f'    [OK] 图层已更新')
            return True
        return False
    print(f'    [OK] 图层已发布')
    return True


def set_default_style(layer_name, style_name='polygon'):
    """设置图层默认样式"""
    url = (f'{GEOSERVER_URL}/rest/layers/{WORKSPACE}:{layer_name}')
    xml = f'''<layer>
      <defaultStyle>
        <name>{style_name}</name>
      </defaultStyle>
    </layer>'''
    r = session.put(url, data=xml.encode('utf-8'))
    if r.status_code == 200:
        print(f'    样式: {style_name}')
    return True


def main():
    print('=' * 60)
    print('  GeoServer REST API 批量发布')
    print(f'  扫描目录: {SHAPE_DIR}')
    print(f'  工作区: {WORKSPACE}')
    print('=' * 60)

    if not os.path.exists(SHAPE_DIR):
        print(f'[FAIL] 找不到目录: {SHAPE_DIR}')
        return

    shp_files = [f for f in os.listdir(SHAPE_DIR) if f.endswith('.shp')]
    if not shp_files:
        print(f'[FAIL] 目录下没有 .shp 文件')
        return

    print(f'\n发现 {len(shp_files)} 个 shapefile:')
    for f in shp_files:
        print(f'  - {f}')

    # 1. 创建工作区
    if not create_workspace():
        return

    # 2. 逐个发布
    print(f'\n[2] 批量发布图层...')
    success = 0
    for shp_name in shp_files:
        layer_name = shp_name.replace('.shp', '')
        print(f'\n  >> {shp_name}')

        if not create_datastore(shp_name):
            continue
        if not publish_layer(shp_name):
            continue
        # 自动配样式
        if 'roads' in shp_name:
            set_default_style(layer_name, 'line')
        elif 'poi' in shp_name:
            set_default_style(layer_name, 'point')
        else:
            set_default_style(layer_name, 'polygon')
        success += 1

    # 3. 汇总
    print(f'\n{"=" * 60}')
    print(f'  完成！{success}/{len(shp_files)} 个图层已发布')
    print(f'  预览地址: {GEOSERVER_URL}/web/')
    print(f'  工作区: {WORKSPACE}')
    print(f'  WFS 地址: {GEOSERVER_URL}/{WORKSPACE}/ows')
    print(f'{"=" * 60}')


if __name__ == '__main__':
    main()
