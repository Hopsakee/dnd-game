# System Context & Architectural Guidelines for Solo Python Applications

This document provides system-level architectural guidelines and coding standards for agentic coding systems and solo Python developers. It defines a lightweight, pragmatic adaptation of Clean Architecture optimized for single-developer projects, small-scale web tools, local applications, and micro-services serving between 1 and 30 concurrent users.

The architecture eliminates unnecessary enterprise overhead and mapping taxes while maintaining strict separation of business logic, infrastructure, and deployment concerns.

---

## 1. Core Architectural Principles & Scope

### 1.1 Target Operational Context
- **Developer Scale**: Solo developer or small team (1–3 engineers).
- **Application Scale**: Single-purpose applications, internal tools, or web services serving 1 to 30 concurrent users (handling up to millions of requests per month on modest hardware).
- **Codebase Constraints**: Typically 10 to 25 Python modules per application.
- **Infrastructure Target**: Single Linux server/VM (e.g., Hetzner, DigitalOcean) running Docker Compose, fronted by Caddy as reverse proxy/TLS terminator and Authelia for perimeter authentication.

### 1.2 Pragmatic Two-Layer Clean Architecture
Classical Clean Architecture prescribes four or five concentric rings (Entities, Use Cases, Interface Adapters, Frameworks). For solo projects under 25 files, strict four-layer isolation leads to excessive boilerplate and "mapping tax" (converting between nearly identical request DTOs, domain models, and ORM entities).

This architecture simplifies Clean Architecture into two core zones:

- **The Core Layer (Inner)**: Contains business entities, calculations, use case logic, and abstract storage interfaces (Ports). Has **zero dependencies** on external web frameworks, database drivers, or network protocols.
- **The Infrastructure Layer (Outer)**: Contains web controllers, HTTP request handlers, database drivers, file system operations, and external API clients. Implements the abstract ports defined in the Core.

### 1.3 The Dependency Rule
Dependencies MUST only point inward:
- **Infrastructure** knows about **Core**.
- **Core** knows NOTHING about **Infrastructure**.
- Core modules must never import Flask, FastAPI, PyMongo, SQLAlchemy, or Caddy-specific utilities.

### 1.4 Vertical Slice Alternative for Micro-Tools
For focused micro-applications (<10 total files), technical layering can be replaced with **Vertical Slice Architecture**. Group code by feature folder (e.g., `features/user_billing/`, `features/report_generation/`) where entities, storage logic, and HTTP endpoints for that feature reside in one directory, while keeping business logic functions pure.

---

## 2. Domain & Application Core Rules

### 2.1 Pydantic as a Stable Extension
To avoid duplicate model definitions (the "mapping tax"), **Pydantic is approved for use in the Core layer**.
- Pydantic is treated as a stable extension of Python's type system rather than a volatile third-party dependency.
- Domain Entities and Data Transfer Objects (DTOs) inherit from `pydantic.BaseModel`.
- Incoming HTTP payloads are validated at the edge and passed directly into Core functions as Pydantic models without manual field-by-field re-mapping.

```python
# core/models.py
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class ProjectEntity(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1)
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def deactivate(self) -> None:
        self.is_active = False
```

### 2.2 Abstract Storage Interfaces (Repository Ports)
Core business logic must interact with persistence through abstract interfaces defined in the Core using Python's `abc.ABC` or `typing.Protocol`.

```python
# core/ports.py
from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID
from core.models import ProjectEntity

class ProjectRepositoryPort(ABC):
    @abstractmethod
    def save(self, project: ProjectEntity) -> None:
        """Persist a project entity."""
        pass

    @abstractmethod
    def get_by_id(self, project_id: UUID) -> Optional[ProjectEntity]:
        """Retrieve a project by its unique ID."""
        pass

    @abstractmethod
    def list_active(self) -> List[ProjectEntity]:
        """List all active projects."""
        pass
```

### 2.3 Pure Business Logic & Domain Services
Business operations must be encapsulated in pure Python functions or service classes that depend only on Pydantic models and abstract ports.

```python
# core/services.py
from uuid import UUID
from core.models import ProjectEntity
from core.ports import ProjectRepositoryPort

class ProjectService:
    def __init__(self, repo: ProjectRepositoryPort):
        self.repo = repo

    def create_project(self, name: str) -> ProjectEntity:
        project = ProjectEntity(name=name)
        self.repo.save(project)
        return project

    def archive_project(self, project_id: UUID) -> ProjectEntity:
        project = self.repo.get_by_id(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        project.deactivate()
        self.repo.save(project)
        return project
```

---

## 3. Infrastructure & Interface Adapters

