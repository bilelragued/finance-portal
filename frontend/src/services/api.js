import axios from 'axios';

// API Base URL - use environment variable or default to /api for production
const API_BASE = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
  // Enable credentials for HTTP Basic Auth
  withCredentials: true,
});

// Retry configuration for handling serverless cold starts
const RETRY_STATUSES = [502, 503, 504]; // Gateway errors from cold starts
const MAX_RETRIES = 2;
const RETRY_DELAY = 1000; // 1 second

// Helper to delay execution
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// Add retry interceptor for cold start errors
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config;

    // Handle auth errors
    if (error.response?.status === 401) {
      console.warn('Authentication required');
      return Promise.reject(error);
    }

    // Retry on cold start errors (502, 503, 504)
    if (error.response && RETRY_STATUSES.includes(error.response.status)) {
      config.__retryCount = config.__retryCount || 0;

      if (config.__retryCount < MAX_RETRIES) {
        config.__retryCount += 1;
        console.log(`Retrying request (${config.__retryCount}/${MAX_RETRIES}) after ${error.response.status}...`);
        await delay(RETRY_DELAY * config.__retryCount); // Exponential backoff
        return api(config);
      }
    }

    return Promise.reject(error);
  }
);

// Accounts API
export const accountsApi = {
  list: () => api.get('/accounts/'),
  get: (id) => api.get(`/accounts/${id}`),
  create: (data) => api.post('/accounts/', data),
  update: (id, data) => api.put(`/accounts/${id}`, data),
  delete: (id) => api.delete(`/accounts/${id}`),
  getSummary: (id) => api.get(`/accounts/${id}/summary`),
  getByNumber: (accountNumber) => api.get(`/accounts/by-number/${accountNumber}`),
};

// Transactions API
export const transactionsApi = {
  list: (params = {}) => api.get('/transactions/', { params }),
  get: (id) => api.get(`/transactions/${id}`),
  update: (id, data) => api.put(`/transactions/${id}`, data),
  bulkUpdate: (items) => api.post('/transactions/bulk-update-items', items),
  bulkUpdateSame: (ids, data) => api.post('/transactions/bulk-update', data, { 
    params: { transaction_ids: ids.join(',') }
  }),
  getStats: (params = {}) => api.get('/transactions/stats/summary', { params }),
};

// Upload API
export const uploadApi = {
  preview: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/upload/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  confirm: (fileId, accountId, createAccount = null) => {
    const params = new URLSearchParams();
    params.append('file_id', fileId);
    if (accountId) params.append('account_id', accountId);
    
    return api.post(`/upload/confirm?${params.toString()}`, createAccount);
  },
  cancel: (fileId) => api.delete(`/upload/cancel/${fileId}`),
  getHistory: (accountId = null) => api.get('/upload/history', { 
    params: accountId ? { account_id: accountId } : {} 
  }),
};

// Categories API
export const categoriesApi = {
  list: () => api.get('/categories/'),
  get: (id) => api.get(`/categories/${id}`),
  create: (data) => api.post('/categories/', data),
  update: (id, data) => api.put(`/categories/${id}`, data),
  delete: (id, reassignTo = null) => 
    api.delete(`/categories/${id}${reassignTo ? `?reassign_to=${reassignTo}` : ''}`),
  seed: () => api.post('/categories/seed'),
  getUsage: () => api.get('/categories/stats/usage'),
  reassign: (fromId, toId) => 
    api.post(`/categories/${fromId}/reassign?target_category_id=${toId}`),
};

// Categorization API
export const categorizationApi = {
  categorize: (transactionId, forceLlm = false) => 
    api.post('/categorization/categorize', { transaction_id: transactionId, force_llm: forceLlm }),
  
  categorizeBulk: (transactionIds, applyRulesOnly = false) =>
    api.post('/categorization/categorize-bulk', { 
      transaction_ids: transactionIds, 
      apply_rules_only: applyRulesOnly 
    }),
  
  apply: (transactionId, classification, categoryId = null, learn = true) =>
    api.post('/categorization/apply', {
      transaction_id: transactionId,
      classification,
      category_id: categoryId,
      learn
    }),
  
  applyBulk: (items) => api.post('/categorization/apply-bulk', items),
  
  getSuggestions: (accountId = null, limit = 50, useLlm = false) =>
    api.get('/categorization/suggestions', { 
      params: { account_id: accountId, limit, use_llm: useLlm } 
    }),
  
  suggestOne: (transactionId) =>
    api.post(`/categorization/suggest-one?transaction_id=${transactionId}`),
  
  getRules: (minConfidence = 0) =>
    api.get('/categorization/rules', { params: { min_confidence: minConfidence } }),
  
  deleteRule: (ruleId) => api.delete(`/categorization/rules/${ruleId}`),
  
  getRuleStats: () => api.get('/categorization/rules/stats'),
  
  autoCategorize: (accountId = null, apply = false) =>
    api.post('/categorization/auto-categorize', null, { 
      params: { account_id: accountId, apply } 
    }),
  
  // Stats - categorization overview
  getStats: () => api.get('/categorization/stats'),
  
  // Reset a transaction for re-categorization
  reset: (transactionId, recategorize = true) =>
    api.post(`/categorization/reset/${transactionId}`, null, {
      params: { recategorize }
    }),
  
  // Find similar transactions
  findSimilar: (transactionId, includeCategorized = false) =>
    api.post(`/categorization/find-similar/${transactionId}`, null, {
      params: { include_categorized: includeCategorized }
    }),
  
  // ML endpoints
  mlTrain: (minSamples = 20) =>
    api.post('/categorization/ml/train', null, { params: { min_samples: minSamples } }),
  
  mlPredict: (transactionId) =>
    api.post(`/categorization/ml/predict/${transactionId}`),
  
  mlAutoCategorize: (minConfidence = 0.7, apply = false) =>
    api.post('/categorization/ml/auto-categorize', null, {
      params: { min_confidence: minConfidence, apply }
    }),
};

// Reports API
export const reportsApi = {
  getSpendingByCategory: (params = {}) => api.get('/reports/spending-by-category', { params }),
  getIncomeVsExpenses: (params = {}) => api.get('/reports/income-vs-expenses', { params }),
  getSpendingTrends: (params = {}) => api.get('/reports/spending-trends', { params }),
  getSummary: (params = {}) => api.get('/reports/summary', { params }),
};

// NLP API - Natural Language Processing for categorization and search
export const nlpApi = {
  // Check if NLP features are available
  status: () => api.get('/nlp/status'),

  // Parse natural language query into structured filters
  parseQuery: (query) => api.post('/nlp/parse-query', { query }),

  // Search transactions using natural language
  search: (query, params = {}) => api.post('/nlp/search', { query }, { params }),

  // Match single transaction to best category
  matchTransaction: (transactionId, minConfidence = 0.7) =>
    api.post('/nlp/match-transaction', { transaction_id: transactionId, min_confidence: minConfidence }),

  // Categorize multiple transactions using NL descriptions
  categorize: (transactionIds = null, minConfidence = 0.7, apply = false) =>
    api.post('/nlp/categorize', {
      transaction_ids: transactionIds,
      min_confidence: minConfidence,
      apply
    }),
};

// Health check
export const healthCheck = () => api.get('/health');

export default api;

