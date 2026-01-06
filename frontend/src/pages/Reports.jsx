import { useState, useEffect } from 'react';
import {
  RefreshCw,
  AlertCircle,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Calendar
} from 'lucide-react';
import {
  PieChart, Pie, Cell,
  BarChart, Bar,
  LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';
import { format, subMonths, subWeeks, startOfMonth, endOfMonth } from 'date-fns';
import clsx from 'clsx';
import { reportsApi, accountsApi } from '../services/api';

// Chart color palette
const CHART_COLORS = [
  '#0ea5e9', // ocean
  '#10b981', // emerald
  '#f43f5e', // coral
  '#f59e0b', // amber
  '#8b5cf6', // violet
  '#ec4899', // pink
  '#06b6d4', // cyan
  '#84cc16', // lime
  '#f97316', // orange
  '#6366f1', // indigo
];

function Reports() {
  const [accounts, setAccounts] = useState([]);
  const [selectedAccountId, setSelectedAccountId] = useState('');
  const [granularity, setGranularity] = useState('monthly');
  const [dateRange, setDateRange] = useState({
    from: format(subMonths(new Date(), 11), 'yyyy-MM-dd'),
    to: format(new Date(), 'yyyy-MM-dd')
  });
  const [showCustomDates, setShowCustomDates] = useState(false);

  const [summary, setSummary] = useState(null);
  const [categoryData, setCategoryData] = useState([]);
  const [incomeExpenseData, setIncomeExpenseData] = useState([]);
  const [trendData, setTrendData] = useState([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadAccounts();
  }, []);

  useEffect(() => {
    loadReports();
  }, [selectedAccountId, granularity, dateRange]);

  const loadAccounts = async () => {
    try {
      const res = await accountsApi.list();
      setAccounts(res.data);
    } catch (err) {
      console.error('Failed to load accounts:', err);
    }
  };

  const loadReports = async () => {
    setLoading(true);
    setError(null);

    const params = {
      date_from: dateRange.from,
      date_to: dateRange.to,
      granularity
    };
    if (selectedAccountId) {
      params.account_id = selectedAccountId;
    }

    try {
      const [summaryRes, categoryRes, incomeExpenseRes, trendRes] = await Promise.all([
        reportsApi.getSummary(params),
        reportsApi.getSpendingByCategory(params),
        reportsApi.getIncomeVsExpenses(params),
        reportsApi.getSpendingTrends(params)
      ]);

      setSummary(summaryRes.data);
      setCategoryData(categoryRes.data);
      setIncomeExpenseData(incomeExpenseRes.data);
      setTrendData(trendRes.data);
    } catch (err) {
      setError('Failed to load reports data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handlePeriodChange = (period) => {
    const now = new Date();
    setShowCustomDates(period === 'custom');

    if (period === 'weekly') {
      setGranularity('weekly');
      setDateRange({
        from: format(subWeeks(now, 12), 'yyyy-MM-dd'),
        to: format(now, 'yyyy-MM-dd')
      });
    } else if (period === 'monthly') {
      setGranularity('monthly');
      setDateRange({
        from: format(subMonths(now, 11), 'yyyy-MM-dd'),
        to: format(now, 'yyyy-MM-dd')
      });
    }
    // For custom, keep current dates and let user modify
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-NZ', {
      style: 'currency',
      currency: 'NZD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(Math.abs(amount));
  };

  const formatCurrencyShort = (amount) => {
    const absAmount = Math.abs(amount);
    if (absAmount >= 1000) {
      return `$${(absAmount / 1000).toFixed(1)}k`;
    }
    return `$${absAmount.toFixed(0)}`;
  };

  // Custom tooltip styles
  const tooltipStyle = {
    backgroundColor: 'rgba(30, 41, 59, 0.95)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: '12px',
    padding: '12px'
  };

  if (loading && !summary) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-ocean-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold text-slate-100">Reports</h1>
          <p className="text-slate-400 mt-1">Visualize your spending patterns and trends</p>
        </div>
        <button
          onClick={loadReports}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition-all disabled:opacity-50"
        >
          <RefreshCw className={clsx("w-4 h-4", loading && "animate-spin")} />
          Refresh
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-coral-500/10 border border-coral-500/20 text-coral-400">
          <AlertCircle className="w-5 h-5" />
          {error}
        </div>
      )}

      {/* Filters */}
      <div className="glass rounded-2xl p-4">
        <div className="flex flex-wrap items-center gap-4">
          {/* Period Toggle */}
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-slate-400" />
            <div className="flex rounded-xl bg-slate-800 p-1">
              {['monthly', 'weekly', 'custom'].map((period) => (
                <button
                  key={period}
                  onClick={() => handlePeriodChange(period)}
                  className={clsx(
                    'px-4 py-2 rounded-lg text-sm font-medium transition-all',
                    (period === granularity && !showCustomDates) || (period === 'custom' && showCustomDates)
                      ? 'bg-ocean-500 text-white'
                      : 'text-slate-400 hover:text-slate-300'
                  )}
                >
                  {period.charAt(0).toUpperCase() + period.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Account Filter */}
          <select
            value={selectedAccountId}
            onChange={(e) => setSelectedAccountId(e.target.value)}
            className="px-4 py-2.5 rounded-xl bg-slate-800 border border-slate-700 text-slate-100 focus:border-ocean-500 focus:outline-none"
          >
            <option value="">All Accounts</option>
            {accounts.map(acc => (
              <option key={acc.id} value={acc.id}>{acc.name}</option>
            ))}
          </select>

          {/* Custom Date Range */}
          {showCustomDates && (
            <div className="flex items-center gap-3">
              <div>
                <label className="block text-xs text-slate-500 mb-1">From</label>
                <input
                  type="date"
                  value={dateRange.from}
                  onChange={(e) => setDateRange(prev => ({ ...prev, from: e.target.value }))}
                  className="px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-slate-100 focus:border-ocean-500 focus:outline-none text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">To</label>
                <input
                  type="date"
                  value={dateRange.to}
                  onChange={(e) => setDateRange(prev => ({ ...prev, to: e.target.value }))}
                  className="px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-slate-100 focus:border-ocean-500 focus:outline-none text-sm"
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Summary Stats */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="glass rounded-xl p-4 animate-fade-in">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center">
                <TrendingUp className="w-5 h-5 text-emerald-400" />
              </div>
              <div>
                <p className="text-sm text-slate-400">Total Income</p>
                <p className="text-xl font-bold text-emerald-400">{formatCurrency(summary.total_income)}</p>
              </div>
            </div>
          </div>

          <div className="glass rounded-xl p-4 animate-fade-in" style={{ animationDelay: '50ms' }}>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-coral-500/20 flex items-center justify-center">
                <TrendingDown className="w-5 h-5 text-coral-400" />
              </div>
              <div>
                <p className="text-sm text-slate-400">Total Expenses</p>
                <p className="text-xl font-bold text-coral-400">{formatCurrency(summary.total_expenses)}</p>
              </div>
            </div>
          </div>

          <div className="glass rounded-xl p-4 animate-fade-in" style={{ animationDelay: '100ms' }}>
            <div className="flex items-center gap-3">
              <div className={clsx(
                "w-10 h-10 rounded-lg flex items-center justify-center",
                summary.net_cashflow >= 0 ? "bg-emerald-500/20" : "bg-coral-500/20"
              )}>
                <DollarSign className={clsx(
                  "w-5 h-5",
                  summary.net_cashflow >= 0 ? "text-emerald-400" : "text-coral-400"
                )} />
              </div>
              <div>
                <p className="text-sm text-slate-400">Net Cashflow</p>
                <p className={clsx(
                  "text-xl font-bold",
                  summary.net_cashflow >= 0 ? "text-emerald-400" : "text-coral-400"
                )}>
                  {summary.net_cashflow >= 0 ? '+' : '-'}{formatCurrency(summary.net_cashflow)}
                </p>
              </div>
            </div>
          </div>

          <div className="glass rounded-xl p-4 animate-fade-in" style={{ animationDelay: '150ms' }}>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-ocean-500/20 flex items-center justify-center">
                <Calendar className="w-5 h-5 text-ocean-400" />
              </div>
              <div>
                <p className="text-sm text-slate-400">Transactions</p>
                <p className="text-xl font-bold text-slate-100">{summary.total_transactions}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Spending by Category - Donut Chart */}
        <div className="glass rounded-2xl p-6 animate-slide-up">
          <h2 className="text-lg font-display font-semibold text-slate-100 mb-4">
            Spending by Category
          </h2>
          {categoryData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={categoryData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={2}
                  dataKey="total_amount"
                  nameKey="category_name"
                >
                  {categoryData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={entry.color || CHART_COLORS[index % CHART_COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(value) => formatCurrency(value)}
                  labelStyle={{ color: '#f1f5f9' }}
                />
                <Legend
                  wrapperStyle={{ color: '#94a3b8' }}
                  formatter={(value) => <span className="text-slate-300 text-sm">{value}</span>}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-64 text-slate-500">
              No spending data for this period
            </div>
          )}
        </div>

        {/* Income vs Expenses - Bar Chart */}
        <div className="glass rounded-2xl p-6 animate-slide-up" style={{ animationDelay: '100ms' }}>
          <h2 className="text-lg font-display font-semibold text-slate-100 mb-4">
            Income vs Expenses
          </h2>
          {incomeExpenseData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={incomeExpenseData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis
                  dataKey="period_label"
                  stroke="#94a3b8"
                  tick={{ fill: '#94a3b8', fontSize: 12 }}
                  angle={-45}
                  textAnchor="end"
                  height={60}
                />
                <YAxis
                  stroke="#94a3b8"
                  tick={{ fill: '#94a3b8', fontSize: 12 }}
                  tickFormatter={formatCurrencyShort}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(value) => formatCurrency(value)}
                  labelStyle={{ color: '#f1f5f9' }}
                />
                <Legend
                  wrapperStyle={{ color: '#94a3b8' }}
                  formatter={(value) => <span className="text-slate-300 text-sm">{value}</span>}
                />
                <Bar dataKey="income" name="Income" fill="#10b981" radius={[4, 4, 0, 0]} />
                <Bar dataKey="expenses" name="Expenses" fill="#f43f5e" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-64 text-slate-500">
              No data for this period
            </div>
          )}
        </div>
      </div>

      {/* Spending Trends - Full Width Line Chart */}
      <div className="glass rounded-2xl p-6 animate-slide-up" style={{ animationDelay: '200ms' }}>
        <h2 className="text-lg font-display font-semibold text-slate-100 mb-4">
          Spending Trends
        </h2>
        {trendData.length > 0 ? (
          <ResponsiveContainer width="100%" height={350}>
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis
                dataKey="period_label"
                stroke="#94a3b8"
                tick={{ fill: '#94a3b8', fontSize: 12 }}
              />
              <YAxis
                stroke="#94a3b8"
                tick={{ fill: '#94a3b8', fontSize: 12 }}
                tickFormatter={formatCurrencyShort}
              />
              <Tooltip
                contentStyle={tooltipStyle}
                formatter={(value) => formatCurrency(value)}
                labelStyle={{ color: '#f1f5f9' }}
              />
              <Legend
                wrapperStyle={{ color: '#94a3b8' }}
                formatter={(value) => <span className="text-slate-300 text-sm">{value}</span>}
              />
              <Line
                type="monotone"
                dataKey="amount"
                name="Spending"
                stroke="#0ea5e9"
                strokeWidth={3}
                dot={{ fill: '#0ea5e9', strokeWidth: 2, r: 4 }}
                activeDot={{ r: 6, fill: '#0ea5e9' }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex items-center justify-center h-64 text-slate-500">
            No spending data for this period
          </div>
        )}
      </div>

      {/* Top Categories Table */}
      {categoryData.length > 0 && (
        <div className="glass rounded-2xl p-6 animate-slide-up" style={{ animationDelay: '300ms' }}>
          <h2 className="text-lg font-display font-semibold text-slate-100 mb-4">
            Top Spending Categories
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-slate-400 text-sm border-b border-slate-700/50">
                  <th className="pb-3 font-medium">Category</th>
                  <th className="pb-3 font-medium text-right">Transactions</th>
                  <th className="pb-3 font-medium text-right">Amount</th>
                  <th className="pb-3 font-medium text-right">% of Total</th>
                </tr>
              </thead>
              <tbody>
                {categoryData.slice(0, 10).map((cat, index) => {
                  const totalSpending = categoryData.reduce((sum, c) => sum + c.total_amount, 0);
                  const percentage = totalSpending > 0 ? (cat.total_amount / totalSpending * 100) : 0;

                  return (
                    <tr
                      key={cat.category_id || 'uncategorized'}
                      className="border-b border-slate-700/30 hover:bg-slate-800/50 transition-colors"
                    >
                      <td className="py-3">
                        <div className="flex items-center gap-3">
                          <div
                            className="w-3 h-3 rounded-full"
                            style={{ backgroundColor: cat.color || CHART_COLORS[index % CHART_COLORS.length] }}
                          />
                          <span className="text-slate-100">{cat.category_name}</span>
                        </div>
                      </td>
                      <td className="py-3 text-right text-slate-400">
                        {cat.transaction_count}
                      </td>
                      <td className="py-3 text-right text-coral-400 font-medium">
                        {formatCurrency(cat.total_amount)}
                      </td>
                      <td className="py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <div className="w-16 h-2 bg-slate-700 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${percentage}%`,
                                backgroundColor: cat.color || CHART_COLORS[index % CHART_COLORS.length]
                              }}
                            />
                          </div>
                          <span className="text-slate-400 text-sm w-12 text-right">
                            {percentage.toFixed(1)}%
                          </span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default Reports;
