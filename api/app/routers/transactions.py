"""Transaction management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, case
from typing import List, Optional
from datetime import date

from app.database import get_db
from app.models import Transaction, Account, Category, TransactionClassification
from app.schemas import (
    TransactionResponse, TransactionUpdate, TransactionListResponse,
    CategoryResponse, AccountResponse
)
from app.routers.categories import get_business_na_category

router = APIRouter(prefix="/transactions", tags=["transactions"])


def transaction_to_response(trans: Transaction) -> TransactionResponse:
    """Convert Transaction model to response schema."""
    category_resp = None
    if trans.category:
        category_resp = CategoryResponse(
            id=trans.category.id,
            name=trans.category.name,
            icon=trans.category.icon,
            color=trans.category.color,
            parent_id=trans.category.parent_id,
            is_income=trans.category.is_income,
            created_at=trans.category.created_at
        )
    
    account_resp = None
    if trans.account:
        account_resp = AccountResponse(
            id=trans.account.id,
            account_number=trans.account.account_number,
            name=trans.account.name,
            owner=trans.account.owner,
            account_type=trans.account.account_type.value,
            created_at=trans.account.created_at,
            updated_at=trans.account.updated_at,
            transaction_count=0  # Not needed for nested response
        )
    
    return TransactionResponse(
        id=trans.id,
        transaction_date=trans.transaction_date,
        processed_date=trans.processed_date,
        transaction_type=trans.transaction_type,
        details=trans.details,
        particulars=trans.particulars,
        code=trans.code,
        reference=trans.reference,
        amount=trans.amount,
        balance=trans.balance,
        to_from_account=trans.to_from_account,
        account_id=trans.account_id,
        category_id=trans.category_id,
        classification=trans.classification.value,
        is_reviewed=trans.is_reviewed,
        is_user_confirmed=trans.is_user_confirmed or False,
        categorization_source=trans.categorization_source or "pending",
        user_notes=trans.user_notes,
        card_number_last4=trans.card_number_last4,
        created_at=trans.created_at,
        category=category_resp,
        account=account_resp
    )


@router.get("/", response_model=TransactionListResponse)
def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    account_id: Optional[int] = None,
    category_id: Optional[str] = None,  # Can be "null" for uncategorized or an int
    classification: Optional[str] = None,
    is_reviewed: Optional[bool] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    search: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """
    List transactions with filtering and pagination.
    """
    # Build filters list to apply to both count and data queries
    filters = []

    if account_id:
        filters.append(Transaction.account_id == account_id)

    if category_id:
        if category_id.lower() == "null":
            filters.append(Transaction.category_id == None)
        else:
            try:
                filters.append(Transaction.category_id == int(category_id))
            except ValueError:
                pass

    if classification:
        try:
            class_enum = TransactionClassification(classification.lower())
            filters.append(Transaction.classification == class_enum)
        except ValueError:
            pass

    if is_reviewed is not None:
        filters.append(Transaction.is_reviewed == is_reviewed)

    if date_from:
        filters.append(Transaction.transaction_date >= date_from)

    if date_to:
        filters.append(Transaction.transaction_date <= date_to)

    if search:
        search_term = f"%{search}%"
        filters.append(
            or_(
                Transaction.details.ilike(search_term),
                Transaction.particulars.ilike(search_term),
                Transaction.code.ilike(search_term),
                Transaction.reference.ilike(search_term)
            )
        )

    if min_amount is not None:
        filters.append(Transaction.amount >= min_amount)

    if max_amount is not None:
        filters.append(Transaction.amount <= max_amount)

    # Get total count with lightweight query (no joins)
    total = db.query(func.count(Transaction.id)).filter(*filters).scalar()

    # Get paginated data with eager loading
    offset = (page - 1) * page_size
    transactions = db.query(Transaction).options(
        joinedload(Transaction.account),
        joinedload(Transaction.category)
    ).filter(*filters).order_by(
        Transaction.transaction_date.desc(),
        Transaction.id.desc()
    ).offset(offset).limit(page_size).all()

    # Calculate total pages
    total_pages = (total + page_size - 1) // page_size

    return TransactionListResponse(
        transactions=[transaction_to_response(t) for t in transactions],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
    """Get a single transaction by ID."""
    trans = db.query(Transaction).options(
        joinedload(Transaction.account),
        joinedload(Transaction.category)
    ).filter(Transaction.id == transaction_id).first()
    
    if not trans:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    return transaction_to_response(trans)


@router.put("/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: int,
    update: TransactionUpdate,
    db: Session = Depends(get_db)
):
    """Update transaction classification, category, or notes."""
    trans = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    
    if not trans:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    if update.category_id is not None:
        # Verify category exists
        if update.category_id != 0:  # 0 means remove category
            category = db.query(Category).filter(Category.id == update.category_id).first()
            if not category:
                raise HTTPException(status_code=400, detail="Category not found")
            trans.category_id = update.category_id
        else:
            trans.category_id = None
    
    if update.classification is not None:
        new_classification = TransactionClassification(update.classification.value)
        trans.classification = new_classification
        
        # Auto-assign N/A category for business transactions without a category
        if new_classification == TransactionClassification.BUSINESS and trans.category_id is None:
            na_category = get_business_na_category(db)
            trans.category_id = na_category.id
    
    if update.user_notes is not None:
        trans.user_notes = update.user_notes
    
    if update.is_reviewed is not None:
        trans.is_reviewed = update.is_reviewed
    
    # Mark as user-confirmed if category or classification changed
    if update.category_id is not None or update.classification is not None:
        trans.is_user_confirmed = True
        trans.categorization_source = "user"
    
    db.commit()
    db.refresh(trans)
    
    # Propagate to similar transactions
    if update.category_id is not None or update.classification is not None:
        from app.services.ml_categorizer import propagate_categorization
        propagate_categorization(db, trans, apply_to_similar=True)
    
    # Reload with relationships
    trans = db.query(Transaction).options(
        joinedload(Transaction.account),
        joinedload(Transaction.category)
    ).filter(Transaction.id == transaction_id).first()
    
    return transaction_to_response(trans)


@router.post("/bulk-update")
def bulk_update_transactions(
    transaction_ids: List[int],
    update: TransactionUpdate,
    db: Session = Depends(get_db)
):
    """Bulk update multiple transactions with the same values."""
    transactions = db.query(Transaction).filter(
        Transaction.id.in_(transaction_ids)
    ).all()
    
    if len(transactions) != len(transaction_ids):
        found_ids = {t.id for t in transactions}
        missing = [id for id in transaction_ids if id not in found_ids]
        raise HTTPException(
            status_code=404,
            detail=f"Transactions not found: {missing}"
        )
    
    for trans in transactions:
        if update.category_id is not None:
            trans.category_id = update.category_id if update.category_id != 0 else None
        
        if update.classification is not None:
            trans.classification = TransactionClassification(update.classification.value)
        
        if update.is_reviewed is not None:
            trans.is_reviewed = update.is_reviewed
    
    db.commit()
    
    return {"message": f"Updated {len(transactions)} transactions"}


from pydantic import BaseModel
from typing import Optional as Opt

class BulkUpdateItem(BaseModel):
    id: int
    classification: Optional[str] = None
    category_id: Optional[int] = None
    is_reviewed: Optional[bool] = None


@router.post("/bulk-update-items")
def bulk_update_individual_transactions(
    items: List[BulkUpdateItem],
    db: Session = Depends(get_db)
):
    """Bulk update transactions with individual values per transaction."""
    if not items:
        raise HTTPException(status_code=400, detail="No items provided")
    
    transaction_ids = [item.id for item in items]
    transactions = db.query(Transaction).filter(
        Transaction.id.in_(transaction_ids)
    ).all()
    
    # Create lookup map
    trans_map = {t.id: t for t in transactions}
    
    # Get the N/A category for business transactions
    na_category = get_business_na_category(db)
    
    updated = 0
    for item in items:
        trans = trans_map.get(item.id)
        if not trans:
            continue
        
        if item.classification is not None:
            new_classification = TransactionClassification(item.classification.lower())
            trans.classification = new_classification
            
            # Auto-assign N/A category for business transactions without a category
            if new_classification == TransactionClassification.BUSINESS:
                if item.category_id is None and trans.category_id is None:
                    trans.category_id = na_category.id
        
        if item.category_id is not None:
            trans.category_id = item.category_id if item.category_id != 0 else None
        
        if item.is_reviewed is not None:
            trans.is_reviewed = item.is_reviewed
        
        # Mark as user-confirmed if category or classification changed
        if item.category_id is not None or item.classification is not None:
            trans.is_user_confirmed = True
            trans.categorization_source = "user"
        
        updated += 1
    
    db.commit()
    
    return {"message": f"Updated {updated} transactions", "count": updated}


@router.get("/stats/summary")
def get_transaction_stats(
    account_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Get transaction statistics - optimized single query."""
    # Build base filter conditions
    filters = []
    if account_id:
        filters.append(Transaction.account_id == account_id)
    if date_from:
        filters.append(Transaction.transaction_date >= date_from)
    if date_to:
        filters.append(Transaction.transaction_date <= date_to)

    # Single query with all aggregations using CASE statements
    stats = db.query(
        func.count(Transaction.id).label('total_count'),
        func.sum(case((Transaction.amount > 0, Transaction.amount), else_=0)).label('income'),
        func.sum(case((Transaction.amount < 0, Transaction.amount), else_=0)).label('expenses'),
        func.sum(case((Transaction.classification == TransactionClassification.UNCLASSIFIED, 1), else_=0)).label('unclassified'),
        func.sum(case((Transaction.classification == TransactionClassification.PERSONAL, 1), else_=0)).label('personal'),
        func.sum(case((Transaction.classification == TransactionClassification.BUSINESS, 1), else_=0)).label('business'),
        func.sum(case((Transaction.is_reviewed == False, 1), else_=0)).label('unreviewed'),
        func.sum(case(
            (and_(
                Transaction.classification == TransactionClassification.PERSONAL,
                Transaction.category_id == None
            ), 1),
            else_=0
        )).label('uncategorized')
    ).filter(*filters).first()

    return {
        "total_transactions": stats.total_count or 0,
        "total_income": float(stats.income or 0),
        "total_expenses": float(stats.expenses or 0),
        "net_cashflow": float((stats.income or 0) + (stats.expenses or 0)),
        "classification": {
            "unclassified": stats.unclassified or 0,
            "personal": stats.personal or 0,
            "business": stats.business or 0
        },
        "unreviewed_count": stats.unreviewed or 0,
        "uncategorized_count": stats.uncategorized or 0
    }

