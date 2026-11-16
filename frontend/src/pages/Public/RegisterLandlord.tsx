import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { registerLandlord } from '../../api/verification'; // stub API to be added later

const RegisterLandlord: React.FC = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await registerLandlord({ email, password, full_name: fullName });
      navigate('/login');
    } catch (e: any) {
      setError(e.message || 'Registration failed');
    }
  };

  return (
    <div className="p-4 max-w-md mx-auto">
      <h1 className="text-2xl font-bold mb-4">Register Landlord</h1>
      {error && <p className="text-red-600 mb-2">{error}</p>}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block mb-1">Email</label>
          <input type="email" value={email} onChange={e => setEmail(e.target.value)} required className="input" />
        </div>
        <div>
          <label className="block mb-1">Password</label>
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} required className="input" />
        </div>
        <div>
          <label className="block mb-1">Full Name</label>
          <input type="text" value={fullName} onChange={e => setFullName(e.target.value)} required className="input" />
        </div>
        <button type="submit" className="btn-primary w-full">Register</button>
      </form>
    </div>
  );
};

export default RegisterLandlord;
