import { useState, useEffect } from 'react';
import { 
  Sparkles, 
  Check, 
  X, 
  ChevronRight,
  RefreshCw,
  AlertCircle,
  Brain,
  Zap,
  CheckCircle2,
  Filter,
  SkipForward
} from 'lucide-react';
import { categorizationApi, categoriesApi, accountsApi } from '../services/api';
import clsx from 'clsx';
import { format } from 'date-fns';

function Review() {
  const [suggestions, setSuggestions] = useState([]);
  const [categories, setCategories] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  
  // Current transaction being reviewed
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [selectedClassification, setSelectedClassification] = useState(null);
  const [loadingAiSuggestion, setLoadingAiSuggestion] = useState(false);
  
  // Stats
  const [stats, setStats] = useState({ reviewed: 0, remaining: 0 });
  
  // Filters
  const [filterAccount, setFilterAccount] = useState('');

  useEffect(() => {
    loadInitialData();
  }, []);

  useEffect(() => {
    loadSuggestions();
  }, [filterAccount]);

  const loadInitialData = async () => {
    try {
      const [categoriesRes, accountsRes] = await Promise.all([
        categoriesApi.list(),
        accountsApi.list()
      ]);
      setCategories(categoriesRes.data);
      setAccounts(accountsRes.data);
    } catch (err) {
      console.error('Failed to load initial data', err);
    }
  };

  const loadSuggestions = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await categorizationApi.getSuggestions(
        filterAccount || null,
        50
      );
      setSuggestions(response.data.items || []);
      setStats({
        reviewed: 0,
        remaining: response.data.total || 0
      });
      setCurrentIndex(0);
      
      // Pre-select the suggestion for first item
      if (response.data.items?.length > 0) {
        const first = response.data.items[0];
        setSelectedClassification(first.suggestion.classification);
        setSelectedCategory(first.suggestion.category_id);
      }
    } catch (err) {
      setError('Failed to load transactions for review');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const currentItem = suggestions[currentIndex];
  
  const handleApply = async (skipLearn = false) => {
    if (!currentItem) return;
    
    setProcessing(true);
    try {
      const response = await categorizationApi.apply(
        currentItem.transaction.id,
        selectedClassification || 'personal',
        selectedCategory,
        !skipLearn  // learn = true unless skipping
      );
      
      const similarUpdated = response.data?.similar_updated || 0;
      
      // Move to next - also remove similar transactions if they were updated
      let newSuggestions = suggestions.filter((_, i) => i !== currentIndex);
      
      // If similar transactions were updated, remove them from the queue too
      if (similarUpdated > 0 && response.data?.category_id) {
        // Find and remove transactions that might have been auto-categorized
        const updatedCategory = response.data.category_id;
        // Reload suggestions to get fresh data
        setTimeout(() => loadSuggestions(), 500);
      }
      
      setSuggestions(newSuggestions);
      
      // Update stats
      setStats(prev => ({
        reviewed: prev.reviewed + 1 + similarUpdated,
        remaining: Math.max(0, prev.remaining - 1 - similarUpdated)
      }));
      
      // Pre-select next suggestion
      if (newSuggestions.length > 0) {
        const nextIndex = Math.min(currentIndex, newSuggestions.length - 1);
        setCurrentIndex(nextIndex);
        const next = newSuggestions[nextIndex];
        setSelectedClassification(next.suggestion.classification);
        setSelectedCategory(next.suggestion.category_id);
      }
      
      // Show success with similar count
      if (similarUpdated > 0) {
        setSuccess(`Categorized! Also applied to ${similarUpdated} similar transactions 🎉`);
      } else {
        setSuccess('Transaction categorized!');
      }
      setTimeout(() => setSuccess(null), 3000);
      
    } catch (err) {
      setError('Failed to apply categorization');
      console.error(err);
    } finally {
      setProcessing(false);
    }
  };

  const handleSkip = () => {
    if (currentIndex < suggestions.length - 1) {
      const nextIndex = currentIndex + 1;
      setCurrentIndex(nextIndex);
      const next = suggestions[nextIndex];
      setSelectedClassification(next.suggestion.classification);
      setSelectedCategory(next.suggestion.category_id);
    }
  };

  const handleGetAiSuggestion = async () => {
    if (!currentItem) return;
    setLoadingAiSuggestion(true);
    try {
      const response = await categorizationApi.suggestOne(currentItem.transaction.id);
      const aiSuggestion = response.data.suggestion;
      
      // Update the current item's suggestion
      const updated = [...suggestions];
      updated[currentIndex] = {
        ...updated[currentIndex],
        suggestion: aiSuggestion
      };
      setSuggestions(updated);
      
      // Pre-select the AI suggestion
      setSelectedClassification(aiSuggestion.classification);
      setSelectedCategory(aiSuggestion.category_id);
    } catch (err) {
      setError('Failed to get AI suggestion');
      console.error(err);
    } finally {
      setLoadingAiSuggestion(false);
    }
  };

  const handleAutoApplyAll = async () => {
    setProcessing(true);
    try {
      const response = await categorizationApi.autoCategorize(
        filterAccount || null,
        true  // apply = true
      );
      
      setSuccess(`Auto-categorized ${response.data.applied} transactions!`);
      loadSuggestions();
    } catch (err) {
      setError('Failed to auto-categorize');
      console.error(err);
    } finally {
      setProcessing(false);
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-NZ', {
      style: 'currency',
      currency: 'NZD'
    }).format(amount);
  };

  const formatDate = (dateStr) => {
    try {
      return format(new Date(dateStr), 'EEE, dd MMM yyyy');
    } catch {
      return dateStr;
    }
  };

  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.8) return 'text-emerald-400';
    if (confidence >= 0.5) return 'text-amber-400';
    return 'text-coral-400';
  };

  const expenseCategories = categories.filter(c => !c.is_income);
  const incomeCategories = categories.filter(c => c.is_income);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold text-slate-100 flex items-center gap-3">
            <Brain className="w-8 h-8 text-ocean-400" />
            Smart Review
          </h1>
          <p className="text-slate-400 mt-1">
            Review AI suggestions and teach the system your preferences
          </p>
        </div>
        
        <div className="flex items-center gap-3">
          {/* Account Filter */}
          <select
            value={filterAccount}
            onChange={(e) => setFilterAccount(e.target.value)}
            className="px-4 py-2 rounded-xl bg-slate-800 border border-slate-700 text-slate-100 focus:border-ocean-500"
          >
            <option value="">All Accounts</option>
            {accounts.map(acc => (
              <option key={acc.id} value={acc.id}>{acc.name}</option>
            ))}
          </select>
          
          <button
            onClick={loadSuggestions}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition-all disabled:opacity-50"
          >
            <RefreshCw className={clsx('w-4 h-4', loading && 'animate-spin')} />
            Refresh
          </button>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="glass rounded-2xl p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-8">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              <span className="text-slate-300">
                <span className="font-bold text-emerald-400">{stats.reviewed}</span> reviewed
              </span>
            </div>
            <div className="flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-amber-400" />
              <span className="text-slate-300">
                <span className="font-bold text-amber-400">{stats.remaining}</span> remaining
              </span>
            </div>
          </div>
          
          <button
            onClick={handleAutoApplyAll}
            disabled={processing || suggestions.length === 0}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-purple-500 to-purple-600 text-white font-medium hover:shadow-lg hover:shadow-purple-500/30 transition-all disabled:opacity-50"
          >
            <Zap className="w-4 h-4" />
            Auto-Apply High Confidence
          </button>
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-coral-500/10 border border-coral-500/20 text-coral-400 animate-fade-in">
          <AlertCircle className="w-5 h-5" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {success && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 animate-fade-in">
          <CheckCircle2 className="w-5 h-5" />
          {success}
        </div>
      )}

      {/* Main Review Area */}
      {loading ? (
        <div className="flex items-center justify-center p-12">
          <RefreshCw className="w-8 h-8 text-ocean-400 animate-spin" />
        </div>
      ) : suggestions.length === 0 ? (
        <div className="glass rounded-2xl p-12 text-center animate-fade-in">
          <div className="w-20 h-20 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto mb-6">
            <CheckCircle2 className="w-10 h-10 text-emerald-400" />
          </div>
          <h2 className="text-xl font-display font-bold text-slate-100 mb-2">
            All Caught Up!
          </h2>
          <p className="text-slate-400">
            No transactions need review. Upload more data or check back later.
          </p>
        </div>
      ) : currentItem && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Transaction Details */}
          <div className="lg:col-span-2 space-y-6">
            {/* Transaction Card */}
            <div className="glass rounded-2xl p-6 animate-slide-up">
              <div className="flex items-start justify-between mb-6">
                <div>
                  <p className="text-sm text-slate-500 mb-1">
                    {formatDate(currentItem.transaction.date)}
                  </p>
                  <h2 className="text-2xl font-display font-bold text-slate-100">
                    {/* Show code (merchant) if available, otherwise details, fallback to type */}
                    {currentItem.transaction.code || currentItem.transaction.details || currentItem.transaction.type || 'Unknown'}
                  </h2>
                  <p className="text-slate-400 mt-1">
                    {currentItem.transaction.type}
                    {currentItem.transaction.details && currentItem.transaction.code && (
                      <span className="text-slate-500"> • {currentItem.transaction.details}</span>
                    )}
                  </p>
                </div>
                <div className={clsx(
                  'text-3xl font-mono font-bold',
                  currentItem.transaction.amount < 0 ? 'text-coral-400' : 'text-emerald-400'
                )}>
                  {formatCurrency(currentItem.transaction.amount)}
                </div>
              </div>
              
              {/* Additional Details */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4 text-sm">
                {currentItem.transaction.particulars && (
                  <div className="bg-slate-800/50 rounded-lg p-2">
                    <span className="text-slate-500 block text-xs">Particulars</span>
                    <span className="text-slate-300">{currentItem.transaction.particulars}</span>
                  </div>
                )}
                {currentItem.transaction.reference && (
                  <div className="bg-slate-800/50 rounded-lg p-2">
                    <span className="text-slate-500 block text-xs">Reference</span>
                    <span className="text-slate-300">{currentItem.transaction.reference}</span>
                  </div>
                )}
                {currentItem.transaction.to_from_account && (
                  <div className="bg-slate-800/50 rounded-lg p-2">
                    <span className="text-slate-500 block text-xs">To/From Account</span>
                    <span className="text-slate-300">{currentItem.transaction.to_from_account}</span>
                  </div>
                )}
                {currentItem.transaction.balance && (
                  <div className="bg-slate-800/50 rounded-lg p-2">
                    <span className="text-slate-500 block text-xs">Balance After</span>
                    <span className="text-slate-300">{formatCurrency(currentItem.transaction.balance)}</span>
                  </div>
                )}
              </div>

              {/* AI Suggestion */}
              <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700">
                <div className="flex items-center gap-2 mb-3">
                  <Sparkles className="w-5 h-5 text-purple-400" />
                  <span className="font-medium text-slate-200">
                    {currentItem.suggestion.source === 'none' ? 'No Rules Match' : 'Suggestion'}
                  </span>
                  {currentItem.suggestion.source !== 'none' && (
                    <span className={clsx(
                      'ml-auto text-sm font-mono',
                      getConfidenceColor(currentItem.suggestion.confidence)
                    )}>
                      {Math.round(currentItem.suggestion.confidence * 100)}% confidence
                    </span>
                  )}
                </div>
                
                {currentItem.suggestion.source === 'none' ? (
                  <div className="flex items-center justify-between">
                    <p className="text-sm text-slate-400">
                      No learned rules match this transaction.
                    </p>
                    <button
                      onClick={handleGetAiSuggestion}
                      disabled={loadingAiSuggestion}
                      className="flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 text-purple-400 text-sm font-medium transition-all disabled:opacity-50"
                    >
                      {loadingAiSuggestion ? (
                        <RefreshCw className="w-4 h-4 animate-spin" />
                      ) : (
                        <Brain className="w-4 h-4" />
                      )}
                      Get AI Suggestion
                    </button>
                  </div>
                ) : (
                  <>
                    <div className="flex items-center gap-4">
                      <span className={clsx(
                        'px-3 py-1 rounded-full text-sm font-medium',
                        currentItem.suggestion.classification === 'personal' 
                          ? 'bg-emerald-500/20 text-emerald-400'
                          : 'bg-amber-500/20 text-amber-400'
                      )}>
                        {currentItem.suggestion.classification === 'personal' ? '👤 Personal' : '💼 Business'}
                      </span>
                      {currentItem.suggestion.category_name && (
                        <>
                          <ChevronRight className="w-4 h-4 text-slate-500" />
                          <span className="text-slate-300">{currentItem.suggestion.category_name}</span>
                        </>
                      )}
                    </div>
                    <p className="text-sm text-slate-500 mt-2">
                      {currentItem.suggestion.explanation}
                    </p>
                  </>
                )}
              </div>
            </div>

            {/* Classification Selection */}
            <div className="glass rounded-2xl p-6 animate-slide-up" style={{ animationDelay: '100ms' }}>
              <h3 className="font-semibold text-slate-100 mb-4">Classification</h3>
              <div className="grid grid-cols-2 gap-4">
                <button
                  onClick={() => setSelectedClassification('personal')}
                  className={clsx(
                    'flex items-center gap-3 p-4 rounded-xl border-2 transition-all',
                    selectedClassification === 'personal'
                      ? 'border-emerald-500 bg-emerald-500/10'
                      : 'border-slate-700 hover:border-slate-600'
                  )}
                >
                  <span className="text-2xl">👤</span>
                  <div className="text-left">
                    <p className="font-medium text-slate-100">Personal</p>
                    <p className="text-sm text-slate-400">Track this expense</p>
                  </div>
                </button>
                <button
                  onClick={() => setSelectedClassification('business')}
                  className={clsx(
                    'flex items-center gap-3 p-4 rounded-xl border-2 transition-all',
                    selectedClassification === 'business'
                      ? 'border-amber-500 bg-amber-500/10'
                      : 'border-slate-700 hover:border-slate-600'
                  )}
                >
                  <span className="text-2xl">💼</span>
                  <div className="text-left">
                    <p className="font-medium text-slate-100">Business</p>
                    <p className="text-sm text-slate-400">Ignore for personal tracking</p>
                  </div>
                </button>
              </div>
            </div>

            {/* Category Selection (only for Personal) */}
            {selectedClassification === 'personal' && (
              <div className="glass rounded-2xl p-6 animate-slide-up" style={{ animationDelay: '200ms' }}>
                <h3 className="font-semibold text-slate-100 mb-4">Category</h3>
                
                {/* Expense Categories */}
                <div className="mb-4">
                  <p className="text-sm text-slate-500 mb-2">Expenses</p>
                  <div className="grid grid-cols-3 md:grid-cols-4 gap-2">
                    {expenseCategories.map(cat => (
                      <button
                        key={cat.id}
                        onClick={() => setSelectedCategory(cat.id)}
                        className={clsx(
                          'flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all',
                          selectedCategory === cat.id
                            ? 'bg-ocean-500/20 border border-ocean-500 text-ocean-400'
                            : 'bg-slate-800 hover:bg-slate-700 text-slate-300'
                        )}
                      >
                        <span>{cat.icon}</span>
                        <span className="truncate">{cat.name}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Income Categories */}
                {currentItem.transaction.amount > 0 && (
                  <div>
                    <p className="text-sm text-slate-500 mb-2">Income</p>
                    <div className="grid grid-cols-3 md:grid-cols-4 gap-2">
                      {incomeCategories.map(cat => (
                        <button
                          key={cat.id}
                          onClick={() => setSelectedCategory(cat.id)}
                          className={clsx(
                            'flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all',
                            selectedCategory === cat.id
                              ? 'bg-ocean-500/20 border border-ocean-500 text-ocean-400'
                              : 'bg-slate-800 hover:bg-slate-700 text-slate-300'
                          )}
                        >
                          <span>{cat.icon}</span>
                          <span className="truncate">{cat.name}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center gap-4">
              <button
                onClick={handleSkip}
                disabled={processing || currentIndex >= suggestions.length - 1}
                className="flex items-center gap-2 px-6 py-3 rounded-xl border border-slate-700 text-slate-300 hover:bg-slate-800 transition-all disabled:opacity-50"
              >
                <SkipForward className="w-4 h-4" />
                Skip
              </button>
              <button
                onClick={() => handleApply(false)}
                disabled={processing}
                className="flex-1 flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-ocean-500 to-ocean-600 text-white font-medium hover:shadow-lg hover:shadow-ocean-500/30 transition-all btn-glow disabled:opacity-50"
              >
                {processing ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Applying...
                  </>
                ) : (
                  <>
                    <Check className="w-5 h-5" />
                    Apply & Learn
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Queue Preview */}
          <div className="glass rounded-2xl p-6 h-fit animate-slide-in-right">
            <h3 className="font-semibold text-slate-100 mb-4">
              Up Next ({suggestions.length - 1} more)
            </h3>
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {suggestions.slice(currentIndex + 1, currentIndex + 6).map((item, idx) => (
                <div
                  key={item.transaction.id}
                  className="p-3 rounded-xl bg-slate-800/50 cursor-pointer hover:bg-slate-800 transition-all"
                  onClick={() => {
                    setCurrentIndex(currentIndex + idx + 1);
                    setSelectedClassification(item.suggestion.classification);
                    setSelectedCategory(item.suggestion.category_id);
                  }}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-slate-300 truncate max-w-[150px]">
                      {item.transaction.code || item.transaction.details || item.transaction.type || 'Unknown'}
                    </span>
                    <span className={clsx(
                      'text-sm font-mono',
                      item.transaction.amount < 0 ? 'text-coral-400' : 'text-emerald-400'
                    )}>
                      {formatCurrency(item.transaction.amount)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={clsx(
                      'w-2 h-2 rounded-full',
                      item.suggestion.confidence >= 0.8 ? 'bg-emerald-400' :
                      item.suggestion.confidence >= 0.5 ? 'bg-amber-400' : 'bg-coral-400'
                    )} />
                    <span className="text-xs text-slate-500">
                      {item.suggestion.category_name || 'Uncategorized'}
                    </span>
                  </div>
                </div>
              ))}
              
              {suggestions.length > currentIndex + 6 && (
                <p className="text-center text-sm text-slate-500 py-2">
                  +{suggestions.length - currentIndex - 6} more...
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Review;

