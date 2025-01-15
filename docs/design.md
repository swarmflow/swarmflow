# Swarmflow Design

Goal: To provide a general working guideline of how this prroject will be designed and developed. If you are a contributor, please follow this guideline. And ask in the Discord if you have any questions.

## Definitions

### CEO Agent
An LLM agent that is responsible for querying the database and modifying the database and middleware.
### Entities
The model that a CEO Agent designs which stores data about a workflow for the swarm to modify and take action on.
### Forms
A form is a middleware endpoint that allows agents to quickly add data to the database during a task.
### Workflows
A workflow is a collection of tasks set by the CEO agent (like filling out a form or querying reports) that are executed in a specific order. Actions like submitting a form move an entity down a workflow. Each step in the workflow is added to the task_queue.
### Task Queue
The task queue is a queue of tasks that are waiting to be executed by the AI swarm and is added to mby workflows.
### Reports
A report is a middleware endpoint that allows agents to quickly query the database and get the current status of the workflwo
### Agents
The LLM proccesses that make up the swarm and can execute tasks.

## Database Design
### Meta-tables (Administration Data)
- Forms
- Reports
- Workflows
- Steps
- Agents
  
### Other Tables
- CEO Created Tables
  

### Swarm Design (for prototype)
- Python Middleware (see /core)
- Postgres
- Admin UI (vue+vite) (see /admin)
- Redis for task queue
- Agent Server (see /worker_agent)
## Deployment
- Testing: run docker compose on testing .yml
- Local Hosting: run docker compose in root
- Cloud Hosting: TBD

## CI/CD and Update Strategy
Update and release docker images with built in migration scripts and roll back scripts as needed.
