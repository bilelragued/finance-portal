"""File upload and import endpoints."""
import os
import uuid
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.database import get_db

logger = logging.getLogger(__name__)
from app.models import Account, Transaction, ImportLog, TransactionClassification, AccountType
from app.schemas import (
    UploadPreview, UploadResult, FileUploadInfo, 
    AccountResponse, AccountCreate
)
from app.services.excel_parser import ExcelParser, parse_excel_file
from app.services.categorizer import TransactionCategorizer

router = APIRouter(prefix="/upload", tags=["upload"])

# Temporary upload directory
UPLOAD_DIR = Path(__file__).parent.parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


def get_temp_file_path(file_id: str) -> Path:
    """Get path to temporary uploaded file."""
    return UPLOAD_DIR / f"{file_id}.xlsx"


@router.post("/preview", response_model=UploadPreview)
async def upload_preview(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a file and get a preview before confirming import.
    
    Returns file info, detected account, sample transactions,
    and duplicate/continuity check results.
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=400,
            detail="Only Excel files (.xlsx, .xls) are supported"
        )
    
    # Generate unique file ID and save temporarily
    file_id = str(uuid.uuid4())
    temp_path = get_temp_file_path(file_id)
    
    try:
        # Save uploaded file
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Parse the file
        parser = ExcelParser(str(temp_path))
        parser.load()
        
        valid, missing = parser.validate_headers()
        if not valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file format. Missing columns: {missing}"
            )
        
        # Get file info and transactions
        # Parse the ORIGINAL filename, not the temp file path
        file_info = parser.parse_filename_string(file.filename)
        file_info["raw_filename"] = file.filename
        transactions = parser.parse_transactions()
        parser.close()
        
        if not transactions:
            raise HTTPException(
                status_code=400,
                detail="No valid transactions found in file"
            )
        
        # Sort by date
        transactions.sort(key=lambda x: x["transaction_date"])
        
        # Build file info response
        file_info_response = FileUploadInfo(
            filename=file.filename,
            account_number=file_info.get("account_number"),
            date_from=transactions[0]["transaction_date"] if transactions else None,
            date_to=transactions[-1]["transaction_date"] if transactions else None,
            total_rows=len(transactions)
        )
        
        # Check if account exists
        existing_account = None
        suggested_account = None
        
        if file_info.get("account_number"):
            existing = db.query(Account).filter(
                Account.account_number == file_info["account_number"]
            ).first()
            
            if existing:
                trans_count = db.query(func.count(Transaction.id)).filter(
                    Transaction.account_id == existing.id
                ).scalar()
                
                existing_account = AccountResponse(
                    id=existing.id,
                    account_number=existing.account_number,
                    name=existing.name,
                    owner=existing.owner,
                    account_type=existing.account_type.value,
                    created_at=existing.created_at,
                    updated_at=existing.updated_at,
                    transaction_count=trans_count
                )
        
        # Check for duplicates if account exists
        duplicate_count = 0
        new_count = len(transactions)
        
        if existing_account:
            # Check each transaction for duplicates
            for trans in transactions:
                exists = db.query(Transaction).filter(
                    and_(
                        Transaction.account_id == existing_account.id,
                        Transaction.transaction_date == trans["transaction_date"],
                        Transaction.amount == trans["amount"],
                        Transaction.details == trans.get("details")
                    )
                ).first()
                
                if exists:
                    duplicate_count += 1
            
            new_count = len(transactions) - duplicate_count
        
        # Check balance continuity
        continuity_ok = True
        continuity_message = None
        last_imported_date = None
        last_imported_balance = None
        first_new_date = transactions[0]["transaction_date"] if transactions else None
        first_new_balance = transactions[0].get("balance") if transactions else None
        
        if existing_account:
            # Get the last imported transaction for this account
            last_trans = db.query(Transaction).filter(
                Transaction.account_id == existing_account.id
            ).order_by(Transaction.transaction_date.desc()).first()
            
            if last_trans:
                last_imported_date = last_trans.transaction_date
                last_imported_balance = last_trans.balance
                
                # Check if there's a gap
                if first_new_date and last_imported_date:
                    # Note: Balance continuity is complex because transactions are recorded
                    # after the balance changes. We'll flag if dates don't connect.
                    if first_new_date > last_imported_date:
                        # There might be a gap - check if the oldest new transaction
                        # has a balance that makes sense
                        continuity_message = (
                            f"Last imported: {last_imported_date} (balance: ${last_imported_balance:,.2f}). "
                            f"New data starts: {first_new_date}. Please verify no transactions are missing."
                        )
                        # Don't fail, just warn
                        continuity_ok = True
        
        # Prepare sample transactions (first 5)
        sample = []
        for trans in transactions[:5]:
            sample.append({
                "date": trans["transaction_date"].isoformat(),
                "type": trans.get("transaction_type", ""),
                "details": trans.get("details", ""),
                "amount": trans["amount"],
                "balance": trans.get("balance")
            })
        
        # Store file_id in filename for later retrieval
        # We'll use a simple mapping in-memory for now
        # In production, use Redis or database
        
        return UploadPreview(
            file_info=FileUploadInfo(
                filename=f"{file_id}|{file.filename}",  # Embed file_id
                account_number=file_info.get("account_number"),
                date_from=transactions[0]["transaction_date"],
                date_to=transactions[-1]["transaction_date"],
                total_rows=len(transactions)
            ),
            existing_account=existing_account,
            suggested_account=suggested_account,
            sample_transactions=sample,
            duplicate_count=duplicate_count,
            new_count=new_count,
            continuity_ok=continuity_ok,
            continuity_message=continuity_message,
            last_imported_date=last_imported_date,
            last_imported_balance=last_imported_balance,
            first_new_date=first_new_date,
            first_new_balance=first_new_balance
        )
        
    except HTTPException:
        # Clean up temp file on error
        if temp_path.exists():
            os.remove(temp_path)
        raise
    except Exception as e:
        # Clean up temp file on error
        if temp_path.exists():
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@router.post("/confirm", response_model=UploadResult)
async def confirm_upload(
    file_id: str = Query(..., description="File ID from preview"),
    account_id: Optional[int] = Query(None, description="Existing account ID"),
    auto_categorize: bool = Query(True, description="Auto-apply learned rules"),
    create_account: Optional[AccountCreate] = Body(None, description="New account details"),
    db: Session = Depends(get_db)
):
    """
    Confirm and process the uploaded file.
    
    Either provide account_id for existing account,
    or create_account to create a new one.
    """
    temp_path = get_temp_file_path(file_id)
    
    if not temp_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Upload session expired. Please upload the file again."
        )
    
    try:
        # Get or create account
        if account_id:
            account = db.query(Account).filter(Account.id == account_id).first()
            if not account:
                raise HTTPException(status_code=404, detail="Account not found")
        elif create_account:
            # Check if account number already exists
            existing = db.query(Account).filter(
                Account.account_number == create_account.account_number
            ).first()
            
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Account {create_account.account_number} already exists"
                )
            
            account = Account(
                account_number=create_account.account_number,
                name=create_account.name,
                owner=create_account.owner,
                account_type=AccountType(create_account.account_type.value)
            )
            db.add(account)
            db.commit()
            db.refresh(account)
        else:
            raise HTTPException(
                status_code=400,
                detail="Must provide either account_id or create_account"
            )
        
        # Parse transactions
        summary, transactions = parse_excel_file(str(temp_path))
        
        # Determine default classification based on account type
        if account.account_type == AccountType.BUSINESS:
            default_classification = TransactionClassification.BUSINESS
        else:
            default_classification = TransactionClassification.PERSONAL
        
        # Generate batch ID
        batch_id = str(uuid.uuid4())[:8]
        
        # Import transactions, checking for duplicates
        new_count = 0
        duplicate_count = 0
        
        for trans_data in transactions:
            # Check for duplicate
            existing = db.query(Transaction).filter(
                and_(
                    Transaction.account_id == account.id,
                    Transaction.transaction_date == trans_data["transaction_date"],
                    Transaction.amount == trans_data["amount"],
                    Transaction.details == trans_data.get("details")
                )
            ).first()
            
            if existing:
                duplicate_count += 1
                continue
            
            # Create new transaction
            trans = Transaction(
                account_id=account.id,
                transaction_date=trans_data["transaction_date"],
                processed_date=trans_data.get("processed_date"),
                transaction_type=trans_data.get("transaction_type"),
                details=trans_data.get("details"),
                particulars=trans_data.get("particulars"),
                code=trans_data.get("code"),
                reference=trans_data.get("reference"),
                amount=trans_data["amount"],
                balance=trans_data.get("balance"),
                to_from_account=trans_data.get("to_from_account"),
                conversion_charge=trans_data.get("conversion_charge"),
                foreign_currency_amount=trans_data.get("foreign_currency_amount"),
                card_number_last4=trans_data.get("card_number_last4"),
                classification=default_classification,
                import_batch_id=batch_id
            )
            
            db.add(trans)
            new_count += 1
        
        # Create import log
        sorted_trans = sorted(transactions, key=lambda x: x["transaction_date"])
        
        import_log = ImportLog(
            batch_id=batch_id,
            filename=temp_path.name,
            account_id=account.id,
            date_from=sorted_trans[0]["transaction_date"] if sorted_trans else None,
            date_to=sorted_trans[-1]["transaction_date"] if sorted_trans else None,
            opening_balance=sorted_trans[0].get("balance") if sorted_trans else None,
            closing_balance=sorted_trans[-1].get("balance") if sorted_trans else None,
            total_transactions=len(transactions),
            new_transactions=new_count,
            duplicate_transactions=duplicate_count,
            status="completed"
        )
        
        db.add(import_log)
        db.commit()
        
        # Auto-categorize new transactions using learned rules
        if auto_categorize and new_count > 0:
            try:
                categorizer = TransactionCategorizer(db, use_llm=False)  # Rules only for speed
                new_transactions = db.query(Transaction).filter(
                    Transaction.import_batch_id == batch_id
                ).all()
                
                for trans in new_transactions:
                    rule = categorizer.find_matching_rule(trans)
                    if rule and rule.confidence >= 0.8:
                        trans.classification = rule.classification
                        trans.category_id = rule.category_id
                        trans.is_reviewed = True
                        rule.times_applied += 1
                
                db.commit()
            except Exception as e:
                logger.warning(f"Auto-categorization error (non-fatal): {e}")
        
        # Clean up temp file
        os.remove(temp_path)
        
        return UploadResult(
            success=True,
            batch_id=batch_id,
            total_transactions=len(transactions),
            new_transactions=new_count,
            duplicate_transactions=duplicate_count,
            message=f"Successfully imported {new_count} new transactions. {duplicate_count} duplicates skipped.",
            continuity_ok=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error importing transactions: {str(e)}")
    finally:
        # Clean up temp file if it still exists
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except:
                pass


@router.delete("/cancel/{file_id}")
async def cancel_upload(file_id: str):
    """Cancel an upload and clean up temporary file."""
    temp_path = get_temp_file_path(file_id)
    
    if temp_path.exists():
        os.remove(temp_path)
        return {"message": "Upload cancelled and temporary file removed"}
    
    return {"message": "No temporary file found"}


@router.get("/history")
def get_import_history(
    account_id: Optional[int] = None,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get import history."""
    query = db.query(ImportLog).order_by(ImportLog.imported_at.desc())
    
    if account_id:
        query = query.filter(ImportLog.account_id == account_id)
    
    logs = query.limit(limit).all()
    
    return [
        {
            "id": log.id,
            "batch_id": log.batch_id,
            "filename": log.filename,
            "account_id": log.account_id,
            "date_from": log.date_from.isoformat() if log.date_from else None,
            "date_to": log.date_to.isoformat() if log.date_to else None,
            "total_transactions": log.total_transactions,
            "new_transactions": log.new_transactions,
            "duplicate_transactions": log.duplicate_transactions,
            "status": log.status,
            "imported_at": log.imported_at.isoformat()
        }
        for log in logs
    ]

