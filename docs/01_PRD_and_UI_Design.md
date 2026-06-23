# 01 产品需求与 UI 设计

> Project: ColorLab Pro V1.1
> Status: Frozen for V1.1 (修订须打 D-NNN 标记)

## 1. 目标用户

- 显示器件研发工程师（LED、QD、Color Filter）
- 色彩管理工程师
- 客户支持工程师（FAE）

## 2. 核心场景

1. **光谱导入**：从 CSV / Excel / 厂商格式导入 LED、QD、CF 光谱。
2. **光谱预处理**：归一化、插值、通道检测、单位转换。
3. **混合光谱计算**：基于 Lambert-Beer 物理模型组合多组光谱。
4. **色度计算**：XYZ / xy / u-prime-v-prime / CCT（McCamy）。
5. **Coverage / Match**：vs 目标色域 / 目标光谱。
6. **膜厚优化**：调整 CF 厚度以匹配目标白点 / 色域。
7. **项目管理**：保存 / 加载 / 复用工程数据。

## 3. 非目标（V1.1）

- 不支持实时测量仪器直连
- 不支持多用户协同
- 不支持 Web / Electron
- 不支持 HDR / PQ 色域（仅 SDR sRGB / DCI-P3 / Adobe RGB / NTSC）

## 4. UI 总览

七个工作区（详见 `02_UI_Layout_Specification.md`）：

1. **Project**（项目管理）
2. **Spectrum**（光谱导入 / 预处理）
3. **Mix**（混合光谱）
4. **Analyze**（色度 / Coverage / Match）
5. **Optimize**（膜厚优化）
6. **Report**（报告导出）
7. **Settings**（参数中心）

## 5. UI 设计原则

- 桌面端原生（PySide6）
- 暗色主题默认
- 三栏布局：左侧导航 / 中部工作区 / 右侧属性面板
- 所有数值输入支持表达式（`1.5e-3`）和单位显示