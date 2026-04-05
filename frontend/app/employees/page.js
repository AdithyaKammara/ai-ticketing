'use client';
import { useState, useEffect } from 'react';
import axios from 'axios';

const API = process.env.NEXT_PUBLIC_API_URL;

const availabilityColor = (a) => {
  if (a === 'Available') return 'bg-green-100 text-green-700';
  if (a === 'Busy') return 'bg-yellow-100 text-yellow-700';
  return 'bg-red-100 text-red-700';
};

export default function Employees() {
  const [employees, setEmployees] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ name: '', email: '', department: '', role: '', skills: '' });
  const [filterDept, setFilterDept] = useState('');

  useEffect(() => { fetchEmployees(); }, [filterDept]);

  const fetchEmployees = async () => {
    const params = filterDept ? { department: filterDept } : {};
    const res = await axios.get(`${API}/employees`, { params });
    setEmployees(res.data);
  };

  const addEmployee = async () => {
    await axios.post(`${API}/employees`, form);
    setShowAdd(false);
    setForm({ name: '', email: '', department: '', role: '', skills: '' });
    fetchEmployees();
  };

  const updateAvailability = async (id, availability) => {
    await axios.put(`${API}/employees/${id}`, { availability });
    fetchEmployees();
  };

  const deactivate = async (id) => {
    await axios.delete(`${API}/employees/${id}`);
    fetchEmployees();
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">Employee Directory</h1>
        <div className="flex gap-4 text-sm items-center">
          <a href="/" className="text-blue-600 hover:underline">Submit Ticket</a>
          <a href="/dashboard" className="text-blue-600 hover:underline">Dashboard</a>
          <a href="/analytics" className="text-blue-600 hover:underline">Analytics</a>
          <button onClick={() => setShowAdd(true)}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm">+ Add Employee</button>
        </div>
      </div>

      <div className="px-6 py-4">
        <select className="border rounded-lg px-3 py-2 text-sm bg-white"
          value={filterDept} onChange={e => setFilterDept(e.target.value)}>
          <option value="">All Departments</option>
          {['Engineering', 'IT', 'Finance', 'HR', 'DevOps', 'Product'].map(d => (
            <option key={d}>{d}</option>
          ))}
        </select>
      </div>

      <div className="px-6 pb-6">
        <div className="bg-white rounded-xl shadow overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                {['Name', 'Department', 'Role', 'Skills', 'Load', 'Availability', 'Actions'].map(h => (
                  <th key={h} className="text-left px-4 py-3 font-medium text-gray-600">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {employees.map(e => (
                <tr key={e.id} className="border-b hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">{e.name}</td>
                  <td className="px-4 py-3 text-gray-600">{e.department}</td>
                  <td className="px-4 py-3 text-gray-600">{e.role}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {e.skills.split(',').map(s => (
                        <span key={s} className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded text-xs">{s.trim()}</span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{e.ticket_load}</td>
                  <td className="px-4 py-3">
                    <select className={`text-xs px-2 py-1 rounded font-medium border-0 ${availabilityColor(e.availability)}`}
                      value={e.availability} onChange={ev => updateAvailability(e.id, ev.target.value)}>
                      {['Available', 'Busy', 'On Leave'].map(a => <option key={a}>{a}</option>)}
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <button onClick={() => deactivate(e.id)}
                      className="text-red-500 hover:text-red-700 text-xs">Deactivate</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {showAdd && (
        <div className="fixed inset-0 bg-black bg-opacity-40 z-50 flex items-center justify-center">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md">
            <h2 className="text-lg font-bold mb-4">Add Employee</h2>
            <div className="space-y-3">
              {['name', 'email', 'role', 'skills'].map(f => (
                <div key={f}>
                  <label className="block text-sm font-medium text-gray-700 mb-1 capitalize">{f}</label>
                  <input className="w-full border rounded-lg px-3 py-2 text-sm"
                    value={form[f]} onChange={e => setForm({ ...form, [f]: e.target.value })}
                    placeholder={f === 'skills' ? 'Python, Backend, Bug Fixing' : ''} />
                </div>
              ))}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Department</label>
                <select className="w-full border rounded-lg px-3 py-2 text-sm"
                  value={form.department} onChange={e => setForm({ ...form, department: e.target.value })}>
                  <option value="">Select...</option>
                  {['Engineering', 'IT', 'Finance', 'HR', 'DevOps', 'Product'].map(d => (
                    <option key={d}>{d}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex gap-3 mt-4">
              <button onClick={addEmployee} className="flex-1 bg-blue-600 text-white py-2 rounded-lg text-sm">Add</button>
              <button onClick={() => setShowAdd(false)} className="flex-1 border py-2 rounded-lg text-sm">Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}