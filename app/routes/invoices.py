from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.database import get_db

router = APIRouter(prefix="/invoices", tags=["invoices"])

class InvoiceItemCreate(BaseModel):
    product_id: int
    quantity: int = 1


class InvoiceItem(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    unit_price: float


class InvoiceCreate(BaseModel):
    invoice_no: str
    issue_date: str  # Format: YYYY-MM-DD
    due_date: str    # Format: YYYY-MM-DD
    client_id: int
    address: str
    items: List[InvoiceItemCreate]
    tax: float = 0


class InvoiceResponse(BaseModel):
    id: int
    invoice_no: str
    issue_date: str
    due_date: str
    client_id: int
    client_name: str
    address: str
    items: List[InvoiceItem]
    tax: float
    total: float


class InvoiceListResponse(BaseModel):
    id: int
    invoice_no: str
    issue_date: str
    due_date: str
    client_name: str
    total: float


def calculate_invoice_total(items_with_prices: List[tuple]) -> float:
    """Calculate total from items (quantity, unit_price) tuples."""
    total = 0
    for item in items_with_prices:
        quantity, unit_price = item
        total += quantity * unit_price
    return total


@router.get("")
def list_invoices():
    """
    List all invoices.
    Returns invoice summary with client name and total.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    i.id,
                    i.invoice_no,
                    i.issue_date,
                    i.due_date,
                    c.name as client_name,
                    i.total
                FROM invoices i
                JOIN clients c ON i.client_id = c.id
                ORDER BY i.id DESC
            """)
            rows = cursor.fetchall()
            invoices = [
                {
                    "id": row["id"],
                    "invoice_no": row["invoice_no"],
                    "issue_date": row["issue_date"],
                    "due_date": row["due_date"],
                    "client_name": row["client_name"],
                    "total": row["total"],
                }
                for row in rows
            ]
            return {"invoices": invoices}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/{invoice_id}")
def get_invoice(invoice_id: int):
    """
    Get a single invoice by ID.
    Includes all invoice items and product details.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    i.id,
                    i.invoice_no,
                    i.issue_date,
                    i.due_date,
                    i.client_id,
                    c.name as client_name,
                    i.address,
                    i.tax,
                    i.total
                FROM invoices i
                JOIN clients c ON i.client_id = c.id
                WHERE i.id = ?
            """, (invoice_id,))
            
            row = cursor.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Invoice not found")
            
            cursor.execute("""
                SELECT 
                    ii.id,
                    ii.product_id,
                    p.name as product_name,
                    ii.quantity,
                    ii.unit_price
                FROM invoice_items ii
                JOIN products p ON ii.product_id = p.id
                WHERE ii.invoice_id = ?
            """, (invoice_id,))
            
            item_rows = cursor.fetchall()
            items = [
                {
                    "id": item_row["id"],
                    "product_id": item_row["product_id"],
                    "product_name": item_row["product_name"],
                    "quantity": item_row["quantity"],
                    "unit_price": item_row["unit_price"],
                }
                for item_row in item_rows
            ]
            
            return {
                "id": row["id"],
                "invoice_no": row["invoice_no"],
                "issue_date": row["issue_date"],
                "due_date": row["due_date"],
                "client_id": row["client_id"],
                "client_name": row["client_name"],
                "address": row["address"],
                "items": items,
                "tax": row["tax"],
                "total": row["total"],
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("", status_code=201)
def create_invoice(invoice: InvoiceCreate):
    """
    Create a new invoice with items.
    Automatically calculates total based on items and tax.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Validations
            cursor.execute("SELECT id FROM clients WHERE id = ?", (invoice.client_id,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="Client not found")
            
            cursor.execute("SELECT id FROM invoices WHERE invoice_no = ?", (invoice.invoice_no,))
            if cursor.fetchone() is not None:
                raise HTTPException(status_code=400, detail="Invoice number already exists")
            
            items_with_prices = []
            for item in invoice.items:
                cursor.execute("SELECT price FROM products WHERE id = ?", (item.product_id,))
                product = cursor.fetchone()
                if product is None:
                    raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
                items_with_prices.append((item.quantity, product["price"]))
            
            subtotal = calculate_invoice_total(items_with_prices)
            total = subtotal + invoice.tax
            
            cursor.execute("""
                INSERT INTO invoices (
                    invoice_no, issue_date, due_date, 
                    client_id, address, tax, total
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                invoice.invoice_no,
                invoice.issue_date,
                invoice.due_date,
                invoice.client_id,
                invoice.address,
                invoice.tax,
                total
            ))
            
            invoice_id = cursor.lastrowid
            
            for item, prices in zip(invoice.items, items_with_prices):
                cursor.execute("""
                    INSERT INTO invoice_items (
                        invoice_id, product_id, quantity, unit_price
                    ) VALUES (?, ?, ?, ?)
                """, (
                    invoice_id,
                    item.product_id,
                    item.quantity,
                    prices[1]
                ))
            
            return {
                "id": invoice_id,
                "invoice_no": invoice.invoice_no,
                "issue_date": invoice.issue_date,
                "due_date": invoice.due_date,
                "client_id": invoice.client_id,
                "address": invoice.address,
                "total": total,
                "tax": invoice.tax,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.delete("/{invoice_id}", status_code=204)
def delete_invoice(invoice_id: int):
    """
    Delete an invoice.
    Also deletes associated invoice items.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT id FROM invoices WHERE id = ?", (invoice_id,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="Invoice not found")
            
            cursor.execute("DELETE FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
            
            cursor.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
            
            return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
