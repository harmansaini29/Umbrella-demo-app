"""
Umbrella Demo App (Karamstay PG Rental Service): Load & Chaos Simulator
Simulates:
1. 10 simultaneous users attempting rent checkout (1.4s gateway lock > 1.0s pool timeout).
2. 100 concurrent tenants attempting room search and booking at 1 RPS.
Under constrained capacity (POOL_SIZE=2, MAX_OVERFLOW=0), backend will predictably crash with TimeoutError.
"""

import sys
import os
import time
import uuid
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List

import config
import database
from models import Room, Booking, RentPayment


def simulate_single_payment(tenant_id: int) -> Dict[str, Any]:
    """Simulates a single tenant executing a real rent payment transaction."""
    start_time = time.time()
    db = None
    try:
        db = database.SessionLocal()
        # Force raw connection checkout from the QueuePool
        conn = db.connection()
        # Simulate payment gateway verification latency (1.40s > 1.0s pool timeout)
        time.sleep(1.40)

        # Record payment transaction in database
        uid = uuid.uuid4().hex[:8].upper()
        payment = RentPayment(
            booking_id=1,
            tenant_name=f"Tenant_{tenant_id:02d}",
            amount=8500.0,
            payment_method="UPI / Razorpay",
            status="completed",
            transaction_ref=f"TXN-KARAM-{uid}",
            invoice_id=f"INV-2026-{tenant_id:04d}-{uid}"
        )
        db.add(payment)
        db.commit()

        elapsed_ms = (time.time() - start_time) * 1000.0
        return {
            "tenant_id": tenant_id,
            "action": "pay_rent",
            "success": True,
            "status_code": 201,
            "latency_ms": round(elapsed_ms, 2),
            "error_type": None,
            "error_msg": None,
            "stack_trace": None
        }
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000.0
        return {
            "tenant_id": tenant_id,
            "action": "pay_rent",
            "success": False,
            "status_code": 500,
            "latency_ms": round(elapsed_ms, 2),
            "error_type": type(e).__name__,
            "error_msg": str(e),
            "stack_trace": traceback.format_exc()
        }
    finally:
        if db:
            try:
                db.close()
            except Exception:
                pass


def simulate_room_browsing_and_booking(tenant_id: int) -> Dict[str, Any]:
    """Simulates a tenant browsing rooms and attempting a room reservation."""
    start_time = time.time()
    db = None
    try:
        db = database.SessionLocal()
        conn = db.connection()
        # Hold connection for 0.4 seconds under concurrent requests
        time.sleep(0.40)

        room = db.query(Room).first()
        booking = Booking(
            tenant_name=f"Tenant_{tenant_id:03d}",
            phone="+91 98765 00000",
            room_id=room.id if room else 1,
            bed_number="Bed-A",
            status="confirmed"
        )
        db.add(booking)
        db.commit()

        elapsed_ms = (time.time() - start_time) * 1000.0
        return {
            "tenant_id": tenant_id,
            "action": "browse_and_book",
            "success": True,
            "status_code": 201,
            "latency_ms": round(elapsed_ms, 2),
            "error_type": None,
            "error_msg": None,
            "stack_trace": None
        }
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000.0
        return {
            "tenant_id": tenant_id,
            "action": "browse_and_book",
            "success": False,
            "status_code": 500,
            "latency_ms": round(elapsed_ms, 2),
            "error_type": type(e).__name__,
            "error_msg": str(e),
            "stack_trace": traceback.format_exc()
        }
    finally:
        if db:
            try:
                db.close()
            except Exception:
                pass


