# 上海城市地理数据治理平台

GIS 数据自动化处理流水线 —— 从原始数据到成果地图的全流程演示项目。

## 项目概述

以 OpenStreetMap 上海中心城区真实数据（6万+条道路/建筑/POI）为数据源，构建了一套完整的 GIS 数据处理流水线，覆盖：数据摸底 → 质量检查 → 自动修复 → 坐标系统一 → 入库 → GeoServer 地图服务发布 → 报告生成 → 地图展示。

## 功能模块

| 步骤 | 脚本 | 功能 |
|------|------|------|
| 01 | `scripts/01_获取数据.py` | 从 OSM 拉取上海中心城区数据 + 构造三种脏数据 |
| 02 | `scripts/02_数据摸底.py` | 扫描所有文件，输出基本信息 |
| 03 | `scripts/03_质量检查.py` | 9 条质检规则：属性 / 几何 / 拓扑 / 业务逻辑 |
| 04 | `scripts/04_数据修复.py` | 几何修复、NULL 填充、坐标系统一、字段精简 |
| 05 | `scripts/05_数据入库.py` | 支持 PostGIS 入库，不可用时自动降级为本地文件 |
| 06 | `scripts/06_生成报告.py` | 输出 Excel 格式质检报告（6 个 Sheet） |
| 07 | `scripts/07_自动发布GeoServer.py` | 调用 GeoServer REST API，批量扫描 shapefile 自动创建工作区 + 数据存储 + 发布图层 |
| —– | `scripts/运行全流程.py` | 一键运行全部流程 |

## 质检规则

9 条规则覆盖三大维度：

- **属性维度**：R1 NULL 比例检查、R2 域值合法性、R8 ID 唯一性
- **空间维度**：R3 几何有效性、R4 面重叠检查、R5 线自相交检查
- **逻辑维度**：R6 道路长度一致性、R7 坐标系检查、R9 业务逻辑

## 数据说明

| 数据 | 来源 | 数量 |
|------|------|------|
| 上海道路 | OSM 中心城区 | 18,814 条 |
| 上海建筑 | OSM 中心城区 | 45,202 个 |
| 上海 POI | OSM（学校/医院/餐厅） | 2,537 个 |
| 上海 DEM | SRTM 90m | 3871×3434 |
| 脏数据（CRS错误） | 模拟 | 5 个学校 |
| 脏数据（几何无效） | 模拟 | 7 个面 |
| 脏数据（属性NULL） | 模拟 | 20 条道路 |

## 项目结构

```
├── 原始数据/          ← OSM真实数据 + 模拟脏数据
│   ├── 矢量/
│   └── 栅格/
├── 处理中/            ← 标准化后的中间文件
├── 成果数据/          ← 最终交付的 GeoJSON
├── 质检报告/          ← JSON 日志 + Excel 报告
├── 成果展示/
│   └── index.html     ← Leaflet 交互式地图
└── scripts/           ← 全部 Python 脚本
```

## 技术栈

- **Python**：geopandas / rasterio / shapely / osmnx / xarray
- **数据库**：PostgreSQL + PostGIS（可选，支持本地文件模式）
- **地图服务**：GeoServer（WMS/WFS/REST API 批量发布）
- **前端展示**：Leaflet + OSM 底图 + WFS 实时加载

## 快速开始

```bash
# 1. 安装依赖
pip install geopandas rasterio shapely osmnx openpyxl xarray

# 2. 一键运行
cd scripts
python 运行全流程.py

# 3. 查看成果
# 浏览器打开  成果展示/index.html
# Excel 打开  质检报告/数据处理报告.xlsx
```

## 成果展示

打开 `成果展示/index.html` 查看 Leaflet 交互式地图：

- 道路网络（红色）
- 建筑物分布（蓝色，抽样显示）
- POI 点位（按类别着色）

## 演示亮点

1. 打开 `成果展示/index.html` → 展示 Leaflet 地图（数据通过 WFS 从 GeoServer 实时拉取）
2. 打开 `质检报告/数据处理报告.xlsx` → 展示 6 个 Sheet 的质检报告
3. 打开 `scripts/03_质量检查.py` → 讲解 9 条质检规则的设计逻辑
4. 运行 `python scripts/07_自动发布GeoServer.py` → 演示 REST API 批量发布，3 秒完成全部图层
5. 打开 `http://localhost:8080/geoserver` → 查看已发布的 WMS/WFS 服务

## License

MIT
