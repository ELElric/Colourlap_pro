# 07 编码规范

## 1. 风格

- 格式化：ruff（line-length 100，target 3.10）
- 静态检查：mypy（非严格，但 `no_implicit_optional` 与 `check_untyped_defs` 启用）
- 命名：snake_case（函数/变量）、PascalCase（类）、UPPER_SNAKE（常量）
- 导入顺序：stdlib → third-party → local（ruff I 规则自动）

## 2. 类型

- 所有公共 API 必须有完整类型注解
- `numpy.typing.NDArray[np.float64]` 替代裸 `np.ndarray`
- 避免 `Any`，必要时显式标注

## 3. 文档字符串

- Google 风格
- 公共函数必须包含：Args / Returns / Raises（必要时）
- 算法函数必须包含数学公式（如适用）

## 4. 错误处理

- 自定义异常继承 `ColorLabError`（见 `utils/errors.py`）
- 永远不要 `except:` 裸捕获
- 错误消息包含上下文（操作、参数值、文件路径）

## 5. 日志

- 使用 `loguru`
- 模块顶部：`logger = logger.bind(module=__name__)`
- 级别：DEBUG（详细） / INFO（关键步骤） / WARNING（用户可恢复） / ERROR（失败）

## 6. 测试

- 单元测试：pytest，与源同包结构（`tests/unit/engines/...`）
- 集成测试：使用临时 SQLite
- UI 测试：pytest-qt（V1.1 不强制）
- 覆盖率：engine 层 ≥ 80%，service ≥ 60%

## 7. Git 提交（V1.1 不强制启用 git）

- Conventional Commits：`feat:`, `fix:`, `docs:`, `refactor:`, `test:`
- 关联任务 ID：例如 `feat(engines): add SpectrumNormalizer (T-02)`