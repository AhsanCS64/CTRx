import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createOfficial } from "../../api/admin";

const CreateOfficial: React.FC = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [level, setLevel] = useState("local");
  const [areaId, setAreaId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createOfficial({ email, password, full_name: fullName, level, area_id: level === "local" ? areaId : undefined });
      navigate("/admin/dashboard");
    } catch (e: any) {
      setError(e.message || "Failed to create official");
    }
  };

  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">Create Official</h1>
      {error && <p className="text-red-600 mb-2">{error}</p>}
      <form onSubmit={handleSubmit} className="space-y-4 max-w-md">
        <div>
          <label className="block">Email</label>
          <input type="email" value={email} onChange={e => setEmail(e.target.value)} required className="input" />
        </div>
        <div>
          <label className="block">Password</label>
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} required className="input" />
        </div>
        <div>
          <label className="block">Full Name</label>
          <input type="text" value={fullName} onChange={e => setFullName(e.target.value)} required className="input" />
        </div>
        <div>
          <label className="block">Level</label>
          <select value={level} onChange={e => setLevel(e.target.value)} className="input">
            <option value="local">Local</option>
            <option value="central">Central</option>
          </select>
        </div>
        {level === "local" && (
          <div>
            <label className="block">Area ID</label>
            <input type="text" value={areaId} onChange={e => setAreaId(e.target.value)} required className="input" />
          </div>
        )}
        <button type="submit" className="btn-primary">Create Official</button>
      </form>
    </div>
  );
};

export default CreateOfficial;