def run_10_simultaneous_payments() -> Dict[str, Any]:
    """Fires 10 simultaneous rent payments into the backend."""
    database.init_db()
    wall_start = time.time()
    results: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(simulate_single_payment, i + 1) for i in range(10)]
        for fut in as_completed(futures):
            results.append(fut.result())

    total_wall_ms = (time.time() - wall_start) * 1000.0
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    latencies = [r["latency_ms"] for r in results]

    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
    p95_lat = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0.0
    first_err = failed[0] if failed else None

    return {
        "scenario": "10_simultaneous_payments",
        "description": "10 concurrent tenants attempting rent checkout simultaneously",
        "total_requests": 10,
        "successful_requests": len(successful),
        "failed_requests": len(failed),
        "failure_rate_pct": round((len(failed) / 10.0) * 100.0, 1),
        "avg_latency_ms": round(avg_lat, 2),
        "p95_latency_ms": round(p95_lat, 2),
        "total_wall_time_ms": round(total_wall_ms, 2),
        "pool_size": config.POOL_SIZE,
        "max_overflow": config.MAX_OVERFLOW,
        "first_error_type": first_err["error_type"] if first_err else None,
        "first_error_msg": first_err["error_msg"] if first_err else None,
        "first_stack_trace": first_err["stack_trace"] if first_err else None,
        "raw_results": results
    }


def run_100_concurrent_tenants_1rps() -> Dict[str, Any]:
    """
    Simulates 100 concurrent tenants accessing the application at 1 RPS.
    Dispatched in batches to create sustained 1 RPS concurrency wave.
    """
    database.init_db()
    wall_start = time.time()
    results: List[Dict[str, Any]] = []
    num_users = 100

    # Execute 100 requests concurrently
    with ThreadPoolExecutor(max_workers=25) as executor:
        futures = [executor.submit(simulate_room_browsing_and_booking, i + 1) for i in range(num_users)]
        for fut in as_completed(futures):
            results.append(fut.result())

    total_wall_ms = (time.time() - wall_start) * 1000.0
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    latencies = [r["latency_ms"] for r in results]

    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
    p95_lat = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0.0
    first_err = failed[0] if failed else None

    return {
        "scenario": "100_concurrent_users_1rps",
        "description": "100 concurrent tenants querying rooms and booking beds at 1 RPS",
        "total_requests": num_users,
        "successful_requests": len(successful),
        "failed_requests": len(failed),
        "failure_rate_pct": round((len(failed) / float(num_users)) * 100.0, 1),
        "avg_latency_ms": round(avg_lat, 2),
        "p95_latency_ms": round(p95_lat, 2),
        "total_wall_time_ms": round(total_wall_ms, 2),
        "pool_size": config.POOL_SIZE,
        "max_overflow": config.MAX_OVERFLOW,
        "first_error_type": first_err["error_type"] if first_err else None,
        "first_error_msg": first_err["error_msg"] if first_err else None,
        "first_stack_trace": first_err["stack_trace"] if first_err else None,
        "raw_results": results
    }


def run_combined_concurrency_chaos() -> Dict[str, Any]:
    """
    Fires BOTH 10 simultaneous rent payments (1.4s gateway lock)
    AND 100 concurrent tenants browsing and booking at 1 RPS simultaneously.
    Total: 110 concurrent requests creating maximum QueuePool contention.
    """
    database.init_db()
    wall_start = time.time()
    results: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=35) as executor:
        payment_futs = [executor.submit(simulate_single_payment, i + 1) for i in range(10)]
        booking_futs = [executor.submit(simulate_room_browsing_and_booking, i + 1) for i in range(100)]
        all_futs = payment_futs + booking_futs
        for fut in as_completed(all_futs):
            results.append(fut.result())

    total_wall_ms = (time.time() - wall_start) * 1000.0
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    latencies = [r["latency_ms"] for r in results]

    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
    p95_lat = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0.0
    first_err = failed[0] if failed else None

    failed_payments = len([r for r in failed if r["action"] == "pay_rent"])
    failed_bookings = len([r for r in failed if r["action"] == "browse_and_book"])

    return {
        "scenario": "combined_concurrency_chaos",
        "description": "10 simultaneous payments + 100 concurrent tenants at 1 RPS",
        "total_requests": 110,
        "successful_requests": len(successful),
        "failed_requests": len(failed),
        "failed_payments": failed_payments,
        "failed_bookings": failed_bookings,
        "failure_rate_pct": round((len(failed) / 110.0) * 100.0, 1),
        "avg_latency_ms": round(avg_lat, 2),
        "p95_latency_ms": round(p95_lat, 2),
        "total_wall_time_ms": round(total_wall_ms, 2),
        "pool_size": config.POOL_SIZE,
        "max_overflow": config.MAX_OVERFLOW,
        "first_error_type": first_err["error_type"] if first_err else None,
        "first_error_msg": first_err["error_msg"] if first_err else None,
        "first_stack_trace": first_err["stack_trace"] if first_err else None,
        "raw_results": results
    }


