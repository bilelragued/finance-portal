"""Reports and analytics endpoints for charts and graphs."""
from datetime import date, datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, extract, String

from app.database import get_db
from app.models import Transaction, Category, Account

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/spending-by-category")
def get_spending_by_category(
    date_from: Optional[date] = Query(None, description="Start date"),
    date_to: Optional[date] = Query(None, description="End date"),
    account_id: Optional[int] = Query(None, description="Filter by account"),
    db: Session = Depends(get_db)
):
    """
    Get spending totals grouped by category for pie/donut charts.
    Only includes expenses (negative amounts).
    """
    # Build base query - group by category
    query = db.query(
        Category.id.label("category_id"),
        Category.name.label("category_name"),
        Category.icon,
        Category.color,
        func.count(Transaction.id).label("transaction_count"),
        func.sum(func.abs(Transaction.amount)).label("total_amount")
    ).join(
        Transaction, Transaction.category_id == Category.id
    ).filter(
        Transaction.amount < 0  # Only expenses
    )

    # Apply filters
    if date_from:
        query = query.filter(Transaction.transaction_date >= date_from)
    if date_to:
        query = query.filter(Transaction.transaction_date <= date_to)
    if account_id:
        query = query.filter(Transaction.account_id == account_id)

    # Group and order
    results = query.group_by(
        Category.id, Category.name, Category.icon, Category.color
    ).order_by(
        func.sum(func.abs(Transaction.amount)).desc()
    ).all()

    # Also get uncategorized spending
    uncategorized_query = db.query(
        func.count(Transaction.id).label("transaction_count"),
        func.sum(func.abs(Transaction.amount)).label("total_amount")
    ).filter(
        Transaction.amount < 0,
        Transaction.category_id.is_(None)
    )

    if date_from:
        uncategorized_query = uncategorized_query.filter(Transaction.transaction_date >= date_from)
    if date_to:
        uncategorized_query = uncategorized_query.filter(Transaction.transaction_date <= date_to)
    if account_id:
        uncategorized_query = uncategorized_query.filter(Transaction.account_id == account_id)

    uncategorized = uncategorized_query.first()

    # Build response
    data = [
        {
            "category_id": r.category_id,
            "category_name": r.category_name,
            "icon": r.icon,
            "color": r.color or "#64748b",  # Default slate color
            "transaction_count": r.transaction_count,
            "total_amount": float(r.total_amount or 0)
        }
        for r in results
    ]

    # Add uncategorized if exists
    if uncategorized and uncategorized.total_amount:
        data.append({
            "category_id": None,
            "category_name": "Uncategorized",
            "icon": "help-circle",
            "color": "#94a3b8",
            "transaction_count": uncategorized.transaction_count,
            "total_amount": float(uncategorized.total_amount)
        })

    return data


@router.get("/income-vs-expenses")
def get_income_vs_expenses(
    date_from: Optional[date] = Query(None, description="Start date"),
    date_to: Optional[date] = Query(None, description="End date"),
    account_id: Optional[int] = Query(None, description="Filter by account"),
    granularity: str = Query("monthly", description="Grouping: 'weekly' or 'monthly'"),
    db: Session = Depends(get_db)
):
    """
    Get income and expenses aggregated by time period for bar charts.
    """
    # Set default date range if not provided (last 12 months/weeks)
    if not date_to:
        date_to = date.today()
    if not date_from:
        if granularity == "weekly":
            date_from = date_to - timedelta(weeks=12)
        else:
            date_from = date_to - timedelta(days=365)

    # Build period extraction based on granularity
    if granularity == "weekly":
        # Group by year and week number
        period_expr = func.concat(
            extract('year', Transaction.transaction_date),
            '-W',
            func.lpad(func.cast(extract('week', Transaction.transaction_date), String), 2, '0')
        )
        period_sort = func.concat(
            extract('year', Transaction.transaction_date),
            func.lpad(func.cast(extract('week', Transaction.transaction_date), String), 2, '0')
        )
    else:
        # Group by year and month
        period_expr = func.concat(
            extract('year', Transaction.transaction_date),
            '-',
            func.lpad(func.cast(extract('month', Transaction.transaction_date), String), 2, '0')
        )
        period_sort = period_expr

    # Query with income/expense aggregation
    if granularity == "weekly":
        period_expr = func.concat(
            func.cast(extract('year', Transaction.transaction_date), String),
            '-W',
            func.lpad(func.cast(extract('week', Transaction.transaction_date), String), 2, '0')
        )
    else:
        period_expr = func.concat(
            func.cast(extract('year', Transaction.transaction_date), String),
            '-',
            func.lpad(func.cast(extract('month', Transaction.transaction_date), String), 2, '0')
        )

    query = db.query(
        period_expr.label("period"),
        func.sum(case((Transaction.amount > 0, Transaction.amount), else_=0)).label("income"),
        func.sum(case((Transaction.amount < 0, func.abs(Transaction.amount)), else_=0)).label("expenses")
    ).filter(
        Transaction.transaction_date >= date_from,
        Transaction.transaction_date <= date_to
    )

    if account_id:
        query = query.filter(Transaction.account_id == account_id)

    results = query.group_by(period_expr).order_by(period_expr).all()

    # Format results
    data = []
    for r in results:
        income = float(r.income or 0)
        expenses = float(r.expenses or 0)

        # Create human-readable label
        period = r.period
        if granularity == "weekly" and period:
            # e.g., "2024-W05" -> "Week 5, 2024"
            parts = period.split('-W')
            if len(parts) == 2:
                period_label = f"Week {int(parts[1])}, {parts[0]}"
            else:
                period_label = period
        elif period:
            # e.g., "2024-03" -> "Mar 2024"
            try:
                dt = datetime.strptime(period, "%Y-%m")
                period_label = dt.strftime("%b %Y")
            except:
                period_label = period
        else:
            period_label = "Unknown"

        data.append({
            "period": period,
            "period_label": period_label,
            "income": income,
            "expenses": expenses,
            "net": income - expenses
        })

    return data


