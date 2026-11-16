import React, { useEffect, useState } from 'react';
import { DataTable, ErrorBanner } from '../../components';
import { getTemplates, createTemplate, setDefaultTemplate } from '../../api/admin';
import { Link } from 'react-router-dom';

type Template = {
  id: string;
  name: string;
  version: string;
  is_default: boolean;
};

const TemplatesPage: React.FC = () => {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formName, setFormName] = useState('');
  const [formVersion, setFormVersion] = useState('');

  const fetchTemplates = async () => {
    try {
      const data = await getTemplates();
      setTemplates(data);
    } catch (e: any) {
      setError(e.message || 'Failed to load templates');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTemplates();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createTemplate({ name: formName, version: formVersion });
      setFormName('');
      setFormVersion('');
      setShowForm(false);
      fetchTemplates();
    } catch (e: any) {
      setError(e.message || 'Failed to create template');
    }
  };

  const handleSetDefault = async (id: string) => {
    try {
      await setDefaultTemplate(id);
      fetchTemplates();
    } catch (e: any) {
      setError(e.message || 'Failed to set default');
    }
  };

  const columns = [
    { header: 'Name', accessor: 'name' },
    { header: 'Version', accessor: 'version' },
    {
      header: 'Default',
      accessor: 'is_default',
      cell: (row: any) => (row.is_default ? '✅' : ''),
    },
    {
      header: 'Actions',
      cell: (row: any) => (
        <button className="btn-primary" onClick={() => handleSetDefault(row.id)}>
          Set Default
        </button>
      ),
    },
  ];

  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">Certificate Templates</h1>
      {error && <ErrorBanner message={error} />}
      {loading ? (
        <p>Loading...</p>
      ) : (
        <DataTable data={templates} columns={columns} />
      )}
      <button className="mt-4 btn-primary" onClick={() => setShowForm(!showForm)}>
        {showForm ? 'Cancel' : 'Create New Template'}
      </button>
      {showForm && (
        <form onSubmit={handleCreate} className="mt-4 space-y-2 max-w-md">
          <input placeholder="Name" value={formName} onChange={e => setFormName(e.target.value)} required className="input" />
          <input placeholder="Version" value={formVersion} onChange={e => setFormVersion(e.target.value)} required className="input" />
          <button type="submit" className="btn-primary">Create</button>
        </form>
      )}
    </div>
  );
};

export default TemplatesPage;
