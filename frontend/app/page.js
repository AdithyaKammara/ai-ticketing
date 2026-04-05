'use client';
import { useState } from 'react';
import axios from 'axios';

const API = process.env.NEXT_PUBLIC_API_URL;

export default function Home() {
  const [form, setForm] = useState({ submitter_name: '', submitter_email: '', title: '', description: '' });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API}/tickets`, form);
      setResult(res.data);
    } catch (e) {
      setError('Failed to submit ticket. Is the backend running?');
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-gray-50 py-10 px-4">
      <div className="max-w-2xl mx-auto">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold text-gray-900">AI Support Tickets</h1>
          <p className="text-gray-500 mt-1">Submit a ticket and let AI handle the rest</p>
          <div className="mt-3 flex justify-center gap-4 text-sm">
            <a href="/dashboard" className="text-blue-600 hover:underline">Dashboard</a>
            <a href="/employees" className="text-blue-600 hover:underline">Employees</a>
            <a href="/analytics" className="text-blue-600 hover:underline">Analytics</a>
          </div>
        </div>

        {!result ? (
          <div className="bg-white rounded-xl shadow p-6 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Your Name</label>
              <input className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={form.submitter_name} onChange={e => setForm({ ...form, submitter_name: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Your Email</label>
              <input type="email" className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={form.submitter_email} onChange={e => setForm({ ...form, submitter_email: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Ticket Title</label>
              <input className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
              <textarea rows={5} className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
            </div>
            {error && <p className="text-red-500 text-sm">{error}</p>}
            <button onClick={handleSubmit} disabled={loading}
              className="w-full bg-blue-600 text-white py-2 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50">
              {loading ? 'Analyzing with AI...' : 'Submit Ticket'}
            </button>
          </div>
        ) : (
          <div className="bg-white rounded-xl shadow p-6 space-y-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-green-600 text-2xl">✓</span>
              <h2 className="text-xl font-semibold">Ticket Submitted</h2>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">Category</p>
                <p className="font-semibold">{result.category}</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">Severity</p>
                <p className={`font-semibold ${result.severity === 'Critical' ? 'text-red-600' : result.severity === 'High' ? 'text-orange-500' : result.severity === 'Medium' ? 'text-yellow-600' : 'text-green-600'}`}>
                  {result.severity}
                </p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">Sentiment</p>
                <p className="font-semibold">{result.sentiment}</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500">Status</p>
                <p className="font-semibold">{result.status}</p>
              </div>
            </div>
            {result.status === 'Auto-Resolved' && result.auto_response && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <p className="text-sm font-medium text-green-800 mb-1">AI Auto-Response:</p>
                <p className="text-sm text-green-700">{result.auto_response}</p>
              </div>
            )}
            {result.assigned_to && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-sm font-medium text-blue-800">Assigned to: {result.assigned_to.name} ({result.assigned_to.department})</p>
              </div>
            )}
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500">AI Summary</p>
              <p className="text-sm mt-1">{result.ai_summary}</p>
            </div>
            <button onClick={() => { setResult(null); setForm({ submitter_name: '', submitter_email: '', title: '', description: '' }); }}
              className="w-full border border-blue-600 text-blue-600 py-2 rounded-lg font-medium hover:bg-blue-50">
              Submit Another Ticket
            </button>
          </div>
        )}
      </div>
    </div>
  );
}