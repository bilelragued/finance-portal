import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Upload as UploadIcon, 
  FileSpreadsheet, 
  CheckCircle2, 
  AlertTriangle,
  X,
  ArrowRight,
  RefreshCw,
  Building2,
  User,
  PiggyBank
} from 'lucide-react';
import { uploadApi, accountsApi } from '../services/api';
import clsx from 'clsx';

function Upload() {
  const navigate = useNavigate();
  const [dragOver, setDragOver] = useState(false);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [step, setStep] = useState('upload'); // upload, preview, confirm, success
  
  // Account creation form
  const [accountForm, setAccountForm] = useState({
    name: '',
    owner: '',
    account_type: 'personal'
  });

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && droppedFile.name.match(/\.xlsx?$/)) {
      handleFile(droppedFile);
    } else {
      setError('Please upload an Excel file (.xlsx or .xls)');
    }
  }, []);

  const handleFileInput = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      handleFile(selectedFile);
    }
  };

  const handleFile = async (selectedFile) => {
    setFile(selectedFile);
    setError(null);
    setLoading(true);

    try {
      const response = await uploadApi.preview(selectedFile);
      setPreview(response.data);
      setStep('preview');
      
      // Pre-fill account form if new account
      if (!response.data.existing_account && response.data.file_info.account_number) {
        setAccountForm(prev => ({
          ...prev,
          name: `Account ${response.data.file_info.account_number}`,
        }));
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to process file');
      setFile(null);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmUpload = async () => {
    if (!preview) return;
    
    setLoading(true);
    setError(null);

    try {
      // Extract file_id from the filename (we embedded it earlier)
      const fileId = preview.file_info.filename.split('|')[0];
      
      let accountId = preview.existing_account?.id;
      let response;
      
      // Create new account if needed
      if (!accountId) {
        const newAccount = {
          account_number: preview.file_info.account_number,
          name: accountForm.name,
          owner: accountForm.owner,
          account_type: accountForm.account_type
        };
        response = await uploadApi.confirm(fileId, null, newAccount);
      } else {
        response = await uploadApi.confirm(fileId, accountId);
      }
      
      setPreview(prev => ({ ...prev, result: response.data }));
      setStep('success');
    } catch (err) {
      console.error('Upload error:', err);
      
      // Handle different error formats
      let errorMessage = 'Failed to import transactions';
      if (err.response?.data?.detail) {
        const detail = err.response.data.detail;
        if (typeof detail === 'string') {
          errorMessage = detail;
        } else if (Array.isArray(detail)) {
          // Pydantic validation errors
          errorMessage = detail.map(e => e.msg || e.message || JSON.stringify(e)).join(', ');
        } else if (typeof detail === 'object') {
          errorMessage = detail.msg || detail.message || JSON.stringify(detail);
        }
      } else if (err.message) {
        errorMessage = err.message;
      }
      
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async () => {
    if (preview) {
      const fileId = preview.file_info.filename.split('|')[0];
      try {
        await uploadApi.cancel(fileId);
      } catch (e) {
        // Ignore
      }
    }
    setFile(null);
    setPreview(null);
    setStep('upload');
    setError(null);
  };

  const formatCurrency = (amount) => {
    if (amount === null || amount === undefined) return '-';
    return new Intl.NumberFormat('en-NZ', {
      style: 'currency',
      currency: 'NZD'
    }).format(amount);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-display font-bold text-slate-100">Upload Transactions</h1>
        <p className="text-slate-400 mt-1">Import your bank transaction files</p>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-coral-500/10 border border-coral-500/20 text-coral-400 animate-fade-in">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-auto hover:text-coral-300">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Step: Upload */}
      {step === 'upload' && (
        <div
          className={clsx(
            'drop-zone rounded-2xl p-12 text-center cursor-pointer transition-all animate-fade-in',
            dragOver && 'drag-over'
          )}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => document.getElementById('file-input').click()}
        >
          <input
            id="file-input"
            type="file"
            accept=".xlsx,.xls"
            className="hidden"
            onChange={handleFileInput}
          />
          
          {loading ? (
            <div className="flex flex-col items-center">
              <RefreshCw className="w-12 h-12 text-ocean-400 animate-spin mb-4" />
              <p className="text-slate-300">Processing file...</p>
            </div>
          ) : (
            <>
              <div className="w-16 h-16 rounded-2xl bg-ocean-500/20 flex items-center justify-center mx-auto mb-6">
                <UploadIcon className="w-8 h-8 text-ocean-400" />
              </div>
              <h2 className="text-xl font-semibold text-slate-100 mb-2">
                Drop your Excel file here
              </h2>
              <p className="text-slate-400 mb-4">
                or click to browse
              </p>
              <p className="text-sm text-slate-500">
                Supports .xlsx and .xls files from your bank export
              </p>
            </>
          )}
        </div>
      )}

      {/* Step: Preview */}
      {step === 'preview' && preview && (
        <div className="space-y-6 animate-fade-in">
          {/* File Info */}
          <div className="glass rounded-2xl p-6">
            <div className="flex items-center gap-4 mb-6">
              <div className="w-12 h-12 rounded-xl bg-emerald-500/20 flex items-center justify-center">
                <FileSpreadsheet className="w-6 h-6 text-emerald-400" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-slate-100">{file?.name}</h3>
                <p className="text-sm text-slate-400">
                  {preview.file_info.total_rows} transactions found
                </p>
              </div>
              <button
                onClick={handleCancel}
                className="p-2 rounded-lg hover:bg-slate-700 text-slate-400"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <p className="text-slate-500">Account Number</p>
                <p className="font-mono text-slate-200">{preview.file_info.account_number || 'Unknown'}</p>
              </div>
              <div>
                <p className="text-slate-500">Date Range</p>
                <p className="text-slate-200">
                  {preview.file_info.date_from} to {preview.file_info.date_to}
                </p>
              </div>
              <div>
                <p className="text-slate-500">New Transactions</p>
                <p className="text-emerald-400 font-semibold">{preview.new_count}</p>
              </div>
              <div>
                <p className="text-slate-500">Duplicates</p>
                <p className="text-amber-400">{preview.duplicate_count}</p>
              </div>
            </div>
          </div>

          {/* Continuity Warning */}
          {preview.continuity_message && (
            <div className="flex items-start gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20">
              <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-amber-400 font-medium">Balance Continuity Notice</p>
                <p className="text-sm text-amber-300/80 mt-1">{preview.continuity_message}</p>
              </div>
            </div>
          )}

          {/* Account Selection/Creation */}
          <div className="glass rounded-2xl p-6">
            <h3 className="font-semibold text-slate-100 mb-4">Account</h3>
            
            {preview.existing_account ? (
              <div className="flex items-center gap-4 p-4 rounded-xl bg-slate-800/50">
                <div className="w-10 h-10 rounded-xl bg-ocean-500/20 flex items-center justify-center">
                  <CheckCircle2 className="w-5 h-5 text-ocean-400" />
                </div>
                <div>
                  <p className="font-medium text-slate-100">{preview.existing_account.name}</p>
                  <p className="text-sm text-slate-400">
                    {preview.existing_account.account_number} • {preview.existing_account.owner}
                  </p>
                </div>
                <span className="badge badge-success ml-auto">Existing Account</span>
              </div>
            ) : (
              <div className="space-y-4">
                <p className="text-sm text-amber-400 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4" />
                  New account detected. Please provide account details:
                </p>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-slate-400 mb-2">Account Name</label>
                    <input
                      type="text"
                      value={accountForm.name}
                      onChange={(e) => setAccountForm(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="e.g., Main Account"
                      className="w-full px-4 py-3 rounded-xl bg-slate-800 border border-slate-700 text-slate-100 placeholder-slate-500 focus:border-ocean-500 focus:ring-1 focus:ring-ocean-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-slate-400 mb-2">Owner</label>
                    <input
                      type="text"
                      value={accountForm.owner}
                      onChange={(e) => setAccountForm(prev => ({ ...prev, owner: e.target.value }))}
                      placeholder="e.g., John"
                      className="w-full px-4 py-3 rounded-xl bg-slate-800 border border-slate-700 text-slate-100 placeholder-slate-500 focus:border-ocean-500 focus:ring-1 focus:ring-ocean-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm text-slate-400 mb-2">Account Type</label>
                  <div className="grid grid-cols-3 gap-3">
                    <button
                      onClick={() => setAccountForm(prev => ({ ...prev, account_type: 'personal' }))}
                      className={clsx(
                        'flex items-center gap-3 p-4 rounded-xl border transition-all',
                        accountForm.account_type === 'personal'
                          ? 'border-ocean-500 bg-ocean-500/10'
                          : 'border-slate-700 hover:border-slate-600'
                      )}
                    >
                      <User className={clsx('w-5 h-5', accountForm.account_type === 'personal' ? 'text-ocean-400' : 'text-slate-400')} />
                      <span className={clsx('font-medium', accountForm.account_type === 'personal' ? 'text-slate-100' : 'text-slate-400')}>Personal</span>
                    </button>
                    <button
                      onClick={() => setAccountForm(prev => ({ ...prev, account_type: 'business' }))}
                      className={clsx(
                        'flex items-center gap-3 p-4 rounded-xl border transition-all',
                        accountForm.account_type === 'business'
                          ? 'border-amber-500 bg-amber-500/10'
                          : 'border-slate-700 hover:border-slate-600'
                      )}
                    >
                      <Building2 className={clsx('w-5 h-5', accountForm.account_type === 'business' ? 'text-amber-400' : 'text-slate-400')} />
                      <span className={clsx('font-medium', accountForm.account_type === 'business' ? 'text-slate-100' : 'text-slate-400')}>Business</span>
                    </button>
                    <button
                      onClick={() => setAccountForm(prev => ({ ...prev, account_type: 'savings' }))}
                      className={clsx(
                        'flex items-center gap-3 p-4 rounded-xl border transition-all',
                        accountForm.account_type === 'savings'
                          ? 'border-emerald-500 bg-emerald-500/10'
                          : 'border-slate-700 hover:border-slate-600'
                      )}
                    >
                      <PiggyBank className={clsx('w-5 h-5', accountForm.account_type === 'savings' ? 'text-emerald-400' : 'text-slate-400')} />
                      <span className={clsx('font-medium', accountForm.account_type === 'savings' ? 'text-slate-100' : 'text-slate-400')}>Savings</span>
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Sample Transactions */}
          <div className="glass rounded-2xl p-6">
            <h3 className="font-semibold text-slate-100 mb-4">Sample Transactions</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-slate-400 border-b border-slate-700">
                    <th className="pb-3 font-medium">Date</th>
                    <th className="pb-3 font-medium">Type</th>
                    <th className="pb-3 font-medium">Details</th>
                    <th className="pb-3 font-medium text-right">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.sample_transactions.map((trans, idx) => (
                    <tr key={idx} className="border-b border-slate-800 table-row-hover">
                      <td className="py-3 text-slate-300">{trans.date}</td>
                      <td className="py-3 text-slate-400">{trans.type}</td>
                      <td className="py-3 text-slate-300">{trans.details}</td>
                      <td className={clsx(
                        'py-3 text-right font-mono',
                        trans.amount < 0 ? 'text-coral-400' : 'text-emerald-400'
                      )}>
                        {formatCurrency(trans.amount)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-4">
            <button
              onClick={handleCancel}
              className="px-6 py-3 rounded-xl border border-slate-700 text-slate-300 hover:bg-slate-800 transition-all"
            >
              Cancel
            </button>
            <button
              onClick={handleConfirmUpload}
              disabled={loading || (!preview.existing_account && (!accountForm.name || !accountForm.owner))}
              className="flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-ocean-500 to-ocean-600 text-white font-medium hover:shadow-lg hover:shadow-ocean-500/30 transition-all btn-glow disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Importing...
                </>
              ) : (
                <>
                  Import {preview.new_count} Transactions
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Step: Success */}
      {step === 'success' && preview?.result && (
        <div className="glass rounded-2xl p-12 text-center animate-fade-in">
          <div className="w-20 h-20 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto mb-6">
            <CheckCircle2 className="w-10 h-10 text-emerald-400" />
          </div>
          <h2 className="text-2xl font-display font-bold text-slate-100 mb-2">
            Import Successful!
          </h2>
          <p className="text-slate-400 mb-6">
            {preview.result.message}
          </p>
          
          <div className="flex items-center justify-center gap-4">
            <button
              onClick={() => {
                setFile(null);
                setPreview(null);
                setStep('upload');
              }}
              className="px-6 py-3 rounded-xl border border-slate-700 text-slate-300 hover:bg-slate-800 transition-all"
            >
              Upload More
            </button>
            <button
              onClick={() => navigate('/transactions')}
              className="flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-ocean-500 to-ocean-600 text-white font-medium hover:shadow-lg hover:shadow-ocean-500/30 transition-all btn-glow"
            >
              View Transactions
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default Upload;