### 3.1 Database Persistence Adapters
Concrete storage adapters reside entirely in `infrastructure/persistence/`. They implement Core ports using SQLite, PostgreSQL (`psycopg2`/`pgx`), or MongoDB (`pymongo`).

#### SQLite Adapter Example (Local / Embedded DB)
```python
# infrastructure/persistence/sqlite_project_repo.py
import sqlite3
from typing import Optional, List
from uuid import UUID
from core.models import ProjectEntity
from core.ports import ProjectRepositoryPort

class SQLiteProjectRepository(ProjectRepositoryPort):
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def save(self, project: ProjectEntity) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO projects (id, name, is_active, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    is_active=excluded.is_active
                """,
                (str(project.id), project.name, int(project.is_active), project.created_at.isoformat())
            )

    def get_by_id(self, project_id: UUID) -> Optional[ProjectEntity]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (str(project_id),)).fetchone()
            if not row:
                return None
            return ProjectEntity(
                id=UUID(row["id"]),
                name=row["name"],
                is_active=bool(row["is_active"]),
                created_at=row["created_at"]
            )

    def list_active(self) -> List[ProjectEntity]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM projects WHERE is_active = 1").fetchall()
            return [
                ProjectEntity(
                    id=UUID(r["id"]),
                    name=r["name"],
                    is_active=bool(r["is_active"]),
                    created_at=r["created_at"]
                )
                for r in rows
            ]
```

### 3.2 Web Handlers & UI Integration (Flask / FastAPI + HTMX)
Web endpoints handle HTTP input parsing, invoke Core services, and return HTML partials (HTMX) or JSON.
- Handlers MUST NOT write SQL queries or handle raw database transactions directly.
- Authentication credentials are provided via proxy headers (`X-Forwarded-User`).

```python
# infrastructure/web/routes.py
from flask import Blueprint, request, render_template, g
from core.services import ProjectService

project_bp = Blueprint("projects", __name__)

def get_project_service() -> ProjectService:
    return g.project_service  # Injected at request startup or composition root

@project_bp.route("/projects", methods=["POST"])
def create_project_endpoint():
    # User identity extracted from Authelia reverse proxy header
    authenticated_user = request.headers.get("X-Forwarded-User", "anonymous")
    
    name = request.form.get("name", "").strip()
    if not name:
        return "<div class='error'>Project name is required</div>", 400

    service = get_project_service()
    project = service.create_project(name=name)

    # Return HTMX partial
    return f"<tr id='project-{project.id}'><td>{project.name}</td><td>Active</td></tr>"
```

### 3.3 Composition Root & Dependency Injection
All application components are wired together in a single entry point (`app.py` or `main.py`).

```python
# app.py
import os
from flask import Flask, g
from core.services import ProjectService
from infrastructure.persistence.sqlite_project_repo import SQLiteProjectRepository

def create_app() -> Flask:
    app = Flask(__name__)
    
    # Configuration
    db_path = os.getenv("DATABASE_PATH", "/data/app.db")
    
    # Instantiate Infrastructure
    repo = SQLiteProjectRepository(db_path=db_path)
    
    # Instantiate Core Services
    project_service = ProjectService(repo=repo)

    @app.before_request
    def inject_services():
        g.project_service = project_service

    from infrastructure.web.routes import project_bp
    app.register_blueprint(project_bp)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8000)
```

---

## 4. Stack-Native Deployment Architecture

### 4.1 "One Big Server" Operating Model
- Deploy all applications on a **single Linux cloud VM** (e.g., 4 to 8 vCPU, 8 to 16 GB RAM on Hetzner or DigitalOcean).
- Use **Docker Compose** exclusively for container orchestration. Do not use Kubernetes or complex orchestrators.
- Utilize shared host volumes for persistent database storage and backups.

### 4.2 Production Python Web Server
Run Python applications using high-performance, lightweight production web servers such as **Granian** (Rust-backed) or **Gunicorn** with `uvicorn` workers.

Example container entrypoint using Granian:
```bash
granian --interface wsgi app:create_app() --host 0.0.0.0 --port 8000 --workers 4
```

### 4.3 Docker Compose Topology (`docker-compose.yml`)
```yaml
version: '3.8'

networks:
  app-network:
    driver: bridge

volumes:
  caddy_data:
  caddy_config:
  authelia_data:
  app_db_data:

services:
  # Reverse Proxy & Automatic HTTPS
  caddy:
    image: caddy:2-alpine
    container_name: caddy
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config
    networks:
      - app-network

  # Authentication & Authorization Server
  authelia:
    image: authelia/authelia:latest
    container_name: authelia
    restart: unless-stopped
    volumes:
      - ./authelia:/config
      - authelia_data:/data
    networks:
      - app-network

  # Primary Python Application
  python-app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: python_app
    restart: unless-stopped
    environment:
      - DATABASE_PATH=/data/app.db
      - ENVIRONMENT=production
    volumes:
      - app_db_data:/data
    networks:
      - app-network
```

