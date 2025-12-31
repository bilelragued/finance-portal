import { useState, useEffect } from 'react';
import { 
  Plus, 
  Edit2, 
  Trash2, 
  User, 
  Building2, 
  PiggyBank,
  RefreshCw,
  X,
  AlertCircle,
  CheckCircle2
} from 'lucide-react';
import { accountsApi } from '../services/api';
import clsx from 'clsx';

function Accounts() {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  
  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [editingAccount, setEditingAccount] = useState(null);
  const [formData, setFormData] = useState({
    account_number: '',
    name: '',
    owner: '',
    account_type: 'personal'
  });

  useEffect(() => {
    loadAccounts();
  }, []);

  const loadAccounts = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await accountsApi.list();
      setAccounts(response.data);
    } catch (err) {
      setError('Failed to load accounts');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenModal = (account = null) => {
    if (account) {
      setEditingAccount(account);
      setFormData({
        account_number: account.account_number,
        name: account.name,
        owner: account.owner,
        account_type: account.account_type
      });
    } else {
      setEditingAccount(null);
      setFormData({
        account_number: '',
        name: '',
        owner: '',
        account_type: 'personal'
      });
    }
    setShowModal(true);
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setEditingAccount(null);
    setFormData({
      account_number: '',
      name: '',
      owner: '',
      account_type: 'personal'
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    try {
      if (editingAccount) {
        await accountsApi.update(editingAccount.id, {
          name: formData.name,
          owner: formData.owner,
          account_type: formData.account_type
        });
        setSuccess('Account updated successfully');
      } else {
        await accountsApi.create(formData);
        setSuccess('Account created successfully');
      }
      handleCloseModal();
      loadAccounts();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save account');
    }
  };

  const handleDelete = async (account) => {
    if (!confirm(`Are you sure you want to delete "${account.name}"?`)) {
      return;
    }

    try {
      await accountsApi.delete(account.id);
      setSuccess('Account deleted successfully');
      loadAccounts();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete account');
    }
  };

  const getAccountIcon = (type) => {
    switch (type) {
      case 'personal':
        return <User className="w-5 h-5" />;
      case 'business':
        return <Building2 className="w-5 h-5" />;
      case 'savings':
        return <PiggyBank className="w-5 h-5" />;
      default:
        return <User className="w-5 h-5" />;
    }
  };

  const getAccountColor = (type) => {
    switch (type) {
      case 'personal':
        return 'bg-ocean-500/20 text-ocean-400';
      case 'business':
        return 'bg-amber-500/20 text-amber-400';
      case 'savings':
        return 'bg-emerald-500/20 text-emerald-400';
      default:
        return 'bg-slate-500/20 text-slate-400';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold text-slate-100">Accounts</h1>
          <p className="text-slate-400 mt-1">Manage your bank accounts</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={loadAccounts}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition-all disabled:opacity-50"
          >
            <RefreshCw className={clsx('w-4 h-4', loading && 'animate-spin')} />
            Refresh
          </button>
          <button
            onClick={() => handleOpenModal()}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-ocean-500 to-ocean-600 text-white font-medium hover:shadow-lg hover:shadow-ocean-500/30 transition-all btn-glow"
          >
            <Plus className="w-4 h-4" />
            Add Account
          </button>
        </div>
      </div>

      {/* Success Message */}
      {success && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 animate-fade-in">
          <CheckCircle2 className="w-5 h-5" />
          {success}
          <button onClick={() => setSuccess(null)} className="ml-auto hover:text-emerald-300">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-coral-500/10 border border-coral-500/20 text-coral-400 animate-fade-in">
          <AlertCircle className="w-5 h-5" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto hover:text-coral-300">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Accounts Grid */}
      {loading ? (
        <div className="flex items-center justify-center p-12">
          <RefreshCw className="w-8 h-8 text-ocean-400 animate-spin" />
        </div>
      ) : accounts.length === 0 ? (
        <div className="glass rounded-2xl p-12 text-center animate-fade-in">
          <div className="w-16 h-16 rounded-2xl bg-slate-800 flex items-center justify-center mx-auto mb-4">
            <Building2 className="w-8 h-8 text-slate-500" />
          </div>
          <h2 className="text-xl font-semibold text-slate-100 mb-2">No accounts yet</h2>
          <p className="text-slate-400 mb-6">
            Add your first account or upload a transaction file to get started.
          </p>
          <button
            onClick={() => handleOpenModal()}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-ocean-500 to-ocean-600 text-white font-medium hover:shadow-lg hover:shadow-ocean-500/30 transition-all btn-glow"
          >
            <Plus className="w-4 h-4" />
            Add Account
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {accounts.map((account, idx) => (
            <div
              key={account.id}
              className="glass rounded-2xl p-6 animate-slide-up hover:bg-slate-800/50 transition-all"
              style={{ animationDelay: `${idx * 100}ms` }}
            >
              <div className="flex items-start justify-between mb-4">
                <div className={clsx(
                  'w-12 h-12 rounded-xl flex items-center justify-center',
                  getAccountColor(account.account_type)
                )}>
                  {getAccountIcon(account.account_type)}
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => handleOpenModal(account)}
                    className="p-2 rounded-lg hover:bg-slate-700 text-slate-400 hover:text-slate-200 transition-all"
                  >
                    <Edit2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(account)}
                    className="p-2 rounded-lg hover:bg-coral-500/20 text-slate-400 hover:text-coral-400 transition-all"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <h3 className="text-lg font-semibold text-slate-100 mb-1">{account.name}</h3>
              <p className="text-sm font-mono text-slate-400 mb-3">{account.account_number}</p>
              
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-500">Owner</span>
                <span className="text-slate-300">{account.owner}</span>
              </div>
              <div className="flex items-center justify-between text-sm mt-1">
                <span className="text-slate-500">Type</span>
                <span className={clsx(
                  'capitalize px-2 py-0.5 rounded-full text-xs',
                  getAccountColor(account.account_type)
                )}>
                  {account.account_type}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm mt-1">
                <span className="text-slate-500">Transactions</span>
                <span className="text-slate-300">{account.transaction_count || 0}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in">
          <div className="glass rounded-2xl p-6 w-full max-w-md mx-4 animate-slide-up">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-display font-semibold text-slate-100">
                {editingAccount ? 'Edit Account' : 'Add Account'}
              </h2>
              <button
                onClick={handleCloseModal}
                className="p-2 rounded-lg hover:bg-slate-700 text-slate-400"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-2">Account Number</label>
                <input
                  type="text"
                  value={formData.account_number}
                  onChange={(e) => setFormData(prev => ({ ...prev, account_number: e.target.value }))}
                  disabled={!!editingAccount}
                  placeholder="e.g., 01-0183-0950462-00"
                  className="w-full px-4 py-3 rounded-xl bg-slate-800 border border-slate-700 text-slate-100 placeholder-slate-500 focus:border-ocean-500 focus:ring-1 focus:ring-ocean-500 disabled:opacity-50"
                  required
                />
              </div>

              <div>
                <label className="block text-sm text-slate-400 mb-2">Account Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="e.g., Main Account"
                  className="w-full px-4 py-3 rounded-xl bg-slate-800 border border-slate-700 text-slate-100 placeholder-slate-500 focus:border-ocean-500 focus:ring-1 focus:ring-ocean-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm text-slate-400 mb-2">Owner</label>
                <input
                  type="text"
                  value={formData.owner}
                  onChange={(e) => setFormData(prev => ({ ...prev, owner: e.target.value }))}
                  placeholder="e.g., John"
                  className="w-full px-4 py-3 rounded-xl bg-slate-800 border border-slate-700 text-slate-100 placeholder-slate-500 focus:border-ocean-500 focus:ring-1 focus:ring-ocean-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm text-slate-400 mb-2">Account Type</label>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { value: 'personal', label: 'Personal', icon: User },
                    { value: 'business', label: 'Business', icon: Building2 },
                    { value: 'savings', label: 'Savings', icon: PiggyBank },
                  ].map(({ value, label, icon: Icon }) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setFormData(prev => ({ ...prev, account_type: value }))}
                      className={clsx(
                        'flex flex-col items-center gap-2 p-3 rounded-xl border transition-all',
                        formData.account_type === value
                          ? 'border-ocean-500 bg-ocean-500/10'
                          : 'border-slate-700 hover:border-slate-600'
                      )}
                    >
                      <Icon className={clsx(
                        'w-5 h-5',
                        formData.account_type === value ? 'text-ocean-400' : 'text-slate-400'
                      )} />
                      <span className={clsx(
                        'text-sm font-medium',
                        formData.account_type === value ? 'text-slate-100' : 'text-slate-400'
                      )}>
                        {label}
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-3 pt-4">
                <button
                  type="button"
                  onClick={handleCloseModal}
                  className="flex-1 px-4 py-3 rounded-xl border border-slate-700 text-slate-300 hover:bg-slate-800 transition-all"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 px-4 py-3 rounded-xl bg-gradient-to-r from-ocean-500 to-ocean-600 text-white font-medium hover:shadow-lg hover:shadow-ocean-500/30 transition-all btn-glow"
                >
                  {editingAccount ? 'Update' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default Accounts;


