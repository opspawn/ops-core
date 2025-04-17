# Technical Context: Ops-Core Python Module

## 1. Technologies Used
- **Programming Language:** Python (Version 3.9 or higher recommended)
- **Web Framework:** FastAPI (for building the RESTful API endpoints)
    - *Dependencies:* Uvicorn (ASGI server), Pydantic (data validation)
- **Testing Framework:** Pytest (for unit and integration tests)
    - *Potential Plugins:* `pytest-cov` (coverage), `pytest-asyncio` (for testing async FastAPI code)
- **Containerization:** Docker & Docker Compose (for creating reproducible development/testing environments)
- **Version Control:** Git (hosted on GitHub, assumed)
- **CI/CD:** GitHub Actions (planned for automated testing, linting)
- **Data Format:** JSON (for API communication and potentially workflow definitions)
- **Logging:** Python standard `logging` module (configured for structured JSON output)
- **Initial Storage:** Python dictionaries (in-memory)

## 2. Development Setup
- **Environment Management:** Python virtual environments (`venv` recommended) to isolate dependencies.
- **Dependency Management:** `requirements.txt` file listing all Python package dependencies. Install using `pip install -r requirements.txt`.
- **Code Editor/IDE:** VS Code is assumed based on the environment, but any Python-supporting editor is suitable. Recommended extensions: Python (Microsoft), Pylint/Flake8/Black (for linting/formatting).
- **Local Execution:**
    - Run the FastAPI application locally using `uvicorn opscore.api:app --reload` (or similar, depending on file structure).
    - Run tests using the `pytest` command in the terminal.
    - Use Docker Compose (`docker-compose up`) to run Ops-Core and potentially simulate AgentKit/Agents in containers.
- **Configuration:**
    - Environment variables will be used for sensitive information like API keys (`OPSCORE_API_KEY`) and potentially external service URLs (`AGENTKIT_API_URL`). A `.env` file pattern might be used locally (requires `python-dotenv` package).

## 3. Technical Constraints
- **Local-First:** Initial versions must run efficiently on a standard developer machine without mandatory cloud dependencies.
- **Python Version:** Must maintain compatibility with Python 3.9+.
- **Stateless API (Mostly):** API endpoints should ideally be stateless, relying on the storage subsystem to manage state persistence between requests.
- **Synchronous/Asynchronous:** While FastAPI supports async, initial core logic (lifecycle, workflow) might be implemented synchronously for simplicity, with async primarily at the API boundary. Future enhancements may leverage async more deeply.

## 4. Dependencies
- **External Service:** AgentKit (Ops-Core needs to communicate with its API). The exact AgentKit API endpoint for agent discovery (`GET /v1/agents`) needs confirmation.
- **Python Packages:** Defined in `requirements.txt` (FastAPI, Uvicorn, Pytest, etc.).

## 5. Tool Usage Patterns
- **API Documentation:** FastAPI automatically generates OpenAPI (Swagger UI at `/docs`, ReDoc at `/redoc`) documentation from code and type hints.
- **Testing:** Tests should cover individual functions (unit tests) and interactions between components/API endpoints (integration tests).
- **Formatting/Linting:** Tools like Black, Flake8, or Pylint should be used (potentially enforced via CI) to maintain code quality and consistency.