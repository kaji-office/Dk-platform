import React, { useEffect } from 'react';
import { Activity, Network, MessageSquare, Play, Clock, CheckCircle, AlertCircle } from 'lucide-react';
import StatsCard from '../components/ui/StatsCard';
import useWorkflowStore from '../store/useWorkflowStore';

const Dashboard = () => {
  const { workflows, fetchWorkflows } = useWorkflowStore();

  useEffect(() => {
    fetchWorkflows();
  }, []);

  const stats = [
    { title: 'Total Workflows', value: (workflows || []).length.toString(), icon: <Network size={24} />, trend: 'up', trendValue: 12 },
    { title: 'Active Executions', value: '5', icon: <Activity size={24} />, trend: 'up', trendValue: 8 },
    { title: 'Total Messages', value: '1.2k', icon: <MessageSquare size={24} />, trend: 'up', trendValue: 15 },
    { title: 'Success Rate', value: '98.4%', icon: <CheckCircle size={24} />, trend: 'up', trendValue: 2 },
  ];

  const recentExecutions = [
    { id: '1', name: 'Data Pipeline A', status: 'completed', time: '2 mins ago' },
    { id: '2', name: 'Email Automation', status: 'running', time: '5 mins ago' },
    { id: '3', name: 'Inventory Sync', status: 'failed', time: '12 mins ago' },
    { id: '4', name: 'Customer Onboarding', status: 'completed', time: '1 hour ago' },
  ];

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-neutral-900 mb-2">Welcome Dashboard</h1>
          <p className="text-neutral-500 text-lg">Monitor your platform's performance and recent activities.</p>
        </div>
        <button className="btn-primary flex items-center gap-2">
          <Play size={18} />
          <span>New Execution</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, index) => (
          <StatsCard key={index} {...stat} />
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Recent Workflows */}
        <div className="card h-full">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold text-neutral-900">Recent Workflows</h2>
            <button className="text-primary-600 font-medium hover:text-primary-700">View All</button>
          </div>
          <div className="space-y-4">
            {(workflows || []).slice(0, 4).map((wf) => (
               <div key={wf.id} className="flex items-center justify-between p-4 bg-neutral-50 rounded-xl hover:bg-neutral-100 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-white rounded-lg border border-neutral-200">
                      <Network size={18} className="text-primary-500" />
                    </div>
                    <div>
                      <p className="font-semibold text-neutral-900">{wf.name}</p>
                      <p className="text-xs text-neutral-500">{wf.description || 'No description'}</p>
                    </div>
                  </div>
                  <button className="p-2 text-neutral-400 hover:text-primary-600 transition-colors">
                    <Play size={18} />
                  </button>
               </div>
            ))}
            {(workflows || []).length === 0 && (
              <p className="text-center text-neutral-400 py-12 italic">No workflows created yet.</p>
            )}
          </div>
        </div>

        {/* Execution History */}
        <div className="card h-full">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold text-neutral-900">Execution History</h2>
            <button className="text-primary-600 font-medium hover:text-primary-700">View History</button>
          </div>
          <div className="space-y-4">
            {recentExecutions.map((ex) => (
               <div key={ex.id} className="flex items-center justify-between p-4 border-b border-neutral-50 last:border-0">
                  <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-full ${
                      ex.status === 'completed' ? 'bg-green-100 text-green-600' :
                      ex.status === 'running' ? 'bg-blue-100 text-blue-600' :
                      'bg-red-100 text-red-600'
                    }`}>
                      {ex.status === 'completed' ? <CheckCircle size={16} /> :
                       ex.status === 'running' ? <Clock size={16} className="animate-spin" /> :
                       <AlertCircle size={16} />}
                    </div>
                    <div>
                      <p className="font-semibold text-neutral-900">{ex.name}</p>
                      <p className="text-xs text-neutral-500 uppercase font-medium">{ex.status}</p>
                    </div>
                  </div>
                  <span className="text-xs text-neutral-400 font-medium">{ex.time}</span>
               </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