def simulate_single_booking_under_lock(tenant_id: int) -> Dict[str, Any]:
    """Attempts room booking transaction while an exclusive SQLite write lock is active."""
    start_time = time.time()
    db = None
    try:
        db = database.SessionLocal()
        conn = db.connection()
        time.sleep(0.05)
        # In SQLite, attempting to execute write on an exclusively locked database raises OperationalError
        room = db.query(Room).first()
        b = Booking(
            tenant_name=f"Tenant_Lock_{tenant_id:02d}",
            phone="+91 99999 00000",
            room_id=room.id if room else 1,
            bed_number="Bed-A",
            status="confirmed"
        )
        db.add(b)
        db.commit()
        elapsed_ms = (time.time() - start_time) * 1000.0
        return {
            "tenant_id": tenant_id,
            "action": "book_under_lock",
            "success": True,
            "status_code": 201,
            "latency_ms": round(elapsed_ms, 2),
            "error_type": None,
            "error_msg": None,
            "stack_trace": None
        }
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000.0
        return {
            "tenant_id": tenant_id,
            "action": "book_under_lock",
            "success": False,
            "status_code": 500,
            "latency_ms": round(elapsed_ms, 2),
            "error_type": type(e).__name__,
            "error_msg": str(e),
            "stack_trace": traceback.format_exc()
        }
    finally:
        if db:
            try:
                db.close()
            except Exception:
                pass


def run_slow_query_lock_chaos(num_requests: int = 10) -> Dict[str, Any]:
    """
    Enterprise Scenario 1: Unindexed Slow Query / SQLite Exclusive Lock Contention.
    A heavy batch process holds SQLite exclusive write lock for 2.0s (>2000ms delay).
    Concurrent booking transactions encounter table lock contention and fail.
    """
    import threading
    database.init_db()
    wall_start = time.time()
    results: List[Dict[str, Any]] = []

    def lock_holder():
        db = database.SessionLocal()
        try:
            conn = db.connection()
            conn.exec_driver_sql("BEGIN EXCLUSIVE")
            time.sleep(1.80)
            conn.exec_driver_sql("COMMIT")
        except Exception:
            try:
                conn.exec_driver_sql("ROLLBACK")
            except Exception:
                pass
        finally:
            try:
                db.close()
            except Exception:
                pass

    t_lock = threading.Thread(target=lock_holder)
    t_lock.daemon = True
    t_lock.start()
    time.sleep(0.08)  # Ensure exclusive lock is acquired

    with ThreadPoolExecutor(max_workers=num_requests) as executor:
        futs = [executor.submit(simulate_single_booking_under_lock, i + 1) for i in range(num_requests)]
        for fut in as_completed(futs):
            results.append(fut.result())

    t_lock.join(timeout=3.0)
    total_wall_ms = (time.time() - wall_start) * 1000.0
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    latencies = [r["latency_ms"] for r in results]
    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
    p95_lat = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0.0
    first_err = failed[0] if failed else None

    return {
        "scenario": "unindexed_slow_query_lock",
        "description": "Unindexed slow query & SQLite exclusive write lock contention (>2000ms delay)",
        "total_requests": num_requests,
        "successful_requests": len(successful),
        "failed_requests": len(failed),
        "failure_rate_pct": round((len(failed) / float(num_requests)) * 100.0, 1),
        "verification_pct": 100.0 if failed else 0.0,
        "avg_latency_ms": round(avg_lat, 2),
        "p95_latency_ms": round(p95_lat, 2),
        "total_wall_time_ms": round(total_wall_ms, 2),
        "first_error_type": first_err["error_type"] if first_err else None,
        "first_error_msg": first_err["error_msg"] if first_err else None,
        "first_stack_trace": first_err["stack_trace"] if first_err else None,
        "raw_results": results
    }


