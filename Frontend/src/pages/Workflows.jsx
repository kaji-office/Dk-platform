import React, { useEffect, useState } from 'react';
import { Plus, Network, Play, Search, Filter, Loader2, MoreVertical, Clock } from 'lucide-react';
import useWorkflowStore from '../store/useWorkflowStore';
import { toast } from 'react-toastify';

const Workflows = () => {
  const { workflows, fetchWorkflows, createWorkflow, triggerExecution, loading, error } = useWorkflowStore();
  const [showModal, setShowModal] = useState(false);
  const [newWorkflow, setNewWorkflow] = useState({ name: '', description: '' });
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    fetchWorkflows();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setIsCreating(true);
    const result = await createWorkflow(newWorkflow);
    setIsCreating(false);
    if (result) {
      toast.success('Workflow created successfully!');
      setShowModal(false);
      setNewWorkflow({ name: '', description: '' });
    } else {
      toast.error('Failed to create workflow');
    }
  };

  const handleRun = async (id) => {
    if (!id) {
      toast.error('Workflow id is missing. Please refresh workflows.');
      return;
    }
    const execution = await triggerExecution(id);
    if (execution) {
      toast.success(`Execution started: ${execution.run_id || execution.id || 'created'}`);
    } else {
      toast.error(error || 'Failed to trigger execution');
    }
  };

  return (
    <div className="space-y-8 animate-fade-in relative">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-neutral-900 mb-2">My Workflows</h1>
          <p className="text-neutral-500">Manage and automate your repetitive tasks with ease.</p>
        </div>
        <button 
          onClick={() => setShowModal(true)}
          className="btn-primary flex items-center gap-2"
        >
          <Plus size={18} />
          <span>Create Workflow</span>
        </button>
      </div>

      {/* Header Filters */}
      <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
        <div className="relative w-full md:w-96">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400">
            <Search size={18} />
          </span>
          <input 
            type="text" 
            placeholder="Search workflows..." 
            className="input-field pl-10" 
          />
        </div>
        <div className="flex gap-2 w-full md:w-auto">
          <button className="btn-secondary flex items-center gap-2">
            <Filter size={18} />
            <span>Filter</span>
          </button>
          <button className="btn-secondary">
            Last Updated
          </button>
        </div>
      </div>

      {/* Workflow Table */}
      <div className="card overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="bg-neutral-50 border-b border-neutral-100">
              <tr>
                <th className="px-6 py-4 text-xs font-semibold text-neutral-500 uppercase tracking-wider">Name</th>
                <th className="px-6 py-4 text-xs font-semibold text-neutral-500 uppercase tracking-wider">Description</th>
                <th className="px-6 py-4 text-xs font-semibold text-neutral-500 uppercase tracking-wider">Last Run</th>
                <th className="px-6 py-4 text-xs font-semibold text-neutral-500 uppercase tracking-wider text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {workflows.map((wf) => (
                <tr key={wf.id || wf.workflow_id} className="hover:bg-neutral-50 transition-colors group">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-primary-50 rounded-lg text-primary-600">
                        <Network size={18} />
                      </div>
                      <span className="font-semibold text-neutral-900">{wf.name}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-neutral-500 text-sm">{wf.description || '-'}</span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-1.5 text-neutral-500 text-sm">
                      <Clock size={14} />
                      <span>{wf.last_run ? new Date(wf.last_run).toLocaleDateString() : 'Never'}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-2 op-0 group-hover:opacity-100 transition-opacity">
                      <button 
                        onClick={() => handleRun(wf.id || wf.workflow_id)}
                        className="p-2 text-primary-600 hover:bg-primary-50 rounded-lg transition-colors border border-transparent hover:border-primary-100"
                        title="Run Workflow"
                      >
                         <Play size={18} fill="currentColor" />
                      </button>
                      <button className="p-2 text-neutral-400 hover:text-neutral-600">
                        <MoreVertical size={18} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {workflows.length === 0 && !loading && (
                <tr>
                   <td colSpan="4" className="px-6 py-24 text-center">
                     <div className="flex flex-col items-center gap-3">
                       <div className="p-4 bg-neutral-100 rounded-full text-neutral-400">
                         <Network size={32} />
                       </div>
                       <p className="text-neutral-500 font-medium">No workflows found. Create your first one to get started!</p>
                       <button 
                          onClick={() => setShowModal(true)}
                          className="btn-primary mt-2"
                        >
                          Create Now
                       </button>
                     </div>
                   </td>
                </tr>
              )}
              {loading && (
                <tr>
                  <td colSpan="4" className="px-6 py-24 text-center">
                    <Loader2 className="animate-spin mx-auto text-primary-600" size={32} />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal Backdrop */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-900/40 backdrop-blur-sm animate-fade-in">
          <div className="bg-white w-full max-w-md rounded-2xl shadow-2xl p-8 animate-slide-up">
            <h2 className="text-2xl font-bold text-neutral-900 mb-6">Create New Workflow</h2>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-neutral-700">Workflow Name</label>
                <input 
                  type="text" 
                  required
                  placeholder="e.g. Daily Inventory Update"
                  className="input-field" 
                  value={newWorkflow.name}
                  onChange={(e) => setNewWorkflow({ ...newWorkflow, name: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-neutral-700">Description (Optional)</label>
                <textarea 
                   rows="3"
                   placeholder="Short overview of what this workflow does."
                   className="input-field py-3" 
                   value={newWorkflow.description}
                   onChange={(e) => setNewWorkflow({ ...newWorkflow, description: e.target.value })}
                />
              </div>
              <div className="flex gap-3 pt-4">
                <button 
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="flex-1 btn-secondary"
                >
                  Cancel
                </button>
                <button 
                  type="submit"
                  disabled={isCreating}
                  className="flex-1 btn-primary flex items-center justify-center gap-2"
                >
                  {isCreating ? <Loader2 className="animate-spin" size={18} /> : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Workflows;
