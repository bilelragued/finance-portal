"""
NLP Agent for transaction categorization and natural language querying.

This service uses Anthropic's Claude API to:
1. Match transactions to categories based on natural language descriptions
2. Parse natural language queries into structured transaction filters
3. Provide intelligent categorization suggestions
"""
import os
import json
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, date

from sqlalchemy.orm import Session
from anthropic import Anthropic

from app.models import Transaction, Category, TransactionClassification

logger = logging.getLogger(__name__)


class NLPAgent:
    """
    Natural Language Processing agent for finance portal.
    Uses Claude to understand natural language and make intelligent decisions.
    """

    def __init__(self, db: Session, api_key: Optional[str] = None):
        self.db = db
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not set. NLP features will be disabled.")
            self.client = None
        else:
            self.client = Anthropic(api_key=self.api_key)

    def is_available(self) -> bool:
        """Check if NLP agent is available (API key configured)."""
        return self.client is not None

    def _format_transaction_for_llm(self, transaction: Transaction) -> str:
        """Format a transaction into a human-readable string for the LLM."""
        parts = []

        if transaction.details:
            parts.append(f"Details: {transaction.details}")
        if transaction.code:
            parts.append(f"Code: {transaction.code}")
        if transaction.particulars:
            parts.append(f"Particulars: {transaction.particulars}")
        if transaction.transaction_type:
            parts.append(f"Type: {transaction.transaction_type}")

        parts.append(f"Amount: ${abs(transaction.amount):.2f}")
        parts.append(f"Date: {transaction.transaction_date}")

        if transaction.amount > 0:
            parts.append("(Income/Credit)")
        else:
            parts.append("(Expense/Debit)")

        return " | ".join(parts)

    def _format_categories_for_llm(self, categories: List[Category]) -> str:
        """Format categories with their NL descriptions for the LLM."""
        lines = []
        for cat in categories:
            line = f"- ID {cat.id}: {cat.name}"
            if cat.nl_description:
                line += f"\n  Description: {cat.nl_description}"
            if cat.nl_keywords:
                line += f"\n  Keywords: {cat.nl_keywords}"
            lines.append(line)
        return "\n".join(lines)

    def match_transaction_to_category(
        self,
        transaction: Transaction,
        categories: Optional[List[Category]] = None,
        min_confidence: float = 0.7
    ) -> Optional[Dict[str, Any]]:
        """
        Match a single transaction to the most appropriate category using NLP.

        Args:
            transaction: The transaction to categorize
            categories: List of categories to choose from (or all if None)
            min_confidence: Minimum confidence threshold (0-1)

        Returns:
            {
                "category_id": int,
                "category_name": str,
                "confidence": float,
                "reasoning": str,
                "source": "llm"
            }
            or None if confidence too low or error
        """
        if not self.is_available():
            return None

        # Get categories if not provided
        if categories is None:
            categories = self.db.query(Category).filter(
                Category.nl_description.isnot(None)
            ).all()

        # Filter categories that have NL descriptions
        categories = [c for c in categories if c.nl_description]

        if not categories:
            logger.warning("No categories with NL descriptions found")
            return None

        # Format transaction and categories for LLM
        trans_str = self._format_transaction_for_llm(transaction)
        cats_str = self._format_categories_for_llm(categories)

        prompt = f"""You are a financial transaction categorization assistant. Your task is to match a transaction to the most appropriate category based on natural language descriptions.

Transaction to categorize:
{trans_str}

Available categories:
{cats_str}

Please analyze the transaction and determine which category it best matches. Consider:
1. The merchant/vendor name
2. The transaction type and description
3. The amount and context
4. The natural language descriptions and keywords for each category

Respond in JSON format with:
{{
    "category_id": <the category ID>,
    "confidence": <a number between 0 and 1 indicating how confident you are>,
    "reasoning": "<brief explanation of why this category was chosen>"
}}

If no category is a good match, set category_id to null and confidence to 0.0."""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=500,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Parse response
            content = response.content[0].text.strip()

            # Try to extract JSON from response (handle cases where LLM adds markdown)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)

            # Validate result
            if result.get("category_id") is None:
                return None

            confidence = result.get("confidence", 0.0)
            if confidence < min_confidence:
                logger.info(f"Low confidence ({confidence}) for transaction {transaction.id}")
                return None

            # Get category name
            category = next((c for c in categories if c.id == result["category_id"]), None)
            if not category:
                logger.error(f"LLM returned invalid category_id: {result['category_id']}")
                return None

            return {
                "category_id": result["category_id"],
                "category_name": category.name,
                "confidence": confidence,
                "reasoning": result.get("reasoning", ""),
                "source": "llm"
            }

        except Exception as e:
            logger.error(f"NLP categorization error: {e}")
            return None

    def categorize_transactions_batch(
        self,
        transactions: List[Transaction],
        min_confidence: float = 0.7,
        apply: bool = False
    ) -> Dict[str, Any]:
        """
        Categorize multiple transactions using NLP.

        Args:
            transactions: List of transactions to categorize
            min_confidence: Minimum confidence threshold
            apply: If True, apply categorizations to database

        Returns:
            Statistics about the categorization process
        """
        if not self.is_available():
            return {"error": "NLP agent not available (missing API key)", "processed": 0}

        # Get categories with NL descriptions
        categories = self.db.query(Category).filter(
            Category.nl_description.isnot(None)
        ).all()

        if not categories:
            return {"error": "No categories with NL descriptions", "processed": 0}

        results = {
            "total": len(transactions),
            "categorized": 0,
            "skipped": 0,
            "low_confidence": 0,
            "categories_assigned": {}
        }

        for trans in transactions:
            # Skip if already user-confirmed
            if trans.is_user_confirmed:
                results["skipped"] += 1
                continue

            # Get NLP prediction
            prediction = self.match_transaction_to_category(
                trans,
                categories=categories,
                min_confidence=min_confidence
            )

            if prediction:
                results["categorized"] += 1

                # Track which categories were assigned
                cat_name = prediction["category_name"]
                results["categories_assigned"][cat_name] = \
                    results["categories_assigned"].get(cat_name, 0) + 1

                # Apply if requested
                if apply:
                    trans.category_id = prediction["category_id"]
                    trans.categorization_source = "llm"
                    trans.is_reviewed = False  # Still needs review
            else:
                results["low_confidence"] += 1

        if apply and results["categorized"] > 0:
            self.db.commit()
            logger.info(f"Applied NLP categorization to {results['categorized']} transactions")

        return results

    def parse_natural_language_query(self, query: str) -> Dict[str, Any]:
        """
        Parse a natural language query into structured transaction filters.

        Args:
            query: Natural language query like "show me all coffee purchases over $5 last month"

        Returns:
            {
                "filters": {
                    "search": str,
                    "min_amount": float,
                    "max_amount": float,
                    "date_from": date,
                    "date_to": date,
                    "category_names": List[str],
                    "classification": str
                },
                "explanation": str
            }
        """
        if not self.is_available():
            return {"error": "NLP agent not available", "filters": {}}

        # Get all categories for reference
        categories = self.db.query(Category).all()
        cat_list = [f"- {cat.name}" for cat in categories]

        prompt = f"""You are a query parsing assistant for a personal finance application. Parse the user's natural language query into structured filters.

User query: "{query}"

Available categories:
{chr(10).join(cat_list)}

Today's date is: {datetime.now().strftime('%Y-%m-%d')}

Parse this query into structured filters. Return JSON with these fields (only include fields that are mentioned in the query):
{{
    "search": "<keywords to search in transaction descriptions>",
    "min_amount": <minimum amount as a number>,
    "max_amount": <maximum amount as a number>,
    "date_from": "<date in YYYY-MM-DD format>",
    "date_to": "<date in YYYY-MM-DD format>",
    "category_names": ["<category name 1>", "<category name 2>"],
    "classification": "<personal|business|unclassified>",
    "explanation": "<brief explanation of how you interpreted the query>"
}}

Important:
- For relative dates like "last month", "this week", calculate the actual dates
- For amount filters, convert currency mentions to numbers (e.g., "$5" -> 5)
- Match category names from the available list above
- Only include fields that are relevant to the query
- Set classification only if explicitly mentioned"""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=800,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            content = response.content[0].text.strip()

            # Extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)

            # Convert date strings to date objects
            if "date_from" in result and result["date_from"]:
                result["date_from"] = datetime.strptime(result["date_from"], "%Y-%m-%d").date()

            if "date_to" in result and result["date_to"]:
                result["date_to"] = datetime.strptime(result["date_to"], "%Y-%m-%d").date()

            # Map category names to IDs
            if "category_names" in result and result["category_names"]:
                category_ids = []
                for cat_name in result["category_names"]:
                    cat = next((c for c in categories if c.name.lower() == cat_name.lower()), None)
                    if cat:
                        category_ids.append(cat.id)
                result["category_ids"] = category_ids

            return {
                "filters": result,
                "explanation": result.get("explanation", "")
            }

        except Exception as e:
            logger.error(f"NLP query parsing error: {e}")
            return {
                "error": str(e),
                "filters": {},
                "explanation": "Failed to parse query"
            }


def get_nlp_agent(db: Session) -> NLPAgent:
    """Factory function to create NLP agent."""
    return NLPAgent(db)