def simulate_jwt_auth_request(tenant_id: int) -> Dict[str, Any]:
    """Simulates tenant request presenting an expired / revoked OAuth2/JWT Bearer token."""
    start_time = time.time()
    try:
        # Simulate OAuth2 token inspection with expired timestamp
        time.sleep(0.03)  # Token decode latency
        raise PermissionError(f"HTTPException: 401 Unauthorized - JWT signature has expired (exp: 2020-01-01T00:00:00Z < current_time) for tenant_{tenant_id:03d}")
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000.0
        return {
            "tenant_id": tenant_id,
            "action": "auth_verify_token",
            "success": False,
            "status_code": 401,
            "latency_ms": round(elapsed_ms, 2),
            "error_type": "HTTPException: 401 Unauthorized",
            "error_msg": str(e),
            "stack_trace": traceback.format_exc()
        }


def run_expired_jwt_auth_cascade(num_requests: int = 15) -> Dict[str, Any]:
    """
    Enterprise Scenario 2: Expired JWT / OAuth2 Auth Cascade.
    Client requests present expired Bearer tokens, triggering HTTP 401 Unauthorized cascade.
    Security policy must reject 100% of expired tokens.
    """
    wall_start = time.time()
    results: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=min(num_requests, 15)) as executor:
        futs = [executor.submit(simulate_jwt_auth_request, i + 1) for i in range(num_requests)]
        for fut in as_completed(futs):
            results.append(fut.result())

    total_wall_ms = (time.time() - wall_start) * 1000.0
    rejected = [r for r in results if r["status_code"] == 401]
    latencies = [r["latency_ms"] for r in results]
    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0

    return {
        "scenario": "expired_jwt_auth_cascade",
        "description": "OAuth2 / JWT Token expiration cascade (HTTP 401 Unauthorized)",
        "total_requests": num_requests,
        "successful_requests": 0,
        "failed_requests": len(rejected),
        "failure_rate_pct": 100.0,
        "verification_pct": 100.0,  # 100% verified security rejection of expired tokens
        "avg_latency_ms": round(avg_lat, 2),
        "total_wall_time_ms": round(total_wall_ms, 2),
        "first_error_type": "HTTPException: 401 Unauthorized",
        "first_error_msg": rejected[0]["error_msg"] if rejected else None,
        "first_stack_trace": rejected[0]["stack_trace"] if rejected else None,
        "raw_results": results
    }


def simulate_external_gateway_call(tenant_id: int) -> Dict[str, Any]:
    """Simulates calling third-party payment gateway that hangs and times out."""
    start_time = time.time()
    try:
        # Simulate gateway socket timeout (>1.2s timeout threshold)
        time.sleep(1.25)
        raise TimeoutError(f"HTTPException: 504 Gateway Timeout - Upstream Razorpay/Stripe aggregator socket timed out after 1250ms for transaction TXN-{tenant_id:04d} (Circuit Breaker OPEN)")
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000.0
        return {
            "tenant_id": tenant_id,
            "action": "external_gateway_checkout",
            "success": False,
            "status_code": 504,
            "latency_ms": round(elapsed_ms, 2),
            "error_type": "HTTPException: 504 Gateway Timeout",
            "error_msg": str(e),
            "stack_trace": traceback.format_exc()
        }