@router.get("/spending-trends")
def get_spending_trends(
    date_from: Optional[date] = Query(None, description="Start date"),
    date_to: Optional[date] = Query(None, description="End date"),
    account_id: Optional[int] = Query(None, description="Filter by account"),
    granularity: str = Query("monthly", description="Grouping: 'weekly' or 'monthly'"),
    db: Session = Depends(get_db)
):
    """
    Get expense amounts over time for line charts.
    """
    # Set default date range
    if not date_to:
        date_to = date.today()
    if not date_from:
        if granularity == "weekly":
            date_from = date_to - timedelta(weeks=12)
        else:
            date_from = date_to - timedelta(days=365)

    if granularity == "weekly":
        period_expr = func.concat(
            func.cast(extract('year', Transaction.transaction_date), String),
            '-W',
            func.lpad(func.cast(extract('week', Transaction.transaction_date), String), 2, '0')
        )
    else:
        period_expr = func.concat(
            func.cast(extract('year', Transaction.transaction_date), String),
            '-',
            func.lpad(func.cast(extract('month', Transaction.transaction_date), String), 2, '0')
        )

    query = db.query(
        period_expr.label("period"),
        func.sum(func.abs(Transaction.amount)).label("total_amount"),
        func.count(Transaction.id).label("transaction_count")
    ).filter(
        Transaction.transaction_date >= date_from,
        Transaction.transaction_date <= date_to,
        Transaction.amount < 0  # Only expenses
    )

    if account_id:
        query = query.filter(Transaction.account_id == account_id)

    results = query.group_by(period_expr).order_by(period_expr).all()

    # Format results
    data = []
    for r in results:
        period = r.period

        # Create human-readable label
        if granularity == "weekly" and period:
            parts = period.split('-W')
            if len(parts) == 2:
                period_label = f"Week {int(parts[1])}"
            else:
                period_label = period
        elif period:
            try:
                dt = datetime.strptime(period, "%Y-%m")
                period_label = dt.strftime("%b %Y")
            except:
                period_label = period
        else:
            period_label = "Unknown"

        data.append({
            "period": period,
            "period_label": period_label,
            "amount": float(r.total_amount or 0),
            "transaction_count": r.transaction_count
        })

    return data


@router.get("/summary")
def get_report_summary(
    date_from: Optional[date] = Query(None, description="Start date"),
    date_to: Optional[date] = Query(None, description="End date"),
    account_id: Optional[int] = Query(None, description="Filter by account"),
    db: Session = Depends(get_db)
):
    """
    Get overall summary statistics for the reports page header.
    """
    # Set default date range (last 12 months)
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date_to - timedelta(days=365)

    # Base query
    query = db.query(Transaction).filter(
        Transaction.transaction_date >= date_from,
        Transaction.transaction_date <= date_to
    )

    if account_id:
        query = query.filter(Transaction.account_id == account_id)

    # Calculate aggregates
    stats = query.with_entities(
        func.count(Transaction.id).label("total_transactions"),
        func.sum(case((Transaction.amount > 0, Transaction.amount), else_=0)).label("total_income"),
        func.sum(case((Transaction.amount < 0, Transaction.amount), else_=0)).label("total_expenses"),
        func.avg(case((Transaction.amount < 0, func.abs(Transaction.amount)), else_=None)).label("avg_expense")
    ).first()

    total_income = float(stats.total_income or 0)
    total_expenses = float(abs(stats.total_expenses or 0))

    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "total_transactions": stats.total_transactions or 0,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_cashflow": total_income - total_expenses,
        "avg_expense": float(stats.avg_expense or 0)
    }
