"""
Invoice Service - PDF generation and invoice management
Uses billing_system_* prefixed tables
"""
import os
import base64
from typing import Dict, Any, Optional
from datetime import datetime
from io import BytesIO
from decimal import Decimal
from uuid import uuid4

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as ReportLabImage, KeepTogether
)
from reportlab.lib.colors import black, grey, HexColor
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from twilio.rest import Client
from jinja2 import Template

from core.database import db
from core.config import settings


class InvoiceService:
    """Service for invoice PDF generation and distribution"""
    
    def __init__(self):
        self.crud = db
        self.setup_twilio()
        self.setup_email()
    
    def setup_twilio(self):
        """Setup Twilio client for WhatsApp and SendGrid for email"""
        self.twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.twilio_phone_number = os.getenv("TWILIO_PHONE_NUMBER", "+14155238886")
        self.sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
        
        if self.twilio_account_sid and self.twilio_auth_token:
            self.twilio_client = Client(self.twilio_account_sid, self.twilio_auth_token)
        else:
            self.twilio_client = None
            print("⚠️  Twilio credentials not configured")
        
        if not self.sendgrid_api_key:
            print("⚠️  SendGrid API key not configured")
    
    def setup_email(self):
        """Setup email configuration (deprecated - using Twilio SendGrid)"""
        # Keep this method for backward compatibility but use Twilio SendGrid instead
        self.from_email = os.getenv("FROM_EMAIL", "noreply@minaki.com")
    
    def get_invoice_data(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        """Get complete invoice data with items, payments, and customer"""
        try:
            # Get invoice from billing_system_invoices_master
            invoice_query = f"SELECT * FROM billing_system_invoices_master WHERE id = '{invoice_id}'"
            invoice_df = self.crud.execute_query(invoice_query, return_data=True)
            
            if invoice_df.empty:
                return None
            
            invoice = invoice_df.iloc[0].to_dict()
            print(f"🔍 Invoice data: customer_id = {invoice.get('customer_id')}")
            
            # Get invoice items from billing_system_invoice_items with better product details
            items_query = f"""
                SELECT 
                    ii.*,
                    COALESCE(ii.product_name, pv.sku_name, zp.item_name, 'Unknown Product') as product_name,
                    COALESCE(ii.sku, pv.sku, zp.sku, 'N/A') as sku
                FROM billing_system_invoice_items ii
                LEFT JOIN billing_system_product_variants pv ON pv.id::text = ii.variant_id::text
                LEFT JOIN zakya_products zp ON zp.item_id::bigint = ii.variant_id
                WHERE ii.invoice_id = '{invoice_id}'
            """
            items_df = self.crud.execute_query(items_query, return_data=True)
            
            if items_df.empty:
                print(f"⚠️  No items found for invoice {invoice_id}")
                invoice['items'] = []
            else:
                items = items_df.to_dict('records')
                print(f"✅ Found {len(items)} items for invoice")
                for item in items:
                    print(f"   - {item.get('product_name', 'Unknown')} (SKU: {item.get('sku', 'N/A')})")
                invoice['items'] = items
            
            # Get payments from billing_system_payments
            payments_query = f"SELECT * FROM billing_system_payments WHERE invoice_id = '{invoice_id}'"
            payments_df = self.crud.execute_query(payments_query, return_data=True)
            invoice['payments'] = payments_df.to_dict('records')
            print(f"💰 Found {len(invoice['payments'])} payments")
            
            # Get customer from billing_system_customers - with better error handling
            customer_id = invoice.get('customer_id')
            if customer_id and str(customer_id).strip():
                print(f"👤 Looking up customer: {customer_id}")
                customer_query = f"SELECT * FROM customer_master WHERE \"Contact ID\" = '{customer_id}'"
                customer_df = self.crud.execute_query(customer_query, return_data=True)
                if not customer_df.empty:
                    customer_data = customer_df.iloc[0].to_dict()
                    invoice['customer'] = customer_data
                    print(f"✅ Found customer: {customer_data.get('full_name', 'Unknown')}")
                else:
                    print(f"⚠️  Customer {customer_id} not found in database")
                    invoice['customer'] = None
            else:
                print("👤 No customer_id provided - Walk-in customer")
                invoice['customer'] = None
            
            # Get company information
            invoice['company'] = self.get_company_info()
            
            return invoice
            
        except Exception as e:
            print(f"❌ Error getting invoice data: {e}")
            return None
    
    def get_company_info(self) -> Dict[str, str]:
        """Get company information for invoice header"""
        return {
            'name': os.getenv('COMPANY_NAME', 'Minaki Business Solutions'),
            'address': os.getenv('COMPANY_ADDRESS', '123 Business Street, City, State 12345'),
            'phone': os.getenv('COMPANY_PHONE', '+91-9876543210'),
            'email': os.getenv('COMPANY_EMAIL', 'info@minaki.com'),
            'website': os.getenv('COMPANY_WEBSITE', 'www.minaki.com'),
            'tax_id': os.getenv('COMPANY_TAX_ID', 'TAX123456789'),
            'logo_path': os.getenv('COMPANY_LOGO_PATH', '')  # Optional logo
        }
    
    def generate_invoice_pdf(self, invoice_id: str, save_to_disk: bool = False) -> Dict[str, Any]:
        """
        Generate professional PDF for invoice
        
        Args:
            invoice_id: Invoice ID
            save_to_disk: Whether to save PDF to disk
            
        Returns:
            Dictionary with success status, file_path (if saved), and pdf_bytes
        """
        try:
            # Get invoice data
            invoice_data = self.get_invoice_data(invoice_id)
            if not invoice_data:
                return {
                    'success': False,
                    'error': 'Invoice not found'
                }
            
            # Create PDF buffer
            buffer = BytesIO()
            
            # Create PDF document with better margins
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=50,
                leftMargin=50,
                topMargin=50,
                bottomMargin=50
            )
            
            # Build PDF content
            story = []
            styles = getSampleStyleSheet()
            
            # Add custom styles
            title_style = ParagraphStyle(
                'InvoiceTitle',
                parent=styles['Heading1'],
                fontSize=28,
                spaceAfter=20,
                spaceBefore=10,
                textColor=HexColor('#2c3e50'),
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
            
            company_name_style = ParagraphStyle(
                'CompanyName',
                parent=styles['Normal'],
                fontSize=20,
                textColor=HexColor('#2c3e50'),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=5
            )
            
            company_detail_style = ParagraphStyle(
                'CompanyDetail',
                parent=styles['Normal'],
                fontSize=10,
                textColor=HexColor('#7f8c8d'),
                alignment=TA_LEFT,
                fontName='Helvetica'
            )
            
            section_header_style = ParagraphStyle(
                'SectionHeader',
                parent=styles['Normal'],
                fontSize=12,
                textColor=HexColor('#2c3e50'),
                fontName='Helvetica-Bold',
                spaceAfter=8
            )
            
            # Header Section with Company Info
            company = invoice_data['company']
            
            # Company header table (Company info on left, Invoice info on right)
            header_data = [
                [
                    # Left column - Company info
                    [
                        Paragraph(company['name'], company_name_style),
                        Paragraph(company['address'], company_detail_style),
                        Paragraph(f"Phone: {company['phone']}", company_detail_style),
                        Paragraph(f"Email: {company['email']}", company_detail_style),
                        Paragraph(f"GST: {company['tax_id']}", company_detail_style),
                    ],
                    # Right column - Invoice info
                    [
                        Paragraph("SALES INVOICE", title_style),
                        Spacer(1, 10),
                        Paragraph(f"<b>Invoice #:</b> {invoice_data['invoice_number']}", section_header_style),
                        Paragraph(f"<b>Date:</b> {invoice_data['invoice_date'].strftime('%d %B, %Y') if isinstance(invoice_data['invoice_date'], datetime) else invoice_data['invoice_date']}", styles['Normal']),
                        Paragraph(f"<b>Status:</b> {invoice_data['payment_status'].upper()}", styles['Normal']),
                    ]
                ]
            ]
            
            header_table = Table(header_data, colWidths=[4*inch, 3*inch])
            header_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]))
            
            story.append(header_table)
            story.append(Spacer(1, 30))
            
            # Customer Information
            if invoice_data.get('customer'):
                customer = invoice_data['customer']
                story.append(Paragraph("BILL TO:", section_header_style))
                story.append(Paragraph(f"<b>{customer.get('full_name', 'Walk-in Customer')}</b>", styles['Normal']))
                if customer.get('phone'):
                    story.append(Paragraph(f"Phone: {customer['phone']}", styles['Normal']))
                if customer.get('email'):
                    story.append(Paragraph(f"Email: {customer['email']}", styles['Normal']))
                if customer.get('address'):
                    story.append(Paragraph(f"Address: {customer['address']}", styles['Normal']))
            else:
                story.append(Paragraph("BILL TO:", section_header_style))
                story.append(Paragraph("<b>Walk-in Customer</b>", styles['Normal']))
            
            story.append(Spacer(1, 25))
            
            # Items Table
            story.extend(self._build_professional_items_table(invoice_data['items']))
            story.append(Spacer(1, 20))
            
            # Totals Section
            story.extend(self._build_professional_totals_section(invoice_data))
            story.append(Spacer(1, 20))
            
            # Payment details
            if invoice_data.get('payments'):
                story.extend(self._build_professional_payment_details(invoice_data['payments']))
                story.append(Spacer(1, 20))
            
            # Notes if any
            if invoice_data.get('notes'):
                story.append(Paragraph("Notes:", section_header_style))
                story.append(Paragraph(invoice_data['notes'], styles['Normal']))
                story.append(Spacer(1, 15))
            
            # Footer
            story.extend(self._build_professional_footer())
            
            # Build PDF
            doc.build(story)
            
            # Get PDF bytes
            pdf_bytes = buffer.getvalue()
            buffer.close()
            
            result = {
                'success': True,
                'pdf_bytes': pdf_bytes,
                'filename': f"invoice_{invoice_data['invoice_number']}.pdf"
            }
            
            # Save to disk if requested
            if save_to_disk:
                file_path = f"invoices/invoice_{invoice_data['invoice_number']}.pdf"
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                with open(file_path, 'wb') as f:
                    f.write(pdf_bytes)
                
                result['file_path'] = file_path
            
            return result
            
        except Exception as e:
            print(f"❌ Error generating invoice PDF: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _build_professional_items_table(self, items: list) -> list:
        """Build professional items table"""
        elements = []
        
        if not items:
            elements.append(Paragraph("No items in this invoice", getSampleStyleSheet()['Normal']))
            return elements
        
        # Table headers
        headers = ['#', 'Item Description', 'SKU', 'Qty', 'Unit Price', 'Discount', 'Line Total']
        
        # Prepare data
        data = [headers]
        
        # Add items
        for i, item in enumerate(items, 1):
            row = [
                str(i),
                item.get('product_name', 'N/A'),
                item.get('sku', 'N/A'),
                str(item.get('quantity', 0)),
                f"₹{float(item.get('unit_price', 0)):,.2f}",
                f"₹{float(item.get('discount_amount', 0)):,.2f}",
                f"₹{float(item.get('line_total', 0)):,.2f}"
            ]
            data.append(row)
        
        # Create table with better column widths
        table = Table(data, colWidths=[0.5*inch, 3*inch, 1*inch, 0.8*inch, 1.2*inch, 1*inch, 1.2*inch])
        
        # Professional table styling
        table.setStyle(TableStyle([
            # Header styling
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),  # Item description left aligned
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            
            # Data rows styling
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (2, 1), (-1, -1), 'CENTER'),  # Numbers center aligned
            ('ALIGN', (4, 1), (-1, -1), 'RIGHT'),   # Prices right aligned
            ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#bdc3c7')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Alternate row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f8f9fa')]),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))
        
        elements.append(table)
        return elements
    
    def _build_professional_totals_section(self, invoice_data: Dict[str, Any]) -> list:
        """Build professional totals section"""
        elements = []
        
        # Prepare totals data
        subtotal = float(invoice_data.get('subtotal', 0))
        discount_amount = float(invoice_data.get('discount_amount', 0))
        tax_rate = float(invoice_data.get('tax_rate_percent', 0))
        tax_amount = float(invoice_data.get('tax_amount', 0))
        total_amount = float(invoice_data.get('total_amount', 0))
        paid_amount = float(invoice_data.get('paid_amount', 0))
        outstanding = float(invoice_data.get('outstanding_amount', 0))
        
        # Create totals table
        totals_data = [
            ['Subtotal:', f"₹{subtotal:,.2f}"],
            ['Discount:', f"-₹{discount_amount:,.2f}"],
            ['Tax ({:.1f}%):'.format(tax_rate), f"₹{tax_amount:,.2f}"],
            ['', ''],  # Spacer
            ['Total Amount:', f"₹{total_amount:,.2f}"],
            ['Amount Paid:', f"₹{paid_amount:,.2f}"],
            ['Balance Due:', f"₹{outstanding:,.2f}"],
        ]
        
        # Create table aligned to right
        table = Table(totals_data, colWidths=[2.5*inch, 1.5*inch], hAlign='RIGHT')
        
        # Style the totals table
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            
            # Total amount row (bold and larger)
            ('FONTNAME', (0, 4), (1, 4), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 4), (1, 4), 13),
            ('BACKGROUND', (0, 4), (1, 4), HexColor('#ecf0f1')),
            
            # Balance due row
            ('FONTNAME', (0, 6), (1, 6), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, 6), (1, 6), HexColor('#e74c3c') if outstanding > 0 else HexColor('#27ae60')),
            
            # Lines
            ('LINEBELOW', (0, 3), (1, 3), 1, HexColor('#bdc3c7')),
            ('LINEBELOW', (0, 4), (1, 4), 2, HexColor('#34495e')),
            
            # Padding
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
            ('RIGHTPADDING', (0, 0), (-1, -1), 15),
        ]))
        
        elements.append(table)
        return elements
    
    def _build_professional_payment_details(self, payments: list) -> list:
        """Build professional payment details section"""
        elements = []
        
        if not payments:
            return elements
        
        # Section header
        styles = getSampleStyleSheet()
        section_header_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Normal'],
            fontSize=12,
            textColor=HexColor('#2c3e50'),
            fontName='Helvetica-Bold',
            spaceAfter=8
        )
        
        elements.append(Paragraph("Payment Details:", section_header_style))
        
        # Payment table headers
        headers = ['Payment Method', 'Amount', 'Date', 'Transaction ID', 'Status']
        data = [headers]
        
        # Add payments
        for payment in payments:
            payment_date = payment.get('payment_date', '')
            if isinstance(payment_date, datetime):
                payment_date = payment_date.strftime('%d %b, %Y')
            
            row = [
                payment.get('payment_method', '').title(),
                f"₹{float(payment.get('payment_amount', 0)):,.2f}",
                str(payment_date),
                payment.get('transaction_id', 'N/A'),
                payment.get('payment_status', '').title()
            ]
            data.append(row)
        
        # Create table
        table = Table(data, colWidths=[1.5*inch, 1.2*inch, 1.2*inch, 2*inch, 1*inch])
        
        # Style table
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),  # Amount right aligned
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#bdc3c7')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elements.append(table)
        return elements
    
    def _build_professional_footer(self) -> list:
        """Build professional invoice footer"""
        elements = []
        styles = getSampleStyleSheet()
        
        # Thank you message
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=10,
            textColor=HexColor('#7f8c8d'),
            alignment=TA_CENTER,
            spaceAfter=10
        )
        
        elements.append(Spacer(1, 30))
        elements.append(Paragraph("<b>Thank you for your business!</b>", footer_style))
        elements.append(Paragraph("This invoice was generated electronically and is valid without signature.", footer_style))
        elements.append(Paragraph("For any queries regarding this invoice, please contact us using the details above.", footer_style))
        
        return elements
    
    def _build_company_header(self, company: Dict[str, str], styles) -> list:
        """Build company header section"""
        elements = []
        
        # Company name
        company_style = ParagraphStyle(
            'CompanyName',
            parent=styles['Heading2'],
            fontSize=18,
            textColor=HexColor('#1a472a'),
            alignment=TA_LEFT
        )
        
        elements.append(Paragraph(company['name'], company_style))
        
        # Company details
        details = [
            company['address'],
            f"Phone: {company['phone']}",
            f"Email: {company['email']}",
            f"Website: {company['website']}",
            f"Tax ID: {company['tax_id']}"
        ]
        
        for detail in details:
            elements.append(Paragraph(detail, styles['Normal']))
        
        return elements
    
    def _build_invoice_info(self, invoice_data: Dict[str, Any], styles) -> list:
        """Build invoice information section"""
        elements = []
        
        # Create two-column layout for invoice info and customer info
        data = []
        
        # Left column - Invoice info
        invoice_info = [
            f"Invoice #: {invoice_data['invoice_number']}",
            f"Date: {invoice_data['invoice_date'].strftime('%B %d, %Y') if isinstance(invoice_data['invoice_date'], datetime) else invoice_data['invoice_date']}",
            f"Status: {invoice_data['payment_status'].upper()}",
        ]
        
        if invoice_data.get('due_date'):
            invoice_info.append(f"Due Date: {invoice_data['due_date']}")
        
        if invoice_data.get('sales_person'):
            invoice_info.append(f"Sales Person: {invoice_data['sales_person']}")
            
        if invoice_data.get('branch'):
            invoice_info.append(f"Branch: {invoice_data['branch']}")
            
        if invoice_data.get('terms'):
            invoice_info.append(f"Terms: {invoice_data['terms']}")
        
        # Right column - Customer info
        customer_info = []
        if invoice_data.get('customer'):
            customer = invoice_data['customer']
            customer_info = [
                "Bill To:",
                customer.get('full_name', 'N/A'),
                customer.get('email', ''),
                customer.get('phone', ''),
                customer.get('address', ''),
            ]
        else:
            customer_info = ["Bill To:", "Walk-in Customer"]
        
        # Create table
        max_len = max(len(invoice_info), len(customer_info))
        for i in range(max_len):
            left = invoice_info[i] if i < len(invoice_info) else ""
            right = customer_info[i] if i < len(customer_info) else ""
            data.append([left, right])
        
        table = Table(data, colWidths=[3*inch, 3*inch])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        elements.append(table)
        
        return elements
    
    def _build_items_table(self, items: list, styles) -> list:
        """Build items table"""
        elements = []
        
        # Table headers
        headers = ['Item', 'SKU', 'Qty', 'Unit Price', 'Discount', 'Line Total']
        
        data = [headers]
        
        # Add items
        for item in items:
            row = [
                item.get('product_name', ''),
                item.get('sku', ''),
                str(item.get('quantity', 0)),
                f"₹{float(item.get('unit_price', 0)):.2f}",
                f"₹{float(item.get('discount_amount', 0)):.2f}",
                f"₹{float(item.get('line_total', 0)):.2f}"
            ]
            data.append(row)
        
        # Create table
        table = Table(data, colWidths=[2.5*inch, 1*inch, 0.5*inch, 1*inch, 1*inch, 1*inch])
        
        # Style table
        table.setStyle(TableStyle([
            # Header row styling
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1a472a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            
            # Data rows styling
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (0, 1), (1, -1), 'LEFT'),  # Item name and SKU left aligned
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),  # Numbers right aligned
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Alternate row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f8f9fa')]),
        ]))
        
        elements.append(table)
        
        return elements
    
    def _build_totals_section(self, invoice_data: Dict[str, Any], styles) -> list:
        """Build totals section"""
        elements = []
        
        # Totals data
        discount_percent = float(invoice_data.get('discount_percent', 0))
        discount_label = f"Discount ({discount_percent:.1f}%):" if discount_percent > 0 else "Discount:"
        
        totals_data = [
            ['Subtotal:', f"₹{float(invoice_data.get('subtotal', 0)):.2f}"],
            [discount_label, f"-₹{float(invoice_data.get('discount_amount', 0)):.2f}"],
            ['Tax ({:.1f}%):'.format(float(invoice_data.get('tax_rate_percent', 0))), 
             f"₹{float(invoice_data.get('tax_amount', 0)):.2f}"],
            ['', ''],  # Separator
            ['Total Amount:', f"₹{float(invoice_data.get('total_amount', 0)):.2f}"],
            ['Paid Amount:', f"₹{float(invoice_data.get('paid_amount', 0)):.2f}"],
            ['Outstanding:', f"₹{float(invoice_data.get('outstanding_amount', 0)):.2f}"],
        ]
        
        # Create table aligned to right
        table = Table(totals_data, colWidths=[2*inch, 1.5*inch], hAlign='RIGHT')
        
        # Style table
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (0, 4), (1, 4), 'Helvetica-Bold'),  # Total Amount row
            ('FONTSIZE', (0, 4), (1, 4), 12),
            ('LINEBELOW', (0, 3), (1, 3), 1, colors.black),  # Line above total
            ('LINEBELOW', (0, 4), (1, 4), 1, colors.black),  # Line below total
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        
        elements.append(table)
        
        return elements
    
    def _build_payment_details(self, payments: list, styles) -> list:
        """Build payment details section"""
        elements = []
        
        # Payment header
        payment_style = ParagraphStyle(
            'PaymentHeader',
            parent=styles['Heading3'],
            fontSize=14,
            spaceAfter=10
        )
        elements.append(Paragraph("Payment Details", payment_style))
        
        # Payment table headers
        headers = ['Date', 'Method', 'Amount', 'Transaction ID', 'Status']
        data = [headers]
        
        # Add payments
        for payment in payments:
            row = [
                payment['payment_date'].strftime('%Y-%m-%d') if isinstance(payment['payment_date'], datetime) else str(payment['payment_date']),
                payment.get('payment_method', '').title(),
                f"₹{float(payment.get('payment_amount', 0)):.2f}",
                payment.get('transaction_id', 'N/A'),
                payment.get('payment_status', '').title()
            ]
            data.append(row)
        
        # Create table
        table = Table(data, colWidths=[1.2*inch, 1.2*inch, 1*inch, 2*inch, 1*inch])
        
        # Style table
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1a472a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        elements.append(table)
        
        return elements
    
    def _build_footer(self, styles) -> list:
        """Build invoice footer"""
        elements = []
        
        elements.append(Spacer(1, 30))
        
        footer_text = """
        <para align=center>
        <b>Thank you for your business!</b><br/>
        This is a computer generated invoice and does not require signature.<br/>
        For any queries, please contact us at the above mentioned details.
        </para>
        """
        
        elements.append(Paragraph(footer_text, styles['Normal']))
        
        return elements
    
    def send_invoice_via_whatsapp(self, invoice_id: str, phone_number: str, message: str = None) -> Dict[str, Any]:
        """
        Send invoice PDF via WhatsApp using Twilio
        
        Args:
            invoice_id: Invoice ID
            phone_number: Customer's WhatsApp number (with country code)
            message: Custom message (optional)
        """
        try:
            if not self.twilio_client:
                return {
                    'success': False,
                    'error': 'Twilio not configured'
                }
            
            # Generate PDF
            pdf_result = self.generate_invoice_pdf(invoice_id, save_to_disk=True)
            if not pdf_result['success']:
                return pdf_result
            
            # Get invoice data for message
            invoice_data = self.get_invoice_data(invoice_id)
            
            if "+" in phone_number:
                phone_number = phone_number.replace("+", "")
            if "'" in phone_number:
                phone_number = phone_number.replace("'", "")
            
            # Default message if none provided
            if not message:
                message = f"""
🧾 *Invoice #{invoice_data['invoice_number']}*

Dear Customer,

Thank you for your business! Please find your invoice details below.

💰 Total Amount: ₹{float(invoice_data['total_amount']):.2f}
💳 Paid Amount: ₹{float(invoice_data['paid_amount']):.2f}
⏳ Outstanding: ₹{float(invoice_data['outstanding_amount']):.2f}

For any queries, please contact us.

Best regards,
{invoice_data['company']['name']}
                """.strip()
            
            # Send WhatsApp message
            whatsapp_message = self.twilio_client.messages.create(
                from_=f'whatsapp:{self.twilio_phone_number}',
                body=message,
                to=f'whatsapp:{phone_number}'
            )
            
            # Log the sending
            self._log_invoice_communication(
                invoice_id,
                'whatsapp',
                phone_number,
                'sent',
                whatsapp_message.sid
            )
            
            return {
                'success': True,
                'message': 'Invoice sent via WhatsApp successfully',
                'message_sid': whatsapp_message.sid,
                'filename': pdf_result['filename']
            }
            
        except Exception as e:
            print(f"❌ Error sending invoice via WhatsApp: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def send_invoice_via_email(
        self, 
        invoice_id: str, 
        recipient_email: str, 
        subject: str = None, 
        message: str = None
    ) -> Dict[str, Any]:
        """
        Send invoice PDF via Email using Twilio SendGrid
        
        Args:
            invoice_id: Invoice ID
            recipient_email: Customer's email address
            subject: Email subject (optional)
            message: Email body message (optional)
        """
        try:
            if not self.sendgrid_api_key:
                return {
                    'success': False,
                    'error': 'SendGrid API key not configured'
                }
            
            # Generate PDF
            pdf_result = self.generate_invoice_pdf(invoice_id)
            if not pdf_result['success']:
                return pdf_result
            
            # Get invoice data
            invoice_data = self.get_invoice_data(invoice_id)
            
            # Default subject if none provided
            if not subject:
                subject = f"Invoice #{invoice_data['invoice_number']} - {invoice_data['company']['name']}"
            
            # Default message if none provided
            if not message:
                message = f"""
Dear Customer,

Thank you for your business! Please find your invoice #{invoice_data['invoice_number']} attached.

Invoice Details:
- Invoice Number: {invoice_data['invoice_number']}
- Invoice Date: {invoice_data['invoice_date']}
- Total Amount: ₹{float(invoice_data['total_amount']):.2f}
- Paid Amount: ₹{float(invoice_data['paid_amount']):.2f}
- Outstanding Amount: ₹{float(invoice_data['outstanding_amount']):.2f}

If you have any questions about this invoice, please contact us.

Best regards,
{invoice_data['company']['name']}
{invoice_data['company']['phone']}
{invoice_data['company']['email']}
                """.strip()
            
            # Prepare PDF attachment as base64
            import base64
            pdf_base64 = base64.b64encode(pdf_result['pdf_bytes']).decode('utf-8')
            
            # Create email data for SendGrid
            email_data = {
                "personalizations": [
                    {
                        "to": [{"email": recipient_email}],
                        "subject": subject
                    }
                ],
                "from": {"email": self.from_email, "name": invoice_data['company']['name']},
                "content": [
                    {
                        "type": "text/plain",
                        "value": message
                    }
                ],
                "attachments": [
                    {
                        "content": pdf_base64,
                        "type": "application/pdf",
                        "filename": pdf_result["filename"],
                        "disposition": "attachment"
                    }
                ]
            }
            
            # Send email using Twilio SendGrid API
            import requests
            
            headers = {
                "Authorization": f"Bearer {self.sendgrid_api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers=headers,
                json=email_data
            )
            
            if response.status_code == 202:  # SendGrid success status code
                # Log the sending
                self._log_invoice_communication(
                    invoice_id,
                    'email',
                    recipient_email,
                    'sent'
                )
                
                return {
                    'success': True,
                    'message': 'Invoice sent via email successfully',
                    'filename': pdf_result['filename']
                }
            else:
                return {
                    'success': False,
                    'error': f'SendGrid API error: {response.status_code} - {response.text}'
                }
            
        except Exception as e:
            print(f"❌ Error sending invoice via email: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _log_invoice_communication(
        self, 
        invoice_id: str, 
        method: str, 
        recipient: str, 
        status: str,
        message_id: str = None
    ):
        """Log invoice communication for tracking"""
        try:
            log_record = {
                'id': str(uuid4()),
                'invoice_id': invoice_id,
                'communication_method': method,
                'recipient': recipient,
                'status': status,
                'message_id': message_id,
                'sent_at': datetime.utcnow()
            }
            
            self.crud.insert_record('billing_system_invoice_communications', log_record)
            
        except Exception as e:
            print(f"❌ Error logging communication: {e}")
