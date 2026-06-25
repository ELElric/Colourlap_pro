"""SQLAlchemy 2.0 ORM models for ColorLab Pro.

Tables (see docs/06):
- projects
- spectra
- spectrum_points
- optimizations
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    """A ColorLab Pro project / workspace."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=_utc_now, onupdate=_utc_now)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    spectra: Mapped[list[Spectrum]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    optimizations: Mapped[list[Optimization]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Project id={self.id} name={self.name!r}>"


class Spectrum(Base):
    """Spectrum metadata.

    The actual per-wavelength values are stored in spectrum_points (D-018).
    """

    __tablename__ = "spectra"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True, default="import")
    channel: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    wavelength_min: Mapped[float | None] = mapped_column(nullable=True)
    wavelength_max: Mapped[float | None] = mapped_column(nullable=True)
    wavelength_step: Mapped[float | None] = mapped_column(nullable=True)
    point_count: Mapped[int | None] = mapped_column(nullable=True)
    fwhm: Mapped[float | None] = mapped_column(nullable=True)
    peak_wavelength: Mapped[float | None] = mapped_column(nullable=True)
    xy_x: Mapped[float | None] = mapped_column(nullable=True)
    xy_y: Mapped[float | None] = mapped_column(nullable=True)
    uv_u: Mapped[float | None] = mapped_column(nullable=True)
    uv_v: Mapped[float | None] = mapped_column(nullable=True)
    dominant_wavelength: Mapped[float | None] = mapped_column(nullable=True)
    purity: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_utc_now)
    meta_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project] = relationship(back_populates="spectra")
    points: Mapped[list[SpectrumPoint]] = relationship(
        back_populates="spectrum",
        cascade="all, delete-orphan",
        order_by="SpectrumPoint.idx",
    )

    def __repr__(self) -> str:
        return f"<Spectrum id={self.id} name={self.name!r}>"


class SpectrumPoint(Base):
    """A single wavelength/value pair belonging to a Spectrum."""

    __tablename__ = "spectrum_points"

    spectrum_id: Mapped[int] = mapped_column(
        ForeignKey("spectra.id"), primary_key=True, nullable=False
    )
    idx: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    wavelength: Mapped[float] = mapped_column(nullable=False)
    value: Mapped[float] = mapped_column(nullable=False)

    spectrum: Mapped[Spectrum] = relationship(back_populates="points")

    def __repr__(self) -> str:
        return (
            f"<SpectrumPoint spectrum_id={self.spectrum_id} "
            f"idx={self.idx} wavelength={self.wavelength}>"
        )


class Optimization(Base):
    """A thickness / white-point optimization run."""

    __tablename__ = "optimizations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_xy_x: Mapped[float | None] = mapped_column(nullable=True)
    target_xy_y: Mapped[float | None] = mapped_column(nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_utc_now, nullable=False)

    project: Mapped[Project] = relationship(back_populates="optimizations")

    def __repr__(self) -> str:
        return f"<Optimization id={self.id} name={self.name!r}>"
