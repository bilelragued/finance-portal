import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { 
  TrendingUp, 
  TrendingDown, 
  Wallet, 
  Upload, 
  ArrowRight,
  RefreshCw,
  AlertCircle
} from 'lucide-react';
import { accountsApi, transactionsApi } from '../services/api';
import clsx from 'clsx';
import CategorizationStatsBar from '../components/CategorizationStatsBar';

function StatCard({ title, value, subtitle, icon: Icon, trend, color = 'ocean' }) {
  const colorClasses = {
    ocean: 'from-ocean-50 to-ocean-100 text-ocean-600',
    emerald: 'from-emerald-50 to-emerald-100 text-emerald-600',
    coral: 'from-red-50 to-red-100 text-red-600',
    amber: 'from-amber-50 to-amber-100 text-amber-600',
  };

  return (
    <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 animate-fade-in">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-slate-500 text-sm font-medium">{title}</p>
          <p className="text-2xl font-display font-bold mt-1 text-slate-800">{value}</p>
          {subtitle && (
            <p className="text-sm text-slate-400 mt-1">{subtitle}</p>
          )}
        </div>
        <div className={clsx(
          'w-12 h-12 rounded-xl bg-gradient-to-br flex items-center justify-center',
          colorClasses[color]
        )}>
          <Icon className="w-6 h-6" />
        </div>
      </div>
      {trend && (
        <div className={clsx(
          'flex items-center gap-1 mt-4 text-sm font-medium',
          trend > 0 ? 'text-emerald-600' : 'text-red-600'
        )}>
          {trend > 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
          <span>{Math.abs(trend)}% from last month</span>
        </div>
      )}
    </div>
  );
}

function Dashboard() {
  const navigate = useNavigate();
  const [accounts, setAccounts] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [accountsRes, statsRes] = await Promise.all([
        accountsApi.list(),
        transactionsApi.getStats()
      ]);
      setAccounts(accountsRes.data);
      setStats(statsRes.data);
    } catch (err) {
      setError('Failed to load dashboard data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount) => {
    const absAmount = Math.abs(amount);
    return new Intl.NumberFormat('en-NZ', {
      style: 'currency',
      currency: 'NZD',
      minimumFractionDigits: 2
    }).format(absAmount);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-ocean-500 animate-spin" />
      </div>
    );
  }

  const hasData = accounts.length > 0 && stats?.total_transactions > 0;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold text-slate-800">Dashboard</h1>
          <p className="text-slate-500 mt-1">Overview of your personal finances</p>
        </div>
        <button
          onClick={loadData}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white hover:bg-slate-50 text-slate-600 border border-slate-200 shadow-sm transition-all"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-red-50 border border-red-200 text-red-600">
          <AlertCircle className="w-5 h-5" />
          {error}
        </div>
      )}

      {/* Categorization Stats Bar */}
      {hasData && (
        <CategorizationStatsBar
          onNeedsAttentionClick={() => navigate('/transactions?category_id=null')}
        />
      )}

      {/* Empty state */}
      {!hasData && !error && (
        <div className="bg-white rounded-2xl p-12 text-center shadow-sm border border-slate-100 animate-fade-in">
          <div className="w-20 h-20 rounded-2xl bg-ocean-50 flex items-center justify-center mx-auto mb-6">
            <Upload className="w-10 h-10 text-ocean-500" />
          </div>
          <h2 className="text-xl font-display font-bold text-slate-800 mb-2">
            Welcome to Finance Portal
          </h2>
          <p className="text-slate-500 max-w-md mx-auto mb-6">
            Get started by uploading your bank transaction files. We'll help you analyze your spending and track your budget.
          </p>
          <Link
            to="/upload"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-ocean-500 to-ocean-600 text-white font-medium hover:shadow-lg hover:shadow-ocean-500/20 transition-all btn-glow"
          >
            Upload Transactions
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      )}

      {/* Stats Grid */}
      {hasData && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <StatCard
              title="Total Income"
              value={formatCurrency(stats?.total_income || 0)}
              icon={TrendingUp}
              color="emerald"
            />
            <StatCard
              title="Total Expenses"
              value={formatCurrency(stats?.total_expenses || 0)}
              icon={TrendingDown}
              color="coral"
            />
            <StatCard
              title="Net Cashflow"
              value={formatCurrency(stats?.net_cashflow || 0)}
              icon={Wallet}
              color={stats?.net_cashflow >= 0 ? 'emerald' : 'coral'}
            />
            <StatCard
              title="Transactions"
              value={stats?.total_transactions || 0}
              subtitle={`${stats?.classification?.unclassified || 0} need review`}
              icon={Upload}
              color="ocean"
            />
          </div>

          {/* Accounts List */}
          <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 animate-slide-up">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-display font-semibold text-slate-800">Accounts</h2>
              <Link
                to="/accounts"
                className="text-sm text-ocean-600 hover:text-ocean-700 flex items-center gap-1"
              >
                View all <ArrowRight className="w-4 h-4" />
              </Link>
            </div>

            <div className="space-y-3">
              {accounts.map((account, index) => (
                <div
                  key={account.id}
                  className="flex items-center justify-between p-4 rounded-xl bg-slate-50 hover:bg-slate-100 transition-all"
                  style={{ animationDelay: `${index * 100}ms` }}
                >
                  <div className="flex items-center gap-4">
                    <div className={clsx(
                      'w-10 h-10 rounded-xl flex items-center justify-center text-lg',
                      account.account_type === 'personal' && 'bg-ocean-100',
                      account.account_type === 'business' && 'bg-amber-100',
                      account.account_type === 'savings' && 'bg-emerald-100'
                    )}>
                      {account.account_type === 'personal' ? '👤' :
                       account.account_type === 'business' ? '💼' : '🏦'}
                    </div>
                    <div>
                      <p className="font-medium text-slate-800">{account.name}</p>
                      <p className="text-sm text-slate-500">{account.account_number}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-slate-600">{account.owner}</p>
                    <p className="text-sm text-slate-400">
                      {account.transaction_count} transactions
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Actions */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Link
              to="/upload"
              className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 hover:border-ocean-200 hover:shadow-md transition-all group"
            >
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-ocean-50 flex items-center justify-center group-hover:scale-110 transition-transform">
                  <Upload className="w-6 h-6 text-ocean-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-800">Upload More Data</h3>
                  <p className="text-sm text-slate-500">Import new bank transactions</p>
                </div>
                <ArrowRight className="w-5 h-5 text-slate-400 ml-auto group-hover:translate-x-1 transition-transform" />
              </div>
            </Link>

            <Link
              to="/transactions"
              className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 hover:border-amber-200 hover:shadow-md transition-all group"
            >
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-amber-50 flex items-center justify-center group-hover:scale-110 transition-transform">
                  <AlertCircle className="w-6 h-6 text-amber-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-800">Review Transactions</h3>
                  <p className="text-sm text-slate-500">
                    {stats?.classification?.unclassified || 0} transactions need categorization
                  </p>
                </div>
                <ArrowRight className="w-5 h-5 text-slate-400 ml-auto group-hover:translate-x-1 transition-transform" />
              </div>
            </Link>
          </div>
        </>
      )}
    </div>
  );
}

export default Dashboard;

