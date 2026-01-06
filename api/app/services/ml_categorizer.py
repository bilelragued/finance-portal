"""
Local ML-based transaction categorization service.

This service:
1. Trains on user-confirmed categorizations
2. Predicts categories for new transactions
3. Runs automatically after each user categorization
4. Saves/loads model to disk for persistence
"""
import os
import re
import logging
import pickle
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import Transaction, Category, TransactionClassification

logger = logging.getLogger(__name__)

# Model storage path
MODEL_DIR = Path(__file__).parent.parent.parent / "data" / "models"
MODEL_PATH = MODEL_DIR / "transaction_classifier.pkl"
VECTORIZER_PATH = MODEL_DIR / "text_vectorizer.pkl"


class MLCategorizer:
    """
    Local ML categorizer using scikit-learn.
    
    Features used:
    - Merchant name (TF-IDF vectorized)
    - Transaction type
    - Amount (binned)
    - Day of week
    - Hour of day (if available)
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.model = None
        self.vectorizer = None
        self.category_encoder = None
        self.classification_encoder = None
        self._load_model()
    
    def _load_model(self):
        """Load saved model from disk if exists."""
        try:
            if MODEL_PATH.exists() and VECTORIZER_PATH.exists():
                with open(MODEL_PATH, 'rb') as f:
                    model_data = pickle.load(f)
                    self.model = model_data.get('model')
                    self.category_encoder = model_data.get('category_encoder')
                    self.classification_encoder = model_data.get('classification_encoder')
                
                with open(VECTORIZER_PATH, 'rb') as f:
                    self.vectorizer = pickle.load(f)
                
                logger.info("ML model loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load ML model: {e}")
            self.model = None
    
    def _save_model(self):
        """Save model to disk."""
        try:
            MODEL_DIR.mkdir(parents=True, exist_ok=True)
            
            with open(MODEL_PATH, 'wb') as f:
                pickle.dump({
                    'model': self.model,
                    'category_encoder': self.category_encoder,
                    'classification_encoder': self.classification_encoder
                }, f)
            
            with open(VECTORIZER_PATH, 'wb') as f:
                pickle.dump(self.vectorizer, f)
            
            logger.info("ML model saved successfully")
        except Exception as e:
            logger.error(f"Could not save ML model: {e}")
    
    def _extract_merchant_name(self, transaction: Transaction) -> str:
        """Extract clean merchant name from transaction."""
        # Priority: code > details > particulars
        text = transaction.code or transaction.details or transaction.particulars or ""
        
        # Clean up common patterns
        text = text.lower().strip()
        
        # Remove card numbers
        text = re.sub(r'\d{4}[-*]+\d{4}[-*]+\d{4}', '', text)
        text = re.sub(r'\*+\d+', '', text)
        
        # Remove common suffixes
        text = re.sub(r'\s+(nz|ltd|limited|inc|pty|co)\s*$', '', text, flags=re.IGNORECASE)
        
        return text.strip()
    
    def _extract_features(self, transaction: Transaction) -> Dict:
        """Extract features from a transaction."""
        merchant = self._extract_merchant_name(transaction)
        
        # Amount bin
        amount = abs(transaction.amount)
        if amount < 10:
            amount_bin = "tiny"
        elif amount < 50:
            amount_bin = "small"
        elif amount < 100:
            amount_bin = "medium"
        elif amount < 500:
            amount_bin = "large"
        else:
            amount_bin = "xlarge"
        
        # Day of week
        day_of_week = transaction.transaction_date.weekday()
        is_weekend = day_of_week >= 5
        
        return {
            "merchant": merchant,
            "transaction_type": (transaction.transaction_type or "").lower(),
            "amount_bin": amount_bin,
            "day_of_week": day_of_week,
            "is_weekend": is_weekend,
            "is_debit": transaction.amount < 0,
        }
    
    def _prepare_text_features(self, transactions: List[Transaction]) -> List[str]:
        """Prepare text features for vectorization."""
        texts = []
        for t in transactions:
            features = self._extract_features(t)
            # Combine all text features
            text = f"{features['merchant']} {features['transaction_type']} {features['amount_bin']}"
            if features['is_weekend']:
                text += " weekend"
            texts.append(text)
        return texts
    
    def train(self, min_samples: int = 20) -> Dict:
        """
        Train the ML model on user-confirmed transactions.
        
        Returns training statistics.
        """
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.preprocessing import LabelEncoder
            from sklearn.model_selection import cross_val_score
        except ImportError:
            logger.error("scikit-learn not installed. Run: pip install scikit-learn")
            return {"error": "scikit-learn not installed"}
        
        # Get user-confirmed transactions for training
        confirmed = self.db.query(Transaction).filter(
            Transaction.is_user_confirmed == True,
            Transaction.category_id.isnot(None)
        ).all()
        
        if len(confirmed) < min_samples:
            return {
                "error": f"Not enough training data. Need {min_samples}, have {len(confirmed)}",
                "samples": len(confirmed)
            }
        
        # Prepare features
        texts = self._prepare_text_features(confirmed)
        
        # Prepare labels (category_id)
        category_ids = [t.category_id for t in confirmed]
        
        # Encode labels
        self.category_encoder = LabelEncoder()
        y = self.category_encoder.fit_transform(category_ids)
        
        # Vectorize text
        self.vectorizer = TfidfVectorizer(
            max_features=500,
            ngram_range=(1, 2),
            min_df=2
        )
        X = self.vectorizer.fit_transform(texts)
        
        # Train model
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1
        )
        self.model.fit(X, y)
        
        # Calculate accuracy with cross-validation
        try:
            scores = cross_val_score(self.model, X, y, cv=min(5, len(confirmed) // 5))
            accuracy = scores.mean()
        except:
            accuracy = 0.0
        
        # Save model
        self._save_model()
        
        return {
            "success": True,
            "samples": len(confirmed),
            "categories": len(set(category_ids)),
            "accuracy": round(accuracy, 3)
        }
    
    def predict(self, transaction: Transaction) -> Optional[Dict]:
        """
        Predict category for a single transaction.
        
        Returns:
        {
            "category_id": int,
            "category_name": str,
            "confidence": float,
            "source": "ml"
        }
        """
        if self.model is None or self.vectorizer is None:
            return None
        
        try:
            text = self._prepare_text_features([transaction])[0]
            X = self.vectorizer.transform([text])
            
            # Get prediction and probability
            pred = self.model.predict(X)[0]
            proba = self.model.predict_proba(X)[0]
            confidence = float(max(proba))
            
            # Decode category
            category_id = int(self.category_encoder.inverse_transform([pred])[0])
            
            # Get category name
            category = self.db.query(Category).filter(Category.id == category_id).first()
            
            return {
                "category_id": category_id,
                "category_name": category.name if category else None,
                "confidence": confidence,
                "source": "ml"
            }
        except Exception as e:
            logger.error(f"ML prediction error: {e}")
            return None
    
    def predict_batch(self, transactions: List[Transaction]) -> List[Optional[Dict]]:
        """Predict categories for multiple transactions."""
        if self.model is None or self.vectorizer is None:
            return [None] * len(transactions)
        
        try:
            texts = self._prepare_text_features(transactions)
            X = self.vectorizer.transform(texts)
            
            preds = self.model.predict(X)
            probas = self.model.predict_proba(X)
            
            results = []
            for i, (pred, proba) in enumerate(zip(preds, probas)):
                confidence = float(max(proba))
                category_id = int(self.category_encoder.inverse_transform([pred])[0])
                category = self.db.query(Category).filter(Category.id == category_id).first()
                
                results.append({
                    "category_id": category_id,
                    "category_name": category.name if category else None,
                    "confidence": confidence,
                    "source": "ml"
                })
            
            return results
        except Exception as e:
            logger.error(f"ML batch prediction error: {e}")
            return [None] * len(transactions)
    
    def auto_categorize_pending(
        self, 
        min_confidence: float = 0.7,
        apply: bool = False
    ) -> Dict:
        """
        Auto-categorize pending transactions with ML predictions.
        
        Only updates transactions where:
        - is_user_confirmed = False
        - categorization_source != "user"
        
        Returns stats on what was (or would be) updated.
        """
        # Get pending transactions
        pending = self.db.query(Transaction).filter(
            Transaction.is_user_confirmed == False,
            Transaction.category_id.is_(None)
        ).all()
        
        if not pending:
            return {"pending": 0, "would_update": 0, "updated": 0}
        
        predictions = self.predict_batch(pending)
        
        would_update = 0
        updated = 0
        
        for trans, pred in zip(pending, predictions):
            if pred and pred["confidence"] >= min_confidence:
                would_update += 1
                
                if apply:
                    trans.category_id = pred["category_id"]
                    trans.categorization_source = "ml"
                    trans.is_reviewed = False  # Still needs review
                    updated += 1
        
        if apply and updated > 0:
            self.db.commit()
        
        return {
            "pending": len(pending),
            "would_update": would_update,
            "updated": updated,
            "min_confidence": min_confidence
        }


def find_similar_transactions(
    db: Session, 
    transaction: Transaction,
    include_categorized: bool = False
) -> List[Transaction]:
    """
    Find transactions similar to the given one.
    
    Matches on:
    - Similar merchant name (code or details)
    - Same transaction type
    """
    # Extract merchant pattern
    merchant = transaction.code or transaction.details or ""
    if not merchant:
        return []
    
    # Clean and create pattern
    merchant_clean = merchant.strip()[:20]  # First 20 chars
    
    # Build query
    query = db.query(Transaction).filter(
        Transaction.id != transaction.id,
    )
    
    # Match on code or details
    if transaction.code:
        query = query.filter(Transaction.code.ilike(f"{merchant_clean}%"))
    else:
        query = query.filter(Transaction.details.ilike(f"{merchant_clean}%"))
    
    # Optionally exclude already categorized
    if not include_categorized:
        query = query.filter(
            Transaction.is_user_confirmed == False,
        )
    
    return query.limit(100).all()


def propagate_categorization(
    db: Session,
    source_transaction: Transaction,
    apply_to_similar: bool = True
) -> Dict:
    """
    After a user categorizes a transaction, propagate to similar ones.
    
    Returns stats on what was updated.
    """
    if not source_transaction.category_id:
        return {"similar_found": 0, "updated": 0}
    
    # Find similar uncategorized transactions
    similar = find_similar_transactions(db, source_transaction, include_categorized=False)
    
    if not similar:
        return {"similar_found": 0, "updated": 0}
    
    updated = 0
    if apply_to_similar:
        for trans in similar:
            # Only update if not user-confirmed
            if not trans.is_user_confirmed:
                trans.category_id = source_transaction.category_id
                trans.classification = source_transaction.classification
                trans.categorization_source = "rule"
                trans.is_reviewed = False  # Needs review
                updated += 1
        
        if updated > 0:
            db.commit()
    
    return {
        "similar_found": len(similar),
        "updated": updated
    }


