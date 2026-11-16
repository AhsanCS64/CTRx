import React, { useEffect, useState } from 'react';
import { DataTable, ErrorBanner } from '../../components';
import { getSettings, updateSetting } from '../../api/admin';

type Setting = {
  key: string;
  value: string;
};

const SettingsPage: React.FC = () => {
  const [settings, setSettings] = useState<Setting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSettings = async () => {
    try {
      const data = await getSettings();
      setSettings(data);
    } catch (e: any) {
      setError(e.message || 'Failed to load settings');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  const handleChange = async (key: string, newValue: string) => {
    try {
      await updateSetting(key, newValue);
      fetchSettings();
    } catch (e: any) {
      setError(e.message || 'Failed to update setting');
    }
  };

  const columns = [
    { header: 'Key', accessor: 'key' },
    {
      header: 'Value',
      accessor: 'value',
      cell: (row: any) => (
        <input
          type="text"
          defaultValue={row.value}
          onBlur={e => handleChange(row.key, e.target.value)}
          className="input"
        />
      ),
    },
  ];

  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">System Settings</h1>
      {error && <ErrorBanner message={error} />}
      {loading ? (
        <p>Loading...</p>
      ) : (
        <DataTable data={settings} columns={columns} />
      )}
    </div>
  );
};

export default SettingsPage;
