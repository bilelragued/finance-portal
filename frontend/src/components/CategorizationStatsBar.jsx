import { useState, useEffect } from 'react';
import { categorizationApi } from '../services/api';
import { AlertCircle, CheckCircle2, RefreshCw, Zap, Lock, Bot } from 'lucide-react';
import clsx from 'clsx';

/**
 * Stats bar showing categorization status.
 * Can be placed on any page to show current categorization state.
 */
function CategorizationStatsBar({ 
  onNeedsAttentionClick,
  compact = false,
  className = ''
}) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [mlTraining, setMlTraining] = useState(false);
  const [mlResult, setMlResult] = useState(null);

  const loadStats = async () => {
    try {
      const response = await categorizationApi.getStats();
      setStats(response.data);
    } catch (err) {
      console.error('Failed to load categorization stats:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStats();
    // Refresh every 30 seconds
    const interval = setInterval(loadStats, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleTrainML = async () => {
    setMlTraining(true);
    setMlResult(null);
    try {
      const response = await categorizationApi.mlTrain();
      setMlResult(response.data);
      loadStats();
    } catch (err) {
      setMlResult({ error: err.message || 'Training failed' });
    } finally {
      setMlTraining(false);
    }
  };

  const handleAutoCategorizeMl = async () => {
    setMlTraining(true);
    try {
      const response = await categorizationApi.mlAutoCategorize(0.7, true);
      setMlResult({ 
        success: true, 
        message: `Updated ${response.data.updated} transactions` 
      });
      loadStats();
    } catch (err) {
      setMlResult({ error: err.message || 'Auto-categorize failed' });
    } finally {
      setMlTraining(false);
    }
  };

  if (loading) {
    return (
      <div className={clsx("bg-white rounded-xl p-4 shadow-sm border border-slate-100 animate-pulse", className)}>
        <div className="h-6 bg-slate-200 rounded w-1/2"></div>
      </div>
    );
  }

  if (!stats) return null;

  const percentConfirmed = stats.total > 0
    ? Math.round((stats.user_confirmed / stats.total) * 100)
    : 0;

  if (compact) {
    return (
      <div className={clsx("flex items-center gap-4 text-sm", className)}>
        {stats.needs_attention > 0 && (
          <button
            onClick={onNeedsAttentionClick}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-amber-100 text-amber-700 hover:bg-amber-200 transition-all"
          >
            <AlertCircle className="w-4 h-4" />
            <span>{stats.needs_attention} need attention</span>
          </button>
        )}
        <div className="flex items-center gap-1.5 text-slate-500">
          <Lock className="w-4 h-4 text-emerald-600" />
          <span>{stats.user_confirmed} confirmed</span>
        </div>
        <div className="flex items-center gap-1.5 text-slate-500">
          <Bot className="w-4 h-4 text-blue-600" />
          <span>{stats.auto_categorized} auto</span>
        </div>
      </div>
    );
  }

  return (
    <div className={clsx("bg-white rounded-xl p-4 shadow-sm border border-slate-100", className)}>
      {/* Main stats row */}
      <div className="flex flex-wrap items-center gap-6">
        {/* Needs Attention */}
        {stats.needs_attention > 0 ? (
          <button
            onClick={onNeedsAttentionClick}
            className="flex items-center gap-3 px-4 py-2 rounded-xl bg-amber-50 border border-amber-200 hover:bg-amber-100 transition-all group"
          >
            <div className="p-2 rounded-lg bg-amber-100">
              <AlertCircle className="w-5 h-5 text-amber-600" />
            </div>
            <div className="text-left">
              <p className="text-2xl font-bold text-amber-600">{stats.needs_attention}</p>
              <p className="text-xs text-slate-500 group-hover:text-slate-600">Need Attention</p>
            </div>
          </button>
        ) : (
          <div className="flex items-center gap-3 px-4 py-2 rounded-xl bg-emerald-50 border border-emerald-200">
            <div className="p-2 rounded-lg bg-emerald-100">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            </div>
            <div>
              <p className="text-sm font-medium text-emerald-600">All Categorized!</p>
              <p className="text-xs text-slate-500">No transactions need attention</p>
            </div>
          </div>
        )}

        {/* Divider */}
        <div className="h-12 w-px bg-slate-200"></div>

        {/* User Confirmed */}
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-emerald-50">
            <Lock className="w-5 h-5 text-emerald-600" />
          </div>
          <div>
            <p className="text-xl font-semibold text-slate-800">{stats.user_confirmed}</p>
            <p className="text-xs text-slate-500">Confirmed ({percentConfirmed}%)</p>
          </div>
        </div>

        {/* Auto Categorized */}
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-blue-50">
            <Bot className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <p className="text-xl font-semibold text-slate-800">{stats.auto_categorized}</p>
            <p className="text-xs text-slate-500">Auto-categorized</p>
          </div>
        </div>

        {/* Uncategorized */}
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-slate-100">
            <AlertCircle className="w-5 h-5 text-slate-500" />
          </div>
          <div>
            <p className="text-xl font-semibold text-slate-800">{stats.uncategorized}</p>
            <p className="text-xs text-slate-500">Uncategorized</p>
          </div>
        </div>

        {/* ML Actions */}
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={handleTrainML}
            disabled={mlTraining}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-purple-50 text-purple-700 hover:bg-purple-100 disabled:opacity-50 transition-all text-sm border border-purple-200"
            title="Train ML model on your confirmed categorizations"
          >
            {mlTraining ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Zap className="w-4 h-4" />
            )}
            Train ML
          </button>

          {stats.uncategorized > 0 && (
            <button
              onClick={handleAutoCategorizeMl}
              disabled={mlTraining}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-ocean-50 text-ocean-700 hover:bg-ocean-100 disabled:opacity-50 transition-all text-sm border border-ocean-200"
              title="Auto-categorize uncategorized transactions with ML"
            >
              <Bot className="w-4 h-4" />
              Auto-categorize
            </button>
          )}
        </div>
      </div>

      {/* ML Result feedback */}
      {mlResult && (
        <div className={clsx(
          "mt-3 px-4 py-2 rounded-lg text-sm",
          mlResult.error ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"
        )}>
          {mlResult.error ? (
            mlResult.error
          ) : mlResult.message ? (
            mlResult.message
          ) : mlResult.success ? (
            `ML trained on ${mlResult.samples} samples with ${Math.round(mlResult.accuracy * 100)}% accuracy`
          ) : (
            JSON.stringify(mlResult)
          )}
        </div>
      )}
    </div>
  );
}

export default CategorizationStatsBar;


