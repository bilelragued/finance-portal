"""
LLM-powered transaction categorization service.

This service handles:
1. Auto-categorization of transactions using LLM
2. Learning from user feedback
3. Applying learned merchant rules
4. Two-stage classification for business accounts (Personal/Business → Category)
"""
import os
import json
import re
import logging
from typing import Optional, List, Dict, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import (
    Transaction, Category, MerchantRule, Account,
    TransactionClassification, AccountType
)

logger = logging.getLogger(__name__)


class TransactionCategorizer:
    """
    Intelligent transaction categorization with learning capabilities.
    
    Supports:
    - Anthropic Claude API (default)
    - OpenAI API (GPT-4/3.5)
    - Rule-based fallback
    """
    
    def __init__(self, db: Session, use_llm: bool = True, llm_provider: str = "claude"):
        self.db = db
        self.use_llm = use_llm
        self.llm_provider = llm_provider
        self.anthropic_client = None
        self.openai_client = None
        
        # Initialize LLM client based on provider
        if use_llm:
            if llm_provider == "claude":
                self._init_anthropic()
            elif llm_provider == "openai":
                self._init_openai()
    
    def _init_anthropic(self):
        """Initialize Anthropic Claude client if API key is available."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            try:
                from anthropic import Anthropic
                self.anthropic_client = Anthropic(api_key=api_key)
            except ImportError:
                logger.warning("Anthropic package not installed. Install with: pip install anthropic")
                self.use_llm = False
        else:
            logger.info("ANTHROPIC_API_KEY not set. LLM categorization disabled.")
            self.use_llm = False
    
    def _init_openai(self):
        """Initialize OpenAI client if API key is available."""
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=api_key)
            except ImportError:
                logger.warning("OpenAI package not installed. Install with: pip install openai")
                self.use_llm = False
        else:
            logger.info("OPENAI_API_KEY not set. LLM categorization disabled.")
            self.use_llm = False
    
    def get_categories(self) -> List[Dict]:
        """Get all categories from database."""
        categories = self.db.query(Category).all()
        return [
            {
                "id": cat.id,
                "name": cat.name,
                "icon": cat.icon,
                "is_income": cat.is_income
            }
            for cat in categories
        ]
    
    def find_matching_rule(self, transaction: Transaction) -> Optional[MerchantRule]:
        """
        Find a matching merchant rule for the transaction.
        
        Checks:
        1. Exact merchant name match
        2. Contains match
        3. Pattern match with context (amount, day of week, etc.)
        """
        merchant = transaction.details or ""
        
        # Get all rules, ordered by specificity (more conditions = more specific)
        rules = self.db.query(MerchantRule).order_by(
            MerchantRule.confidence.desc()
        ).all()
        
        for rule in rules:
            if self._rule_matches(rule, transaction):
                return rule
        
        return None
    
    def _rule_matches(self, rule: MerchantRule, transaction: Transaction) -> bool:
        """Check if a rule matches a transaction."""
        merchant = (transaction.details or "").lower()
        pattern = rule.merchant_pattern.lower()
        
        # Check merchant pattern
        if rule.match_type == "exact":
            if merchant != pattern:
                return False
        elif rule.match_type == "contains":
            if pattern not in merchant:
                return False
        elif rule.match_type == "startswith":
            if not merchant.startswith(pattern):
                return False
        elif rule.match_type == "regex":
            if not re.search(pattern, merchant, re.IGNORECASE):
                return False
        else:  # default to contains
            if pattern not in merchant:
                return False
        
        # Check optional context conditions
        if rule.account_type:
            account = self.db.query(Account).filter(
                Account.id == transaction.account_id
            ).first()
            if account and account.account_type != rule.account_type:
                return False
        
        if rule.min_amount is not None:
            if abs(transaction.amount) < rule.min_amount:
                return False
        
        if rule.max_amount is not None:
            if abs(transaction.amount) > rule.max_amount:
                return False
        
        if rule.day_of_week:
            trans_day = transaction.transaction_date.strftime("%A").lower()
            if rule.day_of_week == "weekend":
                if trans_day not in ["saturday", "sunday"]:
                    return False
            elif rule.day_of_week == "weekday":
                if trans_day in ["saturday", "sunday"]:
                    return False
            elif trans_day != rule.day_of_week.lower():
                return False
        
        return True
    
    def categorize_transaction(
        self, 
        transaction: Transaction,
        force_llm: bool = False
    ) -> Dict:
        """
        Categorize a single transaction.
        
        Returns:
        {
            "classification": "personal" | "business",
            "category_id": int | None,
            "category_name": str | None,
            "confidence": float,
            "source": "rule" | "llm" | "default",
            "explanation": str
        }
        """
        # Get account info
        account = self.db.query(Account).filter(
            Account.id == transaction.account_id
        ).first()
        
        is_business_account = account and account.account_type == AccountType.BUSINESS
        
        # Step 1: Check for matching learned rules
        if not force_llm:
            rule = self.find_matching_rule(transaction)
            if rule and rule.confidence >= 0.8:
                return {
                    "classification": rule.classification.value,
                    "category_id": rule.category_id,
                    "category_name": rule.category.name if rule.category else None,
                    "confidence": rule.confidence,
                    "source": "rule",
                    "explanation": f"Matched rule: '{rule.merchant_pattern}'"
                }
        
        # Step 2: Use LLM if available
        if self.use_llm:
            if self.anthropic_client:
                return self._categorize_with_claude(transaction, is_business_account)
            elif self.openai_client:
                return self._categorize_with_openai(transaction, is_business_account)
        
        # Step 3: Fallback to basic rules
        return self._categorize_with_basic_rules(transaction, is_business_account)
    
    def categorize_with_rules_only(self, transaction: Transaction) -> Dict:
        """
        Fast categorization using only learned rules and basic pattern matching.
        Does NOT call LLM - use this for bulk operations.
        
        Returns:
        {
            "classification": "personal" | "business",
            "category_id": int | None,
            "category_name": str | None,
            "confidence": float,
            "source": "rule" | "basic" | "none",
            "explanation": str
        }
        """
        # Get account info
        account = self.db.query(Account).filter(
            Account.id == transaction.account_id
        ).first()
        
        is_business_account = account and account.account_type == AccountType.BUSINESS
        
        # Check for matching learned rules
        rule = self.find_matching_rule(transaction)
        if rule:
            return {
                "classification": rule.classification.value,
                "category_id": rule.category_id,
                "category_name": rule.category.name if rule.category else None,
                "confidence": rule.confidence,
                "source": "rule",
                "explanation": f"Matched rule: '{rule.merchant_pattern}'"
            }
        
        # Use basic keyword matching
        result = self._categorize_with_basic_rules(transaction, is_business_account)
        if result["category_id"]:
            return result
        
        # No match - return empty suggestion with low confidence
        default_classification = "personal" if not is_business_account else "business"
        return {
            "classification": default_classification,
            "category_id": None,
            "category_name": None,
            "confidence": 0.0,
            "source": "none",
            "explanation": "No matching rules. Click 'Get AI Suggestion' for smart categorization."
        }
    
    def _build_categorization_prompt(self, transaction: Transaction, is_business_account: bool) -> tuple:
        """Build the system and user prompts for categorization."""
        categories = self.get_categories()
        category_list = "\n".join([
            f"- {cat['name']} (ID: {cat['id']}, {'Income' if cat['is_income'] else 'Expense'})"
            for cat in categories
        ])
        
        # Build context
        context = {
            "date": transaction.transaction_date.isoformat(),
            "day_of_week": transaction.transaction_date.strftime("%A"),
            "merchant": transaction.details or "Unknown",
            "type": transaction.transaction_type,
            "amount": transaction.amount,
            "particulars": transaction.particulars,
            "code": transaction.code,
            "reference": transaction.reference,
            "is_business_account": is_business_account
        }
        
        system_prompt = """You are a financial transaction categorizer. Your job is to:
