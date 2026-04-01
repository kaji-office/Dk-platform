import { create } from 'zustand';
import api from '../services/api';

const unwrapPayload = (data) => data?.data ?? data;

const normalizeWorkflow = (workflow) => ({
  ...workflow,
  id: workflow?.id ?? workflow?.workflow_id,
});

const useWorkflowStore = create((set, get) => ({
  workflows: [],
  executions: {}, // Map by run_id
  loading: false,
  error: null,

  fetchWorkflows: async () => {
    set({ loading: true, error: null });
    try {
      const response = await api.get('/workflows');
      const payload = unwrapPayload(response.data);
      const workflows = Array.isArray(payload)
        ? payload
        : payload?.items || payload?.workflows || payload?.data || [];
      set({ workflows: workflows.map(normalizeWorkflow), loading: false });
    } catch (err) {
      set({ workflows: [], error: 'Failed to fetch workflows.', loading: false });
    }
  },

  createWorkflow: async (workflowData) => {
    set({ loading: true, error: null });
    try {
      const payload = {
        ...workflowData,
        nodes: workflowData?.nodes ?? [],
        edges: workflowData?.edges ?? [],
      };
      const response = await api.post('/workflows', payload);
      const workflow = normalizeWorkflow(unwrapPayload(response.data));
      set((state) => ({ 
        workflows: [workflow, ...state.workflows], 
        loading: false 
      }));
      return workflow;
    } catch (err) {
      set({ error: 'Failed to create workflow.', loading: false });
      return null;
    }
  },

  triggerExecution: async (workflowId) => {
    try {
      if (!workflowId) {
        set({ error: 'Missing workflow id for execution.' });
        return null;
      }

      let execution = null;
      try {
        const response = await api.post('/executions', {
          workflow_id: workflowId,
          inputs: {},
        });
        execution = unwrapPayload(response.data);
      } catch (primaryErr) {
        // Fallback for backends using workflow-scoped trigger endpoint.
        const fallback = await api.post(`/workflows/${workflowId}/execute`, { inputs: {} });
        execution = unwrapPayload(fallback.data);
      }

      const runId = execution?.run_id ?? execution?.id;
      
      set((state) => ({
        executions: runId ? { ...state.executions, [runId]: execution } : state.executions
      }));
      set({ error: null });
      return execution;
    } catch (err) {
      const details =
        err?.response?.data?.message ||
        err?.response?.data?.error?.message ||
        err?.response?.data?.detail ||
        `Failed to trigger execution${err?.response?.status ? ` (${err.response.status})` : ''}.`;
      set({ error: details });
      return null;
    }
  },

  pollExecutionStatus: async (runId) => {
    try {
      const response = await api.get(`/executions/${runId}`);
      const execution = unwrapPayload(response.data);
      set((state) => ({
        executions: { ...state.executions, [runId]: execution }
      }));
      return execution;
    } catch (err) {
      return get().executions[runId] || null;
    }
  }
}));

export default useWorkflowStore;
