# 06 数据库设计与数据字典

> 与 D-014（SQLAlchemy）、D-018（spectrum + spectrum_point 表分离）一致。

## 1. 数据库

- 引擎：SQLite（单用户）
- ORM：SQLAlchemy 2.0+
- 路径：`data/user/<project_hash>/colorlab.db`
- 迁移：手工 SQL（`database/migrations/`）

## 2. 表结构

### 2.1 projects

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| name | TEXT NOT NULL | 工程名 |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |
| description | TEXT | |

### 2.2 spectra（元数据表，D-018）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| project_id | INTEGER FK | |
| name | TEXT | 用户命名 |
| unit | TEXT | 见 04 §1 |
| source | TEXT | "import" / "calculated" / "optimized" |
| channel | TEXT | 通道类型（详见 04 §2.3） |
| wavelength_min | REAL | |
| wavelength_max | REAL | |
| wavelength_step | REAL | |
| point_count | INTEGER | |
| created_at | TIMESTAMP | |
| meta_json | TEXT | JSON |

### 2.3 spectrum_points（数值表，D-018）

> 不使用 BLOB 存储完整 numpy 数组（D-018）

| 字段 | 类型 | 说明 |
|------|------|------|
| spectrum_id | INTEGER FK | |
| index | INTEGER | 0-based |
| wavelength | REAL | nm |
| value | REAL | |

复合主键：(spectrum_id, index)

### 2.4 optimizations

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| project_id | INTEGER FK | |
| name | TEXT | |
| target_xy_x | REAL | |
| target_xy_y | REAL | |
| result_json | TEXT | 厚度结果 + 收敛信息 |

## 3. 索引

- `idx_spectra_project (project_id)`
- `idx_points_spectrum (spectrum_id)`

## 4. 备份

- 关闭工程时自动备份到 `data/user/<project_hash>/backups/<timestamp>.db`
- 仅保留最近 5 份