---

## 5. Reverse Proxy & Authentication Boundary

### 5.1 Caddy Reverse Proxy & TLS
Caddy handles SSL/TLS certificates automatically via Let's Encrypt and acts as the edge router. Authentication is offloaded to Authelia via Caddy's `forward_auth` directive.

#### Caddyfile Configuration
```caddy
{
    email admin@example.com
}

# Authelia Portal Domain
auth.example.com {
    reverse_proxy authelia:9091
}

# Protected Python Application
app.example.com {
    # Enforce Authelia Authentication Gateway
    forward_auth authelia:9091 {
        uri /api/auth/zrouter
        copy_headers Remote-User Remote-Groups Remote-Name Remote-Email
    }

    # Proxy authenticated requests to Python application container
    reverse_proxy python-app:8000 {
        header_up X-Forwarded-User {http.header.Remote-User}
        header_up X-Forwarded-Email {http.header.Remote-Email}
    }
}
```

### 5.2 Authelia Authentication Architecture
- Authelia handles single sign-on (SSO), 2FA, session state, and password hashing.
- **Security Boundary**: The Python application assumes that all traffic routed through Caddy has already been authenticated if `X-Forwarded-User` is set.
- The Python application reads `request.headers.get('X-Forwarded-User')` to obtain user context for auditing and authorization without requiring local login screens or JWT validation logic.

---

## 6. Directory Layout Template

Use this standard layout for single-developer Python projects:

```
my_app/
├── Caddyfile
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── app.py                      # Composition Root / App Factory
├── core/                       # Core Layer (Zero external dependencies)
│   ├── __init__.py
│   ├── models.py               # Pydantic Entities & Data Structures
│   ├── ports.py                # Abstract Base Classes / Repository Interfaces
│   └── services.py             # Business Logic & Domain Operations
├── infrastructure/             # Infrastructure Layer
│   ├── __init__.py
│   ├── persistence/            # Concrete Database Repositories
│   │   ├── __init__.py
│   │   └── sqlite_project_repo.py
│   └── web/                    # HTTP Routes & Templates
│       ├── __init__.py
│       ├── routes.py
│       └── templates/          # HTMX / Jinja2 Templates
│           ├── base.html
│           └── partials/
└── tests/                      # Unit & Integration Tests
    ├── test_domain.py
    └── test_services.py
```

---

## 7. Testing & Quality Assurance Guidelines

1. **Unit Test Core Logic in Isolation**:
   - Write unit tests for `core/services.py` and `core/models.py` using standard `pytest`.
   - Mock repository ports using lightweight fake in-memory classes or `unittest.mock.MagicMock`.
   - Core tests must run in milliseconds with zero database or Docker dependencies.

```python
# tests/test_services.py
from core.models import ProjectEntity
from core.ports import ProjectRepositoryPort
from core.services import ProjectService

class MemoryProjectRepository(ProjectRepositoryPort):
    def __init__(self):
        self.data = {}

    def save(self, project: ProjectEntity) -> None:
        self.data[project.id] = project

    def get_by_id(self, project_id):
        return self.data.get(project_id)

    def list_active(self):
        return [p for p in self.data.values() if p.is_active]

def test_create_and_archive_project():
    repo = MemoryProjectRepository()
    service = ProjectService(repo=repo)

    project = service.create_project("Test Project")
    assert project.is_active is True

    archived = service.archive_project(project.id)
    assert archived.is_active is False
    assert repo.get_by_id(project.id).is_active is False
```

2. **Integration Testing**:
   - Test concrete database adapters (`infrastructure/persistence/`) against a temporary SQLite database or ephemeral Docker database container.
   - Test web endpoints using Flask/FastAPI built-in test clients, simulating proxy headers (`X-Forwarded-User: testuser`).

---

## Summary Rules for Agentic Coding Systems

1. **Never create 4-layer class hierarchies** for simple models. Use the 2-layer Core + Infrastructure pattern.
2. **Never import web frameworks or ORMs inside `core/`**.
3. **Use Pydantic models freely** across `core/models.py`.
4. **Define repository interfaces** in `core/ports.py` using `abc.ABC`.
5. **Keep routes thin**: Parse requests, invoke `core/services.py`, return HTML/JSON.
6. **Rely on Caddy + Authelia** for HTTPS, reverse proxying, and user auth headers.
