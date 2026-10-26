# 🏠 Umbrella Demo App (Karamstay PG Rental Service)
> **Realistic High-Concurrency Microservice Modeling PG Room Rental, Monthly Rent Payments, and Autonomous Self-Healing via Project UMBRELLA**

---

## 🌟 Overview

The **Umbrella Demo App** is a standalone, production-grade microservice modeling **Karamstay** — India's premier smart PG room rental and coliving tenant management platform (featuring branches in Koramangala, Indiranagar, and Whitefield).

The service is intentionally designed with configurable capacity limits (`POOL_SIZE=2`, `MAX_OVERFLOW=0`) to reproduce realistic real-world concurrency bottlenecks and database lock contention under multi-tenant checkout spikes.

Embedded within the service is the **UMBRELLA Agentic Client SDK**, which continuously streams operational telemetry to Project UMBRELLA Mission Control (`http://localhost:8000`) and intercepts unhandled runtime exceptions for autonomous 6-agent closed-loop diagnosis and self-healing.

---

## 🚀 Key Features

1. **Karamstay PG Room & Bed Management**:
   - 12 pre-seeded room inventories: Single Bed Deluxe (AC), Double Sharing Bed, Triple Sharing Budget, and Executive Balcony Suites (rents from ₹6,500 to ₹16,000/month).
   - Real-time room availability, bed selection (`Bed-A`, `Bed-B`), and amenity specifications.
2. **Real Transaction Endpoints**:
   - `POST /book-room`: Books a tenant into a room with phone & KYC details.
   - `POST /pay-rent`: Processes monthly rent with realistic payment gateway latency (1.4s hold).
   - `GET /metrics`: Reports connection pool utilization, checked-out connections, and overflow status.
3. **Interactive Web UI Chaos Controls**:
   - **⚡ Fire 10 Simultaneous Payments**: 10 parallel tenants checkout simultaneously. With 1.4s gateway hold time exceeding the 1.0s pool timeout, 8 out of 10 requests crash with HTTP 500 (`sqlalchemy.exc.TimeoutError: QueuePool limit of size 2 overflow 0 reached`).
   - **🔥 Trigger 100 Concurrent Tenants Load (1 RPS)**: Emulates a high-traffic rush of 100 concurrent tenants browsing and booking beds, demonstrating connection pool exhaustion under sustained RPS.
   - **🔄 Reset Backend**: Restores database pool to initial constrained parameters (`POOL_SIZE=2`).
   - **🛡️ UMBRELLA Auto-Healing**: Triggers the 6-Agent Council on Project UMBRELLA to analyze AST, map topology blast radius, synthesize unified diffs, enforce HITL approval, and hot-reload capacity.

---

## 🛠️ Architecture & Components

```
Umbrella-demo-app/
├── config.py                 # Capacity limits (POOL_SIZE=2) & UMBRELLA integration settings
├── database.py               # SQLAlchemy QueuePool engine with dynamic reload support
├── models.py                 # Room, Booking, RentPayment SQLAlchemy schema
├── server.py                 # FastAPI microservice serving Karamstay UI & API endpoints
├── load_simulator.py         # Multi-threaded stress testing engine (10 payments / 100 users)
├── test_demo_app.py          # Comprehensive 5-part unit & concurrency verification suite
├── start_demo_app.py         # Microservice launcher
├── start_demo_app.bat        # Windows 1-click startup script
├── static/
│   ├── index.html            # Karamstay UI with Chaos Engine & Live Metrics Strip
│   ├── style.css             # Polished dark-mode responsive theme
│   └── app.js                # Real-time polling, booking, payment, and chaos triggers
└── umbrella_sdk/             # Embedded UMBRELLA Agentic Client SDK
    ├── __init__.py
    ├── client.py             # Heartbeat, telemetry reporting, and AST incident dispatch
    └── middleware.py         # FastAPI exception interceptor middleware
```

---

## 🏃 Running the Application

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Launch the Microservice
```bash
python start_demo_app.py
```
Access the Karamstay Web UI at:
👉 **`http://localhost:8002`**

### 3. Run Automated Concurrency Tests
```bash
python test_demo_app.py
```

---

## 🛡️ Project UMBRELLA Integration

When `UMBRELLA_AGENT_ENABLED = True` in `config.py`, this application:
1. Automatically registers with UMBRELLA Mission Control (`http://localhost:8000/api/sdk/register`).
2. Streams real-time connection pool metrics every 2 seconds (`/api/sdk/telemetry`).
3. Dispatches full AST coordinates, traceback frames, and pool metrics upon any 500 crash (`/api/sdk/incident`).
4. Accommodates zero-downtime hot reloading when UMBRELLA synthesizes and merges capacity patches to `config.py`.
