"""SQLAlchemy database models."""
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class AccountType(enum.Enum):
    """Account type enumeration."""
    PERSONAL = "personal"
    BUSINESS = "business"
    SAVINGS = "savings"


class TransactionClassification(enum.Enum):
    """Transaction classification for business accounts."""
    PERSONAL = "personal"
    BUSINESS = "business"
    UNCLASSIFIED = "unclassified"


class Account(Base):
    """Bank account model."""
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    account_number = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)  # Friendly name
    owner = Column(String(100), nullable=False)  # Who owns this account
    account_type = Column(SQLEnum(AccountType), default=AccountType.PERSONAL)
    default_classification = Column(SQLEnum(TransactionClassification), default=TransactionClassification.PERSONAL)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    transactions = relationship("Transaction", back_populates="account")
    
    def __repr__(self):
        return f"<Account {self.account_number} - {self.name}>"


class Category(Base):
    """Spending category model."""
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    icon = Column(String(50))  # Emoji or icon name
    color = Column(String(20))  # Hex color for charts
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    is_income = Column(Boolean, default=False)  # True for income categories
    nl_description = Column(Text, nullable=True)  # Natural language description for AI matching
    nl_keywords = Column(Text, nullable=True)  # Additional keywords for matching
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    parent = relationship("Category", remote_side=[id], backref="subcategories")
    transactions = relationship("Transaction", back_populates="category")
    
    def __repr__(self):
        return f"<Category {self.name}>"


class Transaction(Base):
    """Bank transaction model."""
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    
    # Source data (from Excel)
    transaction_date = Column(Date, nullable=False, index=True)
    processed_date = Column(Date)
    transaction_type = Column(String(50))  # Bank Fee, Visa Purchase, Payment, etc.
    details = Column(String(255))  # Merchant/description
    particulars = Column(String(100))
    code = Column(String(100))
    reference = Column(String(100))
    amount = Column(Float, nullable=False)  # Negative for debits, positive for credits
    balance = Column(Float)
    to_from_account = Column(String(50))
    conversion_charge = Column(String(100))
    foreign_currency_amount = Column(String(100))
    
    # Computed/extracted fields
    card_number_last4 = Column(String(4))  # Last 4 digits of card if present
    
    # Classification and categorization
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
    classification = Column(SQLEnum(TransactionClassification), default=TransactionClassification.UNCLASSIFIED, index=True)
    
    # User overrides and tracking
    user_notes = Column(Text)
    is_reviewed = Column(Boolean, default=False)  # Has user confirmed categorization?
    is_user_confirmed = Column(Boolean, default=False)  # True = user manually set, never auto-change
    categorization_source = Column(String(20), default="pending")  # pending, user, rule, ml, llm
    
    # Metadata
    import_batch_id = Column(String(50))  # Track which import this came from
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    account = relationship("Account", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")
    
    # Unique constraint to prevent duplicates
    # Using transaction_date + amount + details + account_id as composite key
    
    def __repr__(self):
        return f"<Transaction {self.transaction_date} {self.details} {self.amount}>"


class MerchantRule(Base):
    """Learned merchant categorization rules."""
    __tablename__ = "merchant_rules"

    id = Column(Integer, primary_key=True, index=True)
    
    # Matching criteria
    merchant_pattern = Column(String(255), nullable=False)  # Pattern to match (e.g., "Countdown", "Bunnings")
    match_type = Column(String(20), default="contains")  # exact, contains, startswith, regex
    
    # Optional context conditions
    account_type = Column(SQLEnum(AccountType), nullable=True)  # Only apply to specific account type
    min_amount = Column(Float, nullable=True)
    max_amount = Column(Float, nullable=True)
    day_of_week = Column(String(20), nullable=True)  # e.g., "weekend", "weekday", "monday"
    time_of_day = Column(String(20), nullable=True)  # e.g., "morning", "evening", "business_hours"
    
    # Classification result
    classification = Column(SQLEnum(TransactionClassification), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    
    # Confidence and usage tracking
    confidence = Column(Float, default=1.0)  # How confident we are in this rule
    times_applied = Column(Integer, default=0)  # How many times this rule was used
    times_overridden = Column(Integer, default=0)  # How many times user changed the result
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    category = relationship("Category")
    
    def __repr__(self):
        return f"<MerchantRule {self.merchant_pattern} -> {self.classification.value}>"


class ImportLog(Base):
    """Track file imports for duplicate detection and continuity checks."""
    __tablename__ = "import_logs"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String(50), unique=True, nullable=False)
    filename = Column(String(255), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    
    # Date range of imported transactions
    date_from = Column(Date)
    date_to = Column(Date)
    
    # Balance tracking for continuity
    opening_balance = Column(Float)
    closing_balance = Column(Float)
    
    # Import stats
    total_transactions = Column(Integer, default=0)
    new_transactions = Column(Integer, default=0)
    duplicate_transactions = Column(Integer, default=0)
    
    # Status
    status = Column(String(20), default="completed")  # pending, completed, failed
    error_message = Column(Text)
    
    imported_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    account = relationship("Account")
    
    def __repr__(self):
        return f"<ImportLog {self.filename} - {self.status}>"

