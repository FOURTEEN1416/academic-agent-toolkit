# Multi-Language Development Patterns

Language-specific patterns and best practices for autonomous code generation.

## Language Detection & Setup

### Detection Indicators

| Language | Files/Patterns |
|----------|----------------|
| Python | `requirements.txt`, `pyproject.toml`, `setup.py`, `*.py` |
| Node.js | `package.json`, `*.ts`, `*.js`, `tsconfig.json` |
| Go | `go.mod`, `*.go` |
| Rust | `Cargo.toml`, `*.rs` |
| Java | `pom.xml`, `build.gradle`, `*.java` |
| .NET | `*.csproj`, `*.cs`, `*.fs` |

## Python

### Project Structure

```
project/
├── src/
│   └── package_name/
│       ├── __init__.py
│       ├── domain/
│       ├── application/
│       └── infrastructure/
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_*.py
├── pyproject.toml
├── requirements.txt
└── README.md
```

### Commands

```bash
# Create virtual environment
python -m venv .venv

# Install dependencies
pip install -r requirements.txt
pip install -e ".[dev]"

# Run tests
pytest tests/ -v --cov=src

# Format code
black src/ tests/
isort src/ tests/

# Type check
mypy src/
```

### Common Patterns

```python
# Dependency Injection
from dependency_injector import containers, providers

class Container(containers.DeclarativeContainer):
    config = providers.Configuration()

    task_repository = providers.Singleton(
        SQLiteTaskRepository,
        db_path=config.db_path
    )

    task_service = providers.Factory(
        TaskService,
        repository=task_repository
    )

# Async patterns
from asyncio import gather

async def process_tasks(tasks: List[Task]):
    results = await gather(
        *[process_task(t) for t in tasks],
        return_exceptions=True
    )
    return [r for r in results if not isinstance(r, Exception)]

# FastAPI setup
from fastapi import FastAPI, Depends

app = FastAPI()

@app.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    service: TaskService = Depends(get_task_service)
):
    return await service.get_task(task_id)
```

## Node.js / TypeScript

### Project Structure

```
project/
├── src/
│   ├── index.ts
│   ├── domain/
│   ├── application/
│   └── infrastructure/
├── tests/
│   ├── unit/
│   └── integration/
├── package.json
├── tsconfig.json
├── jest.config.js
└── README.md
```

### Commands

```bash
# Install dependencies
npm install
yarn install
pnpm install

# Run tests
npm test
npm run test:coverage

# Build
npm run build

# Lint
npm run lint
npm run lint:fix

# Type check
npx tsc --noEmit
```

### Common Patterns

```typescript
// Dependency Injection with Inversify
import { Container, injectable, inject } from 'inversify';

@injectable()
class TaskRepository implements ITaskRepository {
    async findById(id: string): Promise<Task | null> {
        // implementation
    }
}

@injectable()
class TaskService {
    constructor(
        @inject('TaskRepository') private repo: ITaskRepository
    ) {}

    async getTask(id: string): Promise<Task> {
        const task = await this.repo.findById(id);
        if (!task) throw new NotFoundError('Task not found');
        return task;
    }
}

const container = new Container();
container.bind('TaskRepository').to(TaskRepository);
container.bind(TaskService).toSelf();

// Express setup
import express from 'express';

const app = express();
app.use(express.json());

app.get('/tasks/:id', async (req, res) => {
    const task = await taskService.getTask(req.params.id);
    res.json(task);
});
```

## Go

### Project Structure

```
project/
├── cmd/
│   └── server/
│       └── main.go
├── internal/
│   ├── domain/
│   ├── service/
│   └── repository/
├── pkg/
│   └── utils/
├── api/
│   └── openapi.yaml
├── go.mod
└── README.md
```

### Commands

```bash
# Initialize module
go mod init github.com/user/project

# Install dependencies
go mod tidy

# Run tests
go test ./... -v -cover

# Build
go build -o bin/server ./cmd/server

# Lint
golangci-lint run
```

### Common Patterns

```go
// Interface for dependency injection
type TaskRepository interface {
    FindByID(ctx context.Context, id string) (*Task, error)
    Save(ctx context.Context, task *Task) error
}

// Service with injected repository
type TaskService struct {
    repo TaskRepository
}

func NewTaskService(repo TaskRepository) *TaskService {
    return &TaskService{repo: repo}
}

func (s *TaskService) GetTask(ctx context.Context, id string) (*Task, error) {
    task, err := s.repo.FindByID(ctx, id)
    if err != nil {
        return nil, fmt.Errorf("find task: %w", err)
    }
    if task == nil {
        return nil, ErrNotFound
    }
    return task, nil
}

// HTTP handler
func (h *TaskHandler) GetTask(w http.ResponseWriter, r *http.Request) {
    id := chi.URLParam(r, "id")
    task, err := h.service.GetTask(r.Context(), id)
    if err != nil {
        http.Error(w, err.Error(), http.StatusNotFound)
        return
    }
    json.NewEncoder(w).Encode(task)
}
```

## Rust

### Project Structure

```
project/
├── src/
│   ├── main.rs
│   ├── lib.rs
│   ├── domain/
│   │   └── mod.rs
│   ├── service/
│   │   └── mod.rs
│   └── repository/
│       └── mod.rs
├── tests/
│   └── integration_test.rs
├── Cargo.toml
└── README.md
```

### Commands

```bash
# Build
cargo build

# Run tests
cargo test

# Run with release optimizations
cargo run --release

# Format
cargo fmt

# Lint
cargo clippy

# Documentation
cargo doc --open
```

### Common Patterns

```rust
// Trait for dependency injection
#[async_trait]
pub trait TaskRepository: Send + Sync {
    async fn find_by_id(&self, id: &str) -> Result<Option<Task>, Error>;
    async fn save(&self, task: &Task) -> Result<(), Error>;
}

// Service with trait object
pub struct TaskService {
    repo: Arc<dyn TaskRepository>,
}

impl TaskService {
    pub fn new(repo: Arc<dyn TaskRepository>) -> Self {
        Self { repo }
    }

    pub async fn get_task(&self, id: &str) -> Result<Task, Error> {
        self.repo.find_by_id(id)
            .await?
            .ok_or(Error::NotFound)
    }
}

// Error handling with thiserror
#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("Task not found")]
    NotFound,
    #[error("Database error: {0}")]
    Database(#[from] sqlx::Error),
}
```

## Technology Stack Decision Tree

```
PROJECT TYPE?
├── Web API
│   ├── High performance? ──> Go (Fiber/Gin) or Rust (Actix-web)
│   ├── Rapid development? ──> Python (FastAPI) or Node.js (Express)
│   └── Type safety? ──> TypeScript (NestJS) or Rust
│
├── CLI Tool
│   ├── Simple? ──> Python (Click/Typer)
│   ├── Performance? ──> Go or Rust
│   └── Cross-platform? ──> Go or Rust
│
├── Web App (Frontend)
│   ├── Complex UI? ──> React + TypeScript
│   ├── SEO critical? ──> Next.js
│   └── Simple? ──> Vue.js or Svelte
│
├── Data Processing
│   ├── ML/AI? ──> Python
│   ├── High volume? ──> Go or Rust
│   └── Real-time? ──> Rust or Go
│
└── Mobile
    ├── Cross-platform? ──> React Native or Flutter
    ├── Native? ──> Swift (iOS) / Kotlin (Android)
    └── Simple? ──> React Native Expo
```
