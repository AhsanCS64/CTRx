import React, { useEffect, useState } from "react";
import { DataTable, StatusBadge } from "../../components";
import { getUsers, setUserActive } from "../../api/admin";
import { Link } from "react-router-dom";

type User = {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
};

const UsersPage: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchUsers = async () => {
    try {
      const data = await getUsers();
      setUsers(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const toggleActive = async (id: string, current: boolean) => {
    try {
      await setUserActive(id, !current);
      // Refresh list
      fetchUsers();
    } catch (e) {
      console.error(e);
    }
  };

  const columns = [
    { header: "Email", accessor: "email" },
    { header: "Role", accessor: "role" },
    {
      header: "Active",
      accessor: "is_active",
      cell: (row: any) => (
        <StatusBadge status={row.is_active ? "active" : "inactive"} />
      ),
    },
    {
      header: "Actions",
      cell: (row: any) => (
        <button
          className="btn-primary"
          onClick={() => toggleActive(row.id, row.is_active)}
        >
          {row.is_active ? "Deactivate" : "Activate"}
        </button>
      ),
    },
  ];

  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">User Management</h1>
      {loading ? (
        <p>Loading...</p>
      ) : (
        <DataTable data={users} columns={columns} />
      )}
      <div className="mt-4">
        <Link to="/admin/create-official" className="text-blue-600 underline">
          + Create Official
        </Link>
      </div>
    </div>
  );
};

export default UsersPage;
