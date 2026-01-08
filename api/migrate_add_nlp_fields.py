"""
Database migration script to add NLP fields to categories table.

This script adds the following fields:
- nl_description: Text field for natural language category description
- nl_keywords: Text field for additional keywords

Run this script with:
    python migrate_add_nlp_fields.py
"""
import os
import sys
from pathlib import Path

# Add parent directory to path so we can import app
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text, inspect
from app.database import DATABASE_URL, engine


def check_column_exists(engine, table_name, column_name):
    """Check if a column exists in a table."""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def migrate():
    """Add NLP fields to categories table."""
    print("Starting migration: Adding NLP fields to categories table...")
    print(f"Database: {DATABASE_URL}")

    try:
        # Check if migration is needed
        needs_nl_description = not check_column_exists(engine, 'categories', 'nl_description')
        needs_nl_keywords = not check_column_exists(engine, 'categories', 'nl_keywords')

        if not needs_nl_description and not needs_nl_keywords:
            print("✓ Migration not needed. Columns already exist.")
            return

        with engine.connect() as conn:
            # Determine if we're using SQLite or PostgreSQL
            is_sqlite = 'sqlite' in str(engine.url)

            if needs_nl_description:
                print("Adding nl_description column...")
                if is_sqlite:
                    conn.execute(text("ALTER TABLE categories ADD COLUMN nl_description TEXT"))
                else:
                    conn.execute(text("ALTER TABLE categories ADD COLUMN nl_description TEXT"))
                conn.commit()
                print("✓ Added nl_description column")

            if needs_nl_keywords:
                print("Adding nl_keywords column...")
                if is_sqlite:
                    conn.execute(text("ALTER TABLE categories ADD COLUMN nl_keywords TEXT"))
                else:
                    conn.execute(text("ALTER TABLE categories ADD COLUMN nl_keywords TEXT"))
                conn.commit()
                print("✓ Added nl_keywords column")

        print("\n✓ Migration completed successfully!")
        print("\nNext steps:")
        print("1. Restart your API server")
        print("2. Go to Categories page and add NL descriptions to your categories")
        print("3. Try the AI search feature in Transactions page")
        print("\nNote: You'll need to set ANTHROPIC_API_KEY environment variable to use NLP features.")

    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    migrate()
