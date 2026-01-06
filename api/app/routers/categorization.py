"""Categorization and learning endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.models import Transaction, Category, MerchantRule, TransactionClassification
from app.services.categorizer import TransactionCategorizer
from app.routers.categories import get_business_na_category

router = APIRouter(prefix="/categorization", tags=["categorization"])


# Request/Response schemas
class CategorizationRequest(BaseModel):
    transaction_id: int
    force_llm: bool = False


class CategorizationResult(BaseModel):
    transaction_id: int
    classification: str
    category_id: Optional[int]
    category_name: Optional[str]
    confidence: float
    source: str
    explanation: str


class BulkCategorizationRequest(BaseModel):
    transaction_ids: List[int]
    apply_rules_only: bool = False


class FeedbackRequest(BaseModel):
    transaction_id: int
    classification: str  # "personal" or "business"
    category_id: Optional[int] = None


class ApplyCategorizationRequest(BaseModel):
    transaction_id: int
    classification: str
    category_id: Optional[int] = None
    learn: bool = True  # Whether to create/update a merchant rule


class MerchantRuleResponse(BaseModel):
    id: int
    merchant_pattern: str
    match_type: str
    classification: str
    category_id: Optional[int]
    category_name: Optional[str]
    confidence: float
    times_applied: int
    times_overridden: int


@router.post("/categorize", response_model=CategorizationResult)
def categorize_transaction(
    request: CategorizationRequest,
    db: Session = Depends(get_db)
):
    """
    Get a categorization suggestion for a single transaction.
    
    Uses:
    1. Learned merchant rules (highest priority)
    2. LLM categorization (if available)
    3. Basic keyword matching (fallback)
    """
    transaction = db.query(Transaction).filter(
        Transaction.id == request.transaction_id
    ).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    categorizer = TransactionCategorizer(db)
    result = categorizer.categorize_transaction(transaction, force_llm=request.force_llm)
    
    return CategorizationResult(
        transaction_id=transaction.id,
        **result
    )


@router.post("/categorize-bulk", response_model=List[CategorizationResult])
def categorize_transactions_bulk(
    request: BulkCategorizationRequest,
    db: Session = Depends(get_db)
):
    """
    Get categorization suggestions for multiple transactions.
    
    Set apply_rules_only=True for faster processing using only learned rules.
    """
    transactions = db.query(Transaction).filter(
        Transaction.id.in_(request.transaction_ids)
    ).all()
    
    if len(transactions) != len(request.transaction_ids):
        found_ids = {t.id for t in transactions}
        missing = [id for id in request.transaction_ids if id not in found_ids]
        raise HTTPException(
            status_code=404,
            detail=f"Transactions not found: {missing}"
        )
    
    categorizer = TransactionCategorizer(db)
    results = categorizer.categorize_batch(
        transactions, 
        apply_rules_only=request.apply_rules_only
    )
    
    return [
        CategorizationResult(
            transaction_id=r["transaction_id"],
            classification=r.get("classification") or "unclassified",
            category_id=r.get("category_id"),
            category_name=r.get("category_name"),
            confidence=r.get("confidence", 0),
            source=r.get("source", "none"),
            explanation=r.get("explanation", "")
        )
        for r in results
    ]


@router.post("/apply")
def apply_categorization(
    request: ApplyCategorizationRequest,
    db: Session = Depends(get_db)
):
    """
    Apply a categorization to a transaction and optionally learn from it.
    
    This is called when the user confirms or corrects a categorization.
    """
    transaction = db.query(Transaction).filter(
        Transaction.id == request.transaction_id
    ).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    # Validate category if provided
    if request.category_id:
        category = db.query(Category).filter(
            Category.id == request.category_id
        ).first()
        if not category:
            raise HTTPException(status_code=400, detail="Category not found")
    
    # Update transaction
    classification = TransactionClassification(request.classification)
    transaction.classification = classification
    
    # Auto-assign N/A category for business transactions without a category
    if classification == TransactionClassification.BUSINESS and request.category_id is None:
        na_category = get_business_na_category(db)
        transaction.category_id = na_category.id
    else:
        transaction.category_id = request.category_id
    
    transaction.is_reviewed = True
    transaction.is_user_confirmed = True  # User manually confirmed
    transaction.categorization_source = "user"
    
    # Learn from feedback
    rule_created = None
    if request.learn:
        categorizer = TransactionCategorizer(db, use_llm=False)
        rule = categorizer.learn_from_feedback(
            transaction,
            classification,
            request.category_id,
            user_confirmed=True
        )
        if rule:
            rule_created = {
                "id": rule.id,
                "pattern": rule.merchant_pattern,
                "confidence": rule.confidence
            }
    
    db.commit()
    
    # Propagate to similar transactions
    from app.services.ml_categorizer import propagate_categorization
    propagation_result = propagate_categorization(db, transaction, apply_to_similar=True)
    
    return {
        "success": True,
        "transaction_id": transaction.id,
        "classification": request.classification,
        "category_id": transaction.category_id,
        "rule_created": rule_created,
        "similar_updated": propagation_result.get("updated", 0)
    }


@router.post("/apply-bulk")
def apply_categorization_bulk(
    requests: List[ApplyCategorizationRequest],
    db: Session = Depends(get_db)
):
    """Apply categorizations to multiple transactions."""
    results = []
    
    for req in requests:
        transaction = db.query(Transaction).filter(
            Transaction.id == req.transaction_id
        ).first()
        
        if not transaction:
            results.append({
                "transaction_id": req.transaction_id,
                "success": False,
                "error": "Not found"
            })
            continue
        
        classification = TransactionClassification(req.classification)
        transaction.classification = classification
        
        # Auto-assign N/A category for business transactions without a category
        if classification == TransactionClassification.BUSINESS and req.category_id is None:
            na_category = get_business_na_category(db)
            transaction.category_id = na_category.id
        else:
            transaction.category_id = req.category_id
        
        transaction.is_reviewed = True
        
        if req.learn:
            categorizer = TransactionCategorizer(db, use_llm=False)
            categorizer.learn_from_feedback(
                transaction,
                classification,
                req.category_id,
                user_confirmed=True
            )
        
        results.append({
            "transaction_id": req.transaction_id,
            "success": True
        })
    
    db.commit()
    
    return {
        "total": len(requests),
        "successful": len([r for r in results if r.get("success")]),
        "results": results
    }


@router.get("/suggestions")
def get_categorization_suggestions(
    account_id: Optional[int] = None,
    limit: int = Query(50, le=100),
    use_llm: bool = Query(False, description="Use LLM for suggestions (slower but smarter)"),
    db: Session = Depends(get_db)
):
    """
    Get uncategorized transactions with suggestions.

    By default uses fast rule-based matching. Set use_llm=true for AI suggestions.
    """
    from sqlalchemy.orm import joinedload
    import re

    # OPTIMIZED: Single query with eager loading of account relationship
    query = db.query(Transaction).options(
        joinedload(Transaction.account)
    ).filter(
        Transaction.is_reviewed == False
    )

    if account_id:
        query = query.filter(Transaction.account_id == account_id)

    transactions = query.order_by(
        Transaction.transaction_date.desc()
    ).limit(limit).all()

    if use_llm:
        # Slow path: use LLM for each transaction
        categorizer = TransactionCategorizer(db)
        results = []
        for trans in transactions:
            suggestion = categorizer.categorize_transaction(trans)
            results.append(_build_suggestion_item(trans, suggestion))
        return {"total": len(results), "items": results}

    # FAST PATH: Batch process all transactions with pre-loaded data
    # Pre-load all rules ONCE
    rules = db.query(MerchantRule).order_by(MerchantRule.confidence.desc()).all()

    # Pre-load categories for name lookup
    categories = {c.id: c.name for c in db.query(Category).all()}

    # Build account type cache from eager-loaded relationships
    account_types = {}
    for trans in transactions:
        if trans.account and trans.account_id not in account_types:
            account_types[trans.account_id] = trans.account.account_type

    results = []
    for trans in transactions:
        suggestion = _fast_categorize(trans, rules, categories, account_types)
        results.append(_build_suggestion_item(trans, suggestion))

    return {
        "total": len(results),
        "items": results
    }


def _build_suggestion_item(trans: Transaction, suggestion: dict) -> dict:
    """Build a suggestion response item."""
    return {
        "transaction": {
            "id": trans.id,
            "date": trans.transaction_date.isoformat(),
            "processed_date": trans.processed_date.isoformat() if trans.processed_date else None,
            "details": trans.details,
            "type": trans.transaction_type,
            "amount": trans.amount,
            "balance": trans.balance,
            "particulars": trans.particulars,
            "code": trans.code,
            "reference": trans.reference,
            "to_from_account": trans.to_from_account,
            "card_number_last4": trans.card_number_last4,
            "account_id": trans.account_id
        },
        "suggestion": suggestion
    }


def _fast_categorize(
    trans: Transaction,
    rules: list,
    categories: dict,
    account_types: dict
) -> dict:
    """Fast categorization without database queries."""
    import re
    from app.models import AccountType

    is_business = account_types.get(trans.account_id) == AccountType.BUSINESS
    merchant = (trans.details or "").lower()

    # Try to match a rule
    for rule in rules:
        pattern = rule.merchant_pattern.lower()

        # Pattern matching
        if rule.match_type == "exact" and merchant != pattern:
            continue
        elif rule.match_type == "contains" and pattern not in merchant:
            continue
        elif rule.match_type == "startswith" and not merchant.startswith(pattern):
            continue
        elif rule.match_type == "regex":
            if not re.search(pattern, merchant, re.IGNORECASE):
                continue
        elif rule.match_type not in ("exact", "contains", "startswith", "regex") and pattern not in merchant:
            continue

        # Account type check
        if rule.account_type and account_types.get(trans.account_id) != rule.account_type:
            continue

        # Amount checks
        if rule.min_amount is not None and abs(trans.amount) < rule.min_amount:
            continue
        if rule.max_amount is not None and abs(trans.amount) > rule.max_amount:
            continue

        # Day of week check
        if rule.day_of_week:
            trans_day = trans.transaction_date.strftime("%A").lower()
            if rule.day_of_week == "weekend" and trans_day not in ["saturday", "sunday"]:
                continue
            elif rule.day_of_week == "weekday" and trans_day in ["saturday", "sunday"]:
                continue
            elif rule.day_of_week not in ["weekend", "weekday"] and trans_day != rule.day_of_week.lower():
                continue

        # Rule matched!
        return {
            "classification": rule.classification.value,
            "category_id": rule.category_id,
            "category_name": categories.get(rule.category_id),
            "confidence": rule.confidence,
            "source": "rule",
            "explanation": f"Matched rule: '{rule.merchant_pattern}'"
        }

    # No rule matched - use basic keyword matching
    return _basic_keyword_match(trans, is_business, categories)


def _basic_keyword_match(trans: Transaction, is_business: bool, categories: dict) -> dict:
    """Fast basic keyword matching without database queries."""
    details = (trans.details or "").lower()
    trans_type = (trans.transaction_type or "").lower()
    classification = "business" if is_business else "personal"

    # Check for income first
    if trans_type in ["direct credit", "payment received", "salary", "wages"]:
        return {
            "classification": "personal",
            "category_id": None,
            "category_name": "Salary",
            "confidence": 0.7,
            "source": "basic",
            "explanation": "Income transaction - needs category selection"
        }

    # Basic keyword rules
    keyword_rules = [
        (["countdown", "new world", "pak n save", "paknsave", "supermarket"], "Groceries", False),
        (["restaurant", "cafe", "coffee", "mcdonald", "burger", "pizza", "sushi"], "Food & Dining", False),
        (["bp", "z energy", "mobil", "caltex", "fuel", "petrol", "uber", "taxi"], "Transport", False),
        (["bunnings", "mitre 10", "mitre10", "placemakers"], "Home & Garden", True),
        (["netflix", "spotify", "disney", "amazon prime", "youtube"], "Entertainment", True),
        (["amazon", "ebay", "trademe", "kmart", "the warehouse"], "Shopping", False),
        (["bank fee", "account fee", "overdraft"], "Bank Fees", False),
    ]

    for keywords, cat_name, force_personal in keyword_rules:
        if any(kw in details for kw in keywords):
            if force_personal and is_business:
                classification = "personal"
            # Find category ID by name
            cat_id = next((cid for cid, cname in categories.items() if cname == cat_name), None)
            return {
                "classification": classification,
                "category_id": cat_id,
                "category_name": cat_name,
                "confidence": 0.5,
                "source": "basic",
                "explanation": f"Matched keyword - suggest: {cat_name}"
            }

    # No match
    return {
        "classification": classification,
        "category_id": None,
        "category_name": None,
        "confidence": 0.0,
        "source": "none",
        "explanation": "No matching rules. Click 'Get AI Suggestion' for smart categorization."
    }


@router.post("/suggest-one")
def get_single_suggestion(
    transaction_id: int,
    db: Session = Depends(get_db)
):
    """Get an LLM-powered suggestion for a single transaction."""
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id
    ).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    categorizer = TransactionCategorizer(db)
    suggestion = categorizer.categorize_transaction(transaction)
    
    return {
        "transaction_id": transaction_id,
        "suggestion": suggestion
    }


@router.get("/rules", response_model=List[MerchantRuleResponse])
def list_merchant_rules(
    min_confidence: float = Query(0, ge=0, le=1),
    db: Session = Depends(get_db)
):
    """List all learned merchant rules."""
    rules = db.query(MerchantRule).filter(
        MerchantRule.confidence >= min_confidence
    ).order_by(
        MerchantRule.times_applied.desc()
    ).all()
    
    return [
        MerchantRuleResponse(
            id=rule.id,
            merchant_pattern=rule.merchant_pattern,
            match_type=rule.match_type,
            classification=rule.classification.value,
            category_id=rule.category_id,
            category_name=rule.category.name if rule.category else None,
            confidence=rule.confidence,
            times_applied=rule.times_applied,
            times_overridden=rule.times_overridden
        )
        for rule in rules
    ]


@router.delete("/rules/{rule_id}")
def delete_merchant_rule(rule_id: int, db: Session = Depends(get_db)):
    """Delete a merchant rule."""
    rule = db.query(MerchantRule).filter(MerchantRule.id == rule_id).first()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    db.delete(rule)
    db.commit()
    
    return {"message": "Rule deleted successfully"}


@router.get("/rules/stats")
def get_rule_statistics(db: Session = Depends(get_db)):
    """Get statistics about learned categorization rules."""
    categorizer = TransactionCategorizer(db, use_llm=False)
    return categorizer.get_rule_statistics()


@router.post("/auto-categorize")
def auto_categorize_all(
    account_id: Optional[int] = None,
    apply: bool = False,
    db: Session = Depends(get_db)
):
    """
    Auto-categorize all uncategorized transactions.
    
    If apply=False (default), returns suggestions without applying.
    If apply=True, applies high-confidence categorizations automatically.
    """
    categorizer = TransactionCategorizer(db)
    
    # Get uncategorized transactions
    query = db.query(Transaction).filter(
        Transaction.is_reviewed == False
    )
    
    if account_id:
        query = query.filter(Transaction.account_id == account_id)
    
    transactions = query.all()
    
    results = {
        "total": len(transactions),
        "high_confidence": 0,
        "medium_confidence": 0,
        "low_confidence": 0,
        "applied": 0,
        "suggestions": []
    }
    
    for trans in transactions:
        suggestion = categorizer.categorize_transaction(trans)
        
        # Categorize by confidence
        if suggestion["confidence"] >= 0.8:
            results["high_confidence"] += 1
            
            # Auto-apply high confidence if requested
            if apply:
                trans.classification = TransactionClassification(suggestion["classification"])
                trans.category_id = suggestion.get("category_id")
                trans.is_reviewed = True
                results["applied"] += 1
                
        elif suggestion["confidence"] >= 0.5:
            results["medium_confidence"] += 1
        else:
            results["low_confidence"] += 1
        
        results["suggestions"].append({
            "transaction_id": trans.id,
            "details": trans.details,
            "amount": trans.amount,
            **suggestion
        })
    
    if apply:
        db.commit()
    
    return results


# ============== NEW ML ENDPOINTS ==============

@router.post("/ml/train")
def train_ml_model(
    min_samples: int = Query(20, description="Minimum confirmed samples needed"),
    db: Session = Depends(get_db)
):
    """
    Train the local ML model on user-confirmed transactions.
    
    The model learns from transactions where is_user_confirmed=True.
    """
    from app.services.ml_categorizer import MLCategorizer
    
    ml = MLCategorizer(db)
    result = ml.train(min_samples=min_samples)
    
    return result


@router.post("/ml/predict/{transaction_id}")
def ml_predict_single(
    transaction_id: int,
    db: Session = Depends(get_db)
):
    """Get ML prediction for a single transaction."""
    from app.services.ml_categorizer import MLCategorizer
    
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    ml = MLCategorizer(db)
    prediction = ml.predict(transaction)
    
    if not prediction:
        return {"error": "ML model not trained or prediction failed"}
    
    return prediction


@router.post("/ml/auto-categorize")
def ml_auto_categorize(
    min_confidence: float = Query(0.7, ge=0, le=1),
    apply: bool = Query(False, description="Actually apply predictions"),
    db: Session = Depends(get_db)
):
    """
    Auto-categorize pending transactions using the ML model.
    
    Only affects transactions where is_user_confirmed=False.
    """
    from app.services.ml_categorizer import MLCategorizer
    
    ml = MLCategorizer(db)
    result = ml.auto_categorize_pending(min_confidence=min_confidence, apply=apply)
    
    return result


@router.get("/stats")
def get_categorization_stats(db: Session = Depends(get_db)):
    """
    Get categorization statistics for the dashboard.
    
    Returns counts of:
    - Uncategorized (pending)
    - Auto-categorized (needs review)
    - User-confirmed (locked)
    """
    from sqlalchemy import func
    
    # Total transactions
    total = db.query(func.count(Transaction.id)).scalar()
    
    # User confirmed (locked)
    user_confirmed = db.query(func.count(Transaction.id)).filter(
        Transaction.is_user_confirmed == True
    ).scalar()
    
    # Auto-categorized (has category but not user confirmed)
    auto_categorized = db.query(func.count(Transaction.id)).filter(
        Transaction.is_user_confirmed == False,
        Transaction.category_id.isnot(None)
    ).scalar()
    
    # Uncategorized (no category)
    uncategorized = db.query(func.count(Transaction.id)).filter(
        Transaction.category_id.is_(None)
    ).scalar()
    
    # Unclassified (no personal/business classification)
    unclassified = db.query(func.count(Transaction.id)).filter(
        Transaction.classification == TransactionClassification.UNCLASSIFIED
    ).scalar()
    
    # Personal transactions needing category
    personal_uncategorized = db.query(func.count(Transaction.id)).filter(
        Transaction.classification == TransactionClassification.PERSONAL,
        Transaction.category_id.is_(None)
    ).scalar()
    
    return {
        "total": total,
        "user_confirmed": user_confirmed,
        "auto_categorized": auto_categorized,
        "uncategorized": uncategorized,
        "unclassified": unclassified,
        "personal_uncategorized": personal_uncategorized,
        "needs_attention": uncategorized + unclassified
    }


@router.post("/reset/{transaction_id}")
def reset_transaction_category(
    transaction_id: int,
    recategorize: bool = Query(True, description="Run ML prediction after reset"),
    db: Session = Depends(get_db)
):
    """
    Reset a transaction's category so the system can re-evaluate it.
    
    Sets is_user_confirmed=False and optionally runs ML prediction.
    """
    from app.services.ml_categorizer import MLCategorizer
    
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    # Reset
    transaction.category_id = None
    transaction.is_user_confirmed = False
    transaction.is_reviewed = False
    transaction.categorization_source = "pending"
    
    db.commit()
    
    result = {"reset": True, "transaction_id": transaction_id}
    
    # Optionally re-categorize with ML
    if recategorize:
        ml = MLCategorizer(db)
        prediction = ml.predict(transaction)
        
        if prediction and prediction.get("confidence", 0) >= 0.7:
            transaction.category_id = prediction["category_id"]
            transaction.categorization_source = "ml"
            db.commit()
            result["new_prediction"] = prediction
    
    return result


@router.post("/find-similar/{transaction_id}")
def find_similar_transactions_endpoint(
    transaction_id: int,
    include_categorized: bool = Query(False),
    db: Session = Depends(get_db)
):
    """Find transactions similar to the given one."""
    from app.services.ml_categorizer import find_similar_transactions
    
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    similar = find_similar_transactions(db, transaction, include_categorized=include_categorized)
    
    return {
        "source_id": transaction_id,
        "similar_count": len(similar),
        "similar": [
            {
                "id": t.id,
                "date": t.transaction_date.isoformat(),
                "details": t.details,
                "code": t.code,
                "amount": t.amount,
                "category_id": t.category_id,
                "is_user_confirmed": t.is_user_confirmed
            }
            for t in similar[:20]  # Limit to 20
        ]
    }

