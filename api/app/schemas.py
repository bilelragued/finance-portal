"""Pydantic schemas for API request/response validation."""
from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from typing import Optional, List
from enum import Enum


# Enums for API
class AccountTypeEnum(str, Enum):
    PERSONAL = "personal"
    BUSINESS = "business"
    SAVINGS = "savings"


class TransactionClassificationEnum(str, Enum):
    PERSONAL = "personal"
    BUSINESS = "business"
    UNCLASSIFIED = "unclassified"


# Account Schemas
class AccountBase(BaseModel):
    account_number: str
    name: str
    owner: str
    account_type: AccountTypeEnum = AccountTypeEnum.PERSONAL


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    owner: Optional[str] = None
    account_type: Optional[AccountTypeEnum] = None


class AccountResponse(AccountBase):
    id: int
    created_at: datetime
    updated_at: datetime
    transaction_count: Optional[int] = 0
    
    model_config = ConfigDict(from_attributes=True)


# Category Schemas
class CategoryBase(BaseModel):
    name: str
    icon: Optional[str] = None
    color: Optional[str] = None
    parent_id: Optional[int] = None
    is_income: bool = False


class CategoryCreate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Transaction Schemas
class TransactionBase(BaseModel):
    transaction_date: date
    processed_date: Optional[date] = None
    transaction_type: Optional[str] = None
    details: Optional[str] = None
    particulars: Optional[str] = None
    code: Optional[str] = None
    reference: Optional[str] = None
    amount: float
    balance: Optional[float] = None
    to_from_account: Optional[str] = None


class TransactionCreate(TransactionBase):
    account_id: int


class TransactionUpdate(BaseModel):
    category_id: Optional[int] = None
    classification: Optional[TransactionClassificationEnum] = None
    user_notes: Optional[str] = None
    is_reviewed: Optional[bool] = None


class TransactionResponse(TransactionBase):
    id: int
    account_id: int
    category_id: Optional[int] = None
    classification: TransactionClassificationEnum
    is_reviewed: bool
    is_user_confirmed: bool = False
    categorization_source: Optional[str] = "pending"  # pending, user, rule, ml, llm
    user_notes: Optional[str] = None
    card_number_last4: Optional[str] = None
    created_at: datetime
    
    # Nested objects
    category: Optional[CategoryResponse] = None
    account: Optional[AccountResponse] = None
    
    model_config = ConfigDict(from_attributes=True)


class TransactionListResponse(BaseModel):
    transactions: List[TransactionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# Upload Schemas
class FileUploadInfo(BaseModel):
    """Information extracted from uploaded file."""
    filename: str
    account_number: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    total_rows: int = 0


class UploadConfirmation(BaseModel):
    """User confirmation for upload."""
    file_id: str
    account_id: int
    confirm: bool = True


class UploadResult(BaseModel):
    """Result of file upload and processing."""
    success: bool
    batch_id: str
    total_transactions: int
    new_transactions: int
    duplicate_transactions: int
    message: str
    
    # Continuity check results
    continuity_ok: bool = True
    continuity_message: Optional[str] = None
    expected_balance: Optional[float] = None
    actual_balance: Optional[float] = None


# Import Log Schemas
class ImportLogResponse(BaseModel):
    id: int
    batch_id: str
    filename: str
    account_id: int
    date_from: Optional[date]
    date_to: Optional[date]
    total_transactions: int
    new_transactions: int
    duplicate_transactions: int
    status: str
    imported_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Dashboard/Summary Schemas
class AccountSummary(BaseModel):
    account: AccountResponse
    total_transactions: int
    latest_transaction_date: Optional[date]
    current_balance: Optional[float]
    total_income: float
    total_expenses: float


class UploadPreview(BaseModel):
    """Preview of file before confirming upload."""
    file_info: FileUploadInfo
    suggested_account: Optional[AccountResponse] = None
    existing_account: Optional[AccountResponse] = None
    sample_transactions: List[dict] = []
    
    # Validation results
    duplicate_count: int = 0
    new_count: int = 0
    
    # Continuity check
    continuity_ok: bool = True
    continuity_message: Optional[str] = None
    last_imported_date: Optional[date] = None
    last_imported_balance: Optional[float] = None
    first_new_date: Optional[date] = None
    first_new_balance: Optional[float] = None

