"""Category management endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from app.database import get_db
from app.models import Category, Transaction
from app.schemas import CategoryCreate, CategoryResponse

router = APIRouter(prefix="/categories", tags=["categories"])


# Special category name for business transactions
BUSINESS_NA_CATEGORY = "Not Applicable (Business)"

# Default categories to seed the database
DEFAULT_CATEGORIES = [
    # Expenses
    {"name": "Food & Dining", "icon": "🍽️", "color": "#FF6B6B", "is_income": False},
    {"name": "Groceries", "icon": "🛒", "color": "#4ECDC4", "is_income": False},
    {"name": "Transport", "icon": "🚗", "color": "#45B7D1", "is_income": False},
    {"name": "Utilities", "icon": "💡", "color": "#96CEB4", "is_income": False},
    {"name": "Entertainment", "icon": "🎬", "color": "#DDA0DD", "is_income": False},
    {"name": "Shopping", "icon": "🛍️", "color": "#FFB347", "is_income": False},
    {"name": "Health & Medical", "icon": "🏥", "color": "#98D8C8", "is_income": False},
    {"name": "Home & Garden", "icon": "🏠", "color": "#F7DC6F", "is_income": False},
    {"name": "Personal Care", "icon": "💅", "color": "#BB8FCE", "is_income": False},
    {"name": "Education", "icon": "📚", "color": "#85C1E9", "is_income": False},
    {"name": "Travel", "icon": "✈️", "color": "#F8B500", "is_income": False},
    {"name": "Subscriptions", "icon": "📱", "color": "#E74C3C", "is_income": False},
    {"name": "Insurance", "icon": "🛡️", "color": "#5D6D7E", "is_income": False},
    {"name": "Bank Fees", "icon": "🏦", "color": "#ABB2B9", "is_income": False},
    {"name": "Gifts & Donations", "icon": "🎁", "color": "#F1948A", "is_income": False},
    {"name": "Kids & Family", "icon": "👨‍👩‍👧‍👦", "color": "#A569BD", "is_income": False},
    {"name": "Pets", "icon": "🐕", "color": "#DC7633", "is_income": False},
    {"name": "Other Expenses", "icon": "📦", "color": "#BDC3C7", "is_income": False},
    
    # Special - for business transactions (not tracked for personal)
    {"name": BUSINESS_NA_CATEGORY, "icon": "🚫", "color": "#7F8C8D", "is_income": False},
    
    # Income
    {"name": "Salary", "icon": "💰", "color": "#27AE60", "is_income": True},
    {"name": "Interest", "icon": "📈", "color": "#2ECC71", "is_income": True},
    {"name": "Refund", "icon": "↩️", "color": "#1ABC9C", "is_income": True},
    {"name": "Transfer In", "icon": "➡️", "color": "#3498DB", "is_income": True},
    {"name": "Other Income", "icon": "💵", "color": "#58D68D", "is_income": True},
]


def get_business_na_category(db: Session) -> Category:
    """Get or create the 'Not Applicable (Business)' category."""
    category = db.query(Category).filter(Category.name == BUSINESS_NA_CATEGORY).first()
    if not category:
        category = Category(
            name=BUSINESS_NA_CATEGORY,
            icon="🚫",
            color="#7F8C8D",
            is_income=False
        )
        db.add(category)
        db.commit()
        db.refresh(category)
    return category


@router.get("/", response_model=List[CategoryResponse])
def list_categories(
    include_counts: bool = False,
    db: Session = Depends(get_db)
):
    """List all categories."""
    categories = db.query(Category).order_by(Category.is_income, Category.name).all()
    
    return [
        CategoryResponse(
            id=cat.id,
            name=cat.name,
            icon=cat.icon,
            color=cat.color,
            parent_id=cat.parent_id,
            is_income=cat.is_income,
            nl_description=cat.nl_description,
            nl_keywords=cat.nl_keywords,
            created_at=cat.created_at
        )
        for cat in categories
    ]


@router.post("/", response_model=CategoryResponse)
def create_category(category: CategoryCreate, db: Session = Depends(get_db)):
    """Create a new category."""
    # Check if name already exists
    existing = db.query(Category).filter(Category.name == category.name).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Category '{category.name}' already exists"
        )
    
    # Validate parent if provided
    if category.parent_id:
        parent = db.query(Category).filter(Category.id == category.parent_id).first()
        if not parent:
            raise HTTPException(status_code=400, detail="Parent category not found")
    
    db_category = Category(
        name=category.name,
        icon=category.icon,
        color=category.color,
        parent_id=category.parent_id,
        is_income=category.is_income,
        nl_description=category.nl_description,
        nl_keywords=category.nl_keywords
    )
    
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    
    return CategoryResponse(
        id=db_category.id,
        name=db_category.name,
        icon=db_category.icon,
        color=db_category.color,
        parent_id=db_category.parent_id,
        is_income=db_category.is_income,
        nl_description=db_category.nl_description,
        nl_keywords=db_category.nl_keywords,
        created_at=db_category.created_at
    )


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(category_id: int, db: Session = Depends(get_db)):
    """Get a category by ID."""
    category = db.query(Category).filter(Category.id == category_id).first()

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    return CategoryResponse(
        id=category.id,
        name=category.name,
        icon=category.icon,
        color=category.color,
        parent_id=category.parent_id,
        is_income=category.is_income,
        nl_description=category.nl_description,
        nl_keywords=category.nl_keywords,
        created_at=category.created_at
    )


@router.put("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    update: CategoryCreate,
    db: Session = Depends(get_db)
):
    """Update a category."""
    category = db.query(Category).filter(Category.id == category_id).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Check name uniqueness if changed
    if update.name != category.name:
        existing = db.query(Category).filter(Category.name == update.name).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Category '{update.name}' already exists"
            )
    
    category.name = update.name
    category.icon = update.icon
    category.color = update.color
    category.parent_id = update.parent_id
    category.is_income = update.is_income
    category.nl_description = update.nl_description
    category.nl_keywords = update.nl_keywords

    db.commit()
    db.refresh(category)

    return CategoryResponse(
        id=category.id,
        name=category.name,
        icon=category.icon,
        color=category.color,
        parent_id=category.parent_id,
        is_income=category.is_income,
        nl_description=category.nl_description,
        nl_keywords=category.nl_keywords,
        created_at=category.created_at
    )


@router.delete("/{category_id}")
def delete_category(
    category_id: int, 
    reassign_to: int = None,
    db: Session = Depends(get_db)
):
    """
    Delete a category.
    
    If reassign_to is provided, transactions will be moved to that category.
    Otherwise, transactions will have their category set to null.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Validate reassign target
    if reassign_to:
        target = db.query(Category).filter(Category.id == reassign_to).first()
        if not target:
            raise HTTPException(status_code=400, detail="Reassignment target category not found")
        if target.id == category_id:
            raise HTTPException(status_code=400, detail="Cannot reassign to the same category")
    
    # Check for subcategories
    sub_count = db.query(func.count(Category.id)).filter(
        Category.parent_id == category_id
    ).scalar()
    
    if sub_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete category with {sub_count} subcategories. Delete or reassign subcategories first."
        )
    
    # Reassign transactions
    trans_count = db.query(Transaction).filter(
        Transaction.category_id == category_id
    ).update({"category_id": reassign_to, "is_reviewed": False})
    
    # Delete the category
    db.delete(category)
    db.commit()
    
    return {
        "message": f"Category deleted successfully. {trans_count} transactions reassigned.",
        "transactions_reassigned": trans_count
    }


