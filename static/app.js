// Umbrella Demo App (Karamstay PG Rental): Frontend Controller

let activeRoomNumber = "ROOM-101";

document.addEventListener("DOMContentLoaded", () => {
  loadRooms();
  pollMetrics();
  pollEvents();
  setInterval(pollMetrics, 2000);
  setInterval(pollEvents, 2500);
});

async function loadRooms() {
  try {
    const res = await fetch("/rooms");
    const rooms = await res.json();
    const container = document.getElementById("rooms-container");
    if (!container) return;

    container.innerHTML = rooms.map(r => `
      <div class="room-card">
        <div class="room-head">
          <div class="room-number">${r.room_number}</div>
          <span style="font-size:0.75rem; color:#10b981; font-weight:700;">Floor ${r.floor}</span>
        </div>
        <div class="room-type">${r.room_type}</div>
        <div class="room-rent">₹${r.rent.toLocaleString()} <span style="font-size:0.75rem; color:var(--text-muted); font-weight:normal;">/ mo</span></div>
        <div class="amenities-tag">✨ ${r.amenities}</div>
        <div class="room-actions">
          <button style="flex:1; padding:6px 10px; font-size:0.8rem;" onclick="openBookingModal('${r.room_number}')">
            Reserve Bed
          </button>
          <button class="btn-outline" style="padding:6px 10px; font-size:0.8rem;" onclick="openPaymentModal('${r.room_number}', ${r.rent})">
            Pay Rent
          </button>
        </div>
      </div>
    `).join("");
  } catch (err) {
    console.error("Failed to load rooms:", err);
  }
}

async function pollMetrics() {
  try {
    const res = await fetch("/metrics");
    const data = await res.json();

    document.getElementById("hud-pool-size").textContent = `POOL_SIZE = ${data.pool_size}`;
    document.getElementById("hud-pool-checkedout").textContent = `${data.checked_out_connections} / ${data.pool_size}`;
    document.getElementById("m-checkedout").textContent = data.checked_out_connections;
    document.getElementById("m-utilization").textContent = `${data.utilization_pct}%`;

    const hudStatus = document.getElementById("hud-backend-status");
    if (data.checked_out_connections >= data.pool_size && data.pool_size <= 2) {
      hudStatus.textContent = "POOL SATURATED";
      hudStatus.style.color = "var(--accent-amber)";
    }
  } catch (err) {
    // Backend may be momentarily unreachable under severe crash
  }
}

async function pollEvents() {
  try {
    const res = await fetch("/api/events");
    const data = await res.json();
    const container = document.getElementById("events-container");
    if (!container || !data.events || data.events.length === 0) return;

    container.innerHTML = data.events.map(e => {
      const isErr = e.status_code >= 500;
      const isSuccess = e.status_code === 201;
      const cls = isErr ? "feed-item feed-err" : (isSuccess ? "feed-item feed-success" : "feed-item");
      return `
        <div class="${cls}">
          <div style="display:flex; justify-content:space-between; color:var(--text-muted); font-size:0.7rem;">
            <span>[${e.type}]</span>
            <span>${e.timestamp}</span>
          </div>
          <div style="font-weight:600; margin-top:2px;">${e.message}</div>
        </div>
      `;
    }).join("");
  } catch (err) {
    console.error("Failed to poll events:", err);
  }
}

