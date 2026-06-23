# 03 技术架构设计

> 与决策 D-013（D-013: 6 层架构）一致。

## 1. 架构分层

```
┌─────────────────────────────────────────────────────┐
│  UI Layer (PySide6)                                  │
│  - widgets, viewmodels, dialogs, resources           │
├─────────────────────────────────────────────────────┤
│  Controller Layer                                    │
│  - 接收 UI 事件，调用 Service，转换结果              │
├─────────────────────────────────────────────────────┤
│  Service Layer                                       │
│  - 业务用例编排，事务边界                             │
├─────────────────────────────────────────────────────┤
│  Engine Layer                                        │
│  - 纯函数式算法（可独立测试）                        │
│  - Spectrum / Color / Gamut / Optimization          │
├─────────────────────────────────────────────────────┤
│  Repository Layer                                    │
│  - 数据访问抽象，ORM 包装                            │
├─────────────────────────────────────────────────────┤
│  Database Layer (SQLite + SQLAlchemy)                │
└─────────────────────────────────────────────────────┘
```

## 2. 模块划分

| 包 | 职责 |
|----|------|
| `colorlab_pro.config` | 全局配置、路径、单位 |
| `colorlab_pro.ui` | Qt UI（widgets, viewmodels, dialogs, resources） |
| `colorlab_pro.controllers` | UI ↔ Service 桥接 |
| `colorlab_pro.services` | 业务用例（导入、计算、优化、报告） |
| `colorlab_pro.engines` | 纯算法模块 |
| `colorlab_pro.repositories` | 数据访问 |
| `colorlab_pro.database` | ORM 模型、会话工厂、迁移 |
| `colorlab_pro.dto` | 数据传输对象（dataclass） |
| `colorlab_pro.importers` | 文件格式解析 |
| `colorlab_pro.exporters` | 文件输出 |
| `colorlab_pro.utils` | 通用工具（日志、验证、错误） |

## 3. 关键依赖（D-014, D-015, D-020）

- **D-014**: SQLAlchemy 2.0+ ORM
- **D-015**: shapely 2.0+ 用于几何运算
- **D-020**: src 布局（src/colorlab_pro/）

## 4. 并发模型

- UI 线程：所有 Qt 操作
- 计算线程：QThreadPool + QRunnable
- 计算结果通过 Signal/Slot 回到 UI 线程
- 全局 QApplication 维护一个 Logger

## 5. 配置与路径

- `~/.colorlab_pro/config.yaml` —— 用户配置
- `data/user/` —— 用户数据
- `data/cache/` —— 计算缓存
- `resources/reference_data/` —— 内置参考数据（CIE 1931 等）