import { useState, useEffect } from 'react';
import { 
  Tags, 
  Plus, 
  Pencil, 
  Trash2, 
  RefreshCw, 
  AlertCircle,
  CheckCircle2,
  X,
  ArrowRight,
  Merge
} from 'lucide-react';
import { categoriesApi } from '../services/api';
import clsx from 'clsx';

// Emoji picker options
const EMOJI_OPTIONS = [
  '🍽️', '🛒', '🚗', '💡', '🎬', '🛍️', '🏥', '🏠', '💅', '📚', 
  '✈️', '📱', '🛡️', '🏦', '🎁', '👨‍👩‍👧‍👦', '🐕', '📦', '💰', '📈',
  '↩️', '➡️', '💵', '🎮', '☕', '🍺', '🎨', '💊', '🔧', '🎯'
];

// Color picker options
const COLOR_OPTIONS = [
  '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#DDA0DD', '#FFB347',
  '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9', '#F8B500', '#E74C3C',
  '#5D6D7E', '#ABB2B9', '#F1948A', '#A569BD', '#DC7633', '#BDC3C7',
  '#27AE60', '#2ECC71', '#1ABC9C', '#3498DB', '#58D68D', '#9B59B6'
];

function Categories() {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  
  // Modal states
  const [showModal, setShowModal] = useState(false);
  const [modalMode, setModalMode] = useState('create'); // create, edit, delete, reassign
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [reassignTarget, setReassignTarget] = useState('');
  
  // Form state
  const [form, setForm] = useState({
    name: '',
    icon: '📦',
    color: '#BDC3C7',
    is_income: false
  });

  useEffect(() => {
    loadCategories();
  }, []);

  const loadCategories = async () => {
    setLoading(true);
    try {
      const response = await categoriesApi.getUsage();
      setCategories(response.data);
    } catch (err) {
      setError('Failed to load categories');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setForm({ name: '', icon: '📦', color: '#BDC3C7', is_income: false });
    setModalMode('create');
    setShowModal(true);
  };

  const handleEdit = (category) => {
    setSelectedCategory(category);
    setForm({
      name: category.name,
      icon: category.icon,
      color: category.color,
      is_income: category.is_income
    });
    setModalMode('edit');
    setShowModal(true);
  };

  const handleDelete = (category) => {
    setSelectedCategory(category);
    setReassignTarget('');
    setModalMode('delete');
    setShowModal(true);
  };

  const handleReassign = (category) => {
    setSelectedCategory(category);
    setReassignTarget('');
    setModalMode('reassign');
    setShowModal(true);
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    
    try {
      if (modalMode === 'create') {
        await categoriesApi.create(form);
        setSuccess('Category created!');
      } else if (modalMode === 'edit') {
        await categoriesApi.update(selectedCategory.id, form);
        setSuccess('Category updated!');
      } else if (modalMode === 'delete') {
        await categoriesApi.delete(selectedCategory.id, reassignTarget || null);
        setSuccess('Category deleted!');
      } else if (modalMode === 'reassign') {
        await categoriesApi.reassign(selectedCategory.id, reassignTarget);
        setSuccess('Transactions reassigned!');
      }
      
      setShowModal(false);
      loadCategories();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Operation failed');
    } finally {
      setLoading(false);
    }
  };

  const expenseCategories = categories.filter(c => !c.is_income);
  const incomeCategories = categories.filter(c => c.is_income);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold text-slate-100 flex items-center gap-3">
            <Tags className="w-8 h-8 text-ocean-400" />
            Categories
          </h1>
          <p className="text-slate-400 mt-1">
            Manage your spending categories
          </p>
        </div>
        
        <div className="flex items-center gap-3">
          <button
            onClick={loadCategories}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition-all"
          >
            <RefreshCw className={clsx('w-4 h-4', loading && 'animate-spin')} />
            Refresh
          </button>
          <button
            onClick={handleCreate}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-ocean-500 to-ocean-600 text-white font-medium hover:shadow-lg hover:shadow-ocean-500/30 transition-all"
          >
            <Plus className="w-4 h-4" />
            Add Category
          </button>
        </div>
      </div>

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

      {/* Expense Categories */}
      <div className="glass rounded-2xl p-6">
        <h2 className="text-xl font-semibold text-slate-100 mb-4">Expense Categories</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {expenseCategories.map(cat => (
            <div
              key={cat.id}
              className="flex items-center gap-4 p-4 rounded-xl bg-slate-800/50 hover:bg-slate-800 transition-all group"
            >
              <div
                className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl"
                style={{ backgroundColor: `${cat.color}20` }}
              >
                {cat.icon}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-slate-100 truncate">{cat.name}</p>
                <p className="text-sm text-slate-400">
                  {cat.transaction_count} transactions • ${Math.abs(cat.total_amount).toLocaleString()}
                </p>
              </div>
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={() => handleReassign(cat)}
                  className="p-2 rounded-lg hover:bg-slate-700 text-slate-400 hover:text-purple-400"
                  title="Reassign transactions"
                >
                  <Merge className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleEdit(cat)}
                  className="p-2 rounded-lg hover:bg-slate-700 text-slate-400 hover:text-ocean-400"
                  title="Edit"
                >
                  <Pencil className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleDelete(cat)}
                  className="p-2 rounded-lg hover:bg-slate-700 text-slate-400 hover:text-coral-400"
                  title="Delete"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Income Categories */}
      <div className="glass rounded-2xl p-6">
        <h2 className="text-xl font-semibold text-slate-100 mb-4">Income Categories</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {incomeCategories.map(cat => (
            <div
              key={cat.id}
              className="flex items-center gap-4 p-4 rounded-xl bg-slate-800/50 hover:bg-slate-800 transition-all group"
            >
              <div
                className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl"
                style={{ backgroundColor: `${cat.color}20` }}
              >
                {cat.icon}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-slate-100 truncate">{cat.name}</p>
                <p className="text-sm text-slate-400">
                  {cat.transaction_count} transactions • ${cat.total_amount.toLocaleString()}
                </p>
              </div>
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={() => handleReassign(cat)}
                  className="p-2 rounded-lg hover:bg-slate-700 text-slate-400 hover:text-purple-400"
                  title="Reassign transactions"
                >
                  <Merge className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleEdit(cat)}
                  className="p-2 rounded-lg hover:bg-slate-700 text-slate-400 hover:text-ocean-400"
                  title="Edit"
                >
                  <Pencil className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleDelete(cat)}
                  className="p-2 rounded-lg hover:bg-slate-700 text-slate-400 hover:text-coral-400"
                  title="Delete"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="glass rounded-2xl p-6 w-full max-w-md mx-4 animate-slide-up">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold text-slate-100">
                {modalMode === 'create' && 'Create Category'}
                {modalMode === 'edit' && 'Edit Category'}
                {modalMode === 'delete' && 'Delete Category'}
                {modalMode === 'reassign' && 'Reassign Transactions'}
              </h2>
              <button
                onClick={() => setShowModal(false)}
                className="p-2 rounded-lg hover:bg-slate-700 text-slate-400"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {(modalMode === 'create' || modalMode === 'edit') && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-slate-400 mb-2">Name</label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="w-full px-4 py-3 rounded-xl bg-slate-800 border border-slate-700 text-slate-100 focus:border-ocean-500"
                    placeholder="Category name"
                  />
                </div>
                
                <div>
                  <label className="block text-sm text-slate-400 mb-2">Icon</label>
                  <div className="flex flex-wrap gap-2">
                    {EMOJI_OPTIONS.map(emoji => (
                      <button
                        key={emoji}
                        onClick={() => setForm({ ...form, icon: emoji })}
                        className={clsx(
                          'w-10 h-10 rounded-lg text-xl flex items-center justify-center transition-all',
                          form.icon === emoji
                            ? 'bg-ocean-500/20 ring-2 ring-ocean-500'
                            : 'bg-slate-800 hover:bg-slate-700'
                        )}
                      >
                        {emoji}
                      </button>
                    ))}
                  </div>
                </div>
                
                <div>
                  <label className="block text-sm text-slate-400 mb-2">Color</label>
                  <div className="flex flex-wrap gap-2">
                    {COLOR_OPTIONS.map(color => (
                      <button
                        key={color}
                        onClick={() => setForm({ ...form, color })}
                        className={clsx(
                          'w-8 h-8 rounded-lg transition-all',
                          form.color === color && 'ring-2 ring-white ring-offset-2 ring-offset-slate-900'
                        )}
                        style={{ backgroundColor: color }}
                      />
                    ))}
                  </div>
                </div>
                
                <div>
                  <label className="block text-sm text-slate-400 mb-2">Type</label>
                  <div className="flex gap-3">
                    <button
                      onClick={() => setForm({ ...form, is_income: false })}
                      className={clsx(
                        'flex-1 py-3 rounded-xl border transition-all',
                        !form.is_income
                          ? 'border-coral-500 bg-coral-500/10 text-coral-400'
                          : 'border-slate-700 text-slate-400 hover:border-slate-600'
                      )}
                    >
                      Expense
                    </button>
                    <button
                      onClick={() => setForm({ ...form, is_income: true })}
                      className={clsx(
                        'flex-1 py-3 rounded-xl border transition-all',
                        form.is_income
                          ? 'border-emerald-500 bg-emerald-500/10 text-emerald-400'
                          : 'border-slate-700 text-slate-400 hover:border-slate-600'
                      )}
                    >
                      Income
                    </button>
                  </div>
                </div>
              </div>
            )}

            {modalMode === 'delete' && (
              <div className="space-y-4">
                <p className="text-slate-300">
                  Are you sure you want to delete <strong>{selectedCategory?.name}</strong>?
                </p>
                {selectedCategory?.transaction_count > 0 && (
                  <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20">
                    <p className="text-amber-400 text-sm mb-3">
                      This category has {selectedCategory.transaction_count} transactions.
                      Choose what to do with them:
                    </p>
                    <select
                      value={reassignTarget}
                      onChange={(e) => setReassignTarget(e.target.value)}
                      className="w-full px-4 py-3 rounded-xl bg-slate-800 border border-slate-700 text-slate-100"
                    >
                      <option value="">Set to Uncategorized</option>
                      {categories
                        .filter(c => c.id !== selectedCategory?.id && c.is_income === selectedCategory?.is_income)
                        .map(c => (
                          <option key={c.id} value={c.id}>
                            Move to: {c.icon} {c.name}
                          </option>
                        ))
                      }
                    </select>
                  </div>
                )}
              </div>
            )}

            {modalMode === 'reassign' && (
              <div className="space-y-4">
                <p className="text-slate-300">
                  Move all transactions from <strong>{selectedCategory?.name}</strong> to another category:
                </p>
                <select
                  value={reassignTarget}
                  onChange={(e) => setReassignTarget(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl bg-slate-800 border border-slate-700 text-slate-100"
                >
                  <option value="">Select target category...</option>
                  {categories
                    .filter(c => c.id !== selectedCategory?.id)
                    .map(c => (
                      <option key={c.id} value={c.id}>
                        {c.icon} {c.name} ({c.transaction_count} existing)
                      </option>
                    ))
                  }
                </select>
                <p className="text-sm text-slate-500">
                  {selectedCategory?.transaction_count} transactions will be moved and marked for review.
                </p>
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center justify-end gap-3 mt-6">
              <button
                onClick={() => setShowModal(false)}
                className="px-4 py-2 rounded-xl border border-slate-700 text-slate-300 hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={loading || (modalMode === 'reassign' && !reassignTarget)}
                className={clsx(
                  'flex items-center gap-2 px-4 py-2 rounded-xl font-medium transition-all disabled:opacity-50',
                  modalMode === 'delete'
                    ? 'bg-coral-500 hover:bg-coral-600 text-white'
                    : 'bg-ocean-500 hover:bg-ocean-600 text-white'
                )}
              >
                {loading && <RefreshCw className="w-4 h-4 animate-spin" />}
                {modalMode === 'create' && 'Create'}
                {modalMode === 'edit' && 'Save'}
                {modalMode === 'delete' && 'Delete'}
                {modalMode === 'reassign' && 'Reassign'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Categories;


