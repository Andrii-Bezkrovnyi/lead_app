# Lead System

## Implemented Features and Project Architecture
### 1. General Architecture and Tech Stack
The project implements a microservices architecture consisting of two independent FastAPI
applications within a single repository:

- /landings (port 8001) — strictly responsible for receiving lead requests;

- /core (port 8000) — the main backend for background processing and analytics.

- Communication between services occurs strictly via Redis. 
The lead reception service does not have direct access to the database,
ensuring fast response times and high isolation.
- Tech Stack: Python, FastAPI, PostgreSQL, SQLAlchemy 2 (with the asyncpg driver), 
Alembic, Redis, and JWT.

### 2. /landings Service (Lead Reception)
- Developed a secured POST /lead endpoint for receiving data from landing pages.
- Implemented strict input data validation: the API checks for the presence of required 
fields and ensures that the affiliate_id passed in the request body perfectly matches 
the ID encrypted in the client's Bearer token.
- Upon successful validation, the lead is instantly dispatched to a Redis Streams queue,
- and the client immediately receives a 200 OK status with a message_id, 
without waiting for a database write operation.

### 3. /core Service (Background Worker and Analytics)

- Database: Designed a DB schema with three tables:
leads (with mandatory creation date recording), offers, and affiliates.
- Background Worker: Wrote a reliable consumer that asynchronously reads new leads 
from Redis Streams and saves them into PostgreSQL.
- Deduplication: Implemented protection against duplicate entries. 
- If a lead with identical parameters (name + phone + offer_id + affiliate_id) 
is submitted repeatedly within a 10-minute window, it is ignored 
(validation implemented via Redis keys with a TTL of 600s).
This logic is fully covered by tests.
- Analytics: Developed a GET /leads endpoint for retrieving statistics. 
It accepts date_from, date_to, and group (date or offer) parameters, 
returning correctly grouped data. The output is strictly scoped and limited 
to the leads belonging to the affiliate whose ID is in the authorization token.

### 4. Authorization and Security (JWT)
- The entire system is secured using JWT authentication. 
Implemented a Bearer token generation mechanism where the payload is formed based on 
{"id": affiliates.id}. All key endpoints require a valid token, 
and the system automatically rejects requests if the affiliate does not exist in the database.

### 5. Code Quality and Documentation
- Swagger: Detailed interactive API documentation is automatically generated 
for both microservices (available on their respective ports at /docs).
- Testing: Key functionality (authorization, worker logic, rate-limiter, endpoints) 
is covered by asynchronous unit tests using pytest-asyncio. 
Configured seamless integration with a test database using isolated transactions (savepoints) 
and a global event loop (loop_scope="session"). 
This guarantees test stability and completely prevents data "leaks" between tests.

## Endpoints

- `POST /auth/token`
- `POST /auth/refresh`
- `POST /auth/logout`
- `POST /lead`
- `GET /leads?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&group=date|offer`

## Local run code of the project

1. Clone this repository to your local machine.

    ```bash
    git clone https://github.com/Andrii-Bezkrovnyi/lead_app.git
    ```

2. Navigate to the project directory:

    ```bash
    cd lead_app
    ```

3. Create virtual environment:

   ```bash
    python -m venv venv
   ```
4. Enter in virtual environment in Linux:

   ```bash
    source venv/bin/activate
   ```
   - in Windows
   ```bash
    venv\Scripts\activate
   ```
5. Install the main dependencies:
    ```bash
    pip install .
    ```
6. You can also install the test dependencies:
    ```bash
    pip install -e .[test]
    ```
7. Clone the exemple environment variables file and fill in the necessary values:
    ```bash
    cp .env.example .env
    ```

8. Run the application using Docker Compose:
    ```bash
    docker-compose up -d --build
    ```
9. Run database migrations for the core service:
    ```bash
    docker-compose exec core alembic upgrade head
    ```
10. Seed the database with test data (optional):
    ```bash
    docker-compose exec core python -m core.seed
    ```
11. Verify that the services are running and the database is accessible:
    ```bash
    docker-compose exec db psql -U postgres -d leads -c "\dt"
    ```
12. You can also check the logs of the services to ensure they are running correctly:
    ```bash
    docker-compose logs -f
    ```
    ```bash
    docker-compose logs -f --tail=10
    ```
13. To stop the services and clean up resources, run:
    ```bash
    docker compose down -v
    ```
    ```bash
    docker compose down
    ```
14. Open the API documentation in your browser to explore 
the available endpoints and test them interactively:
    - API documentation for the core service (Admin panel and logic):
       ```shell
       http://localhost:8000/docs
       ```
    - Landings API Docs (for receiving leads):
      ```shell
      http://localhost:8001/docs
      ```


### How to check the program's operation

#### 1. Generating the Token
- Open http://localhost:8000/docs.
- Find the POST /auth/token endpoint.
- Click the "Try it out" button.
- In the "Request body" field, you will see the JSON structure expected by the server. 
    ```bash
    { 
      "affiliate_id": "11111111-1111-1111-1111-111111111111", 
      "secret_key": "your_password_or_secret" 
    }
    ```

    ```
    (Note: The UUID 11111111-1111-1111-1111-111111111111 is test data 
    that we populated using core/seed.py. 
    You can check the affiliate table in your PostgreSQL database and copy any real ID).``
    ``` 

- Click "Execute".

- If the credentials are correct, the server will return a 200 OK response 
containing your tokens in the body.
- Copy the access_token value (without the quotes).

#### 2. Authorization In Swagger (Port 8000)
- Scroll to the very top of the Swagger page (at http://localhost:8000/docs).
- Click the green "Authorize" button (usually with an open padlock icon).
- The "Available authorizations" window will open. Paste the copied access token into the "Value" field.
- Click "Authorize".
- Close the authorization window.

#### 3. Authorization and Creating a Lead (Port 8001)
- Open http://localhost:8001/docs.
- Scroll to the very top of the Swagger page (at http://localhost:8001/docs).
- Click the green "Authorize" button (usually with an open padlock icon).
- The "Available authorizations" window will open. Paste the copied access token into the "Value" field.
- Click "Authorize".
- Close the authorization window.

#### 4. Create a lead (http://localhost:8001/docs)
- Expand the POST /lead method and click "Try it out".
- You need to enter data into the "Request body" field. 
- Replace the JSON with the following:

    ```bash
    {
      "name": "Олексій",
      "phone": "+380982342123",
      "country": "UA",
      "offer_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", 
      "affiliate_id": "11111111-1111-1111-1111-111111111111"
    }
    ```

    ```
    (Note: The offer_id aaaaaaaa... is a test ID. If the database is clean, 
    make sure such an offer exists in the DB, or use any other existing offer ID).
    ```
- Click "Execute".
- Checking Analytics (Port 8000)
- Now let's check the analytics (at http://localhost:8000/docs).
- Expand the GET /leads method and click "Try it out".
- Fill in the request parameters:
- date_from: Enter the start date of the period (e.g., 2024-01-01 or just today's date in YYYY-MM-DD format).
- date_to: Enter the end date (e.g., 2026-12-31 or tomorrow's date).
- group: Select from the dropdown list either date (grouping by days) or offer (grouping by offers).
- Click "Execute".
- Expected result: In the "Server response" block, you should receive a 200 status code 
and a data structure containing analytics. 
If the worker (Redis Consumer) had enough time to process the lead from the previous step 
and save it in Postgres, you will see statistics where total_count is greater than zero.