# Disposable Email Checker
Developed a lightweight, high-performance API to detect and block disposable email addresses, ensuring better data quality and security for web applications. The service is built using the Starlette framework for fast, asynchronous HTTP requests and managed using the uv package manager for efficient dependency handling.

## Key Features:

- POST `/check` – Check the validity of a single email address.

- POST `/bulk-check` – Validate multiple email addresses in a single request.

- GET `/stats` – Retrieve usage statistics and checker metrics.

- GET `/health` – Perform a health check to verify service status.

- GET `/ – Display` the home page with API documentation.

- GET `/stats-page` – View a web-based statistics dashboard.

### Benefits :

- Demonstrates expertise in modern Python async web frameworks (Starlette).

- Showcases ability to build scalable, RESTful microservices.

- Illustrates experience with efficient package management (uv).

- Highlights problem-solving for security and data quality challenges.

- Proves capability to deliver user-friendly dashboards and APIs.


### Run the Project:  

```bash
uv sync
uv run uvicorn main:app --port 8000
```
