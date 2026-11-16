import React, { useEffect, useState } from 'react';
import { DataTable, ErrorBanner } from '../../components';
import { getAuditLogs } from '../../api/admin';
import { Link } from 'react-router-dom';

type AuditLog = {
  id: string;
  actor_id: string;
  action: string;
  entity_type: string;
  timestamp: string;
};

const AuditLogPage: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLogs = async () => {
    try {
      const data = await getAuditLogs();
      setLogs(data);
    } catch (e: any) {
      setError(e.message || 'Failed to load audit logs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  const columns = [
    { header: 'Actor ID', accessor: 'actor_id' },
    { header: 'Action', accessor: 'action' },
    { header: 'Entity', accessor: 'entity_type' },
    { header: 'Timestamp', accessor: 'timestamp' },
  ];

  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">Audit Log</h1>
      {error && <ErrorBanner message={error} />}
      {loading ? (
        <p>Loading...</p>
      ) : (
        <DataTable data={logs} columns={columns} />
      )}
      <div className="mt-4">
        <Link to="/admin/dashboard" className="text-blue-600 underline">← Back to Dashboard</Link>
      </div>
    </div>
  );
};

export default AuditLogPage;
