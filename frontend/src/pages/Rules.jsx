import { useState, useEffect } from 'react';
import { 
  BookOpen, 
  Trash2, 
  RefreshCw, 
  AlertCircle,
  CheckCircle2,
  TrendingUp,
  X
} from 'lucide-react';
import { categorizationApi } from '../services/api';
import clsx from 'clsx';

function Rules() {
  const [rules, setRules] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [rulesRes, statsRes] = await Promise.all([
        categorizationApi.getRules(),
        categorizationApi.getRuleStats()
      ]);
      setRules(rulesRes.data);
      setStats(statsRes.data);
    } catch (err) {
      setError('Failed to load rules');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteRule = async (ruleId) => {
    if (!confirm('Are you sure you want to delete this rule?')) return;
    
    try {
      await categorizationApi.deleteRule(ruleId);
      setRules(rules.filter(r => r.id !== ruleId));
      setSuccess('Rule deleted successfully');
      setTimeout(() => setSuccess(null), 2000);
    } catch (err) {
      setError('Failed to delete rule');
      console.error(err);
    }
  };

  const getConfidenceBadge = (confidence) => {
    if (confidence >= 0.8) {
      return <span className="badge badge-success">High ({Math.round(confidence * 100)}%)</span>;
    } else if (confidence >= 0.5) {
      return <span className="badge badge-warning">Medium ({Math.round(confidence * 100)}%)</span>;
    }
    return <span className="badge badge-danger">Low ({Math.round(confidence * 100)}%)</span>;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold text-slate-100 flex items-center gap-3">
            <BookOpen className="w-8 h-8 text-ocean-400" />
            Learned Rules
          </h1>
          <p className="text-slate-400 mt-1">
            Rules the system has learned from your categorizations
          </p>
        </div>
        <button
          onClick={loadData}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition-all disabled:opacity-50"
        >
          <RefreshCw className={clsx('w-4 h-4', loading && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="glass rounded-xl p-4">
            <p className="text-sm text-slate-400">Total Rules</p>
            <p className="text-2xl font-bold text-slate-100">{stats.total_rules}</p>
          </div>
          <div className="glass rounded-xl p-4">
            <p className="text-sm text-slate-400">High Confidence</p>
            <p className="text-2xl font-bold text-emerald-400">{stats.high_confidence_rules}</p>
          </div>
          <div className="glass rounded-xl p-4">
            <p className="text-sm text-slate-400">Times Applied</p>
            <p className="text-2xl font-bold text-ocean-400">{stats.total_times_applied}</p>
          </div>
          <div className="glass rounded-xl p-4">
            <p className="text-sm text-slate-400">Accuracy Rate</p>
            <p className="text-2xl font-bold text-purple-400">
              {Math.round(stats.accuracy_rate * 100)}%
            </p>
          </div>
        </div>
      )}

      {/* Messages */}
      {error && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-coral-500/10 border border-coral-500/20 text-coral-400">
          <AlertCircle className="w-5 h-5" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {success && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
          <CheckCircle2 className="w-5 h-5" />
          {success}
        </div>
      )}

      {/* Rules Table */}
      <div className="glass rounded-2xl overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center p-12">
            <RefreshCw className="w-8 h-8 text-ocean-400 animate-spin" />
          </div>
        ) : rules.length === 0 ? (
          <div className="text-center p-12">
            <BookOpen className="w-12 h-12 text-slate-600 mx-auto mb-4" />
            <p className="text-slate-400">No rules learned yet</p>
            <p className="text-sm text-slate-500 mt-1">
              Start categorizing transactions to build up rules
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-sm text-slate-400 bg-slate-800/50">
                  <th className="px-6 py-4 font-medium">Pattern</th>
                  <th className="px-6 py-4 font-medium">Match Type</th>
                  <th className="px-6 py-4 font-medium">Classification</th>
                  <th className="px-6 py-4 font-medium">Category</th>
                  <th className="px-6 py-4 font-medium">Confidence</th>
                  <th className="px-6 py-4 font-medium">Usage</th>
                  <th className="px-6 py-4 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {rules.map((rule) => (
                  <tr key={rule.id} className="border-t border-slate-800 table-row-hover">
                    <td className="px-6 py-4">
                      <span className="font-mono text-slate-200">{rule.merchant_pattern}</span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-sm text-slate-400 capitalize">{rule.match_type}</span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={clsx(
                        'px-2 py-1 rounded-full text-xs font-medium',
                        rule.classification === 'personal' 
                          ? 'bg-emerald-500/20 text-emerald-400'
                          : 'bg-amber-500/20 text-amber-400'
                      )}>
                        {rule.classification}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-slate-300">{rule.category_name || '-'}</span>
                    </td>
                    <td className="px-6 py-4">
                      {getConfidenceBadge(rule.confidence)}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2 text-sm">
                        <span className="text-emerald-400">{rule.times_applied} applied</span>
                        {rule.times_overridden > 0 && (
                          <span className="text-coral-400">({rule.times_overridden} overridden)</span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <button
                        onClick={() => handleDeleteRule(rule.id)}
                        className="p-2 rounded-lg hover:bg-coral-500/20 text-slate-400 hover:text-coral-400 transition-all"
                        title="Delete rule"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Info */}
      <div className="glass rounded-xl p-4 flex items-start gap-3">
        <TrendingUp className="w-5 h-5 text-ocean-400 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-slate-300 font-medium">How rules work</p>
          <p className="text-sm text-slate-500 mt-1">
            When you categorize a transaction, the system learns the merchant pattern. 
            Next time a similar transaction appears, it will automatically apply the same categorization.
            Rules with higher confidence are applied automatically; lower confidence rules are suggested for review.
          </p>
        </div>
      </div>
    </div>
  );
}

export default Rules;


