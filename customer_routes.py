# This file contains all customer-facing ecommerce routes
# Add the following to app.py to integrate

# ========== CUSTOMER FACING WEBSITE ROUTES ==========

# ----------------SHOP HOME PAGE ----------------
@app.route("/shop")
def shop():
    db = get_db()
    
    # Get all products with proper sorting
    category_filter = request.args.get("category", "").strip()
    search = request.args.get("search", "").strip()
    sort = request.args.get("sort", "created_desc")
    page = int(request.args.get("page", 1))
    per_page = 12
    
    where_clause = "WHERE quantity > 0"
    params = []
    
    if category_filter:
        where_clause += " AND category = ?"
        params.append(category_filter)
    
    if search:
        where_clause += " AND (name LIKE ? OR category LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like])
    
    # Sorting
    sort_map = {
        "created_desc": "created_at DESC",
        "created_asc": "created_at ASC",
        "price_low": "price ASC",
        "price_high": "price DESC",
        "name_asc": "name ASC",
        "name_desc": "name DESC"
    }
    order_by = sort_map.get(sort, "created_at DESC")
    
    # Count total
    count_row = db.execute(
        f"SELECT COUNT(*) AS c FROM clothing {where_clause}",
        params
    ).fetchone()
    total_items = count_row["c"]
    total_pages = ceil(total_items / per_page)
    
    if page > total_pages:
        page = total_pages
    
    offset = (page - 1) * per_page
    
    # Get products
    products = db.execute(
        f"""
        SELECT * FROM clothing
        {where_clause}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
        """,
        params + [per_page, offset]
    ).fetchall()
    
    # Get categories for filter
    categories = db.execute(
        "SELECT DISTINCT category FROM clothing WHERE quantity > 0 ORDER BY category"
    ).fetchall()
    
    pages = list(range(1, total_pages + 1))
    
    return render_template(
        "shop.html",
        products=products,
        categories=categories,
        category_filter=category_filter,
        search=search,
        sort=sort,
        page=page,
        pages=pages,
        total_items=total_items,
        title="Shop - Clothing Store"
    )


