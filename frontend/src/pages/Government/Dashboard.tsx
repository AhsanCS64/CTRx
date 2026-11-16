import React from 'react';
import { Link } from 'react-router-dom';

const Dashboard: React.FC = () => {
  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">Government Dashboard</h1>
      <ul className="space-y-2">
        <li>
          <Link to="/government/review-queue" className="text-blue-600 underline">
            Review Queue
          </Link>
        </li>
        <li>
          <Link to="/government/certificate-list" className="text-blue-600 underline">
            Certificate List
          </Link>
        </li>
      </ul>
    </div>
  );
};

export default Dashboard;
