import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DataTable, StatusBadge } from "../../components";
import { getReviewQueue } from "../../api/government";

type Application = {
  id: string;
  ric_number: string;
  status: string;
  area_name: string;
  applicant_name: string;
};

const ReviewQueue: React.FC = () => {
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await getReviewQueue();
        setApplications(data);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const columns = [
    { header: "RIC #", accessor: "ric_number" },
    { header: "Applicant", accessor: "applicant_name" },
    { header: "Area", accessor: "area_name" },
    {
      header: "Status",
      accessor: "status",
      cell: (row: any) => <StatusBadge status={row.status} />,
    },
    {
      header: "Actions",
      cell: (row: any) => (
        <button
          className="text-blue-600 underline"
          onClick={() => navigate(`/government/application-review/${row.id}`)}
        >
          Review
        </button>
      ),
    },
  ];

  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">Review Queue</h1>
      {loading ? (
        <p>Loading...</p>
      ) : (
        <DataTable data={applications} columns={columns} />
      )}
    </div>
  );
};

export default ReviewQueue;