async function trigger10Payments() {
  const btn = document.getElementById("btn-chaos-10");
  btn.disabled = true;
  btn.textContent = "⚡ Simulating 10 Payments...";

  const banner = document.getElementById("alert-banner");
  banner.style.display = "none";

  try {
    const res = await fetch("/api/chaos/10-payments", { method: "POST" });
    const data = await res.json();

    // Update metrics strip
    document.getElementById("m-total").textContent = data.total_requests;
    document.getElementById("m-failed").textContent = data.failed_requests;
    document.getElementById("m-fail-rate").textContent = `${data.failure_rate_pct}%`;
    document.getElementById("m-latency").textContent = `${data.avg_latency_ms} ms`;

    banner.style.display = "block";
    const hudStatus = document.getElementById("hud-backend-status");

    if (data.failed_requests > 0) {
      hudStatus.textContent = "CRASH / DOWN (500)";
      hudStatus.style.color = "var(--accent-red)";

      banner.className = "alert-box alert-danger";
      banner.innerHTML = `
        <strong>🚨 BACKEND CRASH DETECTED UNDER 10 SIMULTANEOUS PAYMENTS:</strong><br>
        <div style="margin-top:6px;">
          • <strong>${data.failed_requests} out of 10 users</strong> received <strong>HTTP 500 Crashes</strong> (${data.failure_rate_pct}% failure rate).<br>
          • <strong>Root Exception:</strong> <code>${data.first_error_type}: ${data.first_error_msg}</code><br>
          • <strong>Cause:</strong> 1.4s gateway hold time exceeded QueuePool timeout (1.0s) with constrained POOL_SIZE=2.<br>
          • <strong>UMBRELLA Agent Status:</strong> Incident dispatched to Mission Control! Open Mission Control to view live AST diagnosis & patch approval.
        </div>
      `;
    } else {
      hudStatus.textContent = "HEALTHY";
      hudStatus.style.color = "var(--accent-green)";

      banner.className = "alert-box alert-success";
      banner.innerHTML = `
        <strong>🎉 ALL 10 PAYMENTS COMPLETED SUCCESSFULLY:</strong><br>
        10/10 simultaneous tenant transactions processed with 0 errors! Average latency: ${data.avg_latency_ms} ms. Operational headroom is sufficient!
      `;
    }

    pollEvents();
    pollMetrics();
  } catch (err) {
    alert("Request error: " + err);
  } finally {
    btn.disabled = false;
    btn.textContent = "⚡ Fire 10 Simultaneous Payments (1.4s Lock)";
  }
}

async function trigger100Users() {
  const btn = document.getElementById("btn-chaos-100");
  btn.disabled = true;
  btn.textContent = "🔥 Running 100 Tenants...";

  const banner = document.getElementById("alert-banner");
  banner.style.display = "none";

  try {
    const res = await fetch("/api/chaos/100-users-1rps", { method: "POST" });
    const data = await res.json();

    document.getElementById("m-total").textContent = data.total_requests;
    document.getElementById("m-failed").textContent = data.failed_requests;
    document.getElementById("m-fail-rate").textContent = `${data.failure_rate_pct}%`;
    document.getElementById("m-latency").textContent = `${data.avg_latency_ms} ms`;

    banner.style.display = "block";
    const hudStatus = document.getElementById("hud-backend-status");

    if (data.failed_requests > 0) {
      hudStatus.textContent = "OVERLOAD DOWN (500)";
      hudStatus.style.color = "var(--accent-red)";

      banner.className = "alert-box alert-danger";
      banner.innerHTML = `
        <strong>🚨 BACKEND EXHAUSTION UNDER 100 CONCURRENT USERS AT 1 RPS:</strong><br>
        <div style="margin-top:6px;">
          • <strong>${data.failed_requests} out of 100 requests</strong> crashed with HTTP 500 (${data.failure_rate_pct}% failure).<br>
          • <strong>Exception:</strong> <code>${data.first_error_type}: ${data.first_error_msg}</code><br>
          • Capacity bottleneck: QueuePool unable to sustain concurrent tenant inflow.
        </div>
      `;
    } else {
      hudStatus.textContent = "HEALTHY";
      hudStatus.style.color = "var(--accent-green)";

      banner.className = "alert-box alert-success";
      banner.innerHTML = `
        <strong>🎉 ALL 100 CONCURRENT TENANT REQUESTS PASSED WITH 0 ERRORS!</strong><br>
        Avg Latency: ${data.avg_latency_ms} ms | P95 Latency: ${data.p95_latency_ms} ms.
      `;
    }

    pollEvents();
    pollMetrics();
  } catch (err) {
    alert("Request error: " + err);
  } finally {
    btn.disabled = false;
    btn.textContent = "🔥 Trigger 100 Concurrent Tenants Load (1 RPS)";
  }
}

