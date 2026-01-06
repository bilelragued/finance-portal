"""Account management endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from typing import List

from app.database import get_db
from app.models import Account, Transaction
from app.schemas import AccountCreate, AccountUpdate, AccountResponse, AccountSummary

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("/", response_model=List[AccountResponse])
def list_accounts(db: Session = Depends(get_db)):
    """List all accounts with transaction counts - optimized single query."""
    # Single query with LEFT JOIN and GROUP BY to get all accounts with counts
    accounts_with_counts = db.query(
        Account,
        func.count(Transaction.id).label('transaction_count')
    ).outerjoin(
        Transaction, Account.id == Transaction.account_id
    ).group_by(Account.id).all()

    return [
        AccountResponse(
            id=account.id,
            account_number=account.account_number,
            name=account.name,
            owner=account.owner,
            account_type=account.account_type.value,
            created_at=account.created_at,
            updated_at=account.updated_at,
            transaction_count=trans_count
        )
        for account, trans_count in accounts_with_counts
    ]


@router.post("/", response_model=AccountResponse)
def create_account(account: AccountCreate, db: Session = Depends(get_db)):
    """Create a new account."""
    # Check if account number already exists
    existing = db.query(Account).filter(
        Account.account_number == account.account_number
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Account with number {account.account_number} already exists"
        )
    
    db_account = Account(
        account_number=account.account_number,
        name=account.name,
        owner=account.owner,
        account_type=account.account_type
    )
    
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    
    return AccountResponse(
        id=db_account.id,
        account_number=db_account.account_number,
        name=db_account.name,
        owner=db_account.owner,
        account_type=db_account.account_type.value,
        created_at=db_account.created_at,
        updated_at=db_account.updated_at,
        transaction_count=0
    )


@router.get("/{account_id}", response_model=AccountResponse)
def get_account(account_id: int, db: Session = Depends(get_db)):
    """Get account by ID."""
    account = db.query(Account).filter(Account.id == account_id).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    trans_count = db.query(func.count(Transaction.id)).filter(
        Transaction.account_id == account.id
    ).scalar()
    
    return AccountResponse(
        id=account.id,
        account_number=account.account_number,
        name=account.name,
        owner=account.owner,
        account_type=account.account_type.value,
        created_at=account.created_at,
        updated_at=account.updated_at,
        transaction_count=trans_count
    )


@router.put("/{account_id}", response_model=AccountResponse)
def update_account(account_id: int, update: AccountUpdate, db: Session = Depends(get_db)):
    """Update account details."""
    account = db.query(Account).filter(Account.id == account_id).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    if update.name is not None:
        account.name = update.name
    if update.owner is not None:
        account.owner = update.owner
    if update.account_type is not None:
        account.account_type = update.account_type
    
    db.commit()
    db.refresh(account)
    
    trans_count = db.query(func.count(Transaction.id)).filter(
        Transaction.account_id == account.id
    ).scalar()
    
    return AccountResponse(
        id=account.id,
        account_number=account.account_number,
        name=account.name,
        owner=account.owner,
        account_type=account.account_type.value,
        created_at=account.created_at,
        updated_at=account.updated_at,
        transaction_count=trans_count
    )


@router.delete("/{account_id}")
def delete_account(account_id: int, db: Session = Depends(get_db)):
    """Delete an account (only if no transactions)."""
    account = db.query(Account).filter(Account.id == account_id).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    trans_count = db.query(func.count(Transaction.id)).filter(
        Transaction.account_id == account.id
    ).scalar()
    
    if trans_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete account with {trans_count} transactions. Delete transactions first."
        )
    
    db.delete(account)
    db.commit()
    
    return {"message": "Account deleted successfully"}


@router.get("/{account_id}/summary", response_model=AccountSummary)
def get_account_summary(account_id: int, db: Session = Depends(get_db)):
    """Get account summary with statistics - optimized to 2 queries."""
    account = db.query(Account).filter(Account.id == account_id).first()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Single aggregation query for all stats
    stats = db.query(
        func.count(Transaction.id).label('trans_count'),
        func.sum(case((Transaction.amount > 0, Transaction.amount), else_=0)).label('income'),
        func.sum(case((Transaction.amount < 0, Transaction.amount), else_=0)).label('expenses'),
        func.max(Transaction.transaction_date).label('latest_date')
    ).filter(Transaction.account_id == account.id).first()

    trans_count = stats.trans_count or 0
    income = float(stats.income or 0)
    expenses = float(stats.expenses or 0)

    # Get balance from latest transaction (only if there are transactions)
    latest_balance = None
    latest_date = stats.latest_date
    if latest_date:
        latest_trans = db.query(Transaction.balance).filter(
            Transaction.account_id == account.id,
            Transaction.transaction_date == latest_date
        ).order_by(Transaction.id.desc()).first()
        latest_balance = latest_trans.balance if latest_trans else None

    return AccountSummary(
        account=AccountResponse(
            id=account.id,
            account_number=account.account_number,
            name=account.name,
            owner=account.owner,
            account_type=account.account_type.value,
            created_at=account.created_at,
            updated_at=account.updated_at,
            transaction_count=trans_count
        ),
        total_transactions=trans_count,
        latest_transaction_date=latest_date,
        current_balance=latest_balance,
        total_income=income,
        total_expenses=expenses
    )


@router.get("/by-number/{account_number}", response_model=AccountResponse)
def get_account_by_number(account_number: str, db: Session = Depends(get_db)):
    """Get account by account number."""
    account = db.query(Account).filter(
        Account.account_number == account_number
    ).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    trans_count = db.query(func.count(Transaction.id)).filter(
        Transaction.account_id == account.id
    ).scalar()
    
    return AccountResponse(
        id=account.id,
        account_number=account.account_number,
        name=account.name,
        owner=account.owner,
        account_type=account.account_type.value,
        created_at=account.created_at,
        updated_at=account.updated_at,
        transaction_count=trans_count
    )


