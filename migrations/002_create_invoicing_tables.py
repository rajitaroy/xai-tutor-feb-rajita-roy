"""
Migration: Create invoicing tables
Version: 002
Description: Creates products, clients, invoices, and invoice_items tables with seed data
"""

import sqlite3
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import DATABASE_PATH


def upgrade():
    """Apply the migration."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Create migrations tracking table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS _migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Check if this migration has already been applied
    cursor.execute("SELECT 1 FROM _migrations WHERE name = ?", ("002_create_invoicing_tables",))
    if cursor.fetchone():
        print("Migration 002_create_invoicing_tables already applied. Skipping.")
        conn.close()
        return
    
    # Create products table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL
        )
    """)
    
    # Create clients table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            company_registration_no TEXT NOT NULL
        )
    """)
    
    # Create invoices table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT NOT NULL UNIQUE,
            issue_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            client_id INTEGER NOT NULL,
            address TEXT NOT NULL,
            tax REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    """)
    
    # Create invoice_items table (many-to-many between invoices and products)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoice_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            unit_price REAL NOT NULL,
            FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)
    
    # Insert seed data for products
    sample_products = [
        ("Laptop", 1200.00),
        ("Monitor", 350.00),
        ("Keyboard", 80.00),
        ("Mouse", 30.00),
        ("USB-C Cable", 15.00),
    ]
    cursor.executemany("INSERT INTO products (name, price) VALUES (?, ?)", sample_products)
    
    # Insert seed data for clients
    sample_clients = [
        ("Acme Corporation", "123 Business St, New York, NY 10001", "REG-2023-001"),
        ("Tech Innovations Ltd", "456 Tech Ave, San Francisco, CA 94105", "REG-2023-002"),
        ("Global Solutions Inc", "789 Enterprise Blvd, Boston, MA 02101", "REG-2023-003"),
    ]
    cursor.executemany(
        "INSERT INTO clients (name, address, company_registration_no) VALUES (?, ?, ?)",
        sample_clients
    )
    
    cursor.execute("INSERT INTO _migrations (name) VALUES (?)", ("002_create_invoicing_tables",))
    
    conn.commit()
    conn.close()
    print("Migration 002_create_invoicing_tables applied successfully.")


def downgrade():
    """Revert the migration."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DROP TABLE IF EXISTS invoice_items")
    cursor.execute("DROP TABLE IF EXISTS invoices")
    cursor.execute("DROP TABLE IF EXISTS clients")
    cursor.execute("DROP TABLE IF EXISTS products")
    
    cursor.execute("DELETE FROM _migrations WHERE name = ?", ("002_create_invoicing_tables",))
    
    conn.commit()
    conn.close()
    print("Migration 002_create_invoicing_tables reverted successfully.")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run database migration")
    parser.add_argument(
        "action",
        choices=["upgrade", "downgrade"],
        help="Migration action to perform"
    )
    
    args = parser.parse_args()
    
    if args.action == "upgrade":
        upgrade()
    elif args.action == "downgrade":
        downgrade()
