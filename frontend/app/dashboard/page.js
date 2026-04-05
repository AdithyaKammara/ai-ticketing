'use client';
import { useState, useEffect } from 'react';
import axios from 'axios';

const API = process.env.NEXT_PUBLIC_API_URL;

const severityColor = (s) => {
  if (s === 'Critical') return 'bg-red-100 text-red-700';
  if (s === 'High') return 'bg-orange-100 text-orange-700';
  if (s === 'Medium') return 'bg-yellow-100 text-yellow-700';
  return 'bg-green-100 text-green-700';
};

const statusColor = (s) => {
  if (s === 'Auto-Resolved') return 'bg-purple-100 text-purple-700';
  if (s === 'Resolved') return 'bg-green-100 text-green-700';
  if (s === 'In Progress') return 'bg-blue-100 text-blue-700';
  return 'bg-gray-100 text-gray-700';
};

export default function Dashboard() {
  const [tickets, setTickets] = useState([]);
  const [selected, setSelected] = useState(null);
  const [events, setEvents] = useState([]);
  const [note, setNote] = useState('');
  const [filters, setFilters] = useState({ status: '', department: '', severity: '' });
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchTickets(); }, [filters]);

  const fetchTickets = async () => {
    setLoading(true);
    const params = {};
    if (filters.status) params.status = filters.status;
    if (filters.department) params.department = filters.department;
    if (filters.severity) params.severity = filters.severity;
    const res = await axios.get(`${API}/tickets`, { params });
    setTickets(res.data);
    setLoading(false);
  };

  const openTicket = async (ticket) => {
    setSelected(ticket);
    const res = await axios.get(`${API}/tickets/${ticket.id}/events`);
    setEvents(res.data);
  };

  const updateStatus = async (status) => {
    await axios.patch(`${API}/tickets/${selected.id}/status`, { status });
    setSelected({ ...selected, status });
    fetchTickets();
  };

  const addNote = async () => {
    if (!note.trim()) return;
    await axios.post(`${API}/tickets/${selected.id}/events`, { note });
    setNote('');
    const res = await axios.get(`${API}/tickets/${selected.id}/events`);
    setEvents(res.data);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">Ticket Dashboard</h1>
        <div className="flex gap-4 text-sm">
          <a href="/" className="text-blue-600 hover:underline">Submit Ticket</a>
          <a href="/employees" className="text-blue-600 hover:underline">Employees</a>
          <a href="/analytics" className="text-blue-600 hover:underline">Analytics</a>
        </div>
      </div>

      <div className="px-6 py-4 flex gap-3">
        {['status', 'department', 'severity'].map(f => (
          <select key={f} className="border rounded-lg px-3 py-2 text-sm bg-white"
            value={filters[f]} onChange={e => setFilters({ ...filters, [f]: e.target.value })}>
            <option value="">All {f}s</option>
            {f === 'status' && ['New', 'In Progress', 'Resolved', 'Auto-Resolved'].map(o => <option key={o}>{o}</option>)}
            {f === 'department' && ['Engineering', 'IT', 'Finance', 'HR', 'DevOps', 'Product'].map(o => <option key={o}>{o}</option>)}
            {f === 'severity' && ['Critical', 'High', 'Medium', 'Low'].map(o => <option key={o}>{o}</option>)}
          </select>
        ))}
        <button onClick={fetchTickets} className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm">Refresh</button>
      </div>

      <div className="px-6 pb-6">
        {loading ? <p className="text-gray-500">Loading...</p> : (
          <div className="bg-white rounded-xl shadow overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  {['ID', 'Title', 'Category', 'Severity', 'Status', 'Assigned To', 'Created'].map(h => (
                    <th key={h} className="text-left px-4 py-3 font-medium text-gray-600">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tickets.map(t => (
                  <tr key={t.id} onClick={() => openTicket(t)}
                    className="border-b hover:bg-blue-50 cursor-pointer transition">
                    <td className="px-4 py-3 text-gray-500">#{t.id}</td>
                    <td className="px-4 py-3 font-medium text-gray-900 max-w-xs truncate">{t.title}</td>
                    <td className="px-4 py-3"><span className="bg-gray-100 text-gray-700 px-2 py-1 rounded text-xs">{t.category}</span></td>
                    <td className="px-4 py-3"><span className={`px-2 py-1 rounded text-xs font-medium ${severityColor(t.severity)}`}>{t.severity}</span></td>
                    <td className="px-4 py-3"><span className={`px-2 py-1 rounded text-xs font-medium ${statusColor(t.status)}`}>{t.status}</span></td>
                    <td className="px-4 py-3 text-gray-600">{t.assigned_to ? t.assigned_to.name : '—'}</td>
                    <td className="px-4 py-3 text-gray-400">{new Date(t.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
                {tickets.length === 0 && (
                  <tr><td colSpan={7} className="text-center py-8 text-gray-400">No tickets found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selected && (
        <div className="fixed inset-0 bg-black bg-opacity-40 z-50 flex justify-end">
          <div className="bg-white w-full max-w-lg h-full overflow-y-auto shadow-xl p-6">
            <div className="flex justify-between items-start mb-4">
              <h2 className="text-lg font-bold text-gray-900">{selected.title}</h2>
              <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-gray-600 text-2xl">×</button>
            </div>
            <div className="flex gap-2 mb-4">
              <span className={`px-2 py-1 rounded text-xs font-medium ${severityColor(selected.severity)}`}>{selected.severity}</span>
              <span className={`px-2 py-1 rounded text-xs font-medium ${statusColor(selected.status)}`}>{selected.status}</span>
              <span className="bg-gray-100 text-gray-700 px-2 py-1 rounded text-xs">{selected.category}</span>
            </div>
            <div className="bg-gray-50 rounded-lg p-3 mb-4">
              <p className="text-xs text-gray-500 mb-1">AI Summary</p>
              <p className="text-sm">{selected.ai_summary}</p>
            </div>
            {selected.auto_response && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-3 mb-4">
                <p className="text-xs text-green-700 font-medium mb-1">Auto Response</p>
                <p className="text-sm text-green-800">{selected.auto_response}</p>
              </div>
            )}
            {selected.assigned_to && (
              <div className="bg-blue-50 rounded-lg p-3 mb-4">
                <p className="text-xs text-blue-700 font-medium">Assigned to: {selected.assigned_to.name} — {selected.assigned_to.department}</p>
              </div>
            )}
            <div className="mb-4">
              <p className="text-sm font-medium text-gray-700 mb-2">Update Status</p>
              <select className="border rounded-lg px-3 py-2 text-sm w-full"
                value={selected.status} onChange={e => updateStatus(e.target.value)}>
                {['New', 'In Progress', 'Resolved', 'Auto-Resolved'].map(s => <option key={s}>{s}</option>)}
              </select>
            </div>
            <div className="mb-4">
              <p className="text-sm font-medium text-gray-700 mb-2">Timeline</p>
              <div className="space-y-2">
                {events.map(e => (
                  <div key={e.id} className="bg-gray-50 rounded p-2 text-xs">
                    <p className="font-medium text-gray-700">{e.action}</p>
                    {e.note && <p className="text-gray-500 mt-1">{e.note}</p>}
                    <p className="text-gray-400 mt-1">{new Date(e.timestamp).toLocaleString()}</p>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">Add Internal Note</p>
              <textarea rows={3} className="w-full border rounded-lg px-3 py-2 text-sm"
                value={note} onChange={e => setNote(e.target.value)} placeholder="Add a note..." />
              <button onClick={addNote} className="mt-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm">Add Note</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}