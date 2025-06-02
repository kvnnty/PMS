// app/page.tsx (Next.js 14+ App Router)
"use client";

import React, { useEffect, useState } from "react";

export default function Home() {
  const [vehicles, setVehicles] = useState<any[]>([]);

  useEffect(() => {
    fetch("http://localhost:8000/api/vehicles")
      .then((res) => res.json())
      .then((data) => setVehicles(data))
      .catch((err) => console.error(err));
  }, []);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Parking System Dashboard</h1>
      <table className="table-auto w-full border-collapse border border-gray-300">
        <thead>
          <tr className="bg-gray-100">
            <th className="border px-4 py-2">Plate</th>
            <th className="border px-4 py-2">Entry Time</th>
            <th className="border px-4 py-2">Exit Time</th>
            <th className="border px-4 py-2">Payment Due</th>
            <th className="border px-4 py-2">Payment Status</th>
            <th className="border px-4 py-2">Alert</th>
          </tr>
        </thead>
        <tbody>
          {vehicles.map((v, i) => (
            <tr key={i}>
              <td className="border px-4 py-2">{v.car_plate}</td>
              <td className="border px-4 py-2">{v.entry_time}</td>
              <td className="border px-4 py-2">{v.exit_time || "---"}</td>
              <td className="border px-4 py-2">{v.due_payment || "N/A"}</td>
              <td className="border px-4 py-2">{v.payment_status === "1" ? "Paid" : "Unpaid"}</td>
              <td className="border px-4 py-2">{v.payment_status === "0" ? "⚠️ Pending Payment" : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
