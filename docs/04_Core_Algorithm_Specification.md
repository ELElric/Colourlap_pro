# 04 核心算法规范

> 色度科学部分与 `ai_context/DOMAIN_KNOWLEDGE.md` 一致（后者为最终裁定）。

## 1. 光谱数据结构

```
Spectrum:
  wavelengths: np.ndarray[float64]  # 单位 nm
  values:     np.ndarray[float64]  # 任意单位（导入时记录）
  unit:       str                   # "mW/nm" | "counts" | "a.u." | "transmittance"
  meta:       dict                  # 设备、时间、操作者
```

- 标准范围：380–780 nm，1 nm 步长，401 个点
- 任意 5 nm 步长可被插值到 1 nm

## 2. 光谱预处理

### 2.1 归一化

- `peak`：除以最大值
- `area`：除以积分面积
- `unit`：单位转换

### 2.2 插值

- 默认：cubic spline（`scipy.interpolate.CubicSpline`）
- 备选：PCHIP（保留单调性，适合有尖峰的光谱）
- 通道：380–780 nm，1 nm 步长，401 点
- 缺失值：`auto_fill_gaps` 用相邻 5 点线性插值填补

### 2.3 通道检测

通过 **特征峰位置**判断光谱来源：

| 类型 | 特征峰区间（nm） | 典型半高宽 |
|------|----------------|------------|
| R-LED | 620–640 | <30 nm |
| G-LED | 520–540 | <40 nm |
| B-LED | 440–470 | <30 nm |
| QD-Red | 620–640 | <40 nm |
| QD-Green | 520–545 | <40 nm |
| RCF | 600–700（宽带） | >50 nm |
| GCF | 480–580（宽带） | >50 nm |
| BCF | 400–500（宽带） | >50 nm |

- 优先识别为 LED（窄峰），其次 QD，最后 CF
- 半高宽 >50 nm 直接归为 CF

## 3. 色度计算（D-016）

- **统一在 CIE 1931 xy 空间完成 Coverage/Match 计算**（D-016）
- XYZ 计算使用 `colour-science` 的 `sd_to_XYZ`
- 5 nm 步长可接受，1 nm 为默认
- D65 白点：(0.3127, 0.3290)

## 4. Coverage / Match

### 4.1 Coverage

- 目标色域多边形（xy 空间）vs 设备色域多边形
- `coverage = intersect_area / target_area * 100%`
- 几何运算使用 `shapely`（D-015）

### 4.2 Match（D-017）

- **公式**：`match = (1 - mean_delta_xy / 0.1) * 100%`
- 0.1 是参考 Δxy 饱和值（行业经验值）
- Δxy 在 0.1 之内 → match ≥ 0%
- Δxy > 0.1 → match = 0%

### 4.3 CCT

- McCamy 公式：
  ```
  n = (x - 0.3320) / (0.1858 - y)
  CCT = 437 * n^3 + 3601 * n^2 + 6861 * n + 5517
  ```

## 5. 膜厚优化

- 模型：Lambert-Beer `T(λ) = 10^(-α(λ) * d)`
- 优化器：L-BFGS-B（scipy）
- 目标函数：min |xy_target - xy_calculated| 或 min |Δxy_total|
- 决策变量：d_R, d_G, d_B（每通道膜厚）
- 约束：d ∈ [0.1 μm, 10 μm]