"""Repository for CRUD operations on Project entities."""

from __future__ import annotations

from sqlalchemy.orm import Session

from colorlab_pro.database.models import Project


def create(session: Session, name: str, description: str | None = None) -> Project:
    """Create and persist a new Project.

    Args:
        session: Active SQLAlchemy ORM session.
        name: Project display name.
        description: Optional project description.

    Returns:
        The persisted Project ORM instance.
    """
    project = Project(name=name, description=description)
    session.add(project)
    session.flush()
    return project


def get_by_id(session: Session, project_id: int) -> Project | None:
    """Load a Project by id, or None if not found."""
    return session.get(Project, project_id)


def list_all(session: Session) -> list[Project]:
    """Return all projects ordered by creation time (oldest first)."""
    return session.query(Project).order_by(Project.created_at).all()


def update(
    session: Session,
    project_id: int,
    *,
    name: str | None = None,
    description: str | None = None,
) -> Project | None:
    """Update a project's mutable fields and return it.

    Only non-None arguments are applied. Returns None if the project
    does not exist.
    """
    project = session.get(Project, project_id)
    if project is None:
        return None

    if name is not None:
        project.name = name
    if description is not None:
        project.description = description

    return project


def delete(session: Session, project_id: int) -> bool:
    """Delete a project and its cascaded children.

    Returns True if the project existed and was deleted.
    """
    project = session.get(Project, project_id)
    if project is None:
        return False
    session.delete(project)
    return True
