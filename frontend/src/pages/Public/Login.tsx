import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login } from '../../api/verification'; // assuming login endpoint lives here; we will create a stub in api later

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const token = await login(email, password);
      localStorage.setItem('access_token', token);
      // In a real app we would decode token to get role; here we navigate to a generic home
      navigate('/');
    } catch (e: any) {
      setError(e.message || 'Login failed');
    }
  };

  return (
    <div className="p-4 max-w-md mx-auto">
      <h1 className="text-2xl font-bold mb-4">Login</h1>
      {error && <p className="text-red-600 mb-2">{error}</p>}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block mb-1">Email</label>
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            className="input"
          />
        </div>
        <div>
          <label className="block mb-1">Password</label>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            className="input"
          />
        </div>
        <button type="submit" className="btn-primary w-full">Log In</button>
      </form>
    </div>
  );
};

export default LoginPage;
