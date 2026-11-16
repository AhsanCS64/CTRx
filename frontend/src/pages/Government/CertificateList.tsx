import React from 'react';
import { Link } from 'react-router-dom';

const CertificateList: React.FC = () => {
  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">Certificates</h1>
      {/* TODO: fetch certificates via API and display in DataTable */}
      <p className="text-gray-500">Certificate list UI coming soon.</p>
    </div>
  );
};

export default CertificateList;
