import { useState, useEffect } from 'react';
import { 
  Search, 
  Filter, 
  ChevronLeft, 
  ChevronRight,
  RefreshCw,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Calendar,
  CheckSquare,
  Square,
  X,
  Tags,
  Briefcase,
  User,
  Lock,
  Bot,
  RotateCcw,
  Zap
} from 'lucide-react';
import { transactionsApi, accountsApi, categoriesApi, categorizationApi } from '../services/api';
import clsx from 'clsx';
import { format } from 'date-fns';
import CategorizationStatsBar from '../components/CategorizationStatsBar';

function Transactions() {
  const [transactions, setTransactions] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  
  // Pagination
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState(50);
  const pageSizeOptions = [25, 50, 100, 200];

  // Filters
  const [filters, setFilters] = useState({
    search: '',
    account_id: '',
    classification: '',
    category_id: '',
    is_reviewed: '',
    date_from: '',
    date_to: '',
  });
  const [showFilters, setShowFilters] = useState(false);

  // Bulk selection
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [bulkAction, setBulkAction] = useState(''); // 'category', 'classification'
  const [bulkValue, setBulkValue] = useState('');
  const [bulkProcessing, setBulkProcessing] = useState(false);
  const [categorySearch, setCategorySearch] = useState('');

  useEffect(() => {
    loadInitialData();
  }, []);

  useEffect(() => {
    loadTransactions();
    setSelectedIds(new Set()); // Clear selection when filters/page/pageSize change
  }, [page, pageSize, filters]);

  const loadInitialData = async () => {
    try {
      const [accountsRes, categoriesRes] = await Promise.all([
        accountsApi.list(),
        categoriesApi.list()
      ]);
      setAccounts(accountsRes.data);
      setCategories(categoriesRes.data);
    } catch (err) {
      console.error('Failed to load initial data', err);
    }
  };

  const loadTransactions = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {
        page,
        page_size: pageSize,
        ...(filters.search && { search: filters.search }),
        ...(filters.account_id && { account_id: filters.account_id }),
        ...(filters.classification && { classification: filters.classification }),
        ...(filters.category_id && { category_id: filters.category_id }),
        ...(filters.is_reviewed && { is_reviewed: filters.is_reviewed === 'true' }),
        ...(filters.date_from && { date_from: filters.date_from }),
        ...(filters.date_to && { date_to: filters.date_to }),
      };
      
      const response = await transactionsApi.list(params);
      setTransactions(response.data.transactions);
      setTotalPages(response.data.total_pages);
      setTotal(response.data.total);
    } catch (err) {
      setError('Failed to load transactions');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Selection handlers
  const toggleSelect = (id) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
  };

  const selectAll = () => {
    if (selectedIds.size === transactions.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(transactions.map(t => t.id)));
    }
  };

  const clearSelection = () => {
    setSelectedIds(new Set());
  };

  // Bulk action handlers
  const openBulkModal = (action) => {
    setBulkAction(action);
    setBulkValue('');
    setCategorySearch('');
    setShowBulkModal(true);
  };

  const handleBulkApply = async () => {
    if (!bulkValue || selectedIds.size === 0) return;
    
    setBulkProcessing(true);
    setError(null);
    
    try {
      const ids = Array.from(selectedIds);
      
      if (bulkAction === 'classification') {
        await transactionsApi.bulkUpdate(ids.map(id => ({
          id,
          classification: bulkValue,
          is_reviewed: true
        })));
        setSuccess(`Updated classification for ${ids.length} transactions`);
      } else if (bulkAction === 'category') {
        await transactionsApi.bulkUpdate(ids.map(id => ({
          id,
          category_id: parseInt(bulkValue),
          is_reviewed: true
        })));
        setSuccess(`Updated category for ${ids.length} transactions`);
      }
      
      setShowBulkModal(false);
      setSelectedIds(new Set());
      loadTransactions();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update transactions');
    } finally {
      setBulkProcessing(false);
    }
  };

  const handleClassificationChange = async (transactionId, classification) => {
    try {
      const response = await transactionsApi.update(transactionId, { 
        classification,
        is_reviewed: true 
      });
      // Check if similar transactions were updated
      if (response.data?.similar_updated > 0) {
        setSuccess(`Updated! Also applied to ${response.data.similar_updated} similar transactions`);
        setTimeout(() => setSuccess(null), 3000);
        loadTransactions(); // Reload to show all updates
      } else {
        setTransactions(prev => 
          prev.map(t => 
            t.id === transactionId 
              ? { ...t, classification, is_reviewed: true, is_user_confirmed: true, categorization_source: 'user' }
              : t
          )
        );
      }
    } catch (err) {
      console.error('Failed to update classification', err);
    }
  };

  // Reset a transaction so the system can re-categorize it
  const handleResetTransaction = async (transactionId) => {
    try {
      const response = await categorizationApi.reset(transactionId, true);
      setTransactions(prev => 
        prev.map(t => 
          t.id === transactionId 
            ? { 
                ...t, 
                category_id: response.data.new_prediction?.category_id || null,
                is_reviewed: false, 
                is_user_confirmed: false, 
                categorization_source: response.data.new_prediction ? 'ml' : 'pending',
                category: response.data.new_prediction?.category_name 
                  ? { ...t.category, name: response.data.new_prediction.category_name } 
                  : null
              }
            : t
        )
      );
      if (response.data.new_prediction) {
        setSuccess(`Reset! ML suggests: ${response.data.new_prediction.category_name} (${Math.round(response.data.new_prediction.confidence * 100)}% confidence)`);
      } else {
        setSuccess('Transaction reset for re-categorization');
      }
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      console.error('Failed to reset transaction', err);
      setError('Failed to reset transaction');
    }
  };

  // Get source badge for categorization source
  const getSourceBadge = (source) => {
    switch (source) {
      case 'user':
        return (
          <span className="flex items-center gap-1 text-xs text-emerald-600" title="User confirmed">
            <Lock className="w-3 h-3" />
          </span>
        );
      case 'rule':
        return (
          <span className="flex items-center gap-1 text-xs text-blue-600" title="Applied by rule">
            <Zap className="w-3 h-3" />
          </span>
        );
      case 'ml':
        return (
          <span className="flex items-center gap-1 text-xs text-purple-600" title="ML prediction">
            <Bot className="w-3 h-3" />
          </span>
        );
      case 'llm':
        return (
          <span className="flex items-center gap-1 text-xs text-amber-600" title="AI suggestion">
            <Zap className="w-3 h-3" />
          </span>
        );
      default:
        return null;
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-NZ', {
      style: 'currency',
      currency: 'NZD',
      minimumFractionDigits: 2
    }).format(amount);
  };

  const formatDate = (dateStr) => {
    try {
      return format(new Date(dateStr), 'dd MMM yyyy');
    } catch {
      return dateStr;
    }
  };

  const getClassificationBadge = (classification) => {
    switch (classification) {
      case 'personal':
        return <span className="badge badge-success">Personal</span>;
      case 'business':
        return <span className="badge badge-warning">Business</span>;
      default:
        return <span className="badge badge-info">Unclassified</span>;
    }
  };

  const getCategoryById = (categoryId) => {
    return categories.find(c => c.id === categoryId);
  };

  const expenseCategories = categories.filter(c => !c.is_income);
  const incomeCategories = categories.filter(c => c.is_income);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold text-slate-800">Transactions</h1>
          <p className="text-slate-500 mt-1">
            {total.toLocaleString()} transactions total
          </p>
        </div>
        <button
          onClick={loadTransactions}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white hover:bg-slate-50 text-slate-600 border border-slate-200 shadow-sm transition-all disabled:opacity-50"
        >
          <RefreshCw className={clsx('w-4 h-4', loading && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {/* Categorization Stats Bar */}
      <CategorizationStatsBar
        onNeedsAttentionClick={() => {
          setFilters(prev => ({ ...prev, category_id: 'null' }));
          setPage(1);
        }}
      />

      {/* Bulk Action Bar */}
      {selectedIds.size > 0 && (
        <div className="bg-white rounded-2xl p-4 shadow-sm border border-slate-100 flex items-center justify-between animate-slide-up">
          <div className="flex items-center gap-4">
            <span className="text-ocean-600 font-medium">
              {selectedIds.size} selected
            </span>
            <button
              onClick={clearSelection}
              className="text-slate-500 hover:text-slate-700 text-sm"
            >
              Clear
            </button>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => openBulkModal('classification')}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200 transition-all"
            >
              <Briefcase className="w-4 h-4" />
              Set Classification
            </button>
            <button
              onClick={() => openBulkModal('category')}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-purple-50 hover:bg-purple-100 text-purple-700 border border-purple-200 transition-all"
            >
              <Tags className="w-4 h-4" />
              Set Category
            </button>
          </div>
        </div>
      )}

      {/* Search and Filters */}
      <div className="bg-white rounded-2xl p-4 shadow-sm border border-slate-100">
        <div className="flex items-center gap-4">
          {/* Search */}
          <div className="flex-1 relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
            <input
              type="text"
              placeholder="Search transactions..."
              value={filters.search}
              onChange={(e) => {
                setFilters(prev => ({ ...prev, search: e.target.value }));
                setPage(1);
              }}
              className="w-full pl-12 pr-4 py-3 rounded-xl bg-slate-50 border border-slate-200 text-slate-800 placeholder-slate-400 focus:border-ocean-500 focus:ring-1 focus:ring-ocean-500"
            />
          </div>

          {/* Filter toggle */}
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={clsx(
              'flex items-center gap-2 px-4 py-3 rounded-xl border transition-all',
              showFilters
                ? 'border-ocean-500 bg-ocean-50 text-ocean-600'
                : 'border-slate-200 text-slate-500 hover:text-slate-700 hover:bg-slate-50'
            )}
          >
            <Filter className="w-5 h-5" />
            Filters
          </button>
        </div>

        {/* Filter Panel */}
        {showFilters && (
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4 mt-4 pt-4 border-t border-slate-100 animate-slide-up">
            {/* Account Filter */}
            <div>
              <label className="block text-sm text-slate-500 mb-2">Account</label>
              <select
                value={filters.account_id}
                onChange={(e) => {
                  setFilters(prev => ({ ...prev, account_id: e.target.value }));
                  setPage(1);
                }}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-50 border border-slate-200 text-slate-800 focus:border-ocean-500"
              >
                <option value="">All Accounts</option>
                {accounts.map(acc => (
                  <option key={acc.id} value={acc.id}>{acc.name}</option>
                ))}
              </select>
            </div>

            {/* Classification Filter */}
            <div>
              <label className="block text-sm text-slate-500 mb-2">Classification</label>
              <select
                value={filters.classification}
                onChange={(e) => {
                  setFilters(prev => ({ ...prev, classification: e.target.value }));
                  setPage(1);
                }}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-50 border border-slate-200 text-slate-800 focus:border-ocean-500"
              >
                <option value="">All</option>
                <option value="personal">Personal</option>
                <option value="business">Business</option>
                <option value="unclassified">Unclassified</option>
              </select>
            </div>

            {/* Category Filter */}
            <div>
              <label className="block text-sm text-slate-500 mb-2">Category</label>
              <select
                value={filters.category_id}
                onChange={(e) => {
                  setFilters(prev => ({ ...prev, category_id: e.target.value }));
                  setPage(1);
                }}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-50 border border-slate-200 text-slate-800 focus:border-ocean-500"
              >
                <option value="">All Categories</option>
                <option value="null">Uncategorized</option>
                {categories.map(cat => (
                  <option key={cat.id} value={cat.id}>{cat.icon} {cat.name}</option>
                ))}
              </select>
            </div>

            {/* Review Status */}
            <div>
              <label className="block text-sm text-slate-500 mb-2">Review Status</label>
              <select
                value={filters.is_reviewed}
                onChange={(e) => {
                  setFilters(prev => ({ ...prev, is_reviewed: e.target.value }));
                  setPage(1);
                }}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-50 border border-slate-200 text-slate-800 focus:border-ocean-500"
              >
                <option value="">All</option>
                <option value="true">Reviewed</option>
                <option value="false">Needs Review</option>
              </select>
            </div>

            {/* Date From */}
            <div>
              <label className="block text-sm text-slate-500 mb-2">From Date</label>
              <input
                type="date"
                value={filters.date_from}
                onChange={(e) => {
                  setFilters(prev => ({ ...prev, date_from: e.target.value }));
                  setPage(1);
                }}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-50 border border-slate-200 text-slate-800 focus:border-ocean-500"
              />
            </div>

            {/* Date To */}
            <div>
              <label className="block text-sm text-slate-500 mb-2">To Date</label>
              <input
                type="date"
                value={filters.date_to}
                onChange={(e) => {
                  setFilters(prev => ({ ...prev, date_to: e.target.value }));
                  setPage(1);
                }}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-50 border border-slate-200 text-slate-800 focus:border-ocean-500"
              />
            </div>
          </div>
        )}
      </div>

      {/* Messages */}
      {error && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-red-50 border border-red-200 text-red-600">
          <AlertCircle className="w-5 h-5" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {success && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-600">
          <CheckCircle2 className="w-5 h-5" />
          {success}
        </div>
      )}

      {/* Transactions Table */}
      <div className="bg-white rounded-2xl overflow-hidden shadow-sm border border-slate-100">
        {loading ? (
          <div className="flex items-center justify-center p-12">
            <RefreshCw className="w-8 h-8 text-ocean-500 animate-spin" />
          </div>
        ) : transactions.length === 0 ? (
          <div className="text-center p-12">
            <Calendar className="w-12 h-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-500">No transactions found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-sm text-slate-500 bg-slate-50">
                  <th className="px-4 py-4">
                    <button
                      onClick={selectAll}
                      className="p-1 rounded hover:bg-slate-200"
                    >
                      {selectedIds.size === transactions.length ? (
                        <CheckSquare className="w-5 h-5 text-ocean-600" />
                      ) : (
                        <Square className="w-5 h-5" />
                      )}
                    </button>
                  </th>
                  <th className="px-4 py-4 font-medium">Date</th>
                  <th className="px-4 py-4 font-medium">Details</th>
                  <th className="px-4 py-4 font-medium">Type</th>
                  <th className="px-4 py-4 font-medium text-right">Amount</th>
                  <th className="px-4 py-4 font-medium">Category</th>
                  <th className="px-4 py-4 font-medium">Classification</th>
                  <th className="px-4 py-4 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((trans, idx) => {
                  const category = getCategoryById(trans.category_id);
                  return (
                    <tr
                      key={trans.id}
                      className={clsx(
                        'border-t border-slate-100 transition-all',
                        selectedIds.has(trans.id)
                          ? 'bg-ocean-50'
                          : 'hover:bg-slate-50'
                      )}
                      style={{ animationDelay: `${idx * 20}ms` }}
                    >
                      <td className="px-4 py-4">
                        <button
                          onClick={() => toggleSelect(trans.id)}
                          className="p-1 rounded hover:bg-slate-200"
                        >
                          {selectedIds.has(trans.id) ? (
                            <CheckSquare className="w-5 h-5 text-ocean-600" />
                          ) : (
                            <Square className="w-5 h-5 text-slate-400" />
                          )}
                        </button>
                      </td>
                      <td className="px-4 py-4">
                        <span className="text-slate-700">{formatDate(trans.transaction_date)}</span>
                      </td>
                      <td className="px-4 py-4">
                        <div>
                          <p className="text-slate-800 font-medium">
                            {trans.code || trans.details || '-'}
                          </p>
                          {trans.code && trans.details && (
                            <p className="text-sm text-slate-500">{trans.details}</p>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <span className="text-slate-500 text-sm">{trans.transaction_type}</span>
                      </td>
                      <td className="px-4 py-4 text-right">
                        <span className={clsx(
                          'font-mono font-medium',
                          trans.amount < 0 ? 'text-red-600' : 'text-emerald-600'
                        )}>
                          {formatCurrency(trans.amount)}
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-2">
                          {category ? (
                            <span className="flex items-center gap-2 text-sm">
                              <span>{category.icon}</span>
                              <span className="text-slate-700">{category.name}</span>
                            </span>
                          ) : (
                            <span className="text-slate-400 text-sm">-</span>
                          )}
                          {getSourceBadge(trans.categorization_source)}
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-2">
                          {getClassificationBadge(trans.classification)}
                          {trans.is_user_confirmed && (
                            <Lock className="w-3 h-3 text-emerald-600" title="User confirmed - locked" />
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-1">
                          {trans.classification !== 'personal' && (
                            <button
                              onClick={() => handleClassificationChange(trans.id, 'personal')}
                              className="p-2 rounded-lg hover:bg-emerald-50 text-slate-400 hover:text-emerald-600 transition-all"
                              title="Mark as Personal"
                            >
                              <User className="w-4 h-4" />
                            </button>
                          )}
                          {trans.classification !== 'business' && (
                            <button
                              onClick={() => handleClassificationChange(trans.id, 'business')}
                              className="p-2 rounded-lg hover:bg-amber-50 text-slate-400 hover:text-amber-600 transition-all"
                              title="Mark as Business"
                            >
                              <Briefcase className="w-4 h-4" />
                            </button>
                          )}
                          {trans.is_user_confirmed && (
                            <button
                              onClick={() => handleResetTransaction(trans.id)}
                              className="p-2 rounded-lg hover:bg-purple-50 text-slate-400 hover:text-purple-600 transition-all"
                              title="Reset for re-categorization"
                            >
                              <RotateCcw className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {total > 0 && (
          <div className="flex items-center justify-between px-6 py-4 border-t border-slate-100 bg-slate-50">
            <div className="flex items-center gap-4">
              <p className="text-sm text-slate-500">
                Showing {((page - 1) * pageSize) + 1} to {Math.min(page * pageSize, total)} of {total}
              </p>
              <div className="flex items-center gap-2">
                <span className="text-sm text-slate-500">Show</span>
                <select
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value));
                    setPage(1); // Reset to first page when changing page size
                  }}
                  className="px-2 py-1 rounded-lg bg-white border border-slate-200 text-slate-700 text-sm focus:border-ocean-500"
                >
                  {pageSizeOptions.map(size => (
                    <option key={size} value={size}>{size}</option>
                  ))}
                </select>
                <span className="text-sm text-slate-500">per page</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-2 rounded-lg hover:bg-slate-200 text-slate-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ChevronLeft className="w-5 h-5" />
              </button>
              <span className="px-4 py-2 text-sm text-slate-700">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="p-2 rounded-lg hover:bg-slate-200 text-slate-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ChevronRight className="w-5 h-5" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Bulk Action Modal */}
      {showBulkModal && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md mx-4 shadow-xl animate-slide-up">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold text-slate-800">
                {bulkAction === 'classification' ? 'Set Classification' : 'Set Category'}
              </h2>
              <button
                onClick={() => setShowBulkModal(false)}
                className="p-2 rounded-lg hover:bg-slate-100 text-slate-500"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-slate-500 mb-4">
              Apply to <strong className="text-ocean-600">{selectedIds.size}</strong> selected transactions
            </p>

            {bulkAction === 'classification' && (
              <div className="space-y-3">
                <button
                  onClick={() => setBulkValue('personal')}
                  className={clsx(
                    'w-full flex items-center gap-3 p-4 rounded-xl border transition-all',
                    bulkValue === 'personal'
                      ? 'border-emerald-500 bg-emerald-50'
                      : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                  )}
                >
                  <User className="w-5 h-5 text-emerald-600" />
                  <div className="text-left">
                    <p className="font-medium text-slate-800">Personal</p>
                    <p className="text-sm text-slate-500">Track as personal expense</p>
                  </div>
                </button>
                <button
                  onClick={() => setBulkValue('business')}
                  className={clsx(
                    'w-full flex items-center gap-3 p-4 rounded-xl border transition-all',
                    bulkValue === 'business'
                      ? 'border-amber-500 bg-amber-50'
                      : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                  )}
                >
                  <Briefcase className="w-5 h-5 text-amber-600" />
                  <div className="text-left">
                    <p className="font-medium text-slate-800">Business</p>
                    <p className="text-sm text-slate-500">Ignore for personal tracking</p>
                  </div>
                </button>
              </div>
            )}

            {bulkAction === 'category' && (
              <div className="space-y-4">
                {/* Category Search */}
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <input
                    type="text"
                    placeholder="Search categories..."
                    value={categorySearch}
                    onChange={(e) => setCategorySearch(e.target.value)}
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-50 border border-slate-200 text-slate-800 placeholder-slate-400 focus:border-purple-500 focus:ring-1 focus:ring-purple-500"
                    autoFocus
                  />
                </div>

                {/* Filtered Categories */}
                <div className="max-h-64 overflow-y-auto space-y-4">
                  {expenseCategories.filter(cat =>
                    cat.name.toLowerCase().includes(categorySearch.toLowerCase())
                  ).length > 0 && (
                    <div>
                      <label className="block text-xs text-slate-500 uppercase tracking-wide mb-2">Expenses</label>
                      <div className="grid grid-cols-2 gap-2">
                        {expenseCategories
                          .filter(cat => cat.name.toLowerCase().includes(categorySearch.toLowerCase()))
                          .map(cat => (
                            <button
                              key={cat.id}
                              onClick={() => setBulkValue(cat.id.toString())}
                              className={clsx(
                                'flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all',
                                bulkValue === cat.id.toString()
                                  ? 'bg-purple-100 text-purple-700 ring-1 ring-purple-500'
                                  : 'bg-slate-50 text-slate-700 hover:bg-slate-100'
                              )}
                            >
                              <span>{cat.icon}</span>
                              <span className="truncate">{cat.name}</span>
                            </button>
                          ))}
                      </div>
                    </div>
                  )}

                  {incomeCategories.filter(cat =>
                    cat.name.toLowerCase().includes(categorySearch.toLowerCase())
                  ).length > 0 && (
                    <div>
                      <label className="block text-xs text-slate-500 uppercase tracking-wide mb-2">Income</label>
                      <div className="grid grid-cols-2 gap-2">
                        {incomeCategories
                          .filter(cat => cat.name.toLowerCase().includes(categorySearch.toLowerCase()))
                          .map(cat => (
                            <button
                              key={cat.id}
                              onClick={() => setBulkValue(cat.id.toString())}
                              className={clsx(
                                'flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all',
                                bulkValue === cat.id.toString()
                                  ? 'bg-purple-100 text-purple-700 ring-1 ring-purple-500'
                                  : 'bg-slate-50 text-slate-700 hover:bg-slate-100'
                              )}
                            >
                              <span>{cat.icon}</span>
                              <span className="truncate">{cat.name}</span>
                            </button>
                          ))}
                      </div>
                    </div>
                  )}

                  {/* No results message */}
                  {categorySearch &&
                   expenseCategories.filter(cat => cat.name.toLowerCase().includes(categorySearch.toLowerCase())).length === 0 &&
                   incomeCategories.filter(cat => cat.name.toLowerCase().includes(categorySearch.toLowerCase())).length === 0 && (
                    <p className="text-center text-slate-500 py-4">
                      No categories matching "{categorySearch}"
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center justify-end gap-3 mt-6">
              <button
                onClick={() => setShowBulkModal(false)}
                className="px-4 py-2 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleBulkApply}
                disabled={!bulkValue || bulkProcessing}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-ocean-500 hover:bg-ocean-600 text-white font-medium transition-all disabled:opacity-50"
              >
                {bulkProcessing && <RefreshCw className="w-4 h-4 animate-spin" />}
                Apply to {selectedIds.size} transactions
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Transactions;
