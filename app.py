from flask import Flask, render_template, request, redirect, url_for, session
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message

app = Flask(__name__)
app.secret_key = 'secret123'

# 📁 Upload folder
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'codnellsmall@gmail.com'
app.config['MAIL_PASSWORD'] = 'ckkb ehdh gcom ygzo'
app.config['MAIL_DEFAULT_SENDER'] = 'codnellsmall@gmail.com'
mail = Mail(app)

# 🛍️ Store products in memory
products = []

# 📦 Store orders in memory
orders = []


# 🏠 HOME
@app.route('/')
def home():
    latest_products = products[-3:]
    return render_template('index.html', products=latest_products)


# 🛒 SHOP
@app.route('/shop')
def shop():
    return render_template('shop.html', products=products)


# 🔧 ADMIN - ADD PRODUCTS
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        image = request.files['image']

        if image:
            filename = secure_filename(image.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(filepath)

            products.append({
                'id': len(products),
                'name': name,
                'price': float(price),
                'image': filepath
            })

        return redirect(url_for('admin'))

    return render_template('admin.html', products=products, orders=orders)


# 📋 ADMIN - VIEW ORDERS
@app.route('/admin/orders')
def admin_orders():
    return render_template('admin.html', products=products, orders=orders)


# 🔄 ADMIN - UPDATE ORDER STATUS
@app.route('/admin/order/<int:order_id>/status', methods=['POST'])
def update_order_status(order_id):
    new_status = request.form.get('status')
    
    order = next((o for o in orders if o['id'] == order_id), None)
    if order:
        old_status = order['status']
        order['status'] = new_status
        
        # 📧 Send HTML email notification to customer with theme
        customer_email = order['customer_email']
        
        items_html = "".join([f'<div class="order-item"><span>{item["name"]}</span><span style="color:#00ff88">R{item["price"]}</span></div>' for item in order['items']])
        # Status color mapping
        status_colors = {
             'order placed': '#17a2b8',
             'payment received': '#ffc107',
             'out for delivery': '#fd7e14',
             'delivered': '#28a745'
         }
        new_color = status_colors.get(new_status, '#fd7e14')
         
        status_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Order Update #{order_id}</title>
            <style>
                *{{margin:0;padding:0;box-sizing:border-box;font-family:'Inter',sans-serif}}
                body{{background:#000;color:#fff;padding:20px}}
                .email-wrapper{{max-width:600px;margin:auto;background:#0a0a0a;border:1px solid #333;border-radius:10px;overflow:hidden}}
                .header{{background:linear-gradient(135deg,#000,#001a0f);padding:30px;text-align:center;border-bottom:1px solid #222}}
                .logo{{font-weight:700;font-size:1.8rem;color:#00ff88;text-decoration:none}}
                .update-badge{{background:#fd7e14;color:#fff;padding:10px 20px;border-radius:25px;font-size:1rem;margin-top:15px;display:inline-block}}
                .content{{padding:30px}}
                .order-id{{font-size:1.2rem;color:#00ff88;margin-bottom:15px;font-weight:700}}
                .status-change{{margin:25px 0;padding:20px;background:#111;border-radius:8px;border-left:4px solid #fd7e14}}
                .status-change .old{{color:#ffc107;font-weight:700}}
                .status-change .new{{color:#00ff88;font-weight:700;font-size:1.1rem}}
                .order-item{{padding:12px 0;border-bottom:1px solid #222;display:flex;justify-content:space-between}}
                .order-total{{font-size:1.3rem;color:#00ff88;font-weight:700;margin-top:20px;padding-top:15px;border-top:1px solid #333;text-align:right}}
                .footer{{background:#111;padding:20px;text-align:center;color:#888;font-size:0.85rem;border-top:1px solid #222}}
                .note{{background:#111;border-left:3px solid #00ff88;padding:15px;margin-top:20px;color:#ccc;font-size:0.9rem}}
            </style>
        </head>
        <body>
            <div class="email-wrapper">
                <div class="header">
                    <div class="logo">CRIYOYO</div>
                    <h2 style="color:#fff;margin-top:10px;font-weight:400">Order Status Updated</h2>
                    <div class="update-badge" style="background:{new_color};color:#fff">📦 Order #{order_id}</div>
                </div>
                <div class="content">
                    <div class="order-id">Order #{order_id}</div>
                    
                    <p>Hi there,</p>
                    <p style="margin-top:10px">Your order status has been updated:</p>
                    
                    <div class="status-change" style="border-left:4px solid {new_color}">
                        <p><span class="old">◀ {old_status.title()}</span> &nbsp; → &nbsp; <span class="new" style="color:{new_color}">{new_status.title()}</span></p>
                    </div>
                    
                    <p style="margin-top:20px"><strong>Order Contents:</strong></p>
                    {items_html}
                    
                    <div class="order-total">Total: R{order['total']}</div>
                    
                    <div class="note">
                        <strong>What's next?</strong><br>
                        {"We'll notify you when your order is out for delivery!" if new_status == "out for delivery" else
                         "Your order will be delivered soon!" if new_status == "delivered" else
                         "Payment confirmed! We're preparing your order." if new_status == "payment received" else
                         "We'll update you as your order progresses." if new_status == "order placed" else
                         "We'll update you as your order progresses."}
                    </div>
                </div>
                <div class="footer">
                    © 2026 Criyoyo Clothing. All rights reserved.<br>
                    <span style="color:#666">This is an automated message.</span>
                </div>
            </div>
        </body>
        </html>
        """
        
        status_msg = Message(
            subject=f"📦 Order #{order_id} - {new_status.title()} - Criyoyo",
            recipients=[customer_email]
        )
        status_msg.html = status_html
        
        plain_body = f"""Dear Customer,

Your order #{order_id} status has been updated.

Previous Status: {old_status.title()}
New Status: {new_status.title()}

Order Summary:
""" + "\n".join([f"- {item['name']} - R{item['price']}" for item in order['items']]) + f"""

Total: R{order['total']}

Thank you for shopping with us!
"""
        status_msg.body = plain_body
        
        try:
            mail.send(status_msg)
        except Exception as e:
            print("Email error:", e)
    
    return redirect(url_for('admin_orders'))


# 🛒 ADD TO CART
@app.route('/add_to_cart/<int:id>')
def add_to_cart(id):
    if 'cart' not in session:
        session['cart'] = []

    session['cart'].append(id)
    session.modified = True

    return redirect(request.referrer)


# 🛒 CART PAGE
@app.route('/cart')
def cart():
    cart_items = []
    total = 0

    if 'cart' in session:
        for id in session['cart']:
            product = next((p for p in products if p['id'] == id), None)
            if product:
                cart_items.append(product)
                total += product['price']

    return render_template('cart.html', items=cart_items, total=total)


# 🗑️ REMOVE ITEM
@app.route('/remove_from_cart/<int:index>')
def remove_from_cart(index):
    if 'cart' in session and index < len(session['cart']):
        session['cart'].pop(index)
        session.modified = True

    return redirect(url_for('cart'))


# 💳 CHECKOUT + SEND EMAILS + STORE ORDER
@app.route('/checkout', methods=['POST'])
def checkout():
    if 'cart' not in session or len(session['cart']) == 0:
        return redirect(url_for('cart'))

    user_email = request.form.get('email')

    total = 0
    order_items = []

    for id in session['cart']:
        product = next((p for p in products if p['id'] == id), None)
        if product:
            total += product['price']
            order_items.append({
                'name': product['name'],
                'price': product['price']
            })

    # Create order
    order = {
        'id': len(orders),
        'customer_email': user_email,
        'items': order_items,
        'total': total,
        'status': 'order placed',
        'created_at': str(datetime.now())
    }
    orders.append(order)

    # Status color mapping matching admin page
    status_colors = {
        'order placed': '#17a2b8',
        'payment received': '#ffc107',
        'out for delivery': '#fd7e14',
        'delivered': '#28a745'
    }
    status_color = status_colors.get(order['status'], '#17a2b8')
    status_display = order['status'].title()

    # 📧 EMAIL TO ADMIN - HTML themed
    admin_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>New Order #{order['id']}</title>
        <style>
            *{{margin:0;padding:0;box-sizing:border-box;font-family:'Inter',sans-serif}}
            body{{background:#000;color:#fff;padding:20px}}
            .email-wrapper{{max-width:600px;margin:auto;background:#0a0a0a;border:1px solid #333;border-radius:10px;overflow:hidden}}
            .header{{background:linear-gradient(135deg,#000,#001a0f);padding:30px;text-align:center;border-bottom:1px solid #222}}
            .logo{{font-weight:700;font-size:1.8rem;color:#00ff88;text-decoration:none}}
            .content{{padding:30px}}
            .order-id{{font-size:1.5rem;color:#00ff88;margin-bottom:20px;font-weight:700}}
            .order-item{{padding:12px 0;border-bottom:1px solid #222;display:flex;justify-content:space-between}}
            .order-total{{font-size:1.3rem;color:#00ff88;font-weight:700;margin-top:20px;padding-top:15px;border-top:1px solid #333;text-align:right}}
            .status-badge{{display:inline-block;background:#17a2b8;color:#fff;padding:8px 16px;border-radius:20px;font-size:0.85rem;margin-top:10px}}
            .footer{{background:#111;padding:20px;text-align:center;color:#888;font-size:0.85rem;border-top:1px solid #222}}
            .label{{color:#888;font-size:0.9rem}}
            .value{{color:#fff;font-weight:500}}
        </style>
    </head>
    <body>
        <div class="email-wrapper">
            <div class="header">
                <div class="logo">CRIYOYO</div>
                <h2 style="color:#fff;margin-top:10px;font-weight:400">New Order Received</h2>
            </div>
            <div class="content">
                <div class="order-id">Order #{order['id']}</div>
                
                <p><span class="label">Customer Email:</span><br>
                <span class="value">{{ user_email }}</span></p>
                
                <p style="margin-top:20px"><span class="label">Order Details:</span></p>
                {"".join([f'<div class="order-item"><span>{item["name"]}</span><span style="color:#00ff88">R{item["price"]}</span></div>' for item in order_items])}
                
                <div class="order-total">Total: R{total}</div>
                
                <p style="margin-top:20px"><span class="label">Current Status:</span><br>
                <span style="display:inline-block;background:{status_color};color:#fff;padding:8px 16px;border-radius:20px;font-size:0.85rem;margin-top:10px">{status_display}</span></p>
            </div>
            <div class="footer">
                © 2026 Criyoyo Clothing. All rights reserved.
            </div>
        </div>
    </body>
    </html>
    """

    admin_msg = Message(
        subject=f"🛒 New Order #{order['id']} - Criyoyo",
        recipients=['codnellsmall@gmail.com']
    )
    admin_msg.html = admin_html
    admin_msg.body = f"New Order #{order['id']} from {user_email}\nTotal: R{total}\nStatus: {status_display}"

    # 📧 EMAIL TO USER - HTML themed
    status_display = order['status'].title()
    user_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Order Confirmation #{order['id']}</title>
        <style>
            *{{margin:0;padding:0;box-sizing:border-box;font-family:'Inter',sans-serif}}
            body{{background:#000;color:#fff;padding:20px}}
            .email-wrapper{{max-width:600px;margin:auto;background:#0a0a0a;border:1px solid #333;border-radius:10px;overflow:hidden}}
            .header{{background:linear-gradient(135deg,#000,#001a0f);padding:30px;text-align:center;border-bottom:1px solid #222}}
            .logo{{font-weight:700;font-size:1.8rem;color:#00ff88;text-decoration:none}}
            .success-badge{{background:#28a745;color:#fff;padding:10px 20px;border-radius:25px;font-size:1rem;margin-top:15px;display:inline-block}}
            .content{{padding:30px}}
            .order-id{{font-size:1.2rem;color:#00ff88;margin-bottom:15px;font-weight:700}}
            .order-item{{padding:12px 0;border-bottom:1px solid #222;display:flex;justify-content:space-between}}
            .order-total{{font-size:1.3rem;color:#00ff88;font-weight:700;margin-top:20px;padding-top:15px;border-top:1px solid #333;text-align:right}}
            .status-badge{{display:inline-block;background:#17a2b8;color:#fff;padding:8px 16px;border-radius:20px;font-size:0.85rem;margin-top:10px}}
            .footer{{background:#111;padding:20px;text-align:center;color:#888;font-size:0.85rem;border-top:1px solid #222}}
            .note{{background:#111;border-left:3px solid #00ff88;padding:15px;margin-top:20px;color:#ccc;font-size:0.9rem}}
        </style>
    </head>
    <body>
        <div class="email-wrapper">
            <div class="header">
                <div class="logo">CRIYOYO</div>
                <h2 style="color:#fff;margin-top:10px;font-weight:400">Order Confirmed!</h2>
                <div class="success-badge">✅ Order Placed Successfully</div>
            </div>
            <div class="content">
                <div class="order-id">Order #{order['id']}</div>
                
                <p style="margin-bottom:20px">Thank you for your order! Here are your details:</p>
                
                {"".join([f'<div class="order-item"><span>{item["name"]}</span><span style="color:#00ff88">R{item["price"]}</span></div>' for item in order_items])}
                
                <div class="order-total">Total: R{total}</div>
                
                <p style="margin-top:20px"><strong>Current Status:</strong><br>
                <span style="display:inline-block;background:{status_color};color:#fff;padding:8px 16px;border-radius:20px;font-size:0.85rem;margin-top:10px">{status_display}</span></p>
                
                <div class="note">
                    <strong>What's next?</strong><br>
                    We'll notify you when your payment is confirmed and your order moves to the next stage.
                </div>
            </div>
            <div class="footer">
                © 2026 Criyoyo Clothing. All rights reserved.<br>
                <span style="color:#666">This is an automated message.</span>
            </div>
        </div>
    </body>
    </html>
    """

    user_msg = Message(
        subject=f"✅ Order Confirmed! #{order['id']} - Criyoyo",
        recipients=[user_email]
    )
    user_msg.html = user_html
    user_msg.body = f"Thank you for your order!\n\nOrder #{order['id']}\nTotal: R{total}\nStatus: {status_display}\n\nWe will contact you soon."

    try:
        mail.send(admin_msg)
        mail.send(user_msg)
    except Exception as e:
        print("Email error:", e)

    # 🧹 Clear cart
    session.pop('cart', None)

    return redirect(url_for('shop'))


# 📩 CONTACT PAGE
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    message_sent = False

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']

        msg = Message(
            subject="📩 New Contact Message",
            recipients=['codnellsmall@gmail.com']  # change this
        )
        msg.body = f"""
Name: {name}
Email: {email}

Message:
{message}
"""

        try:
            mail.send(msg)
            message_sent = True
        except Exception as e:
            print("Email error:", e)

    return render_template('contact.html', message_sent=message_sent)


# ▶️ RUN APP
if __name__ == '__main__':
    app.run(debug=True)