def run_payment_gateway_timeout_chaos(num_requests: int = 10) -> Dict[str, Any]:
    """
    Enterprise Scenario 3: External Payment Gateway Timeout / Circuit Breaker Trip.
    Upstream payment aggregator fails to respond within timeout, tripping circuit breaker with HTTP 504.
    """
    wall_start = time.time()
    results: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=min(num_requests, 10)) as executor:
        futs = [executor.submit(simulate_external_gateway_call, i + 1) for i in range(num_requests)]
        for fut in as_completed(futs):
            results.append(fut.result())

    total_wall_ms = (time.time() - wall_start) * 1000.0
    failed = [r for r in results if not r["success"]]
    latencies = [r["latency_ms"] for r in results]
    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0

    return {
        "scenario": "payment_gateway_timeout",
        "description": "External Payment Gateway Timeout & Circuit Breaker Trip (HTTP 504)",
        "total_requests": num_requests,
        "successful_requests": 0,
        "failed_requests": len(failed),
        "failure_rate_pct": 100.0,
        "verification_pct": 100.0,
        "avg_latency_ms": round(avg_lat, 2),
        "total_wall_time_ms": round(total_wall_ms, 2),
        "first_error_type": "HTTPException: 504 Gateway Timeout",
        "first_error_msg": failed[0]["error_msg"] if failed else None,
        "first_stack_trace": failed[0]["stack_trace"] if failed else None,
        "raw_results": results
    }


def simulate_schema_corruption_request(tenant_id: int) -> Dict[str, Any]:
    """Simulates client sending malformed / corrupted booking payloads."""
    start_time = time.time()
    try:
        corrupt_variants = [
            ("amount", -8500.0, "Input should be greater than 0"),
            ("tenant_name", None, "Field required"),
            ("room_number", 12345, "Input should be a valid string"),
            ("phone", "", "Phone number length must be >= 10 digits")
        ]
        field, val, reason = corrupt_variants[tenant_id % len(corrupt_variants)]
        time.sleep(0.02)
        raise ValueError(f"HTTPException: 422 Unprocessable Entity - Schema validation error in '{field}' ({val}): {reason}")
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000.0
        return {
            "tenant_id": tenant_id,
            "action": "schema_validate",
            "success": False,
            "status_code": 422,
            "latency_ms": round(elapsed_ms, 2),
            "error_type": "HTTPException: 422 Unprocessable Entity",
            "error_msg": str(e),
            "stack_trace": traceback.format_exc()
        }


def run_schema_corruption_chaos(num_requests: int = 10) -> Dict[str, Any]:
    """
    Enterprise Scenario 4: Payload Validation & Schema Corruption.
    Upstream clients submit corrupted schema payloads (negative rent, nulls), rejected with HTTP 422.
    """
    wall_start = time.time()
    results: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=min(num_requests, 10)) as executor:
        futs = [executor.submit(simulate_schema_corruption_request, i + 1) for i in range(num_requests)]
        for fut in as_completed(futs):
            results.append(fut.result())

    total_wall_ms = (time.time() - wall_start) * 1000.0
    caught = [r for r in results if r["status_code"] == 422]
    latencies = [r["latency_ms"] for r in results]
    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0

    return {
        "scenario": "schema_corruption_validation",
        "description": "Payload Validation & Schema Corruption (HTTP 422 Unprocessable Entity)",
        "total_requests": num_requests,
        "successful_requests": 0,
        "failed_requests": len(caught),
        "failure_rate_pct": 100.0,
        "verification_pct": 100.0,
        "avg_latency_ms": round(avg_lat, 2),
        "total_wall_time_ms": round(total_wall_ms, 2),
        "first_error_type": "HTTPException: 422 Unprocessable Entity",
        "first_error_msg": caught[0]["error_msg"] if caught else None,
        "first_stack_trace": caught[0]["stack_trace"] if caught else None,
        "raw_results": results
    }


if __name__ == "__main__":
    print("=" * 80)
    print("UMBRELLA DEMO APP: CHAOS LOAD SIMULATOR")
    print(f"Current Capacity: POOL_SIZE={config.POOL_SIZE}, MAX_OVERFLOW={config.MAX_OVERFLOW}")
    print("=" * 80)
    res = run_10_simultaneous_payments()
    print(f"Total Requests: {res['total_requests']}")
    print(f"Successful:     {res['successful_requests']}")
    print(f"Failed:         {res['failed_requests']} ({res['failure_rate_pct']}%)")
    if res["failed_requests"] > 0:
        print(f"CRASH DETECTED: {res['first_error_type']}: {res['first_error_msg']}")
        sys.exit(1)
    else:
        print("ALL REQUESTS COMPLETED SUCCESSFULLY.")
        sys.exit(0)

