# VoltPulse Engine: Industrial IoT & Energy Telemetry Platform

VoltPulse is an event-driven industrial IoT telemetry and energy management backend. It is designed to ingest, validate, process, and analyze high-frequency time-series telemetry from distributed edge assets such as smart grid sub-meters, solar inverters, and heavy industrial machinery. 

The architecture simulates a high-throughput, horizontally scalable data pipeline that isolates the HTTP request-response cycle from disk I/O bottlenecks using in-memory streaming, asynchronous background workers, and partitioned relational storage.

## System Architecture

The platform utilizes a decoupled, asynchronous processing pipeline:

┌────────────────────────────────────────────────────────┐
│   Edge Devices / Simulators (Sensors, Inverters, PLCs) │
└───────────────────────────┬────────────────────────────┘
                            │ HTTPS / REST (1,000+ req/sec)
                            ▼
┌────────────────────────────────────────────────────────┐
│               FastAPI Ingestion Gateway                │
│       (Device Token Auth + Pydantic Validation)        │
└─────────────┬────────────────────────────┬─────────────┘
              │ Non-blocking XADD          │ Live Status HSET
              ▼                            ▼
┌──────────────────────────────┐ ┌───────────────────────┐
│     Redis 7.2 Streams        │ │  Redis In-Memory State│
│   (stream:telemetry:raw)     │ │  (device:live:{id})   │
└─────────────┬────────────────┘ └───────────────────────┘
              │ Consumer Groups
              ├─────────────────────────────────────────┐
              ▼                                         ▼
┌──────────────────────────────┐          ┌──────────────────────────────┐
│  Async Ingestion Persister   │          │  Celery / Anomaly Evaluator  │
│  (Micro-Batch Buffer Worker) │          │  (Sliding Window / Z-Score)  │
└─────────────┬────────────────┘          └─────────────┬────────────────┘
              │ Bulk COPY / Batch Insert                │ Alert Triggered
              ▼                                         ▼
┌──────────────────────────────┐          ┌──────────────────────────────┐
│  PostgreSQL 16 Storage Layer │          │   Redis Pub/Sub Event Bus    │
│ (Monthly Range Partitioning) │          │   (ch:site:{id}:telemetry)   │
└─────────────┬────────────────┘          └─────────────┬────────────────┘
              │ Rollups & Aggregates                    │ Real-Time Broadcast
              ▼                                         ▼
┌──────────────────────────────┐          ┌──────────────────────────────┐
│  Celery Beat Downsampling    │          │  FastAPI WebSocket Gateway   │
│ (Hourly/Daily Aggregate DB)  │          │   (/ws/v1/sites/{site_id})   │
└──────────────────────────────┘          └─────────────┬────────────────┘
                                                        │ Push JSON
                                                        ▼
                                          ┌──────────────────────────────┐
                                          │  Industrial Dashboard / UI   │
                                          └──────────────────────────────┘

## Core Technical Achievements & Scaling Solutions

*   **Ingestion Bottleneck Mitigation:** Direct relational database inserts collapse under high-frequency IoT write loads. VoltPulse buffers incoming JSON payloads into a Redis Stream via non-blocking `XADD` operations (sub-2ms response times), completely decoupling the API ingestion layer from disk I/O.
*   **Time-Series Storage Optimization:** The `telemetry_readings` table utilizes PostgreSQL 16 Declarative Range Partitioning (partitioned by month). This enables the query planner to execute aggressive partition pruning on historical analytics queries, preventing index degradation as the table scales into tens of millions of rows.
*   **High-Speed Binary Bulk Persistence:** The stream consumer worker bypasses SQLAlchemy ORM overhead entirely, pulling micro-batches from Redis and utilizing `asyncpg` binary `copy_records_to_table()` to stream records directly into PostgreSQL.
*   **Vectorized Anomaly Detection:** Real-time statistical anomaly detection is executed using `NumPy` to calculate sliding-window Z-scores over the last 100 observations stored in a Redis Sorted Set. Values breaching $3.0\sigma$ immediately trigger incident broadcasts.
*   **Idempotent Background Downsampling:** Celery Beat schedules background workers to compress raw, high-fidelity kW measurements into hourly energy aggregates. The system calculates kWh consumption using the trapezoidal integration rule: $\text{Energy (kWh)} = \int P(t) dt$.

## Technology Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Language** | Python 3.12+ | Asynchronous backend runtime |
| **API Gateway** | FastAPI | High-throughput ASGI framework for REST & WebSockets |
| **Database** | PostgreSQL 16+ | Relational metadata and partitioned time-series storage |
| **DB Driver** | SQLAlchemy 2.0 / `asyncpg` | Async connection pooling & binary-level data copying |
| **Message Broker** | Redis 7.2+ | Redis Streams (`XREADGROUP`), Pub/Sub, and live state caching |
| **Task Queue** | Celery 5.3+ | Asynchronous task processing, downsampling, and alert routing |
| **Math / Stats** | NumPy | Vectorized rolling window statistics |

## Running the Platform Locally

Ensure Docker and Docker Compose are installed.

1. Clone the repository and initialize the virtual environment.
2. Spin up the backing services: `docker compose up -d postgres redis`
3. Run the database migrations: `alembic upgrade head`
4. Start the application servers and background workers: `./dev.sh`
5. Inject the seed data and run the hardware edge simulator: `python -m simulator.runner --rate 1.0`