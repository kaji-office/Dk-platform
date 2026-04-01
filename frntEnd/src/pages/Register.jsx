import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Mail, Lock, User, Loader2, ArrowRight } from 'lucide-react';
import useAuthStore from '../store/useAuthStore';
import { toast } from 'react-toastify';

const Register = () => {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const navigate = useNavigate();
  const { register, loading, error } = useAuthStore();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (formData.password !== formData.confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }

    const { confirmPassword, ...data } = formData;
    const success = await register(data);
    if (success) {
      toast.success('Account created! Please login.');
      navigate('/login');
    } else {
      toast.error(error || 'Registration failed');
    }
  };

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  return (
    <div className="min-h-screen flex bg-neutral-50">
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8">
        <div className="w-full max-w-md space-y-8 animate-slide-up">
          <div className="text-center lg:text-left">
            <h1 className="text-3xl font-bold text-neutral-900 mb-2">Create Account</h1>
            <p className="text-neutral-500">Join the DK Platform and start automating.</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-neutral-700">Full Name</label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400">
                  <User size={18} />
                </span>
                <input
                  name="name"
                  type="text"
                  required
                  className="input-field pl-10"
                  placeholder="John Doe"
                  value={formData.name}
                  onChange={handleChange}
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-neutral-700">Email Address</label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400">
                  <Mail size={18} />
                </span>
                <input
                  name="email"
                  type="email"
                  required
                  className="input-field pl-10"
                  placeholder="name@example.com"
                  value={formData.email}
                  onChange={handleChange}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-neutral-700">Password</label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400">
                    <Lock size={18} />
                  </span>
                  <input
                    name="password"
                    type="password"
                    required
                    className="input-field pl-10"
                    placeholder="••••••••"
                    value={formData.password}
                    onChange={handleChange}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-neutral-700">Confirm Password</label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400">
                    <Lock size={18} />
                  </span>
                  <input
                    name="confirmPassword"
                    type="password"
                    required
                    className="input-field pl-10"
                    placeholder="••••••••"
                    value={formData.confirmPassword}
                    onChange={handleChange}
                  />
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full btn-primary py-3 text-lg font-semibold flex items-center justify-center gap-2 group mt-4"
            >
              {loading ? (
                <Loader2 className="animate-spin" size={20} />
              ) : (
                <>
                  Create Account
                  <ArrowRight size={20} className="group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </button>
          </form>

          <p className="text-center text-neutral-600">
            Already have an account?{' '}
            <Link to="/login" className="font-semibold text-primary-600 hover:text-primary-700 underline underline-offset-4">
              Sign in
            </Link>
          </p>
        </div>
      </div>

      <div className="hidden lg:flex w-1/2 bg-primary-600 items-center justify-center p-12 text-white">
        <div className="max-w-md space-y-8 animate-fade-in text-right">
          <h2 className="text-5xl font-bold leading-tight">
            Design, deploy, and scale in minutes.
          </h2>
          <p className="text-primary-100 text-xl">
            Our platform provides all the tools you need to build powerful automation workflows without the complexity.
          </p>
        </div>
      </div>
    </div>
  );
};

export default Register;
