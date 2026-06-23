# 08 测试与验收规范

## 1. 测试层级

| 层级 | 标记 | 目标 | 依赖 |
|------|------|------|------|
| 单元 | `@pytest.mark.unit` | 纯函数、Engine | 无 |
| 集成 | `@pytest.mark.integration` | Repository + DB | 临时文件 |
| UI | `@pytest.mark.ui` | 控件交互 | Qt offscreen |
| 慢速 | `@pytest.mark.slow` | 端到端 | 全栈 |

## 2. 验收标准

### 2.1 T-01 骨架

- 目录树完整
- `pip install -e .` 成功
- `pytest` 返回 exit code 0（无测试也算通过）

### 2.2 T-02 SpectrumNormalizer

- 归一化结果与 `numpy` 手动计算一致
- 插值结果与 `scipy.interpolate.CubicSpline` 误差 < 1e-10
- 通道检测对参考数据（见 09）正确率 100%
- 覆盖率 ≥ 80%

### 2.3 通用

- 浮点比较：使用 `np.testing.assert_allclose` 或 `pytest.approx`
- 随机数据：固定 seed（`np.random.seed(42)`）

## 3. 端到端验收（V1.1 release 前）

- 完整用例：导入 LED 光谱 → 计算 Coverage vs DCI-P3 → 输出报告
- UI smoke test：启动 + 切换每个工作区
- 性能：5000 点光谱 100 次 Coverage 计算 < 5 s