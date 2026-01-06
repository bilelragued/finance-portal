"""File upload and import endpoints."""
import os
import uuid
import shutil
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.database import get_db

logger = logging.getLogger(__name__)

# ============================================
# DEBUG FLAG - Set to False to disable all debug output
# ============================================
DEBUG_UPLOAD = os.getenv("DEBUG_UPLOAD", "true").lower() == "true"

def debug_log(message: str, context: str = "UPLOAD"):
    """Print debug message if DEBUG_UPLOAD is enabled."""
    if DEBUG_UPLOAD:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}][{context}] {message}")
from app.models import Account, Transaction, ImportLog, TransactionClassification, AccountType
from app.schemas import (
    UploadPreview, UploadResult, FileUploadInfo, 
    AccountResponse, AccountCreate
)
from app.services.excel_parser import ExcelParser, parse_excel_file
from app.services.categorizer import TransactionCategorizer

router = APIRouter(prefix="/upload", tags=["upload"])

# Temporary upload directory - use /tmp for serverless compatibility
import tempfile
UPLOAD_DIR = Path(tempfile.gettempdir()) / "finance_uploads"
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
    start_time = time.time()
    debug_log(f"=== PREVIEW START === File: {file.filename}", "PREVIEW")

    if not file.filename.endswith(('.xlsx', '.xls')):
        debug_log(f"ERROR: Invalid file type: {file.filename}", "PREVIEW")
        raise HTTPException(
            status_code=400,
            detail="Only Excel files (.xlsx, .xls) are supported"
        )

    # Generate unique file ID and save temporarily
    file_id = str(uuid.uuid4())
    temp_path = get_temp_file_path(file_id)
    debug_log(f"Generated file_id: {file_id}", "PREVIEW")
    debug_log(f"Temp path: {temp_path}", "PREVIEW")

    try:
        # Save uploaded file
        save_start = time.time()
        debug_log(f"Saving uploaded file...", "PREVIEW")
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        file_size = temp_path.stat().st_size
        debug_log(f"File saved: {file_size:,} bytes in {time.time()-save_start:.2f}s", "PREVIEW")

        # Parse the file
        parse_start = time.time()
        debug_log(f"Creating ExcelParser...", "PREVIEW")
        parser = ExcelParser(str(temp_path))
        debug_log(f"Loading Excel file...", "PREVIEW")
        parser.load()
        debug_log(f"Excel loaded in {time.time()-parse_start:.2f}s", "PREVIEW")

        debug_log(f"Validating headers...", "PREVIEW")
        valid, missing = parser.validate_headers()
        if not valid:
            debug_log(f"ERROR: Invalid headers, missing: {missing}", "PREVIEW")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file format. Missing columns: {missing}"
            )
        debug_log(f"Headers valid ✓", "PREVIEW")

        # Get file info and transactions
        debug_log(f"Parsing filename: {file.filename}", "PREVIEW")
        file_info = parser.parse_filename_string(file.filename)
        file_info["raw_filename"] = file.filename
        debug_log(f"Account number from filename: {file_info.get('account_number')}", "PREVIEW")

        trans_start = time.time()
        debug_log(f"Parsing transactions...", "PREVIEW")
        transactions = parser.parse_transactions()
        debug_log(f"Parsed {len(transactions)} transactions in {time.time()-trans_start:.2f}s", "PREVIEW")
        parser.close()
        
        if not transactions:
            debug_log(f"ERROR: No transactions found in file", "PREVIEW")
            raise HTTPException(
                status_code=400,
                detail="No valid transactions found in file"
            )

        # Sort by date
        debug_log(f"Sorting transactions by date...", "PREVIEW")
        transactions.sort(key=lambda x: x["transaction_date"])
        debug_log(f"Date range: {transactions[0]['transaction_date']} to {transactions[-1]['transaction_date']}", "PREVIEW")
        
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
            debug_log(f"Checking for duplicates against existing account...", "PREVIEW")
            dup_start = time.time()
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
            debug_log(f"Duplicate check complete in {time.time()-dup_start:.2f}s: {duplicate_count} duplicates, {new_count} new", "PREVIEW")
        
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
        
        total_time = time.time() - start_time
        debug_log(f"=== PREVIEW COMPLETE === {len(transactions)} transactions, {new_count} new, {duplicate_count} duplicates in {total_time:.2f}s", "PREVIEW")

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
    start_time = time.time()
    debug_log(f"=== CONFIRM START === file_id: {file_id}", "CONFIRM")
    debug_log(f"account_id: {account_id}, auto_categorize: {auto_categorize}", "CONFIRM")
    debug_log(f"create_account: {create_account}", "CONFIRM")

    temp_path = get_temp_file_path(file_id)
    debug_log(f"Looking for temp file at: {temp_path}", "CONFIRM")

    if not temp_path.exists():
        debug_log(f"ERROR: Temp file not found!", "CONFIRM")
        raise HTTPException(
            status_code=404,
            detail="Upload session expired. Please upload the file again."
        )
    debug_log(f"Temp file exists, size: {temp_path.stat().st_size:,} bytes", "CONFIRM")
    
    try:
        # Get or create account
        account_start = time.time()
        debug_log(f"Getting/creating account...", "CONFIRM")
        if account_id:
            debug_log(f"Looking up account_id: {account_id}", "CONFIRM")
            account = db.query(Account).filter(Account.id == account_id).first()
            if not account:
                debug_log(f"ERROR: Account not found", "CONFIRM")
                raise HTTPException(status_code=404, detail="Account not found")
            debug_log(f"Found account: {account.name} in {time.time()-account_start:.2f}s", "CONFIRM")
        elif create_account:
            debug_log(f"Creating new account: {create_account.account_number}", "CONFIRM")
            # Check if account number already exists
            existing = db.query(Account).filter(
                Account.account_number == create_account.account_number
            ).first()

            if existing:
                debug_log(f"ERROR: Account already exists", "CONFIRM")
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
            debug_log(f"Account created with id: {account.id} in {time.time()-account_start:.2f}s", "CONFIRM")
        else:
            debug_log(f"ERROR: No account_id or create_account provided", "CONFIRM")
            raise HTTPException(
                status_code=400,
                detail="Must provide either account_id or create_account"
            )

        # Parse transactions
        parse_start = time.time()
        debug_log(f"Parsing Excel file...", "CONFIRM")
        summary, transactions = parse_excel_file(str(temp_path))
        debug_log(f"Parsed {len(transactions)} transactions in {time.time()-parse_start:.2f}s", "CONFIRM")

        # Determine default classification based on account type
        if account.account_type == AccountType.BUSINESS:
            default_classification = TransactionClassification.BUSINESS
        else:
            default_classification = TransactionClassification.PERSONAL
        debug_log(f"Default classification: {default_classification.value}", "CONFIRM")

        # Generate batch ID
        batch_id = str(uuid.uuid4())[:8]
        debug_log(f"Batch ID: {batch_id}", "CONFIRM")

        # Import transactions, checking for duplicates
        new_count = 0
        duplicate_count = 0
        import_start = time.time()
        debug_log(f"Starting transaction import loop for {len(transactions)} transactions...", "CONFIRM")

        for i, trans_data in enumerate(transactions):
            if i % 50 == 0:
                elapsed = time.time() - import_start
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                debug_log(f"Processing transaction {i+1}/{len(transactions)} ({rate:.1f}/sec)...", "CONFIRM")
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

        import_elapsed = time.time() - import_start
        debug_log(f"Import loop complete in {import_elapsed:.2f}s: {new_count} new, {duplicate_count} duplicates", "CONFIRM")

        # Create import log
        debug_log(f"Creating import log...", "CONFIRM")
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
        commit_start = time.time()
        db.commit()
        debug_log(f"Database commit complete in {time.time()-commit_start:.2f}s", "CONFIRM")

        # Auto-categorize new transactions using learned rules
        if auto_categorize and new_count > 0:
            cat_start = time.time()
            debug_log(f"Starting auto-categorization for {new_count} transactions...", "CONFIRM")
            try:
                categorizer = TransactionCategorizer(db, use_llm=False)  # Rules only for speed
                new_transactions = db.query(Transaction).filter(
                    Transaction.import_batch_id == batch_id
                ).all()

                categorized_count = 0
                for trans in new_transactions:
                    rule = categorizer.find_matching_rule(trans)
                    if rule and rule.confidence >= 0.8:
                        trans.classification = rule.classification
                        trans.category_id = rule.category_id
                        trans.is_reviewed = True
                        rule.times_applied += 1
                        categorized_count += 1

                db.commit()
                debug_log(f"Auto-categorization complete in {time.time()-cat_start:.2f}s: {categorized_count} categorized", "CONFIRM")
            except Exception as e:
                debug_log(f"Auto-categorization error (non-fatal): {e}", "CONFIRM")
                logger.warning(f"Auto-categorization error (non-fatal): {e}")
        else:
            debug_log(f"Skipping auto-categorization (auto_categorize={auto_categorize}, new_count={new_count})", "CONFIRM")

        # Clean up temp file
        debug_log(f"Cleaning up temp file...", "CONFIRM")
        os.remove(temp_path)

        total_time = time.time() - start_time
        debug_log(f"=== CONFIRM COMPLETE === {new_count} new, {duplicate_count} duplicates in {total_time:.2f}s", "CONFIRM")

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
    debug_log(f"Cancel request for file_id: {file_id}", "CANCEL")
    temp_path = get_temp_file_path(file_id)

    if temp_path.exists():
        file_size = temp_path.stat().st_size
        os.remove(temp_path)
        debug_log(f"Removed temp file ({file_size:,} bytes)", "CANCEL")
        return {"message": "Upload cancelled and temporary file removed"}

    debug_log(f"No temp file found at: {temp_path}", "CANCEL")
    return {"message": "No temporary file found"}


@router.get("/history")
def get_import_history(
    account_id: Optional[int] = None,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get import history."""
    start_time = time.time()
    debug_log(f"Fetching import history (account_id={account_id}, limit={limit})", "HISTORY")

    query = db.query(ImportLog).order_by(ImportLog.imported_at.desc())

    if account_id:
        query = query.filter(ImportLog.account_id == account_id)

    logs = query.limit(limit).all()
    debug_log(f"Found {len(logs)} import logs in {time.time()-start_time:.2f}s", "HISTORY")

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

