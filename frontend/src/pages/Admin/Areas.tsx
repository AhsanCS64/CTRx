import React, { useEffect, useState } from "react";
import { DataTable, ErrorBanner } from "../../components";
import { getAreas, createArea, updateArea } from "../../api/admin";

type Area = {
  id: string;
  division: string;
  division_code: string;
  district: string;
  district_code: string;
  name: string;
  upazila_code: string;
};

const AreasPage: React.FC = () => {
  const [areas, setAreas] = useState<Area[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<Partial<Area>>({});
  const [showForm, setShowForm] = useState(false);

  const fetchAreas = async () => {
    try {
      const data = await getAreas();
      setAreas(data);
    } catch (e: any) {
      setError(e.message || "Failed to load areas");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAreas();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createArea(form as Area);
      setForm({});
      setShowForm(false);
      fetchAreas();
    } catch (e: any) {
      setError(e.message || "Failed to create area");
    }
  };

  const handleUpdate = async (id: string, updates: Partial<Area>) => {
    try {
      await updateArea(id, updates);
      fetchAreas();
    } catch (e: any) {
      setError(e.message || "Failed to update area");
    }
  };

  const columns = [
    { header: "Division", accessor: "division" },
    { header: "Division Code", accessor: "division_code" },
    { header: "District", accessor: "district" },
    { header: "District Code", accessor: "district_code" },
    { header: "Name", accessor: "name" },
    { header: "Upazila Code", accessor: "upazila_code" },
    {
      header: "Actions",
      cell: (row: any) => (
        <button
          className="btn-primary"
          onClick={() => handleUpdate(row.id, { name: row.name + " (edited)" })}
        >
          Edit (demo)
        </button>
      ),
    },
  ];

  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">Areas</h1>
      {error && <ErrorBanner message={error} />}
      {loading ? (
        <p>Loading...</p>
      ) : (
        <DataTable data={areas} columns={columns} />
      )}
      <button className="mt-4 btn-primary" onClick={() => setShowForm(!showForm)}>
        {showForm ? "Cancel" : "Create New Area"}
      </button>
      {showForm && (
        <form onSubmit={handleCreate} className="mt-4 space-y-2 max-w-md">
          <input placeholder="Division" value={form.division || ""} onChange={e => setForm({ ...form, division: e.target.value })} required className="input" />
          <input placeholder="Division Code" value={form.division_code || ""} onChange={e => setForm({ ...form, division_code: e.target.value })} required className="input" />
          <input placeholder="District" value={form.district || ""} onChange={e => setForm({ ...form, district: e.target.value })} required className="input" />
          <input placeholder="District Code" value={form.district_code || ""} onChange={e => setForm({ ...form, district_code: e.target.value })} required className="input" />
          <input placeholder="Name" value={form.name || ""} onChange={e => setForm({ ...form, name: e.target.value })} required className="input" />
          <input placeholder="Upazila Code" value={form.upazila_code || ""} onChange={e => setForm({ ...form, upazila_code: e.target.value })} required className="input" />
          <button type="submit" className="btn-primary">Create Area</button>
        </form>
      )}
    </div>
  );
};

export default AreasPage;
