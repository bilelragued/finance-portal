"""NLP-powered features for transaction categorization and querying."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from pydantic import BaseModel
from typing import List, Optional
from datetime import date

from app.database import get_db
from app.models import Transaction, Category, TransactionClassification
from app.services.nlp_agent import get_nlp_agent
from app.routers.transactions import transaction_to_response, TransactionListResponse
from app.schemas import TransactionResponse

router = APIRouter(prefix="/nlp", tags=["nlp"])


class NLCategorizationRequest(BaseModel):
    """Request to categorize transactions using NL."""
    transaction_ids: Optional[List[int]] = None  # If None, process all uncategorized
    min_confidence: float = 0.7
    apply: bool = False  # If False, just preview what would be done


class NLCategorizationResponse(BaseModel):
    """Response from NL categorization."""
    total: int
    categorized: int
    skipped: int
    low_confidence: int
    categories_assigned: dict
    error: Optional[str] = None


class NLQueryRequest(BaseModel):
    """Request to query transactions with natural language."""
    query: str


class NLQueryResponse(BaseModel):
    """Response from NL query parsing."""
    filters: dict
    explanation: str
    error: Optional[str] = None


class TransactionMatchRequest(BaseModel):
    """Request to match a single transaction to categories."""
    transaction_id: int
    min_confidence: float = 0.7


class TransactionMatchResponse(BaseModel):
    """Response from single transaction matching."""
    category_id: Optional[int]
    category_name: Optional[str]
    confidence: float
    reasoning: str
    source: str


@router.post("/categorize", response_model=NLCategorizationResponse)
def categorize_transactions_with_nl(
    request: NLCategorizationRequest,
    db: Session = Depends(get_db)
):
    """
    Categorize transactions using natural language descriptions.

    This endpoint uses an AI agent to match transactions to categories based on
    the natural language descriptions stored in each category.
    """
    nlp_agent = get_nlp_agent(db)

    if not nlp_agent.is_available():
        raise HTTPException(
            status_code=503,
            detail="NLP service unavailable. Please configure ANTHROPIC_API_KEY environment variable."
        )

    # Get transactions to categorize
    query = db.query(Transaction)

    if request.transaction_ids:
        # Specific transactions
        query = query.filter(Transaction.id.in_(request.transaction_ids))
    else:
        # All uncategorized, non-user-confirmed transactions
        query = query.filter(
            Transaction.category_id.is_(None),
            Transaction.is_user_confirmed == False
        )

    transactions = query.all()

    if not transactions:
        return NLCategorizationResponse(
            total=0,
            categorized=0,
            skipped=0,
            low_confidence=0,
            categories_assigned={}
        )

    # Run categorization
    result = nlp_agent.categorize_transactions_batch(
        transactions=transactions,
        min_confidence=request.min_confidence,
        apply=request.apply
    )

    return NLCategorizationResponse(
        total=result.get("total", 0),
        categorized=result.get("categorized", 0),
        skipped=result.get("skipped", 0),
        low_confidence=result.get("low_confidence", 0),
        categories_assigned=result.get("categories_assigned", {}),
        error=result.get("error")
    )


@router.post("/match-transaction", response_model=TransactionMatchResponse)
def match_single_transaction(
    request: TransactionMatchRequest,
    db: Session = Depends(get_db)
):
    """
    Match a single transaction to the best category using NL.

    This endpoint is useful for getting a suggestion without applying it.
    """
    nlp_agent = get_nlp_agent(db)

    if not nlp_agent.is_available():
        raise HTTPException(
            status_code=503,
            detail="NLP service unavailable. Please configure ANTHROPIC_API_KEY."
        )

    # Get transaction
    transaction = db.query(Transaction).filter(
        Transaction.id == request.transaction_id
    ).first()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Get match
    result = nlp_agent.match_transaction_to_category(
        transaction=transaction,
        min_confidence=request.min_confidence
    )

    if not result:
        return TransactionMatchResponse(
            category_id=None,
            category_name=None,
            confidence=0.0,
            reasoning="No confident match found",
            source="llm"
        )

    return TransactionMatchResponse(
        category_id=result["category_id"],
        category_name=result["category_name"],
        confidence=result["confidence"],
        reasoning=result["reasoning"],
        source=result["source"]
    )


@router.post("/parse-query", response_model=NLQueryResponse)
def parse_natural_language_query(
    request: NLQueryRequest,
    db: Session = Depends(get_db)
):
    """
    Parse a natural language query into structured filters.

    Example queries:
    - "show me all coffee purchases over $5 last month"
    - "find transactions from grocery stores in December"
    - "all business expenses above $100"
    """
    nlp_agent = get_nlp_agent(db)

    if not nlp_agent.is_available():
        raise HTTPException(
            status_code=503,
            detail="NLP service unavailable. Please configure ANTHROPIC_API_KEY."
        )

    result = nlp_agent.parse_natural_language_query(request.query)

    return NLQueryResponse(
        filters=result.get("filters", {}),
        explanation=result.get("explanation", ""),
        error=result.get("error")
    )


@router.post("/search", response_model=TransactionListResponse)
def search_transactions_with_nl(
    request: NLQueryRequest,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Search transactions using natural language.

    This endpoint parses the NL query and returns matching transactions.

    Example queries:
    - "coffee purchases last week"
    - "grocery shopping over $50"
    - "all entertainment expenses in December"
    """
    nlp_agent = get_nlp_agent(db)

    if not nlp_agent.is_available():
        raise HTTPException(
            status_code=503,
            detail="NLP service unavailable. Please configure ANTHROPIC_API_KEY."
        )

    # Parse query
    parse_result = nlp_agent.parse_natural_language_query(request.query)

    if parse_result.get("error"):
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse query: {parse_result['error']}"
        )

    filters = parse_result.get("filters", {})

    # Build SQL query
    query = db.query(Transaction).options(
        joinedload(Transaction.account),
        joinedload(Transaction.category)
    )

    # Apply filters
    filter_conditions = []

    if "search" in filters and filters["search"]:
        search_term = f"%{filters['search']}%"
        filter_conditions.append(
            or_(
                Transaction.details.ilike(search_term),
                Transaction.particulars.ilike(search_term),
                Transaction.code.ilike(search_term),
                Transaction.reference.ilike(search_term)
            )
        )

    if "min_amount" in filters:
        filter_conditions.append(Transaction.amount >= filters["min_amount"])

    if "max_amount" in filters:
        filter_conditions.append(Transaction.amount <= filters["max_amount"])

    if "date_from" in filters and filters["date_from"]:
        filter_conditions.append(Transaction.transaction_date >= filters["date_from"])

    if "date_to" in filters and filters["date_to"]:
        filter_conditions.append(Transaction.transaction_date <= filters["date_to"])

    if "category_ids" in filters and filters["category_ids"]:
        filter_conditions.append(Transaction.category_id.in_(filters["category_ids"]))

    if "classification" in filters and filters["classification"]:
        try:
            class_enum = TransactionClassification(filters["classification"].lower())
            filter_conditions.append(Transaction.classification == class_enum)
        except ValueError:
            pass

    # Apply all filters
    if filter_conditions:
        query = query.filter(*filter_conditions)

    # Get total count
    from sqlalchemy import func
    total = db.query(func.count(Transaction.id)).filter(*filter_conditions).scalar() if filter_conditions else 0

    # Get paginated results
    offset = (page - 1) * page_size
    transactions = query.order_by(
        Transaction.transaction_date.desc(),
        Transaction.id.desc()
    ).offset(offset).limit(page_size).all()

    # Calculate total pages
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return TransactionListResponse(
        transactions=[transaction_to_response(t) for t in transactions],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/status")
def get_nlp_status(db: Session = Depends(get_db)):
    """Check if NLP features are available and get statistics."""
    nlp_agent = get_nlp_agent(db)

    # Count categories with NL descriptions
    categories_with_nl = db.query(Category).filter(
        Category.nl_description.isnot(None)
    ).count()

    total_categories = db.query(Category).count()

    return {
        "available": nlp_agent.is_available(),
        "api_configured": nlp_agent.api_key is not None,
        "categories_with_nl_descriptions": categories_with_nl,
        "total_categories": total_categories,
        "coverage_percentage": round((categories_with_nl / total_categories * 100), 1) if total_categories > 0 else 0
    }
