import React, { useEffect, useMemo, useState } from 'react';
import {
  Plus,
  Network,
  Play,
  Search,
  Filter,
  Loader2,
  MoreVertical,
  Clock,
  Workflow,
  Sparkles,
  BellRing,
  FileText,
  CalendarDays,
  Mail,
  MessageSquare,
} from 'lucide-react';
import useWorkflowStore from '../store/useWorkflowStore';
import { toast } from 'react-toastify';

const TEMPLATE_CARDS = [
  {
    id: 'daily-slack-summary',
    title: 'Daily Slack Summary',
    description: 'Collect updates and post a morning digest to a Slack channel.',
    icon: BellRing,
    category: 'automation',
  },
  {
    id: 'email-briefing',
    title: 'Email Briefing Generator',
    description: 'Create concise daily briefings from multiple data sources.',
    icon: Mail,
    category: 'assistant',
  },
  {
    id: 'meeting-notes',
    title: 'Meeting Notes to Tasks',
    description: 'Turn meeting notes into structured action items automatically.',
    icon: FileText,
    category: 'ops',
  },
  {
    id: 'weekly-plan',
    title: 'Weekly Planning Copilot',
    description: 'Summarize weekly priorities and generate a proposed plan.',
    icon: CalendarDays,
    category: 'assistant',
  },
];

const Workflows = () => {
  const { workflows, fetchWorkflows, createWorkflow, triggerExecution, loading, error } = useWorkflowStore();
  const [showModal, setShowModal] = useState(false);
  const [newWorkflow, setNewWorkflow] = useState({ name: '', description: '' });
  const [isCreating, setIsCreating] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('all');

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

  const applyTemplate = (template) => {
    setNewWorkflow({
      name: template.title,
      description: template.description,
    });
    setShowModal(true);
  };

  const filteredWorkflows = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return workflows.filter((wf) => {
      const name = (wf.name || '').toLowerCase();
      const description = (wf.description || '').toLowerCase();
      const matchesSearch = !query || name.includes(query) || description.includes(query);
      if (activeTab === 'all') {
        return matchesSearch;
      }
      if (activeTab === 'recent') {
        return matchesSearch && Boolean(wf.last_run);
      }
      return matchesSearch && !wf.last_run;
    });
  }, [workflows, searchQuery, activeTab]);

  const recentCount = workflows.filter((wf) => Boolean(wf.last_run)).length;
  const draftCount = workflows.length - recentCount;

  return (
    <div className="space-y-8 animate-fade-in relative">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-primary-700 bg-primary-50 px-3 py-1 rounded-full mb-3">
            <Sparkles size={14} />
            Workflow Studio
          </p>
          <h1 className="text-3xl font-bold text-neutral-900 mb-2">My Workflows</h1>
          <p className="text-neutral-500">Design, test, and run automations inspired by sandbox-style workflow builders.</p>
        </div>
        <button 
          onClick={() => setShowModal(true)}
          className="btn-primary flex items-center gap-2"
        >
          <Plus size={18} />
          <span>Create Workflow</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="card lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-neutral-900 flex items-center gap-2">
              <Workflow size={18} className="text-primary-600" />
              Start from a template
            </h2>
            <button className="text-sm text-primary-700 hover:text-primary-800 font-medium">Browse all</button>
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            {TEMPLATE_CARDS.map((template) => {
              const TemplateIcon = template.icon;
              return (
                <button
                  key={template.id}
                  onClick={() => applyTemplate(template)}
                  className="text-left border border-neutral-200 rounded-xl p-4 hover:border-primary-300 hover:bg-primary-50/30 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-2">
                      <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-primary-100 text-primary-700">
                        <TemplateIcon size={16} />
                      </span>
                      <h3 className="font-semibold text-neutral-900">{template.title}</h3>
                      <p className="text-sm text-neutral-500">{template.description}</p>
                    </div>
                    <span className="text-[11px] uppercase tracking-wide text-neutral-500 bg-neutral-100 px-2 py-1 rounded-full">
                      {template.category}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="card space-y-4">
          <h2 className="text-lg font-semibold text-neutral-900">Workspace Snapshot</h2>
          <div className="space-y-3">
            <div className="rounded-xl border border-neutral-200 p-4">
              <p className="text-sm text-neutral-500 mb-1">Total workflows</p>
              <p className="text-2xl font-bold text-neutral-900">{workflows.length}</p>
            </div>
            <div className="rounded-xl border border-neutral-200 p-4">
              <p className="text-sm text-neutral-500 mb-1">Recently run</p>
              <p className="text-2xl font-bold text-neutral-900">{recentCount}</p>
            </div>
            <div className="rounded-xl border border-neutral-200 p-4">
              <p className="text-sm text-neutral-500 mb-1">Draft workflows</p>
              <p className="text-2xl font-bold text-neutral-900">{draftCount}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="card space-y-4">
        <div className="flex flex-col md:flex-row gap-3 md:items-center md:justify-between">
          <div className="flex gap-2">
            {[
              { id: 'all', label: 'All' },
              { id: 'recent', label: 'Recently run' },
              { id: 'draft', label: 'Drafts' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                  activeTab === tab.id
                    ? 'bg-primary-600 border-primary-600 text-white'
                    : 'bg-white border-neutral-200 text-neutral-600 hover:bg-neutral-50'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div className="flex gap-2 w-full md:w-auto">
            <div className="relative w-full md:w-80">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400">
                <Search size={18} />
              </span>
              <input 
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search workflows..."
                className="input-field pl-10"
              />
            </div>
            <button className="btn-secondary flex items-center gap-2">
              <Filter size={18} />
              <span>Filter</span>
            </button>
            <button className="btn-secondary">
              Last Updated
            </button>
          </div>
        </div>
        <div className="text-xs text-neutral-500 flex items-center gap-1.5">
          <MessageSquare size={14} />
          Message endpoint conversations can generate workflow specs after requirements are complete.
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
              {filteredWorkflows.map((wf) => (
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
                    <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
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
              {filteredWorkflows.length === 0 && !loading && (
                <tr>
                  <td colSpan="4" className="px-6 py-24 text-center">
                    <div className="flex flex-col items-center gap-3">
                      <div className="p-4 bg-neutral-100 rounded-full text-neutral-400">
                        <Network size={32} />
                      </div>
                      <p className="text-neutral-500 font-medium">No workflows match your current filters.</p>
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
            <h2 className="text-2xl font-bold text-neutral-900 mb-2">Create New Workflow</h2>
            <p className="text-sm text-neutral-500 mb-6">Use a blank workflow or start from one of the templates above.</p>
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