async function resetBackend() {
  try {
    const res = await fetch("/reset", { method: "POST" });
    const data = await res.json();
    const banner = document.getElementById("alert-banner");
    banner.style.display = "block";
    banner.className = "alert-box alert-success";
    banner.textContent = "Backend database pool reset to constrained state: POOL_SIZE=2, MAX_OVERFLOW=0.";

    document.getElementById("m-total").textContent = "0";
    document.getElementById("m-failed").textContent = "0";
    document.getElementById("m-fail-rate").textContent = "0%";
    document.getElementById("m-latency").textContent = "0 ms";

    document.getElementById("hud-backend-status").textContent = "HEALTHY";
    document.getElementById("hud-backend-status").style.color = "var(--accent-green)";

    pollMetrics();
    pollEvents();
  } catch (err) {
    alert("Reset failed: " + err);
  }
}

async function triggerUmbrellaHeal() {
  try {
    const res = await fetch("http://localhost:8000/api/council/heal?grant_hitl=true", { method: "POST" });
    const data = await res.json();
    if (data.agent_4_executor && data.agent_4_executor.test_suite_passed) {
      // Reload config
      await fetch("/api/config/reload", { method: "POST" });
      alert("🎉 UMBRELLA Council successfully healed the backend! Pool capacity scaled.");
      pollMetrics();
      pollEvents();
    } else {
      alert("UMBRELLA Council triggered. Check Mission Control at http://localhost:8000");
    }
  } catch (err) {
    alert("Could not reach UMBRELLA Mission Control at http://localhost:8000. Ensure start_platform.py is running!");
  }
}

function openBookingModal(roomNumber) {
  activeRoomNumber = roomNumber;
  document.getElementById("modal-room-number").value = roomNumber;
  document.getElementById("booking-modal").style.display = "flex";
}

function closeBookingModal() {
  document.getElementById("booking-modal").style.display = "none";
}

async function submitBooking() {
  const name = document.getElementById("modal-tenant-name").value;
  const phone = document.getElementById("modal-tenant-phone").value;
  const bed = document.getElementById("modal-bed-number").value;

  try {
    const res = await fetch("/book-room", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tenant_name: name,
        phone: phone,
        room_number: activeRoomNumber,
        bed_number: bed
      })
    });
    const data = await res.json();
    closeBookingModal();
    pollEvents();
    alert(`🎉 Booking confirmed! Booking ID: #${data.booking_id} for ${data.tenant_name}`);
  } catch (err) {
    alert("Booking failed: " + err);
  }
}

function openPaymentModal(roomNumber, amount) {
  document.getElementById("pay-amount").value = amount;
  document.getElementById("payment-modal").style.display = "flex";
}

function closePaymentModal() {
  document.getElementById("payment-modal").style.display = "none";
}

async function submitPayment() {
  const bId = parseInt(document.getElementById("pay-booking-id").value) || 1;
  const name = document.getElementById("pay-tenant-name").value;
  const amount = parseFloat(document.getElementById("pay-amount").value) || 8500;
  const method = document.getElementById("pay-method").value;

  try {
    const res = await fetch("/pay-rent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        booking_id: bId,
        tenant_name: name,
        amount: amount,
        payment_method: method
      })
    });
    const data = await res.json();
    closePaymentModal();
    pollEvents();
    alert(`✓ Payment Successful! Ref: ${data.transaction_ref} | Invoice: ${data.invoice_id}`);
  } catch (err) {
    alert("Payment transaction failed: " + err);
  }
}

function clearEvents() {
  document.getElementById("events-container").innerHTML = '<div class="feed-item">Event log cleared.</div>';
}