1. Determine if a transaction is PERSONAL or BUSINESS (especially important for business accounts)
2. Assign the most appropriate spending category

Context clues for Personal vs Business:
- Restaurants on evenings/weekends → likely Personal (family dining)
- Hardware stores (Bunnings, Mitre 10) → likely Personal (home renovation)
- Office supplies during work hours → likely Business
- Subscriptions can be either - use your judgment based on the service name

Be conservative: if unsure whether something from a business account is personal, default to BUSINESS.

You MUST respond with ONLY valid JSON, no other text."""

        user_prompt = f"""Categorize this transaction:

Transaction Details:
- Date: {context['date']} ({context['day_of_week']})
- Merchant/Details: {context['merchant']}
- Type: {context['type']}
- Amount: ${abs(context['amount']):.2f} ({'debit' if context['amount'] < 0 else 'credit'})
- Particulars: {context['particulars'] or 'N/A'}
- Code: {context['code'] or 'N/A'}
- Reference: {context['reference'] or 'N/A'}
- Account Type: {'BUSINESS' if is_business_account else 'PERSONAL'}

Available Categories:
{category_list}

Respond with ONLY this JSON structure (no other text):
{{
    "classification": "personal" or "business",
    "category_id": <category ID number>,
    "category_name": "<category name>",
    "confidence": <0.0 to 1.0>,
    "explanation": "<brief explanation>"
}}"""
        
        return system_prompt, user_prompt
    
    def _categorize_with_claude(
        self, 
        transaction: Transaction,
        is_business_account: bool
    ) -> Dict:
        """Use Claude to categorize transaction."""
        system_prompt, user_prompt = self._build_categorization_prompt(transaction, is_business_account)

        try:
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",  # Latest Claude model
                max_tokens=300,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            # Extract text from response
            response_text = response.content[0].text.strip()
            
            # Parse JSON from response (handle potential markdown code blocks)
            if response_text.startswith("```"):
                # Remove markdown code block
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])
            
            result = json.loads(response_text)
            
            return {
                "classification": result.get("classification", "personal"),
                "category_id": result.get("category_id"),
                "category_name": result.get("category_name"),
                "confidence": result.get("confidence", 0.7),
                "source": "llm",
                "explanation": result.get("explanation", "Categorized by Claude")
            }
            
        except Exception as e:
            logger.error(f"Claude categorization error: {e}")
            return self._categorize_with_basic_rules(transaction, is_business_account)
    
    def _categorize_with_openai(
        self, 
        transaction: Transaction,
        is_business_account: bool
    ) -> Dict:
        """Use OpenAI to categorize transaction."""
        system_prompt, user_prompt = self._build_categorization_prompt(transaction, is_business_account)

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Cost-effective model
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=200
            )
            
            result = json.loads(response.choices[0].message.content)
            
            return {
                "classification": result.get("classification", "personal"),
                "category_id": result.get("category_id"),
                "category_name": result.get("category_name"),
                "confidence": result.get("confidence", 0.7),
                "source": "llm",
                "explanation": result.get("explanation", "Categorized by GPT")
            }
            
        except Exception as e:
            logger.error(f"OpenAI categorization error: {e}")
            return self._categorize_with_basic_rules(transaction, is_business_account)
    
    def _categorize_with_basic_rules(
        self, 
        transaction: Transaction,
        is_business_account: bool
    ) -> Dict:
        """Fallback categorization using basic keyword matching."""
        details = (transaction.details or "").lower()
        trans_type = (transaction.transaction_type or "").lower()
        
        # Default classification
        classification = "business" if is_business_account else "personal"
        category_id = None
        category_name = None
        confidence = 0.5
        explanation = "Default classification"
        
        # Basic keyword rules for common NZ merchants/types
        keyword_rules = [
            # Food & Dining
            (["restaurant", "cafe", "coffee", "mcdonald", "burger", "pizza", "sushi", 
              "thai", "indian", "chinese", "kebab", "subway", "kfc", "nando"], 
             "Food & Dining", False),
            
            # Groceries
            (["countdown", "new world", "pak n save", "paknsave", "supermarket", 
              "fresh choice", "four square", "woolworths"], 
             "Groceries", False),
            
            # Transport
            (["bp", "z energy", "mobil", "caltex", "gull", "fuel", "petrol", 
              "uber", "taxi", "parking", "parkable", "wilson parking", "auckland transport",
              "at hop", "snapper"], 
             "Transport", False),
            
            # Home & Garden
            (["bunnings", "mitre 10", "mitre10", "placemakers", "hammer hardware"], 
             "Home & Garden", True),  # Mark as personal for business accounts
            
            # Utilities
            (["power", "electricity", "gas", "water", "internet", "spark", "vodafone", 
              "2degrees", "one nz", "chorus"], 
             "Utilities", False),
            
            # Entertainment
            (["netflix", "spotify", "disney", "amazon prime", "youtube", "cinema", 
              "event", "ticketmaster", "imax"], 
             "Entertainment", True),
            
            # Shopping
            (["amazon", "ebay", "trademe", "kmart", "the warehouse", "farmers", 
              "briscoes", "rebel sport", "jb hi-fi"], 
             "Shopping", False),
            
            # Bank Fees
            (["bank fee", "account fee", "overdraft", "monthly fee"], 
             "Bank Fees", False),
        ]
        
        for keywords, cat_name, force_personal in keyword_rules:
            if any(kw in details for kw in keywords):
                # Find category
                category = self.db.query(Category).filter(
                    Category.name == cat_name
                ).first()
                
                if category:
                    category_id = category.id
                    category_name = cat_name
                    confidence = 0.7
                    explanation = f"Matched keyword in merchant name"
                    
                    if force_personal and is_business_account:
                        classification = "personal"
                        explanation += " (typically personal expense)"
                    
                    break
        
        # Check transaction type for income
        if trans_type in ["direct credit", "payment received", "salary", "wages"]:
            classification = "personal"
            category = self.db.query(Category).filter(
                Category.name == "Salary"
            ).first()
            if category:
                category_id = category.id
                category_name = "Salary"
                confidence = 0.9
                explanation = "Income transaction"
        
        return {
            "classification": classification,
            "category_id": category_id,
            "category_name": category_name,
            "confidence": confidence,
            "source": "default",
            "explanation": explanation
        }
    
    def learn_from_feedback(
        self,
        transaction: Transaction,
        classification: TransactionClassification,
        category_id: Optional[int],
        user_confirmed: bool = True
    ) -> Optional[MerchantRule]:
        """
        Learn from user feedback and create/update merchant rules.
        
        This is called when a user corrects or confirms a categorization.
        """
        if not transaction.details:
            return None
        
        merchant = transaction.details.strip()
        
        # Check if a rule already exists for this merchant
        existing_rule = self.db.query(MerchantRule).filter(
            MerchantRule.merchant_pattern == merchant,
            MerchantRule.match_type == "exact"
        ).first()
        
        if existing_rule:
            # Update existing rule
            if user_confirmed:
                existing_rule.times_applied += 1
                # Increase confidence if consistently confirmed
                if existing_rule.classification == classification:
                    existing_rule.confidence = min(1.0, existing_rule.confidence + 0.05)
                else:
                    # User overrode - decrease confidence and update
                    existing_rule.times_overridden += 1
                    existing_rule.confidence = max(0.3, existing_rule.confidence - 0.1)
                    existing_rule.classification = classification
                    existing_rule.category_id = category_id
            
            self.db.commit()
            return existing_rule
        
        # Create new rule
        # Determine match type - for common merchants, use contains
        match_type = "exact"
        pattern = merchant
        
        # Simplify pattern for chain stores (remove location identifiers)
        chain_patterns = [
            (r"countdown\s+\w+", "Countdown"),
            (r"new world\s+\w+", "New World"),
            (r"pak.?n.?save\s+\w+", "Pak n Save"),
            (r"bp\s+\w+", "BP"),
            (r"z\s+\w+", "Z "),
            (r"bunnings\s+\w+", "Bunnings"),
        ]
        
        for regex, simplified in chain_patterns:
            if re.search(regex, merchant, re.IGNORECASE):
                pattern = simplified
                match_type = "contains"
                break
        
        new_rule = MerchantRule(
            merchant_pattern=pattern,
            match_type=match_type,
            classification=classification,
            category_id=category_id,
            confidence=0.8 if user_confirmed else 0.6,
            times_applied=1,
            times_overridden=0
        )
        
        self.db.add(new_rule)
        self.db.commit()
        self.db.refresh(new_rule)
        
        return new_rule
    
    def categorize_batch(
        self,
        transactions: List[Transaction],
        apply_rules_only: bool = False
    ) -> List[Dict]:
        """
        Categorize multiple transactions.
        
        If apply_rules_only=True, only uses learned rules (faster, no LLM calls).
        """
        results = []
        
        for trans in transactions:
            if apply_rules_only:
                rule = self.find_matching_rule(trans)
                if rule:
                    results.append({
                        "transaction_id": trans.id,
                        "classification": rule.classification.value,
                        "category_id": rule.category_id,
                        "category_name": rule.category.name if rule.category else None,
                        "confidence": rule.confidence,
                        "source": "rule"
                    })
                else:
                    results.append({
                        "transaction_id": trans.id,
                        "classification": None,
                        "category_id": None,
                        "category_name": None,
                        "confidence": 0,
                        "source": "none"
                    })
            else:
                result = self.categorize_transaction(trans)
                result["transaction_id"] = trans.id
                results.append(result)
        
        return results
    
    def get_uncategorized_transactions(
        self,
        account_id: Optional[int] = None,
        limit: int = 50
    ) -> List[Transaction]:
        """Get transactions that need categorization."""
        query = self.db.query(Transaction).filter(
            Transaction.is_reviewed == False
        )
        
        if account_id:
            query = query.filter(Transaction.account_id == account_id)
        
        return query.order_by(
            Transaction.transaction_date.desc()
        ).limit(limit).all()
    
    def get_rule_statistics(self) -> Dict:
        """Get statistics about learned rules."""
        rules = self.db.query(MerchantRule).all()
        
        total_rules = len(rules)
        high_confidence = len([r for r in rules if r.confidence >= 0.8])
        total_applied = sum(r.times_applied for r in rules)
        total_overridden = sum(r.times_overridden for r in rules)
        
        return {
            "total_rules": total_rules,
            "high_confidence_rules": high_confidence,
            "total_times_applied": total_applied,
            "total_times_overridden": total_overridden,
            "accuracy_rate": (total_applied - total_overridden) / total_applied if total_applied > 0 else 0
        }