# ----------------ADD TO CART ----------------
@app.route("/cart/add/<int:item_id>", methods=["POST"])
def add_to_cart(item_id):
    if 'session_id' not in session:
        session['session_id'] = str(datetime.datetime.now().timestamp())
    
    size = request.form.get("size", "M")
    quantity = int(request.form.get("quantity", 1))
    
    db = get_db()
    item = db.execute("SELECT * FROM clothing WHERE id=?", (item_id,)).fetchone()
    
    if not item or item["quantity"] < quantity:
        flash("❌ Item not available or insufficient stock.", "danger")
        return redirect(url_for("shop"))
    
    # Check if already in cart
    existing = db.execute(
        "SELECT * FROM cart WHERE session_id=? AND clothing_id=? AND size=?",
        (session['session_id'], item_id, size)
    ).fetchone()
    
    if existing:
        new_qty = existing["quantity"] + quantity
        db.execute(
            "UPDATE cart SET quantity=? WHERE id=?",
            (new_qty, existing["id"])
        )
    else:
        db.execute(
            "INSERT INTO cart (session_id, clothing_id, size, quantity, added_at) VALUES (?, ?, ?, ?, ?)",
            (session['session_id'], item_id, size, quantity, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
    
    db.commit()
    flash(f"✅ Added {item['name']} to cart!", "success")
    return redirect(url_for("shop"))


# ----------------VIEW CART ----------------
@app.route("/cart")
def view_cart():
    db = get_db()
    session_id = session.get('session_id', '')
    
    cart_items = []
    total = 0
    
    if session_id:
        rows = db.execute(
            """
            SELECT c.*, cl.name, cl.price, cl.image
            FROM cart c
            JOIN clothing cl ON c.clothing_id = cl.id
            WHERE c.session_id = ?
            ORDER BY c.added_at DESC
            """,
            (session_id,)
        ).fetchall()
        
        cart_items = rows
        for row in rows:
            total += row["price"] * row["quantity"]
    
    return render_template(
        "cart.html",
        cart_items=cart_items,
        total=total,
        title="Shopping Cart"
    )


# ----------------REMOVE FROM CART ----------------
@app.route("/cart/remove/<int:cart_id>")
def remove_from_cart(cart_id):
    db = get_db()
    db.execute("DELETE FROM cart WHERE id=?", (cart_id,))
    db.commit()
    flash("✅ Item removed from cart.", "success")
    return redirect(url_for("view_cart"))


# ----------------CHECKOUT ----------------
@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    db = get_db()
    session_id = session.get('session_id', '')
    
    if request.method == "POST":
        # Get form data
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        city = request.form.get("city", "").strip()
        state = request.form.get("state", "").strip()
        zip_code = request.form.get("zip_code", "").strip()
        
        if not all([name, email, address, city, state, zip_code]):
            flash("❌ Please fill all fields.", "danger")
            return redirect(url_for("checkout"))
        
        # Create or get customer
        customer = db.execute(
            "SELECT * FROM customers WHERE email=?", (email,)
        ).fetchone()
        
        if not customer:
            db.execute(
                """INSERT INTO customers (name, email, phone, address, city, state, zip_code, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, email, phone, address, city, state, zip_code, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            db.commit()
            customer = db.execute(
                "SELECT * FROM customers WHERE email=?", (email,)
            ).fetchone()
        else:
            # Update customer info
            db.execute(
                """UPDATE customers SET name=?, phone=?, address=?, city=?, state=?, zip_code=?
                   WHERE id=?""",
                (name, phone, address, city, state, zip_code, customer["id"])
            )
            db.commit()
        
        # Get cart items
        cart_items = db.execute(
            """SELECT c.*, cl.name, cl.price
               FROM cart c
               JOIN clothing cl ON c.clothing_id = cl.id
               WHERE c.session_id = ?""",
            (session_id,)
        ).fetchall()
        
        if not cart_items:
            flash("❌ Your cart is empty.", "danger")
            return redirect(url_for("view_cart"))
        
        # Calculate total and verify stock
        total = 0
        for item in cart_items:
            # Check if stock is available
            clothing = db.execute(
                "SELECT * FROM clothing WHERE id=?", (item["clothing_id"],)
            ).fetchone()
            if clothing["quantity"] < item["quantity"]:
                flash(f"❌ {item['name']} is out of stock.", "danger")
                return redirect(url_for("view_cart"))
            
            total += item["price"] * item["quantity"]
        
        # Create order
        order_number = f"ORD-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        db.execute(
            """INSERT INTO orders (order_number, customer_id, total_amount, status, payment_status, shipping_address, created_at, updated_at)
               VALUES (?, ?, ?, 'pending', 'unpaid', ?, ?, ?)""",
            (order_number, customer["id"], total, address, 
             datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        db.commit()
        
        order = db.execute(
            "SELECT * FROM orders WHERE order_number=?", (order_number,)
        ).fetchone()
        
        # Add order items and reduce stock
        for item in cart_items:
            db.execute(
                """INSERT INTO order_items (order_id, clothing_id, size, quantity, price)
                   VALUES (?, ?, ?, ?, ?)""",
                (order["id"], item["clothing_id"], item["size"], item["quantity"], item["price"])
            )
            
            # Reduce stock
            db.execute(
                "UPDATE clothing SET quantity = quantity - ? WHERE id=?",
                (item["quantity"], item["clothing_id"])
            )
            
            # Create stock log
            db.execute(
                """INSERT INTO stock_logs (clothing_id, change_type, qty_change, note, admin, created_at)
                   VALUES (?, 'out', ?, 'Order placed', 'system', ?)""",
                (item["clothing_id"], -item["quantity"], 
                 datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
        
        db.commit()
        
        # Create notification for admin
        db.execute(
            """INSERT INTO notifications (type, recipient, title, message, order_id, created_at)
               VALUES (?, 'admin', 'New Order Placed', ?, ?, ?)""",
            (f"order_placed", 
             f"New order {order_number} from {name} (${total:.2f})",
             order["id"],
             datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        
        # Create notification for customer
        db.execute(
            """INSERT INTO notifications (type, recipient, title, message, order_id, created_at)
               VALUES (?, ?, 'Order Confirmed', ?, ?, ?)""",
            ("order_placed", customer["id"], 
             f"Your order {order_number} has been received. Total: ${total:.2f}",
             order["id"],
             datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        
        db.commit()
        
        # Clear cart
        db.execute("DELETE FROM cart WHERE session_id=?", (session_id,))
        db.commit()
        
        log_action("order_placed", f"Order {order_number} placed by {name}")
        flash(f"✅ Order placed successfully! Order ID: {order_number}", "success")
        return redirect(url_for("order_confirmation", order_id=order["id"]))
    
    # GET: Show checkout form
    cart_items = []
    total = 0
    
    if session_id:
        cart_items = db.execute(
            """SELECT c.*, cl.name, cl.price
               FROM cart c
               JOIN clothing cl ON c.clothing_id = cl.id
               WHERE c.session_id = ?""",
            (session_id,)
        ).fetchall()
        
        for item in cart_items:
            total += item["price"] * item["quantity"]
    
    return render_template(
        "checkout.html",
        cart_items=cart_items,
        total=total,
        title="Checkout"
    )


# ----------------ORDER CONFIRMATION ----------------
@app.route("/order/<int:order_id>/confirmation")
def order_confirmation(order_id):
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    
    if not order:
        flash("❌ Order not found.", "danger")
        return redirect(url_for("shop"))
    
    items = db.execute(
        """SELECT oi.*, c.name, c.image FROM order_items oi
           JOIN clothing c ON oi.clothing_id = c.id
           WHERE oi.order_id = ?""",
        (order_id,)
    ).fetchall()
    
    customer = db.execute(
        "SELECT * FROM customers WHERE id=?", (order["customer_id"],)
    ).fetchone()
    
    return render_template(
        "order_confirmation.html",
        order=order,
        items=items,
        customer=customer,
        title="Order Confirmation"
    )


# ----------------TRACK ORDER ----------------
@app.route("/order/<int:order_id>/track")
def track_order(order_id):
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    
    if not order:
        flash("❌ Order not found.", "danger")
        return redirect(url_for("shop"))
    
    items = db.execute(
        """SELECT oi.*, c.name FROM order_items oi
           JOIN clothing c ON oi.clothing_id = c.id
           WHERE oi.order_id = ?""",
        (order_id,)
    ).fetchall()
    
    customer = db.execute(
        "SELECT * FROM customers WHERE id=?", (order["customer_id"],)
    ).fetchone()
    
    return render_template(
        "track_order.html",
        order=order,
        items=items,
        customer=customer,
        title="Track Order"
    )


# --------ADMIN ORDERS MANAGEMENT --------
@app.route("/admin/orders")
@require_login
@require_role("admin", "superadmin")
def admin_orders():
    db = get_db()
    
    status_filter = request.args.get("status", "").strip()
    search = request.args.get("search", "").strip()
    page = int(request.args.get("page", 1))
    per_page = 10
    
    where_clause = "WHERE 1=1"
    params = []
    
    if status_filter:
        where_clause += " AND o.status = ?"
        params.append(status_filter)
    
    if search:
        where_clause += " AND (o.order_number LIKE ? OR c.name LIKE ? OR c.email LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like])
    
    # Count total
    count_row = db.execute(
        f"SELECT COUNT(*) AS cnt FROM orders o JOIN customers c ON o.customer_id = c.id {where_clause}",
        params
    ).fetchone()
    total = count_row["cnt"]
    total_pages = ceil(total / per_page)
    
    if page > total_pages:
        page = total_pages
    
    offset = (page - 1) * per_page
    
    orders = db.execute(
        f"""SELECT o.*, c.name, c.email, c.phone
           FROM orders o
           JOIN customers c ON o.customer_id = c.id
           {where_clause}
           ORDER BY o.created_at DESC
           LIMIT ? OFFSET ?""",
        params + [per_page, offset]
    ).fetchall()
    
    pages = list(range(1, total_pages + 1))
    
    return render_template(
        "admin_orders.html",
        orders=orders,
        status_filter=status_filter,
        search=search,
        page=page,
        pages=pages,
        total=total,
        title="Order Management"
    )


# --------UPDATE ORDER STATUS --------
@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@require_login
@require_role("admin", "superadmin")
def update_order_status(order_id):
    status = request.form.get("status", "pending")
    notes = request.form.get("notes", "")
    
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    
    if not order:
        flash("❌ Order not found.", "danger")
        return redirect(url_for("admin_orders"))
    
    db.execute(
        "UPDATE orders SET status=?, notes=?, updated_at=? WHERE id=?",
        (status, notes, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), order_id)
    )
    
    # Create notification for customer
    status_messages = {
        "pending": "Your order is being processed.",
        "confirmed": "Your order has been confirmed.",
        "shipped": "Your order has been shipped!",
        "delivered": "Your order has been delivered. Thank you!",
        "cancelled": "Your order has been cancelled."
    }
    
    message = status_messages.get(status, f"Order status updated to {status}")
    
    db.execute(
        """INSERT INTO notifications (type, recipient, title, message, order_id, created_at)
           VALUES (?, ?, 'Order Status Updated', ?, ?, ?)""",
        ("order_status_update", order["customer_id"], message, order_id,
         datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    
    db.commit()
    
    log_action("order_update", f"Order #{order['order_number']} status updated to {status}")
    flash(f"✅ Order status updated to {status}!", "success")
    return redirect(url_for("admin_orders"))


# --------ORDER DETAILS --------
@app.route("/admin/orders/<int:order_id>")
@require_login
@require_role("admin", "superadmin")
def admin_order_detail(order_id):
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    
    if not order:
        flash("❌ Order not found.", "danger")
        return redirect(url_for("admin_orders"))
    
    items = db.execute(
        """SELECT oi.*, c.name, c.image FROM order_items oi
           JOIN clothing c ON oi.clothing_id = c.id
           WHERE oi.order_id = ?""",
        (order_id,)
    ).fetchall()
    
    customer = db.execute(
        "SELECT * FROM customers WHERE id=?", (order["customer_id"],)
    ).fetchone()
    
    return render_template(
        "admin_order_detail.html",
        order=order,
        items=items,
        customer=customer,
        title="Order Details"
    )


# --------ADMIN CUSTOMERS --------
@app.route("/admin/customers")
@require_login
@require_role("admin", "superadmin")
def admin_customers():
    db = get_db()
    
    search = request.args.get("search", "").strip()
    page = int(request.args.get("page", 1))
    per_page = 15
    
    where_clause = "WHERE 1=1"
    params = []
    
    if search:
        where_clause += " AND (name LIKE ? OR email LIKE ? OR phone LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like])
    
    count_row = db.execute(
        f"SELECT COUNT(*) AS cnt FROM customers {where_clause}",
        params
    ).fetchone()
    total = count_row["cnt"]
    total_pages = ceil(total / per_page)
    
    if page > total_pages:
        page = total_pages
    
    offset = (page - 1) * per_page
    
    customers = db.execute(
        f"""SELECT c.*, COUNT(o.id) as order_count
           FROM customers c
           LEFT JOIN orders o ON c.id = o.customer_id
           {where_clause}
           GROUP BY c.id
           ORDER BY c.created_at DESC
           LIMIT ? OFFSET ?""",
        params + [per_page, offset]
    ).fetchall()
    
    pages = list(range(1, total_pages + 1))
    
    return render_template(
        "admin_customers.html",
        customers=customers,
        search=search,
        page=page,
        pages=pages,
        total=total,
        title="Customer Management"
    )


# --------ADMIN NOTIFICATIONS --------
@app.route("/admin/notifications")
@require_login
def admin_notifications():
    db = get_db()
    
    # Get unread count for badge
    unread_count = db.execute(
        "SELECT COUNT(*) AS cnt FROM notifications WHERE recipient='admin' AND read=0"
    ).fetchone()["cnt"]
    
    # Get notifications
    page = int(request.args.get("page", 1))
    per_page = 20
    
    count_row = db.execute(
        "SELECT COUNT(*) AS cnt FROM notifications WHERE recipient='admin'"
    ).fetchone()
    total = count_row["cnt"]
    total_pages = ceil(total / per_page)
    
    if page > total_pages:
        page = total_pages
    
    offset = (page - 1) * per_page
    
    notifications = db.execute(
        """SELECT * FROM notifications WHERE recipient='admin'
           ORDER BY created_at DESC
           LIMIT ? OFFSET ?""",
        (per_page, offset)
    ).fetchall()
    
    pages = list(range(1, total_pages + 1))
    
    return render_template(
        "admin_notifications.html",
        notifications=notifications,
        unread_count=unread_count,
        page=page,
        pages=pages,
        total=total,
        title="Notifications"
    )


# --------MARK NOTIFICATION AS READ --------
@app.route("/notification/<int:notif_id>/read")
@require_login
def mark_notification_read(notif_id):
    db = get_db()
    db.execute("UPDATE notifications SET read=1 WHERE id=?", (notif_id,))
    db.commit()
    return {"success": True}
