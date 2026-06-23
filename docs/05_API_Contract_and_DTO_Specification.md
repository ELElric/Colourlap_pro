# 05 API 与 DTO 规范

> Service ↔ Engine ↔ Controller 之间的接口契约。**冲突优先级最高**。

## 1. DTO 基类

所有 DTO 用 `@dataclass(frozen=True)` 不可变对象：

```python
from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class Spectrum:
    wavelengths: np.ndarray  # nm
    values: np.ndarray       # 见 04 §1
    unit: str = "a.u."
    meta: dict = field(default_factory=dict)
```

## 2. Service 层接口（摘要）

```python
class SpectrumService:
    def import_file(self, path: Path) -> list[Spectrum]: ...
    def normalize(self, s: Spectrum, mode: str) -> Spectrum: ...
    def interpolate(self, s: Spectrum, step: int = 1) -> Spectrum: ...
    def detect_channel(self, s: Spectrum) -> ChannelType: ...

class ColorService:
    def xyz(self, s: Spectrum) -> XYZ: ...
    def xy(self, s: Spectrum) -> XY: ...
    def cct_mccamy(self, s: Spectrum) -> float: ...

class GamutService:
    def coverage(self, target: Gamut, device: Gamut) -> float: ...
    def match(self, target: Spectrum, device: Spectrum) -> float: ...

class OptimizationService:
    def optimize_thickness(
        self,
        target_xy: XY,
        primaries: tuple[Spectrum, Spectrum, Spectrum],
        bounds: tuple = (0.1, 10.0),
    ) -> OptimizationResult: ...
```

## 3. Engine 层纯函数

```python
# engines/spectrum_normalizer.py
def normalize(s: Spectrum, mode: str) -> Spectrum: ...
def interpolate(s: Spectrum, step: int = 1, method: str = "cubic") -> Spectrum: ...
def auto_fill_gaps(s: Spectrum) -> Spectrum: ...
def detect_channel(s: Spectrum) -> str: ...
```

## 4. Repository 接口

```python
class SpectrumRepository(Protocol):
    def save(self, s: Spectrum, project_id: int) -> int: ...
    def get(self, id: int) -> Spectrum: ...
    def list_by_project(self, project_id: int) -> list[Spectrum]: ...
    def delete(self, id: int) -> None: ...
```

## 5. 错误约定

- 自定义异常继承自 `ColorLabError`
- 包含 `code`（字符串）、`message`、`details`（dict）
- Service 层抛出，UI 层捕获并显示