@router.post("/{category_id}/reassign")
def reassign_category_transactions(
    category_id: int,
    target_category_id: int,
    db: Session = Depends(get_db)
):
    """
    Reassign all transactions from one category to another.
    Useful for merging categories.
    """
    source = db.query(Category).filter(Category.id == category_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source category not found")
    
    if target_category_id:
        target = db.query(Category).filter(Category.id == target_category_id).first()
        if not target:
            raise HTTPException(status_code=404, detail="Target category not found")
    
    # Update transactions
    count = db.query(Transaction).filter(
        Transaction.category_id == category_id
    ).update({"category_id": target_category_id, "is_reviewed": False})
    
    db.commit()
    
    return {
        "message": f"Reassigned {count} transactions from '{source.name}' to '{target.name if target_category_id else 'Uncategorized'}'",
        "count": count
    }


@router.post("/seed")
def seed_categories(db: Session = Depends(get_db)):
    """Seed the database with default categories."""
    created = 0
    skipped = 0
    
    for cat_data in DEFAULT_CATEGORIES:
        existing = db.query(Category).filter(Category.name == cat_data["name"]).first()
        if existing:
            skipped += 1
            continue
        
        category = Category(**cat_data)
        db.add(category)
        created += 1
    
    db.commit()
    
    return {
        "message": f"Seeded {created} categories, skipped {skipped} existing",
        "created": created,
        "skipped": skipped
    }


@router.get("/stats/usage")
def get_category_usage(db: Session = Depends(get_db)):
    """Get category usage statistics - optimized single query."""
    # Single query with LEFT JOIN and GROUP BY to get all categories with stats
    categories_with_stats = db.query(
        Category,
        func.count(Transaction.id).label('transaction_count'),
        func.coalesce(func.sum(Transaction.amount), 0).label('total_amount')
    ).outerjoin(
        Transaction, Category.id == Transaction.category_id
    ).group_by(Category.id).order_by(
        func.count(Transaction.id).desc()
    ).all()

    return [
        {
            "id": cat.id,
            "name": cat.name,
            "icon": cat.icon,
            "color": cat.color,
            "is_income": cat.is_income,
            "transaction_count": trans_count,
            "total_amount": float(total_amount)
        }
        for cat, trans_count, total_amount in categories_with_stats
    ]

