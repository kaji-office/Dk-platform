import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Network, MessageSquare, LogOut, Settings, Play } from 'lucide-react';
import useAuthStore from '../../store/useAuthStore';

const Sidebar = () => {
  const logout = useAuthStore((state) => state.logout);

  const navItems = [
    { name: 'Dashboard', path: '/', icon: <LayoutDashboard size={20} /> },
    { name: 'Workflows', path: '/workflows', icon: <Network size={20} /> },
    { name: 'Chat AI', path: '/chat', icon: <MessageSquare size={20} /> },
    { name: 'Executions', path: '/executions', icon: <Play size={20} /> },
  ];

  return (
    <div className="w-64 h-screen bg-white border-r border-neutral-200 flex flex-col">
      <div className="p-6">
        <h1 className="text-2xl font-bold bg-gradient-to-r from-primary-600 to-primary-400 bg-clip-text text-transparent">
          DK Platform
        </h1>
      </div>

      <nav className="flex-1 px-4 space-y-2">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 ${
                isActive
                  ? 'bg-primary-50 text-primary-600 font-medium shadow-sm'
                  : 'text-neutral-500 hover:bg-neutral-50 hover:text-neutral-700'
              }`
            }
          >
            {item.icon}
            <span>{item.name}</span>
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-neutral-100 space-y-2">
        <button className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-neutral-500 hover:bg-neutral-50 hover:text-neutral-700 transition-all">
          <Settings size={20} />
          <span>Settings</span>
        </button>
        <button
          onClick={logout}
          className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-red-500 hover:bg-red-50 transition-all font-medium"
        >
          <LogOut size={20} />
          <span>Logout</span>
        </button>
      </div>
    </div>
  );
};

export default Sidebar;
