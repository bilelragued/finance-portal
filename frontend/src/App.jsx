import { Routes, Route, NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Upload,
  Receipt,
  Wallet,
  Settings,
  TrendingUp,
  Brain,
  BookOpen,
  Tags,
  BarChart3
} from 'lucide-react';
import clsx from 'clsx';

// Pages
import Dashboard from './pages/Dashboard';
import UploadPage from './pages/Upload';
import TransactionsPage from './pages/Transactions';
import AccountsPage from './pages/Accounts';
import ReviewPage from './pages/Review';
import RulesPage from './pages/Rules';
import CategoriesPage from './pages/Categories';
import ReportsPage from './pages/Reports';

function App() {
  const location = useLocation();

  const navItems = [
    { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/upload', icon: Upload, label: 'Upload' },
    { path: '/review', icon: Brain, label: 'Smart Review' },
    { path: '/transactions', icon: Receipt, label: 'Transactions' },
    { path: '/reports', icon: BarChart3, label: 'Reports' },
    { path: '/accounts', icon: Wallet, label: 'Accounts' },
    { path: '/categories', icon: Tags, label: 'Categories' },
    { path: '/rules', icon: BookOpen, label: 'Learned Rules' },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-gray-50 to-slate-100 text-slate-800">
      {/* Sidebar */}
      <aside className="fixed left-0 top-0 h-full w-64 bg-white border-r border-slate-200 shadow-sm z-50">
        {/* Logo */}
        <div className="p-6 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-ocean-500 to-ocean-700 flex items-center justify-center shadow-lg shadow-ocean-500/20">
              <TrendingUp className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-display font-bold text-lg gradient-text">Finance Portal</h1>
              <p className="text-xs text-slate-400">Personal Accounts</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="p-4 space-y-1">
          {navItems.map(({ path, icon: Icon, label }) => {
            const isActive = location.pathname === path ||
              (path !== '/' && location.pathname.startsWith(path));

            return (
              <NavLink
                key={path}
                to={path}
                className={clsx(
                  'flex items-center gap-3 px-4 py-3 rounded-xl font-medium transition-all duration-200',
                  isActive
                    ? 'bg-ocean-50 text-ocean-700 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
                )}
              >
                <Icon className={clsx('w-5 h-5', isActive && 'text-ocean-600')} />
                <span>{label}</span>
                {isActive && (
                  <div className="ml-auto w-1.5 h-1.5 rounded-full bg-ocean-500" />
                )}
              </NavLink>
            );
          })}
        </nav>

        {/* Bottom section */}
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-slate-100">
          <button className="flex items-center gap-3 px-4 py-3 w-full rounded-xl text-slate-500 hover:text-slate-700 hover:bg-slate-50 transition-all">
            <Settings className="w-5 h-5" />
            <span>Settings</span>
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="ml-64 min-h-screen">
        <div className="p-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/review" element={<ReviewPage />} />
            <Route path="/transactions" element={<TransactionsPage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="/accounts" element={<AccountsPage />} />
            <Route path="/categories" element={<CategoriesPage />} />
            <Route path="/rules" element={<RulesPage />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}

export default App;

