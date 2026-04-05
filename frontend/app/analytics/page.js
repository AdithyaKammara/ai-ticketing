'use client';
import { useState, useEffect } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';

const API = process.env.NEXT_PUBLIC_API_URL;

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

export default function Analytics() {
  const [summary, setSummary] = useState(null);
  const [byDept, setByDept] = useState([]);
  const [topCats, setTopCats] = useState([]);

  useEffect(() => {
    axios.get(`${API}/analytics/summary`).then(r => setSummary(r.data));
    axios.get(`${API}/analytics/by-department`).then(r => setByDept(r.data));
    axios.get(`${API}/analytics/top-categories`).then(r => setTopCats(r.data));
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">Analytics Dashboard</h1>
        <div className="flex gap-4 text-sm">
          <a href="/" className="text-blue-600 hover:underline">Submit Ticket</a>
          <a href="/dashboard" className="text-blue-600 hover:underline">Dashboard</a>
          <a href="/employees" className="text-blue-600 hover:underline">Employees</a>
        </div>
      </div>

      <div className="px-6 py-6 space-y-6">
        {/* Stat Cards */}
        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-blue-600 text-white rounded-xl p-4">
              <p className="text-sm opacity-80">Total Open</p>
              <p className="text-3xl font-bold mt-1">{summary.total_open}</p>
            </div>
            <div className="bg-green-600 text-white rounded-xl p-4">
              <p className="text-sm opacity-80">Total Resolved</p>
              <p className="text-3xl font-bold mt-1">{summary.total_resolved}</p>
            </div>
            <div className="bg-purple-600 text-white rounded-xl p-4">
              <p className="text-sm opacity-80">Auto-Resolved</p>
              <p className="text-3xl font-bold mt-1">{summary.total_auto_resolved}</p>
            </div>
            <div className="bg-teal-600 text-white rounded-xl p-4">
              <p className="text-sm opacity-80">Auto-Resolution Rate</p>
              <p className="text-3xl font-bold mt-1">{summary.auto_resolution_rate}%</p>
            </div>
          </div>
        )}

        {/* Department Chart */}
        <div className="bg-white rounded-xl shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Open Tickets by Department</h2>
          {byDept.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={byDept}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="department" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="open_count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-gray-400 text-center py-10">No data yet — submit some tickets first!</p>
          )}
        </div>

        {/* Top Categories */}
        <div className="bg-white rounded-xl shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Top Ticket Categories</h2>
          {topCats.length > 0 ? (
            <div className="flex flex-col md:flex-row items-center gap-6">
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie data={topCats} dataKey="count" nameKey="category" cx="50%" cy="50%" outerRadius={90} label>
                    {topCats.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
              <div className="w-full md:w-64 space-y-2">
                {topCats.map((c, i) => (
                  <div key={c.category} className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                      <span className="text-sm font-medium">{c.category}</span>
                    </div>
                    <span className="text-sm text-gray-500">{c.count} tickets</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-gray-400 text-center py-10">No data yet — submit some tickets first!</p>
          )}
        </div>
      </div>
    </div>
  );
}