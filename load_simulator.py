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
