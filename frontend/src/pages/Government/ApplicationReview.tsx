import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { DataTable, StatusBadge, ErrorBanner } from "../../components";
import { getApplication, forwardApp, rejectApp, approveApp, rejectCentralApp } from "../../api/government";

type ApplicationDetail = {
  id: string;
  ric_number: string;
  applicant_name: string;
  area_name: string;
  status: string;
  // other fields as needed
};

const ApplicationReview: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [app, setApp] = useState<ApplicationDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch = async () => {
      try {
        const data = await getApplication(id!);
        setApp(data);
      } catch (e: any) {
        setError(e.message || "Failed to load application");
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, [id]);

  const handleForward = async () => {
    try {
      await forwardApp(id!);
      navigate("/government/review-queue");
    } catch (e) {
      setError("Failed to forward");
    }
  };
  const handleRejectLocal = async () => {
    try {
      await rejectApp(id!);
      navigate("/government/review-queue");
    } catch (e) {
      setError("Failed to reject");
    }
  };
  const handleApprove = async () => {
    try {
      await approveApp(id!);
      navigate("/government/review-queue");
    } catch (e) {
      setError("Failed to approve");
    }
  };
  const handleRejectCentral = async () => {
    try {
      await rejectCentralApp(id!);
      navigate("/government/review-queue");
    } catch (e) {
      setError("Failed to reject");
    }
  };

  if (loading) return <p>Loading...</p>;
  if (error) return <ErrorBanner message={error} />;
  if (!app) return null;

  const isLocal = app.status.startsWith("pending_local"); // simplistic check

  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">Application Review</h1>
      <div className="mb-4">
        <p><strong>RIC #:</strong> {app.ric_number}</p>
        <p><strong>Applicant:</strong> {app.applicant_name}</p>
        <p><strong>Area:</strong> {app.area_name}</p>
        <p><strong>Status:</strong> <StatusBadge status={app.status} /></p>
        {/* Add other fields as needed */}
      </div>
      <div className="space-x-2">
        {isLocal ? (
          <>
            <button onClick={handleForward} className="btn-primary">Forward to Central</button>
            <button onClick={handleRejectLocal} className="btn-danger">Reject Local</button>
          </>
        ) : (
          <>
            <button onClick={handleApprove} className="btn-primary">Approve</button>
            <button onClick={handleRejectCentral} className="btn-danger">Reject Central</button>
          </>
        )}
      </div>
    </div>
  );
};

export default ApplicationReview;
