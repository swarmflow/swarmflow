We are in pre-release, join our discord to learn more and contribute https://discord.gg/zBgNDbZnx7

# Swarmflow

An AI Swarm Workflow Orchastration tool.
See [design.md](docs/design.md) to catchup on the design of the project.

## Prerequisites

- Docker and Docker Compose installed on your machine
- Git for version control
- A GitHub account for forking and collaboration

## Getting Started

### Fork and Clone the Repository

1. Visit the original repository on GitHub
2. Click the "Fork" button in the top-right corner
3. Clone your forked repository:
```bash
git clone https://github.com/YOUR_USERNAME/REPO_NAME.git
cd REPO_NAME
```

### Environment Setup

1. Edit the `.env` file in the root directory:
```bash
# Development environment
POSTGRES_USER=dev_user
POSTGRES_PASSWORD=dev_password
POSTGRES_DB=dev_db
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Test environment
TEST_POSTGRES_USER=test_user
TEST_POSTGRES_PASSWORD=test_password
TEST_POSTGRES_DB=test_db
TEST_POSTGRES_HOST=test_postgres
TEST_POSTGRES_PORT=5432
```

### Running the Development Environment

The development environment uses `docker-compose.yml` and includes hot-reloading for both frontend and backend:

```bash
# Start all services
docker compose up --build

# Start specific services
docker compose up --build api db

# View logs
docker compose logs -f

# Stop all services
docker compose down
```

Services will be available at:
- FastAPI Backend: http://localhost:8000
- Vue.js Frontend: http://localhost:3000
- Swagger Documentation: http://localhost:8000/docs
- PostgreSQL Database: localhost:5432

### Running Tests

The test environment uses a separate `docker-compose.test.yml` configuration:

```bash
# Run all tests
docker compose -f docker-compose.test.yml up --build

# Run tests and exit
docker compose -f docker-compose.test.yml up --build --exit-code-from test_app

# Run specific test file
docker compose -f docker-compose.test.yml run --rm test_app pytest tests/test_specific.py -v

# Generate coverage report
docker compose -f docker-compose.test.yml run --rm test_app pytest --cov=app tests/ --cov-report=html
```

### Development Workflow

1. Create a new branch for your feature:
```bash
git checkout -b feature/your-feature-name
```

2. Make your changes and run tests:
```bash
# Run tests to ensure nothing is broken
docker compose -f docker-compose.test.yml up --build

# Run development environment to test changes
docker compose up --build
```

3. Commit your changes:
```bash
git add .
git commit -m "feat: add your feature description"
```

4. Push to your fork:
```bash
git push origin feature/your-feature-name
```

5. Create a Pull Request through GitHub's interface

### Database Management

Access the development database:
```bash
docker compose exec postgres psql -U dev_user -d dev_db
```

Access the test database:
```bash
docker compose -f docker-compose.test.yml exec test_postgres psql -U test_user -d test_db
```

Run migrations:
```bash
docker compose exec api alembic upgrade head
```

### Troubleshooting

1. If services won't start:
   - Check if ports 8000, 3000, or 5432 are already in use
   - Ensure Docker daemon is running
   - Try removing all containers and volumes: `docker compose down -v`

2. If tests fail:
   - Check the test database connection
   - Ensure migrations are up to date
   - Verify test environment variables

3. If hot-reload isn't working:
   - Check volume mounts in docker-compose.yml
   - Verify file permissions in mounted directories

### Project Structure

```
.
├── docker-compose.yml          # Development environment configuration
├── docker-compose.test.yml     # Test environment configuration
├── .env                        # Environment variables
├── src/
│   ├── backend/
│   │   ├── Dockerfile         # API Dockerfile
│   │   ├── requirements.txt   # Python dependencies
│   │   └── tests/            # Python tests
│   └── frontend/
│       ├── Dockerfile         # Vue.js Dockerfile
│       └── package.json       # Node.js dependencies
└── README.md                  # This file
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to your fork
5. Create a Pull Request

### Coding Standards

- Follow PEP 8 for Python code
- Use Vue.js style guide for frontend code
- Write tests for new features
- Update documentation as needed

## License

This project is available under a dual license:
- Elastic License 2.0 (ELv2) for organizations with < $10k annual revenue
- Commercial license for organizations with ≥ $10k annual revenue (contact rishabhsingh@berkeley.edu)

See [LICENSE](LICENSE) for details.