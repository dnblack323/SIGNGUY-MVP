"""
SignGuy AI MVP - Comprehensive Backend API Test Suite

Tests all critical flows:
- Multi-tenant registration and isolation
- Auth flows (register, login, logout, password reset)
- Customer management
- Quote → Order → Work Order → Invoice → Payment flow
- File uploads with tenant scoping
- Email service (SendGrid unconfigured handling)
- Dashboard summary
- Audit trail with actor fields
- Permission enforcement
"""
import requests
import sys
import io
from datetime import datetime, timedelta
from typing import Optional

BASE_URL = "https://sign-builder-stage.preview.emergentagent.com/api"

class SignGuyTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.tenant_a_token = None
        self.tenant_a_id = None
        self.tenant_a_user_id = None
        self.tenant_a_email = None
        self.tenant_b_token = None
        self.tenant_b_id = None
        self.staff_token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failed_tests = []

    def log(self, msg: str):
        print(f"  {msg}")

    def test(self, name: str, method: str, endpoint: str, expected_status: int,
             data: Optional[dict] = None, token: Optional[str] = None,
             headers: Optional[dict] = None, files: Optional[dict] = None) -> tuple[bool, dict, int]:
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        req_headers = headers or {}
        if token:
            req_headers['Authorization'] = f'Bearer {token}'
        if data and not files:
            req_headers['Content-Type'] = 'application/json'

        self.tests_run += 1
        print(f"\n🔍 Test #{self.tests_run}: {name}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=req_headers, timeout=30)
            elif method == 'POST':
                if files:
                    response = requests.post(url, data=data, files=files, headers=req_headers, timeout=30)
                else:
                    response = requests.post(url, json=data, headers=req_headers, timeout=30)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=req_headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=req_headers, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ PASSED - Status: {response.status_code}")
            else:
                self.tests_failed += 1
                self.failed_tests.append(name)
                print(f"❌ FAILED - Expected {expected_status}, got {response.status_code}")
                if response.text:
                    print(f"   Response: {response.text[:200]}")

            result = {}
            if response.text:
                try:
                    result = response.json()
                except:
                    result = {"raw": response.text}

            return success, result, response.status_code

        except Exception as e:
            self.tests_failed += 1
            self.failed_tests.append(name)
            print(f"❌ FAILED - Error: {str(e)}")
            return False, {}, 0

    def run_all_tests(self):
        print("=" * 80)
        print("SignGuy AI MVP - Backend API Test Suite")
        print("=" * 80)

        # 1. Register Tenant A
        print("\n" + "=" * 80)
        print("PHASE 1: TENANT A REGISTRATION & AUTH")
        print("=" * 80)
        
        timestamp = datetime.now().strftime("%H%M%S%f")
        tenant_a_slug = f"test-tenant-a-{timestamp}"
        tenant_a_email = f"owner-a-{timestamp}@example.com"
        
        success, result, _ = self.test(
            "Register Tenant A",
            "POST", "auth/register-tenant", 201,
            data={
                "tenant_name": "Test Tenant A",
                "tenant_slug": tenant_a_slug,
                "owner_email": tenant_a_email,
                "owner_full_name": "Owner A",
                "owner_password": "SecurePass123!"
            }
        )
        
        if not success or 'access_token' not in result:
            print("\n❌ CRITICAL: Tenant A registration failed. Cannot continue.")
            return self.print_summary()
        
        self.tenant_a_token = result['access_token']
        self.tenant_a_id = result['tenant']['id']
        self.tenant_a_user_id = result['user']['id']
        self.tenant_a_email = result['user']['email']
        print(f"   Tenant A ID: {self.tenant_a_id}")
        print(f"   Token: {self.tenant_a_token[:20]}...")

        # Verify JWT contains tenant_id and permissions
        if 'permissions' not in result or len(result['permissions']) == 0:
            print("❌ WARNING: No permissions returned in register response")
        else:
            print(f"   Permissions: {len(result['permissions'])} perms")

        # 2. Test /auth/me
        success, result, _ = self.test(
            "GET /auth/me (Tenant A)",
            "GET", "auth/me", 200,
            token=self.tenant_a_token
        )
        if success:
            if 'user' in result and 'tenant' in result and 'permissions' in result:
                print(f"   User: {result['user'].get('email')}")
                print(f"   Tenant: {result['tenant'].get('name')}")
                print(f"   Permissions: {len(result['permissions'])}")
            else:
                print("❌ WARNING: /auth/me missing user/tenant/permissions")

        # 3. Test login
        success, result, _ = self.test(
            "Login Tenant A",
            "POST", "auth/login", 200,
            data={"email": tenant_a_email, "password": "SecurePass123!"}
        )
        if success and 'access_token' in result:
            print(f"   Login successful, token refreshed")

        # 4. Test logout
        success, result, _ = self.test(
            "Logout Tenant A",
            "POST", "auth/logout", 204,
            token=self.tenant_a_token
        )

        # 5. Password reset flow
        print("\n" + "-" * 80)
        print("Testing Password Reset Flow")
        print("-" * 80)
        
        success, result, _ = self.test(
            "Request password reset",
            "POST", "auth/request-password-reset", 202,
            data={"email": tenant_a_email}
        )
        
        # Get reset token from dev endpoint
        success, result, _ = self.test(
            "Get reset token (dev endpoint)",
            "GET", f"auth/_dev/last-reset-token?email={tenant_a_email}", 200
        )
        
        if success and 'token' in result:
            reset_token = result['token']
            print(f"   Reset token: {reset_token[:20]}...")
            
            # Reset password
            success, result, status = self.test(
                "Reset password",
                "POST", "auth/reset-password", 204,
                data={"token": reset_token, "new_password": "NewSecurePass123!"}
            )
            
            # Login with new password
            success, result, _ = self.test(
                "Login with new password",
                "POST", "auth/login", 200,
                data={"email": tenant_a_email, "password": "NewSecurePass123!"}
            )
            if success:
                self.tenant_a_token = result['access_token']
                print(f"   Token refreshed after password reset")

        # 6. CUSTOMER MANAGEMENT
        print("\n" + "=" * 80)
        print("PHASE 2: CUSTOMER MANAGEMENT")
        print("=" * 80)
        
        success, result, _ = self.test(
            "Create customer",
            "POST", "customers", 201,
            data={
                "name": "Acme Corp",
                "company": "Acme Corporation",
                "email": "contact@acme.com",
                "phone": "555-1234",
                "address_line1": "123 Main St",
                "city": "Springfield",
                "state": "IL",
                "postal_code": "62701",
                "notes": "VIP customer"
            },
            token=self.tenant_a_token
        )
        
        if not success or 'id' not in result:
            print("❌ CRITICAL: Customer creation failed")
            return self.print_summary()
        
        customer_id = result['id']
        print(f"   Customer ID: {customer_id}")

        # List customers
        success, result, _ = self.test(
            "List customers",
            "GET", "customers?limit=10", 200,
            token=self.tenant_a_token
        )
        if success:
            print(f"   Found {result.get('total', 0)} customers")

        # Get customer
        success, result, _ = self.test(
            "Get customer by ID",
            "GET", f"customers/{customer_id}", 200,
            token=self.tenant_a_token
        )

        # Update customer
        success, result, _ = self.test(
            "Update customer",
            "PATCH", f"customers/{customer_id}", 200,
            data={"notes": "Updated VIP customer"},
            token=self.tenant_a_token
        )

        # Get customer related records
        success, result, _ = self.test(
            "Get customer related records",
            "GET", f"customers/{customer_id}/related", 200,
            token=self.tenant_a_token
        )
        if success:
            print(f"   Related: quotes={len(result.get('quotes', []))}, orders={len(result.get('orders', []))}")

        # 7. QUOTE FLOW WITH IDEMPOTENCY
        print("\n" + "=" * 80)
        print("PHASE 3: QUOTE FLOW & IDEMPOTENT CONVERSION")
        print("=" * 80)
        
        success, result, _ = self.test(
            "Create quote",
            "POST", "quotes", 201,
            data={
                "customer_id": customer_id,
                "job_name": "Custom Signage Project",
                "notes": "Large outdoor sign",
                "total_cents": 150000  # $1,500.00
            },
            token=self.tenant_a_token
        )
        
        if not success or 'id' not in result:
            print("❌ CRITICAL: Quote creation failed")
            return self.print_summary()
        
        quote_id = result['id']
        quote_number = result.get('number')
        print(f"   Quote ID: {quote_id}, Number: Q-{quote_number}")

        # Update quote status: draft -> sent -> approved
        for status in ['sent', 'approved']:
            success, result, _ = self.test(
                f"Set quote status to {status}",
                "POST", f"quotes/{quote_id}/status", 200,
                data={"status": status},
                token=self.tenant_a_token
            )

        # Convert to order (first call)
        success, result, _ = self.test(
            "Convert quote to order (1st call)",
            "POST", f"quotes/{quote_id}/convert-to-order", 200,
            token=self.tenant_a_token
        )
        
        if not success or 'order' not in result:
            print("❌ CRITICAL: Quote conversion failed")
            return self.print_summary()
        
        order_id = result['order']['id']
        order_number = result['order'].get('number')
        already_converted_1 = result.get('already_converted', False)
        print(f"   Order ID: {order_id}, Number: O-{order_number}")
        print(f"   Already converted: {already_converted_1}")

        # Convert to order (second call - IDEMPOTENCY TEST)
        success, result, _ = self.test(
            "Convert quote to order (2nd call - idempotent)",
            "POST", f"quotes/{quote_id}/convert-to-order", 200,
            token=self.tenant_a_token
        )
        
        if success:
            order_id_2 = result['order']['id']
            already_converted_2 = result.get('already_converted', False)
            if order_id == order_id_2 and already_converted_2:
                print(f"   ✅ IDEMPOTENCY VERIFIED: Same order returned, already_converted=true")
            else:
                print(f"   ❌ IDEMPOTENCY FAILED: Different order or flag incorrect")
                self.failed_tests.append("Quote conversion idempotency")

        # 8. ORDER & ORDER ITEMS
        print("\n" + "=" * 80)
        print("PHASE 4: ORDER & ORDER ITEMS MANAGEMENT")
        print("=" * 80)
        
        # Get order
        success, result, _ = self.test(
            "Get order",
            "GET", f"orders/{order_id}", 200,
            token=self.tenant_a_token
        )
        if success:
            print(f"   Order status: {result.get('order', {}).get('status')}")
            print(f"   Items: {len(result.get('items', []))}")

        # Add order items
        item_ids = []
        items_data = [
            {"description": "24x36 Aluminum Sign", "quantity": 2, "unit_price_cents": 5000},
            {"description": "Installation Service", "quantity": 1, "unit_price_cents": 10000},
            {"description": "Design Fee", "quantity": 1, "unit_price_cents": 2500}
        ]
        
        for item_data in items_data:
            success, result, _ = self.test(
                f"Add order item: {item_data['description']}",
                "POST", f"orders/{order_id}/items", 201,
                data=item_data,
                token=self.tenant_a_token
            )
            if success and 'id' in result:
                item_ids.append(result['id'])
                print(f"   Item ID: {result['id']}")

        # Update an item
        if item_ids:
            success, result, _ = self.test(
                "Update order item",
                "PATCH", f"orders/{order_id}/items/{item_ids[0]}", 200,
                data={"quantity": 3, "unit_price_cents": 4500},
                token=self.tenant_a_token
            )

        # Delete an item
        if len(item_ids) > 1:
            success, result, _ = self.test(
                "Delete order item",
                "DELETE", f"orders/{order_id}/items/{item_ids[-1]}", 204,
                token=self.tenant_a_token
            )

        # Get order with updated items
        success, result, _ = self.test(
            "Get order with items",
            "GET", f"orders/{order_id}", 200,
            token=self.tenant_a_token
        )
        if success:
            totals = result.get('totals', {})
            print(f"   Subtotal: ${totals.get('subtotal_cents', 0) / 100:.2f}")
            print(f"   Item count: {totals.get('item_count', 0)}")

        # Update order status: draft -> confirmed -> in_production -> completed
        for status in ['confirmed', 'in_production', 'completed']:
            success, result, _ = self.test(
                f"Set order status to {status}",
                "POST", f"orders/{order_id}/status", 200,
                data={"status": status},
                token=self.tenant_a_token
            )

        # 9. MULTIPLE WORK ORDERS PER ORDER
        print("\n" + "=" * 80)
        print("PHASE 5: MULTIPLE WORK ORDERS (CRITICAL TEST)")
        print("=" * 80)
        
        work_order_ids = []
        for i in range(1, 4):  # Create 3 work orders for the same order
            success, result, _ = self.test(
                f"Create work order #{i} for order {order_id}",
                "POST", "work-orders", 201,
                data={
                    "order_id": order_id,
                    "production_instructions": f"Work order {i} instructions",
                    "internal_notes": f"Internal notes for WO {i}"
                },
                token=self.tenant_a_token
            )
            if success and 'id' in result:
                work_order_ids.append(result['id'])
                wo_number = result.get('number')
                items_snapshot = result.get('items_snapshot', [])
                print(f"   Work Order ID: {result['id']}, Number: W-{wo_number}")
                print(f"   Items snapshot: {len(items_snapshot)} items")

        if len(work_order_ids) == 3:
            print(f"   ✅ MULTIPLE WORK ORDERS VERIFIED: Created {len(work_order_ids)} work orders for one order")
        else:
            print(f"   ❌ MULTIPLE WORK ORDERS FAILED: Only created {len(work_order_ids)} work orders")

        # Update work order production status
        if work_order_ids:
            for status in ['in_progress', 'completed']:
                success, result, _ = self.test(
                    f"Set work order production status to {status}",
                    "POST", f"work-orders/{work_order_ids[0]}/production-status", 200,
                    data={"production_status": status},
                    token=self.tenant_a_token
                )

        # 10. INVOICE WITH IDEMPOTENCY & PAYMENTS
        print("\n" + "=" * 80)
        print("PHASE 6: INVOICE IDEMPOTENCY & PAYMENTS")
        print("=" * 80)
        
        # Create invoice (first call)
        success, result, _ = self.test(
            "Create invoice from order (1st call)",
            "POST", "invoices", 201,
            data={
                "order_id": order_id,
                "title": f"Invoice for Order O-{order_number}",
                "description": "Custom signage project",
                "total_cents": 25000,  # $250.00
                "due_date": (datetime.now() + timedelta(days=30)).date().isoformat(),
                "notes": "Net 30"
            },
            token=self.tenant_a_token
        )
        
        if not success or 'invoice' not in result:
            print("❌ CRITICAL: Invoice creation failed")
            return self.print_summary()
        
        invoice_id = result['invoice']['id']
        invoice_number = result['invoice'].get('number')
        already_exists_1 = result.get('already_exists', False)
        print(f"   Invoice ID: {invoice_id}, Number: I-{invoice_number}")
        print(f"   Already exists: {already_exists_1}")

        # Create invoice (second call - IDEMPOTENCY TEST)
        success, result, _ = self.test(
            "Create invoice from order (2nd call - idempotent)",
            "POST", "invoices", 201,
            data={
                "order_id": order_id,
                "title": "Different title",
                "total_cents": 99999
            },
            token=self.tenant_a_token
        )
        
        if success:
            invoice_id_2 = result['invoice']['id']
            already_exists_2 = result.get('already_exists', False)
            if invoice_id == invoice_id_2 and already_exists_2:
                print(f"   ✅ INVOICE IDEMPOTENCY VERIFIED: Same invoice returned, already_exists=true")
            else:
                print(f"   ❌ INVOICE IDEMPOTENCY FAILED: Different invoice or flag incorrect")
                self.failed_tests.append("Invoice creation idempotency")

        # Update invoice
        success, result, _ = self.test(
            "Update invoice",
            "PATCH", f"invoices/{invoice_id}", 200,
            data={"notes": "Updated payment terms"},
            token=self.tenant_a_token
        )

        # Add payments with idempotency
        print("\n" + "-" * 80)
        print("Testing Payment Idempotency")
        print("-" * 80)
        
        # First payment (partial)
        idempotency_key_1 = f"payment-1-{timestamp}"
        success, result, _ = self.test(
            "Add payment 1 (partial, $100)",
            "POST", f"invoices/{invoice_id}/payments", 201,
            data={
                "amount_cents": 10000,
                "method": "card",
                "paid_on": datetime.now().date().isoformat(),
                "reference": "CARD-1234"
            },
            token=self.tenant_a_token,
            headers={"Idempotency-Key": idempotency_key_1}
        )
        
        if success:
            payment_id_1 = result['payment']['id']
            invoice_status_1 = result.get('invoice_status')
            already_exists = result.get('already_exists', False)
            print(f"   Payment ID: {payment_id_1}")
            print(f"   Invoice status: {invoice_status_1}")
            print(f"   Already exists: {already_exists}")

        # Duplicate payment with same idempotency key
        success, result, _ = self.test(
            "Add payment 1 again (same idempotency key)",
            "POST", f"invoices/{invoice_id}/payments", 201,
            data={
                "amount_cents": 99999,  # Different amount
                "method": "cash",
                "paid_on": datetime.now().date().isoformat()
            },
            token=self.tenant_a_token,
            headers={"Idempotency-Key": idempotency_key_1}
        )
        
        if success:
            payment_id_dup = result['payment']['id']
            already_exists = result.get('already_exists', False)
            if payment_id_1 == payment_id_dup and already_exists:
                print(f"   ✅ PAYMENT IDEMPOTENCY VERIFIED: Same payment returned, already_exists=true")
            else:
                print(f"   ❌ PAYMENT IDEMPOTENCY FAILED: Different payment or flag incorrect")
                self.failed_tests.append("Payment idempotency")

        # Second payment (complete the invoice)
        idempotency_key_2 = f"payment-2-{timestamp}"
        success, result, _ = self.test(
            "Add payment 2 (remaining $150)",
            "POST", f"invoices/{invoice_id}/payments", 201,
            data={
                "amount_cents": 15000,
                "method": "check",
                "paid_on": datetime.now().date().isoformat(),
                "reference": "CHECK-5678"
            },
            token=self.tenant_a_token,
            headers={"Idempotency-Key": idempotency_key_2}
        )
        
        if success:
            invoice_status_2 = result.get('invoice_status')
            print(f"   Invoice status after 2nd payment: {invoice_status_2}")
            if invoice_status_2 == 'paid':
                print(f"   ✅ INVOICE AUTO-STATUS VERIFIED: Status changed to 'paid'")
            else:
                print(f"   ⚠️  Invoice status is '{invoice_status_2}', expected 'paid'")

        # Get invoice with payments
        success, result, _ = self.test(
            "Get invoice with payments",
            "GET", f"invoices/{invoice_id}", 200,
            token=self.tenant_a_token
        )
        if success:
            invoice_data = result.get('invoice', {})
            payments = result.get('payments', [])
            print(f"   Total: ${invoice_data.get('total_cents', 0) / 100:.2f}")
            print(f"   Paid: ${invoice_data.get('paid_cents', 0) / 100:.2f}")
            print(f"   Balance: ${invoice_data.get('balance_due_cents', 0) / 100:.2f}")
            print(f"   Payments count: {len(payments)}")

        # 11. FILE UPLOAD & TENANT SCOPING
        print("\n" + "=" * 80)
        print("PHASE 7: FILE UPLOAD & TENANT SCOPING")
        print("=" * 80)
        
        # Create a test file
        test_file_content = b"Test file content for SignGuy AI"
        test_file = io.BytesIO(test_file_content)
        
        success, result, _ = self.test(
            "Upload file with parent attachment",
            "POST", "files/upload", 201,
            data={
                "visibility": "internal",
                "parent_type": "order",
                "parent_id": order_id
            },
            files={"file": ("test-document.txt", test_file, "text/plain")},
            token=self.tenant_a_token
        )
        
        if not success or 'file' not in result:
            print("❌ File upload failed")
            file_id = None
        else:
            file_id = result['file']['id']
            attachment = result.get('attachment')
            print(f"   File ID: {file_id}")
            print(f"   Attachment created: {attachment is not None}")

        # List files
        success, result, _ = self.test(
            "List files",
            "GET", f"files?parent_type=order&parent_id={order_id}", 200,
            token=self.tenant_a_token
        )
        if success:
            print(f"   Found {result.get('total', 0)} files")

        # Download file
        if file_id:
            success, result, status = self.test(
                "Download file (authenticated)",
                "GET", f"files/{file_id}/download", 200,
                token=self.tenant_a_token
            )

            # View file
            success, result, status = self.test(
                "View file (authenticated)",
                "GET", f"files/{file_id}/view", 200,
                token=self.tenant_a_token
            )

            # Toggle visibility
            success, result, _ = self.test(
                "Toggle file visibility",
                "PATCH", f"files/{file_id}/visibility", 200,
                data={"visibility": "customer_visible"},
                token=self.tenant_a_token
            )

        # 12. EMAIL SERVICE (SENDGRID UNCONFIGURED)
        print("\n" + "=" * 80)
        print("PHASE 8: EMAIL SERVICE (SENDGRID UNCONFIGURED)")
        print("=" * 80)
        
        # Get email templates
        success, result, _ = self.test(
            "Get email templates",
            "GET", "emails/templates", 200,
            token=self.tenant_a_token
        )
        if success:
            templates = result.get('templates', {})
            configured = result.get('configured', False)
            print(f"   Templates: {len(templates)}")
            print(f"   SendGrid configured: {configured}")
            if configured:
                print(f"   ⚠️  WARNING: SendGrid should be unconfigured for this test")

        # Send email (should fail gracefully)
        idempotency_key_email = f"email-1-{timestamp}"
        success, result, _ = self.test(
            "Send email (SendGrid unconfigured)",
            "POST", "emails/send", 201,
            data={
                "to_email": "customer@example.com",
                "subject": "Test Email",
                "body": "This is a test email",
                "template": "general",
                "customer_id": customer_id,
                "related_type": "order",
                "related_id": order_id
            },
            token=self.tenant_a_token,
            headers={"Idempotency-Key": idempotency_key_email}
        )
        
        if success:
            email_data = result.get('email', {})
            email_status = email_data.get('status')
            error_message = email_data.get('error_message', '')
            ok = result.get('ok', False)
            print(f"   Email status: {email_status}")
            print(f"   OK: {ok}")
            print(f"   Error: {error_message}")
            
            if email_status == 'failed' and not ok:
                print(f"   ✅ SENDGRID UNCONFIGURED HANDLING VERIFIED: status='failed', ok=false")
            else:
                print(f"   ⚠️  Expected status='failed' and ok=false for unconfigured SendGrid")

        # Send duplicate email (idempotency)
        success, result, _ = self.test(
            "Send email again (same idempotency key)",
            "POST", "emails/send", 201,
            data={
                "to_email": "different@example.com",
                "subject": "Different Subject",
                "body": "Different body"
            },
            token=self.tenant_a_token,
            headers={"Idempotency-Key": idempotency_key_email}
        )
        
        if success:
            already_sent = result.get('already_sent', False)
            if already_sent:
                print(f"   ✅ EMAIL IDEMPOTENCY VERIFIED: already_sent=true")
            else:
                print(f"   ❌ EMAIL IDEMPOTENCY FAILED: already_sent should be true")

        # Get email history
        success, result, _ = self.test(
            "Get email history",
            "GET", "emails/history?limit=10", 200,
            token=self.tenant_a_token
        )
        if success:
            print(f"   Email history: {result.get('total', 0)} emails")

        # 13. DASHBOARD
        print("\n" + "=" * 80)
        print("PHASE 9: DASHBOARD SUMMARY")
        print("=" * 80)
        
        success, result, _ = self.test(
            "Get dashboard summary",
            "GET", "dashboard/summary", 200,
            token=self.tenant_a_token
        )
        if success:
            counts = result.get('counts', {})
            print(f"   Active orders: {counts.get('active_orders', 0)}")
            print(f"   Quotes follow-up: {counts.get('quotes_follow_up', 0)}")
            print(f"   Work orders attention: {counts.get('work_orders_attention', 0)}")
            print(f"   Unpaid invoices: {counts.get('unpaid_invoices', 0)}")
            print(f"   Recent emails: {len(result.get('recent_emails', []))}")
            print(f"   Recent activity: {len(result.get('recent_activity', []))}")

        # 14. AUDIT TRAIL
        print("\n" + "=" * 80)
        print("PHASE 10: AUDIT TRAIL (ACTOR FIELDS)")
        print("=" * 80)
        
        success, result, _ = self.test(
            "Get audit events for order",
            "GET", f"audit?entity_type=order&entity_id={order_id}", 200,
            token=self.tenant_a_token
        )
        
        if success:
            items = result.get('items', [])
            print(f"   Audit events: {len(items)}")
            
            # Verify actor fields are non-empty
            missing_actor_fields = []
            for event in items:
                action = event.get('action', 'unknown')
                actor_user_id = event.get('actor_user_id')
                actor_email = event.get('actor_email')
                
                if not actor_user_id or not actor_email:
                    missing_actor_fields.append(action)
                    print(f"   ❌ Event '{action}' missing actor fields")
            
            if not missing_actor_fields:
                print(f"   ✅ AUDIT ACTOR FIELDS VERIFIED: All events have actor_user_id and actor_email")
            else:
                print(f"   ❌ AUDIT ACTOR FIELDS FAILED: {len(missing_actor_fields)} events missing actor fields")
                self.failed_tests.append("Audit actor fields")
            
            # Check for expected events
            actions = [e.get('action') for e in items]
            expected_actions = ['order.create_from_quote', 'order_item.add', 'order.status_change']
            found_expected = [a for a in expected_actions if any(a in action for action in actions)]
            print(f"   Expected actions found: {len(found_expected)}/{len(expected_actions)}")

        # 15. PERMISSION ENFORCEMENT
        print("\n" + "=" * 80)
        print("PHASE 11: PERMISSION ENFORCEMENT")
        print("=" * 80)
        
        # Create a staff user
        staff_email = f"staff-{timestamp}@example.com"
        success, result, _ = self.test(
            "Create staff user",
            "POST", "users", 201,
            data={
                "email": staff_email,
                "full_name": "Staff User",
                "role": "staff",
                "password": "StaffPass123!"
            },
            token=self.tenant_a_token
        )
        
        if success:
            staff_user_id = result.get('id')
            print(f"   Staff user ID: {staff_user_id}")
            
            # Login as staff
            success, result, _ = self.test(
                "Login as staff user",
                "POST", "auth/login", 200,
                data={"email": staff_email, "password": "StaffPass123!"}
            )
            
            if success:
                self.staff_token = result['access_token']
                print(f"   Staff token: {self.staff_token[:20]}...")
                
                # Try to create a user (should fail - needs USER_WRITE)
                success, result, status = self.test(
                    "Staff tries to create user (should 403)",
                    "POST", "users", 403,
                    data={
                        "email": f"another-{timestamp}@example.com",
                        "full_name": "Another User",
                        "role": "staff",
                        "password": "Pass123!"
                    },
                    token=self.staff_token
                )
                
                if status == 403:
                    print(f"   ✅ PERMISSION ENFORCEMENT VERIFIED: Staff cannot create users")
                else:
                    print(f"   ❌ PERMISSION ENFORCEMENT FAILED: Staff should not be able to create users")
                
                # Staff CAN create customers (has CUSTOMER_WRITE)
                success, result, status = self.test(
                    "Staff creates customer (should succeed)",
                    "POST", "customers", 201,
                    data={"name": "Staff Customer", "email": "staff-customer@example.com"},
                    token=self.staff_token
                )
                
                if status == 201:
                    print(f"   ✅ Staff can create customers (has CUSTOMER_WRITE)")

        # 16. TENANT ISOLATION (CRITICAL)
        print("\n" + "=" * 80)
        print("PHASE 12: TENANT ISOLATION (CRITICAL SECURITY TEST)")
        print("=" * 80)
        
        # Register Tenant B
        tenant_b_slug = f"test-tenant-b-{timestamp}"
        tenant_b_email = f"owner-b-{timestamp}@example.com"
        
        success, result, _ = self.test(
            "Register Tenant B",
            "POST", "auth/register-tenant", 201,
            data={
                "tenant_name": "Test Tenant B",
                "tenant_slug": tenant_b_slug,
                "owner_email": tenant_b_email,
                "owner_full_name": "Owner B",
                "owner_password": "SecurePass123!"
            }
        )
        
        if not success or 'access_token' not in result:
            print("❌ Tenant B registration failed, skipping isolation tests")
        else:
            self.tenant_b_token = result['access_token']
            self.tenant_b_id = result['tenant']['id']
            print(f"   Tenant B ID: {self.tenant_b_id}")
            print(f"   Token: {self.tenant_b_token[:20]}...")
            
            # Try to access Tenant A's resources with Tenant B's token
            print("\n" + "-" * 80)
            print("Testing Cross-Tenant Access (All should return 404)")
            print("-" * 80)
            
            isolation_tests = [
                ("customer", f"customers/{customer_id}"),
                ("quote", f"quotes/{quote_id}"),
                ("order", f"orders/{order_id}"),
                ("work_order", f"work-orders/{work_order_ids[0]}" if work_order_ids else None),
                ("invoice", f"invoices/{invoice_id}"),
                ("file download", f"files/{file_id}/download" if file_id else None),
                ("file view", f"files/{file_id}/view" if file_id else None),
            ]
            
            isolation_passed = 0
            isolation_failed = 0
            
            for resource_name, endpoint in isolation_tests:
                if endpoint is None:
                    continue
                
                success, result, status = self.test(
                    f"Tenant B tries to access Tenant A's {resource_name}",
                    "GET", endpoint, 404,
                    token=self.tenant_b_token
                )
                
                if status == 404:
                    isolation_passed += 1
                    print(f"   ✅ {resource_name}: Correctly returned 404")
                else:
                    isolation_failed += 1
                    print(f"   ❌ {resource_name}: SECURITY BREACH - returned {status}")
                    self.failed_tests.append(f"Tenant isolation: {resource_name}")
            
            print(f"\n   Isolation tests: {isolation_passed} passed, {isolation_failed} failed")
            
            # Test unauthenticated access to file download
            if file_id:
                success, result, status = self.test(
                    "Unauthenticated file download (should 401)",
                    "GET", f"files/{file_id}/download", 401
                )
                
                if status == 401:
                    print(f"   ✅ Unauthenticated file access correctly blocked")
                else:
                    print(f"   ❌ SECURITY BREACH: Unauthenticated access returned {status}")

        return self.print_summary()

    def print_summary(self):
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"Total tests run: {self.tests_run}")
        print(f"✅ Passed: {self.tests_passed}")
        print(f"❌ Failed: {self.tests_failed}")
        
        if self.failed_tests:
            print(f"\nFailed tests:")
            for test in self.failed_tests:
                print(f"  - {test}")
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        print(f"\nSuccess rate: {success_rate:.1f}%")
        
        if self.tests_failed == 0:
            print("\n🎉 ALL TESTS PASSED!")
            return 0
        else:
            print(f"\n⚠️  {self.tests_failed} test(s) failed")
            return 1

def main():
    tester = SignGuyTester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())
