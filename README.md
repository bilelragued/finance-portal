# Finance Portal

A personal finance management application with intelligent transaction categorization, spending analysis, and budget tracking.

## ✨ Features

- 📊 **Dashboard** - Overview of your financial health
- 📤 **Excel Upload** - Import bank transaction files with duplicate detection
- 💳 **Transaction Management** - View, filter, and classify transactions
- 🏦 **Account Management** - Manage multiple bank accounts (personal, business, savings)
- 🤖 **Smart Categorization** - AI-powered automatic categorization with learning
- 🧠 **Local ML Model** - scikit-learn classifier trained on your data
- 🔐 **Secure** - HTTP Basic Authentication
- ☁️ **Cloud Deployed** - Runs 100% free on Vercel + Supabase

## 🚀 Deploy to Production (100% Free)

**Quick Start**: See [QUICK_START.md](../QUICK_START.md) for 20-minute deployment guide

**Detailed Guide**: See [DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md) for full instructions

**Tech Stack**:
- **Frontend**: React 18 + Tailwind CSS + Vite → **Vercel (Free)**
- **Backend**: Python 3.11 + FastAPI + Mangum → **Vercel Serverless (Free)**
- **Database**: PostgreSQL → **Supabase (Free 500MB)**
- **Storage**: File storage → **Supabase Storage (Free 1GB)**
- **AI**: Anthropic Claude API + Local ML (scikit-learn)

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+

### Backend Setup

```bash
cd finance-portal/backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

### Frontend Setup

```bash
cd finance-portal/frontend

# Install dependencies
npm install

# Run the dev server
npm run dev
```

The app will be available at `http://localhost:5173`

## Project Structure

```
finance-portal/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI entry point
│   │   ├── database.py       # Database configuration
│   │   ├── models.py         # SQLAlchemy models
│   │   ├── schemas.py        # Pydantic schemas
│   │   ├── routers/          # API endpoints
│   │   └── services/         # Business logic
│   ├── data/                 # SQLite database
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/       # Reusable components
│   │   ├── pages/           # Page components
│   │   ├── services/        # API client
│   │   └── App.jsx          # Main app
│   └── package.json
├── uploads/                  # Temporary upload storage
├── CONTEXT.md               # Development context
└── README.md
```

## API Endpoints

### Accounts
- `GET /api/accounts/` - List all accounts
- `POST /api/accounts/` - Create account
- `GET /api/accounts/{id}` - Get account details
- `PUT /api/accounts/{id}` - Update account
- `DELETE /api/accounts/{id}` - Delete account

### Transactions
- `GET /api/transactions/` - List transactions (with filters)
- `GET /api/transactions/{id}` - Get transaction
- `PUT /api/transactions/{id}` - Update classification/category
- `GET /api/transactions/stats/summary` - Get statistics

### Upload
- `POST /api/upload/preview` - Upload file and get preview
- `POST /api/upload/confirm` - Confirm and import transactions
- `DELETE /api/upload/cancel/{file_id}` - Cancel upload
- `GET /api/upload/history` - Get import history

### Categories
- `GET /api/categories/` - List categories
- `POST /api/categories/` - Create category
- `POST /api/categories/seed` - Seed default categories

## Development

See `CONTEXT.md` for detailed development progress and decisions.

## License

Private - Personal Use Only


