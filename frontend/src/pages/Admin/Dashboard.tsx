import React from 'react';
import { Link } from 'react-router-dom';

const AdminDashboard: React.FC = () => {
  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">Admin Dashboard</h1>
      <ul className="space-y-2">
        <li>
          <Link to="/admin/users" className="text-blue-600 underline">
            Users
          </Link>
        </li>
        <li>
          <Link to="/admin/officials" className="text-blue-600 underline">
            Officials
          </Link>
        </li>
        <li>
          <Link to="/admin/areas" className="text-blue-600 underline">
            Areas
          </Link>
        </li>
        <li>
          <Link to="/admin/settings" className="text-blue-600 underline">
            Settings
          </Link>
        </li>
        <li>
          <Link to="/admin/templates" className="text-blue-600 underline">
            Templates
          </Link>
        </li>
        <li>
          <Link to="/admin/audit-log" className="text-blue-600 underline">
            Audit Log
          </Link>
        </li>
      </ul>
    </div>
  );
};

export default AdminDashboard;
