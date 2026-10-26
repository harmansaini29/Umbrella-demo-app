"""
Umbrella Demo App (Karamstay PG Rental Service): Test Suite
Validates:
1. Room inventory & reservation flow.
2. Monthly rent payment flow.
3. Concurrency crash under 10 simultaneous payments with POOL_SIZE=2.
4. Full recovery & zero errors when connection pool is scaled to POOL_SIZE=10.
"""

import os
import sys
import unittest
from datetime import datetime

import config
from database import init_db, SessionLocal, engine
from models import Room, Booking, RentPayment
from load_simulator import (
    run_10_simultaneous_payments,
    run_100_concurrent_tenants_1rps,
    run_combined_concurrency_chaos,
    run_slow_query_lock_chaos,
    run_expired_jwt_auth_cascade,
    run_payment_gateway_timeout_chaos,
    run_schema_corruption_chaos
)


class TestUmbrellaDemoApp(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        # Reset to constrained state before each test
        config.POOL_SIZE = 2
        config.MAX_OVERFLOW = 0
        config.POOL_TIMEOUT = 1.0
        init_db()

    def test_01_room_inventory_seeded(self):
        """Verifies Karamstay PG room inventory is automatically seeded."""
        db = SessionLocal()
        try:
            rooms = db.query(Room).all()
            self.assertGreaterEqual(len(rooms), 10, "Expected at least 10 seeded rooms")
            room_numbers = [r.room_number for r in rooms]
            self.assertIn("ROOM-101", room_numbers)
            self.assertIn("ROOM-201", room_numbers)
        finally:
            db.close()

    def test_02_booking_and_payment_flow(self):
        """Verifies tenant booking and payment transactions record correctly."""
        db = SessionLocal()
        try:
            room = db.query(Room).first()
            booking = Booking(
                tenant_name="Test Tenant",
                phone="+91 99999 88888",
                room_id=room.id,
                bed_number="Bed-A",
                status="confirmed"
            )
            db.add(booking)
            db.commit()
            db.refresh(booking)
            self.assertIsNotNone(booking.id)

            import uuid
            uid = uuid.uuid4().hex[:8]
            payment = RentPayment(
                booking_id=booking.id,
                tenant_name="Test Tenant",
                amount=9500.0,
                payment_method="UPI / Razorpay",
                status="completed",
                transaction_ref=f"TXN-TEST-{uid}",
                invoice_id=f"INV-TEST-{uid}"
            )
            db.add(payment)
            db.commit()
            db.refresh(payment)
            self.assertIsNotNone(payment.id)
            self.assertEqual(payment.status, "completed")
        finally:
            db.close()

    def test_03_10_simultaneous_payments_crash_under_constrained_pool(self):
        """
        Validates that under POOL_SIZE=2, firing 10 simultaneous payments
        reproduces real QueuePool exhaustion crashes (HTTP 500 / TimeoutError).
        """
        config.POOL_SIZE = 2
        config.MAX_OVERFLOW = 0
        config.POOL_TIMEOUT = 1.0
        init_db()

        res = run_10_simultaneous_payments()
        self.assertEqual(res["total_requests"], 10)
        self.assertGreater(res["failed_requests"], 0, "Constrained pool must produce failures under 10 concurrent payments")
        self.assertIn("TimeoutError", res["first_error_type"])
        print(f"\n[Verified Concurrency Crash]: {res['failed_requests']}/10 requests failed ({res['failure_rate_pct']}%)")

    def test_04_recovery_after_pool_scaled(self):
        """
        Validates that when POOL_SIZE is scaled to 10 (as done by UMBRELLA Council),
        all 10 simultaneous payments succeed with 0% failure.
        """
        config.POOL_SIZE = 10
        config.MAX_OVERFLOW = 5
        config.POOL_TIMEOUT = 3.0
        init_db()

        res = run_10_simultaneous_payments()
        self.assertEqual(res["total_requests"], 10)
        self.assertEqual(res["failed_requests"], 0, "Scaled pool must handle 10 concurrent payments with 0 errors")
        self.assertEqual(res["failure_rate_pct"], 0.0)
        print(f"\n[Verified Recovery]: 10/10 simultaneous payments succeeded! Avg Latency: {res['avg_latency_ms']} ms")

    def test_05_100_concurrent_tenants_traffic(self):
        """
        Validates 100 concurrent tenant requests under constrained vs scaled pool.
        """
        # 1. Constrained pool crashes
        config.POOL_SIZE = 2
        config.MAX_OVERFLOW = 0
        config.POOL_TIMEOUT = 1.0
        init_db()

        res_crashed = run_100_concurrent_tenants_1rps()
        self.assertEqual(res_crashed["total_requests"], 100)
        self.assertGreater(res_crashed["failed_requests"], 0, "100 concurrent requests must saturate constrained pool")
        print(f"\n[Verified 100 Tenants Crash]: {res_crashed['failed_requests']}/100 requests failed ({res_crashed['failure_rate_pct']}%)")

        # 2. Scaled pool recovers
        config.POOL_SIZE = 25
        config.MAX_OVERFLOW = 10
        config.POOL_TIMEOUT = 5.0
        init_db()

        res_recovered = run_100_concurrent_tenants_1rps()
        self.assertEqual(res_recovered["total_requests"], 100)
        self.assertEqual(res_recovered["failed_requests"], 0, "Scaled pool (POOL_SIZE=25) must handle 100 concurrent tenants")
        print(f"\n[Verified 100 Tenants Recovery]: 100/100 requests passed! Avg Latency: {res_recovered['avg_latency_ms']} ms")

    def test_06_combined_concurrency_chaos(self):
        """
        Validates combined chaos load (10 simultaneous payments + 100 concurrent tenants).
        Constrained pool must produce failures; scaled pool must handle all 110 requests cleanly.
        """
        # 1. Constrained pool
        config.POOL_SIZE = 2
        config.MAX_OVERFLOW = 0
        config.POOL_TIMEOUT = 1.0
        init_db()

        res_crashed = run_combined_concurrency_chaos()
        self.assertEqual(res_crashed["total_requests"], 110)
        self.assertGreater(res_crashed["failed_requests"], 0, "Combined chaos must crash constrained pool")
        print(f"\n[Verified Combined Chaos Crash]: {res_crashed['failed_requests']}/110 failed ({res_crashed['failure_rate_pct']}%)")

        # 2. Scaled pool
        config.POOL_SIZE = 30
        config.MAX_OVERFLOW = 10
        config.POOL_TIMEOUT = 5.0
        init_db()

        res_recovered = run_combined_concurrency_chaos()
        self.assertEqual(res_recovered["total_requests"], 110)
        self.assertEqual(res_recovered["failed_requests"], 0, "Scaled pool (POOL_SIZE=30) must handle combined chaos with 0 errors")
        print(f"\n[Verified Combined Chaos Recovery]: 110/110 requests passed! Avg Latency: {res_recovered['avg_latency_ms']} ms")

    def test_07_slow_query_lock_contention(self):
        """
        Enterprise Scenario 1: Unindexed Slow Query / SQLite Exclusive Lock Contention (>2000ms delay).
        Validates that exclusive write lock blocks concurrent transactions and produces predictable lock contention.
        """
        res = run_slow_query_lock_chaos(num_requests=10)
        self.assertEqual(res["total_requests"], 10)
        self.assertGreater(res["failed_requests"], 0, "Exclusive lock contention must produce failures under concurrency")
        self.assertEqual(res["verification_pct"], 100.0)
        print(f"\n[Verified SQLite Lock Contention]: {res['failed_requests']}/10 requests failed under lock ({res['failure_rate_pct']}%) - 100% Verified")

    def test_08_expired_jwt_auth_cascade(self):
        """
        Enterprise Scenario 2: Expired JWT / OAuth2 Authentication Cascade.
        Validates that 100% of expired tokens are intercepted and rejected with HTTP 401 Unauthorized.
        """
        res = run_expired_jwt_auth_cascade(num_requests=15)
        self.assertEqual(res["total_requests"], 15)
        self.assertEqual(res["failed_requests"], 15)
        self.assertEqual(res["verification_pct"], 100.0)
        self.assertIn("401", res["first_error_type"])
        print(f"\n[Verified Expired JWT Auth Cascade]: 15/15 requests intercepted (100% security gate enforced)")

    def test_09_external_payment_gateway_timeout(self):
        """
        Enterprise Scenario 3: External Payment Gateway Timeout & Circuit Breaker Trip.
        Validates that upstream gateway timeout (>1250ms) trips circuit breaker with HTTP 504.
        """
        res = run_payment_gateway_timeout_chaos(num_requests=10)
        self.assertEqual(res["total_requests"], 10)
        self.assertEqual(res["failed_requests"], 10)
        self.assertEqual(res["verification_pct"], 100.0)
        self.assertIn("504", res["first_error_type"])
        print(f"\n[Verified Gateway Timeout & Breaker]: 10/10 requests intercepted with HTTP 504 (100% Verified)")

    def test_10_schema_corruption_validation(self):
        """
        Enterprise Scenario 4: Payload Validation & Schema Corruption.
        Validates that malformed schema inputs (negative rent, nulls) are rejected with HTTP 422.
        """
        res = run_schema_corruption_chaos(num_requests=10)
        self.assertEqual(res["total_requests"], 10)
        self.assertEqual(res["failed_requests"], 10)
        self.assertEqual(res["verification_pct"], 100.0)
        self.assertIn("422", res["first_error_type"])
        print(f"\n[Verified Schema Corruption]: 10/10 corrupted payloads blocked with HTTP 422 (100% Verified)")


if __name__ == "__main__":
    unittest.main()

