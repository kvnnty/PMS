"use client";

import React, { useEffect, useState } from "react";

interface Vehicle {
  no: number;
  car_plate: string;
  entry_time: string;
  exit_time: string | null;
  payment_status: string;
  due_payment: number;
}

interface Alert {
  id: number;
  car_plate: string;
  alert_time: string;
  due_payment: number;
  alert_type: string;
  resolved: number;
  notes: string;
}

interface Stats {
  total_vehicles: number;
  unpaid_vehicles: number;
  active_alerts: number;
}

export default function Home() {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"vehicles" | "alerts">("vehicles");
  const [search, setSearch] = useState("");

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [vehiclesRes, alertsRes, statsRes] = await Promise.all([
        fetch("http://localhost:8000/api/vehicles"),
        fetch("http://localhost:8000/api/alerts"),
        fetch("http://localhost:8000/api/stats"),
      ]);

      if (!vehiclesRes.ok || !alertsRes.ok || !statsRes.ok) {
        throw new Error("Failed to fetch data");
      }

      const vehiclesData = await vehiclesRes.json();
      const alertsData = await alertsRes.json();
      const statsData = await statsRes.json();

      setVehicles(vehiclesData);
      setAlerts(alertsData);
      setStats(statsData);
    } catch (err) {
      setError("Failed to load data. Please try again.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000); // Poll every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const handleResolveAlert = async (id: number) => {
    try {
      const res = await fetch(`http://localhost:8000/api/resolve_alert/${id}`, {
        method: "POST",
      });
      if (res.ok) {
        setAlerts(alerts.map((alert) => (alert.id === id ? { ...alert, resolved: 1 } : alert)));
      } else {
        setError("Failed to resolve alert");
      }
    } catch (err) {
      setError("Failed to resolve alert");
      console.error(err);
    }
  };

  const filteredVehicles = vehicles.filter((v) => v.car_plate.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-900 text-gray-900 dark:text-gray-100 transition-colors">
      <div className="container mx-auto p-6">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold">Parking System Dashboard</h1>
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
            <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow">
              <h3 className="text-lg font-semibold">Total Vehicles Entrances</h3>
              <p className="text-2xl">{stats.total_vehicles}</p>
            </div>
            <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow">
              <h3 className="text-lg font-semibold">Unpaid Vehicles</h3>
              <p className="text-2xl">{stats.unpaid_vehicles}</p>
            </div>
            <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow">
              <h3 className="text-lg font-semibold">Active Alerts</h3>
              <p className="text-2xl">{stats.active_alerts}</p>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="flex mb-4">
          <button
            onClick={() => setActiveTab("vehicles")}
            className={`px-4 py-2 mr-2 rounded-t-lg ${activeTab === "vehicles" ? "bg-blue-500 text-white" : "bg-gray-200 dark:bg-gray-700"}`}>
            Vehicles
          </button>
          <button
            onClick={() => setActiveTab("alerts")}
            className={`px-4 py-2 rounded-t-lg ${activeTab === "alerts" ? "bg-blue-500 text-white" : "bg-gray-200 dark:bg-gray-700"}`}>
            Alerts
          </button>
        </div>

        {/* Search Bar */}
        {activeTab === "vehicles" && (
          <div className="mb-4">
            <input
              type="text"
              placeholder="Search by plate..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full p-2 rounded-lg border dark:border-gray-700 bg-white dark:bg-gray-800"
            />
          </div>
        )}

        {/* Loading and Error States */}
        {loading && <p className="text-center">Loading...</p>}
        {error && <p className="text-center text-red-500">{error}</p>}

        {/* Vehicles Table */}
        {activeTab === "vehicles" && !loading && !error && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-200 dark:bg-gray-700">
                  <th className="p-3 text-left">Plate</th>
                  <th className="p-3 text-left">Entry Time</th>
                  <th className="p-3 text-left">Exit Time</th>
                  <th className="p-3 text-left">Payment Due</th>
                  <th className="p-3 text-left">Payment Status</th>
                  <th className="p-3 text-left">Alert</th>
                </tr>
              </thead>
              <tbody>
                {filteredVehicles.map((v) => (
                  <tr key={v.no} className="hover:bg-gray-100 dark:hover:bg-gray-700">
                    <td className="p-3">{v.car_plate}</td>
                    <td className="p-3">{v.entry_time}</td>
                    <td className="p-3">{v.exit_time || "---"}</td>
                    <td className="p-3">{v.due_payment || "N/A"}</td>
                    <td className="p-3">{v.payment_status === "1" ? "Paid" : "Unpaid"}</td>
                    <td className="p-3">{v.payment_status === "0" ? "⚠️ Pending Payment" : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Alerts Table */}
        {activeTab === "alerts" && !loading && !error && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-200 dark:bg-gray-700">
                  <th className="p-3 text-left">Plate</th>
                  <th className="p-3 text-left">Alert Time</th>
                  <th className="p-3 text-left">Alert Type</th>
                  <th className="p-3 text-left">Due Payment</th>
                  <th className="p-3 text-left">Notes</th>
                  <th className="p-3 text-left">Status</th>
                  <th className="p-3 text-left">Action</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((a) => (
                  <tr key={a.id} className="hover:bg-gray-100 dark:hover:bg-gray-700">
                    <td className="p-3">{a.car_plate}</td>
                    <td className="p-3">{a.alert_time}</td>
                    <td className="p-3">{a.alert_type}</td>
                    <td className="p-3">{a.due_payment || "N/A"}</td>
                    <td className="p-3">{a.notes}</td>
                    <td className="p-3">{a.resolved === 1 ? "Resolved" : "Active"}</td>
                    <td className="p-3">
                      {a.resolved === 0 && (
                        <button onClick={() => handleResolveAlert(a.id)} className="px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600">
                          Resolve
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
