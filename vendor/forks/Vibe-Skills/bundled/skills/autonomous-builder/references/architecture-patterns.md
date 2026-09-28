# Architecture Patterns Reference

Comprehensive guide to software architecture patterns for autonomous development.

## Pattern Selection Matrix

| Project Type | Recommended Pattern | Reason |
|-------------|---------------------|--------|
| Web API | Hexagonal | Easy testing, clear boundaries |
| CLI Tool | Clean Architecture | Dependency injection, testability |
| Web App (Full-stack) | Layered + DDD | Separation of concerns |
| Microservice | Hexagonal + DDD | Portability, bounded contexts |
| Library/SDK | Minimal | Keep it simple |

## Clean Architecture

### Layers

```
src/
├── domain/           # Entities, Value Objects, Domain Events
│   ├── entities/
│   ├── value_objects/
│   └── events/
├── application/      # Use Cases, Application Services
│   ├── use_cases/
│   └── services/
├── infrastructure/   # External services, Database, APIs
│   ├── persistence/
│   ├── external/
│   └── config/
└── presentation/     # Controllers, Views, API endpoints
    ├── api/
    └── cli/
```

### Dependency Rule

```
Dependencies point INWARD:
Presentation -> Application -> Domain
Infrastructure -> Application -> Domain

Domain has NO dependencies on other layers.
```

### Example Structure (Python)

```python
# domain/entities/task.py
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

@dataclass
class Task:
    id: str
    title: str
    status: TaskStatus
    created_at: datetime

    def complete(self) -> None:
        if self.status == TaskStatus.COMPLETED:
            raise ValueError("Task already completed")
        self.status = TaskStatus.COMPLETED

# application/use_cases/complete_task.py
class CompleteTaskUseCase:
    def __init__(self, task_repository):
        self.task_repository = task_repository

    def execute(self, task_id: str) -> Task:
        task = self.task_repository.find_by_id(task_id)
        if not task:
            raise ValueError("Task not found")
        task.complete()
        self.task_repository.save(task)
        return task

# infrastructure/persistence/sqlite_task_repository.py
import sqlite3
class SQLiteTaskRepository:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)

    def find_by_id(self, task_id: str) -> Task | None:
        cursor = self.conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        )
        row = cursor.fetchone()
        return self._to_entity(row) if row else None
```

## Hexagonal Architecture (Ports & Adapters)

### Structure

```
src/
├── core/             # Domain logic (hexagon center)
│   ├── domain/
│   ├── ports/        # Interfaces
│   │   ├── primary/  # Driving ports (APIs)
│   │   └── secondary/# Driven ports (repositories)
│   └── services/
├── adapters/
│   ├── primary/      # Controllers, CLI handlers
│   │   ├── rest/
│   │   └── cli/
│   └── secondary/    # Repository implementations
│       ├── persistence/
│       └── messaging/
└── config/
```

### Port Examples

```python
# core/ports/secondary/task_repository.py
from abc import ABC, abstractmethod
from typing import Optional, List

class TaskRepositoryPort(ABC):
    @abstractmethod
    async def find_by_id(self, task_id: str) -> Optional[Task]:
        pass

    @abstractmethod
    async def save(self, task: Task) -> Task:
        pass

    @abstractmethod
    async def list_all(self) -> List[Task]:
        pass

# core/ports/primary/task_service.py
class TaskServicePort(ABC):
    @abstractmethod
    async def create_task(self, title: str) -> Task:
        pass

    @abstractmethod
    async def complete_task(self, task_id: str) -> Task:
        pass
```

### Adapter Examples

```python
# adapters/primary/rest/task_controller.py
from fastapi import APIRouter, Depends

router = APIRouter()

@router.post("/tasks")
async def create_task(
    title: str,
    service: TaskServicePort = Depends(get_task_service)
):
    task = await service.create_task(title)
    return {"id": task.id, "title": task.title}

# adapters/secondary/persistence/sqlite_task_repository.py
class SQLiteTaskRepository(TaskRepositoryPort):
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self._create_table()

    async def find_by_id(self, task_id: str) -> Optional[Task]:
        cursor = self.conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        )
        row = cursor.fetchone()
        return self._to_entity(row) if row else None
```
