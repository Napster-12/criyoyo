from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    make_response,
    jsonify
)

import os
import json
import pyotp
import qrcode
import io
import base64
import sqlite3

from datetime import datetime
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message

# ==============================
# ADMIN AUTH
# ==============================

ADMIN_EMAIL = "codnellsmall@gmail.com"
ADMIN_PASSWORD = "Cri123"  # change this later

app = Flask(__name__)

# ==============================
# DATABASE
# ==============================

DATABASE = 'criyoyo.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Products table
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            image TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Orders table
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_email TEXT NOT NULL,
            shipping_address TEXT NOT NULL,
            delivery_type TEXT NOT NULL,
            delivery_cost REAL NOT NULL,
            subtotal REAL NOT NULL,
            total REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'order placed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Order items table
    c.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            product_price REAL NOT NULL,
            size TEXT NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

# ==============================
# 2FA STORAGE
# ==============================

TOTP_SECRET_FILE = "admin_totp_secret.txt"

def get_totp_secret():
    if os.path.exists(TOTP_SECRET_FILE):
        with open(TOTP_SECRET_FILE, 'r') as f:
            return f.read().strip()
    secret = pyotp.random_base32()
    with open(TOTP_SECRET_FILE, 'w') as f:
        f.write(secret)
    return secret

def get_provisioning_uri():
    secret = get_totp_secret()
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=ADMIN_EMAIL,
        issuer_name="CRIYOYO Admin"
    )

def verify_totp(code):
    secret = get_totp_secret()
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)

# ==============================
# SECURITY
# ==============================

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-secret-key"
)

# ==============================
# COOKIE CONFIGURATION
# ==============================

app.config['COOKIE_CONSENT_COOKIE'] = 'cookie_consent'
app.config['PERSISTENT_CART_COOKIE'] = 'persistent_cart'
app.config['USER_PREFERENCES_COOKIE'] = 'user_preferences'
app.config['COOKIE_MAX_AGE'] = 60 * 60 * 24 * 365

COOKIE_CATEGORIES = {
    'essential': 'Essential cookies',
    'functional': 'Functional cookies',
    'analytics': 'Analytics cookies',
    'marketing': 'Marketing cookies'
}

# ==============================
# UPLOAD CONFIG
# ==============================

UPLOAD_FOLDER = 'static/uploads'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ==============================
# MAIL CONFIG
# ==============================

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

app.config['MAIL_USERNAME'] = 'codnellsmall@gmail.com'

# IMPORTANT:
# Replace with your REAL Gmail App Password
app.config['MAIL_PASSWORD'] = 'rebe zhfq blgw yzih'

app.config['MAIL_DEFAULT_SENDER'] = 'codnellsmall@gmail.com'

mail = Mail(app)


@app.context_processor
def inject_cart_count():
    cart_count = len(session.get('cart', []))
    return dict(cart_count=cart_count)


# ==============================
# IN-MEMORY DATABASE
# ==============================

# products = []
# orders = []

def get_all_products():
    conn = get_db()
    products = [dict(row) for row in conn.execute('SELECT * FROM products ORDER BY id DESC').fetchall()]
    conn.close()
    return products

def get_product_by_id(product_id):
    conn = get_db()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    conn.close()
    return dict(product) if product else None

def add_product(name, price, image):
    conn = get_db()
    conn.execute('INSERT INTO products (name, price, image) VALUES (?, ?, ?)', (name, price, image))
    conn.commit()
    product_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    conn.close()
    return product_id

def delete_product(product_id):
    conn = get_db()
    # Get image path to delete file
    product = conn.execute('SELECT image FROM products WHERE id = ?', (product_id,)).fetchone()
    conn.execute('DELETE FROM products WHERE id = ?', (product_id,))
    conn.commit()
    conn.close()
    return product['image'] if product else None

def get_all_orders():
    conn = get_db()
    orders = []
    for row in conn.execute('SELECT * FROM orders ORDER BY id DESC').fetchall():
        order = dict(row)
        # Get order items
        items = conn.execute('SELECT product_name, product_price, size FROM order_items WHERE order_id = ?', (order['id'],)).fetchall()
        order['items'] = [dict(item) for item in items]
        orders.append(order)
    conn.close()
    return orders

def get_order_by_id(order_id):
    conn = get_db()
    order = conn.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()
    if order:
        order = dict(order)
        items = conn.execute('SELECT product_name, product_price, size FROM order_items WHERE order_id = ?', (order['id'],)).fetchall()
        order['items'] = [dict(item) for item in items]
    conn.close()
    return order

def create_order(customer_email, shipping_address, delivery_type, delivery_cost, subtotal, total, items):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        INSERT INTO orders (customer_email, shipping_address, delivery_type, delivery_cost, subtotal, total, status)
        VALUES (?, ?, ?, ?, ?, ?, 'order placed')
    ''', (customer_email, shipping_address, delivery_type, delivery_cost, subtotal, total))
    order_id = c.lastrowid
    
    # Insert order items
    for item in items:
        c.execute('''
            INSERT INTO order_items (order_id, product_name, product_price, size)
            VALUES (?, ?, ?, ?)
        ''', (order_id, item['name'], item['price'], item['size']))
    
    conn.commit()
    conn.close()
    return order_id

def update_order_status(order_id, new_status):
    conn = get_db()
    conn.execute('UPDATE orders SET status = ? WHERE id = ?', (new_status, order_id))
    conn.commit()
    conn.close()

def delete_order(order_id):
    conn = get_db()
    conn.execute('DELETE FROM order_items WHERE order_id = ?', (order_id,))
    conn.execute('DELETE FROM orders WHERE id = ?', (order_id,))
    conn.commit()
    conn.close()

# ==============================
# COOKIE UTILITIES
# ==============================

def get_cookie_consent(req):

    consent_cookie = req.cookies.get(
        app.config['COOKIE_CONSENT_COOKIE']
    )

    if consent_cookie:
        try:
            return json.loads(consent_cookie)
        except:
            pass

    return {
        'essential': True
    }


def set_cookie_consent(response, preferences):

    response.set_cookie(
        app.config['COOKIE_CONSENT_COOKIE'],
        json.dumps(preferences),
        max_age=app.config['COOKIE_MAX_AGE'],
        httponly=True,
        secure=False,
        samesite='Lax'
    )

    return response


def get_persistent_cart(req):

    cart_cookie = req.cookies.get(
        app.config['PERSISTENT_CART_COOKIE']
    )

    if cart_cookie:
        try:
            data = json.loads(cart_cookie)

            if isinstance(data, list):
                return data

        except:
            pass

    return []


def set_persistent_cart(response, cart_items):

    response.set_cookie(
        app.config['PERSISTENT_CART_COOKIE'],
        json.dumps(cart_items),
        max_age=app.config['COOKIE_MAX_AGE'],
        httponly=True,
        secure=False,
        samesite='Lax'
    )

    return response


def get_user_preferences(req):

    prefs_cookie = req.cookies.get(
        app.config['USER_PREFERENCES_COOKIE']
    )

    if prefs_cookie:
        try:
            return json.loads(prefs_cookie)
        except:
            pass

    return {
        'theme': 'dark',
        'currency': 'ZAR'
    }


def set_user_preferences(response, preferences):

    response.set_cookie(
        app.config['USER_PREFERENCES_COOKIE'],
        json.dumps(preferences),
        max_age=app.config['COOKIE_MAX_AGE'],
        httponly=True,
        secure=False,
        samesite='Lax'
    )

    return response

# ==============================
# HOME
# ==============================

@app.route('/')
def home():

    products = get_all_products()
    latest_products = products[-3:]

    return render_template(
        'index.html',
        products=latest_products
    )

# ==============================
# SHOP
# ==============================

@app.route('/shop')
def shop():
    products = get_all_products()

    return render_template(
        'shop.html',
        products=products
    )

@app.route('/login', methods=['GET', 'POST'])
def login():

    error = None

    if request.method == 'POST':

        email = request.form.get('email')
        password = request.form.get('password')

        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session['admin_pass_valid'] = True
            return redirect(url_for('verify_2fa'))
        else:
            error = "Invalid admin credentials"

    return render_template('login.html', error=error)

# ==============================
# 2FA VERIFICATION
# ==============================

@app.route('/verify-2fa', methods=['GET', 'POST'])
def verify_2fa():

    if not session.get('admin_pass_valid'):
        return redirect(url_for('login'))

    error = None

    if request.method == 'POST':
        code = request.form.get('code')

        if verify_totp(code):
            session['admin_logged_in'] = True
            session.pop('admin_pass_valid', None)
            return redirect(url_for('admin'))
        else:
            error = "Invalid authentication code"

    return render_template('verify_2fa.html', error=error)

# ==============================
# 2FA SETUP
# ==============================

@app.route('/setup-2fa')
def setup_2fa():

    uri = get_provisioning_uri()
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    img_str = base64.b64encode(buf.getvalue()).decode()

    return render_template('setup_2fa.html', qr_code=img_str, secret=get_totp_secret())

# ==============================
# LOGOUT
# ==============================

@app.route('/logout')
def logout():

    session.pop('admin_logged_in', None)
    session.pop('admin_pass_valid', None)

    return redirect(url_for('login'))

# ==============================
# ADMIN
# ==============================

@app.route('/admin', methods=['GET', 'POST'])
def admin():

    # ==========================
    # AUTH CHECK
    # ==========================
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    # ==========================
    # ADD PRODUCT
    # ==========================
    if request.method == 'POST':

        name = request.form.get('name')
        price = request.form.get('price')
        image = request.files.get('image')

        if name and price and image:
            filename = f"{datetime.now().timestamp()}_{secure_filename(image.filename)}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(filepath)

            add_product(
                name=name,
                price=float(price),
                image='/' + filepath.replace("\\", "/")
            )

        return redirect(url_for('admin'))

    # ==========================
    # DELETE PRODUCT
    # ==========================
    delete_id = request.args.get('delete')
    if delete_id:
        product = get_product_by_id(int(delete_id))
        if product:
            # Delete image file
            image_path = product['image'].lstrip('/')
            if os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except:
                    pass
            delete_product(int(delete_id))
        return redirect(url_for('admin'))

    # ==========================
    # DELETE ORDER
    # ==========================
    delete_order_id = request.args.get('delete_order')
    if delete_order_id:
        delete_order(int(delete_order_id))
        return redirect(url_for('admin'))

    return render_template(
        'admin.html',
        products=get_all_products(),
        orders=get_all_orders()
    )

# ==============================
# ADMIN ORDERS
# ==============================

@app.route('/admin/orders')
def admin_orders():

    return render_template(
        'admin.html',
        products=get_all_products(),
        orders=get_all_orders()
    )

# ==============================
# UPDATE ORDER STATUS
# ==============================

@app.route('/admin/order/<int:order_id>/status', methods=['POST'])
def update_order_status(order_id):

    new_status = request.form.get('status')
    
    update_order_status(order_id, new_status)
    
    # Get order for email notification
    order = get_order_by_id(order_id)
    
    if order:
        customer_email = order['customer_email']
        
        try:
            msg = Message(
                subject=f"Order #{order_id} Status Updated",
                recipients=[customer_email]
            )
            
            msg.body = f"""
Your order status has been updated.

Order ID: {order_id}
Previous Status: {order['status']}
New Status: {new_status}

You can track your order in your account.

Thank you for shopping with CRIYOYO.
"""
            
            mail.send(msg)
            
        except Exception as e:
            print("Email Error:", e)

    return redirect(url_for('admin_orders'))

# ==============================
# ADD TO CART
# ==============================

@app.route('/add_to_cart/<int:id>')
def add_to_cart(id):

    session.setdefault('cart', [])

    if id not in session['cart']:
        session['cart'].append(id)

    session.modified = True

    return redirect(
        request.referrer or url_for('shop')
    )

# ==============================
# CART
# ==============================

@app.route('/cart')
def cart():

    cart_items = []

    total = 0

    products = get_all_products()

    for product_id in session.get('cart', []):

        product = next(
            (p for p in products if p['id'] == product_id),
            None
        )

        if product:

            cart_items.append(product)

            total += product['price']

    return render_template(
        'cart.html',
        items=cart_items,
        total=total
    )

# ==============================
# REMOVE FROM CART
# ==============================

@app.route('/remove_from_cart/<int:index>')
def remove_from_cart(index):

    if 'cart' in session:

        if index < len(session['cart']):

            session['cart'].pop(index)

            session.modified = True

    return redirect(
        request.referrer or url_for('cart')
    )

# ==============================
# CHECKOUT
# ==============================

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():

    # ==========================
    # SHOW CHECKOUT PAGE
    # ==========================

    if request.method == 'GET':

        if 'cart' not in session or len(session['cart']) == 0:
            return redirect(url_for('cart'))

        cart_items = []
        total = 0

        for product_id in session.get('cart', []):

            product = get_product_by_id(product_id)

            if product:

                cart_items.append(product)
                total += product['price']

        return render_template(
            'checkout.html',
            items=cart_items,
            total=total
        )

    # ==========================
    # PROCESS ORDER
    # ==========================

    if 'cart' not in session or len(session['cart']) == 0:
        return redirect(url_for('cart'))

    user_email = request.form.get('email')
    shipping_address = request.form.get('address')
    delivery_type = request.form.get('delivery_type')

    if not user_email or not shipping_address:
        return redirect(url_for('checkout'))
    products = get_all_products()
    total = 0
    order_items = []
    delivery_type = request.form.get('delivery_type', '3-5')

    for product_id in session.get('cart', []):
        product = next(
            (p for p in products if p['id'] == product_id),
            None
        )

        if product:
            size_key = f'size_{product_id}'
            size = request.form.get(size_key, 'N/A')

            total += product['price']

            order_items.append({
                'name': product['name'],
                'price': product['price'],
                'size': size
            })

    # PAXI courier pricing
    delivery_prices = {
        '3-5': 109.95,
        '7-9': 59.95
    }

    delivery_cost = delivery_prices.get(delivery_type, 59.95)
    grand_total = total + delivery_cost

    order = {
        'id': len(orders) + 1,
        'customer_email': user_email,
        'shipping_address': shipping_address,
        'delivery_type': delivery_type,
        'delivery_cost': delivery_cost,
        'items': order_items,
        'subtotal': total,
        'total': grand_total,
        'status': 'Order Placed',
        'created_at': str(datetime.now())
    }
    orders.append(order)
    # ==========================
    # EMAIL ADMIN
    # ==========================

    try:
        admin_msg = Message(
            subject=f"New Order #{order['id']} - CRIYOYO",
            recipients=['codnellsmall@gmail.com']
        )

        # Render HTML email template
        admin_msg.html = render_template(
            'emails/admin_new_order.html',
            order=order
        )

        # Also add plain text fallback
        items_text = '\n'.join([
            f"- {item['name']} (Size: {item['size']}) - R{item['price']}"
            for item in order_items
        ])

        admin_msg.body = f"""
New Order Received

Order ID: {order['id']}

Customer Email: {user_email}
Delivery Address (PEP/Paxi): {shipping_address}
Delivery Method: {'3-5 Business Days (Standard)' if delivery_type == '3-5' else '7-9 Business Days (Economy)'}

Items:
{items_text}

Subtotal: R{total:.2f}
Delivery Cost: R{delivery_cost:.2f}
Total: R{grand_total:.2f}

Status: {order['status']}
"""

        mail.send(admin_msg)

    except Exception as e:
        print("Admin Email Error:", e)
    except Exception as e:
        print("Admin Email Error:", e)
    # ==========================
    # EMAIL CUSTOMER
    # ==========================

    try:
        user_msg = Message(
            subject=f"Order Confirmation #{order['id']} - CRIYOYO",
            recipients=[user_email]
        )

        # Render HTML email template
        user_msg.html = render_template(
            'emails/customer_confirmation.html',
            order=order
        )

        # Also add plain text fallback
        items_text = '\n'.join([
            f"- {item['name']} (Size: {item['size']}) - R{item['price']}"
            for item in order_items
        ])

        delivery_label = '3-5 Business Days (Standard)' if delivery_type == '3-5' else '7-9 Business Days (Economy)'

        user_msg.body = f"""
Thank you for shopping with CRIYOYO!

Order Number: {order['id']}

Delivery Address (PEP/Paxi):
{shipping_address}

Delivery Method: {delivery_label}

Items:
{items_text}

Subtotal: R{total:.2f}
Delivery Cost: R{delivery_cost:.2f}
Total: R{grand_total:.2f}

Status: {order['status']}

We will notify you when your order ships.
"""

        mail.send(user_msg)

    except Exception as e:
        print("Customer Email Error:", e)

    # ==========================
    # CLEAR CART
    # ==========================

    session.pop('cart', None)

    return render_template(
        'success.html',
        order=order
    )
# ==============================
# CONTACT PAGE
# ==============================

@app.route('/contact', methods=['GET', 'POST'])
def contact():

    message_sent = False

    if request.method == 'POST':

        name = request.form.get('name')

        email = request.form.get('email')

        message = request.form.get('message')

        if name and email and message:

            try:

                msg = Message(
                    subject="New Contact Message",
                    recipients=['codnellsmall@gmail.com']
                )

                msg.body = f"""
Name:
{name}

Email:
{email}

Message:
{message}
"""

                mail.send(msg)

                message_sent = True

            except Exception as e:
                print("Contact Email Error:", e)

    return render_template(
        'contact.html',
        message_sent=message_sent
    )

# ==============================
# COOKIE ROUTES
# ==============================

@app.route('/accept-cookies', methods=['POST'])
def accept_cookies():

    consent = {
        'essential': True,
        'functional': True,
        'analytics': True,
        'marketing': True,
        'timestamp': datetime.now().isoformat()
    }

    response = make_response(
        redirect(request.referrer or url_for('home'))
    )

    response = set_cookie_consent(
        response,
        consent
    )

    return response


@app.route('/reject-cookies', methods=['POST'])
def reject_cookies():

    consent = {
        'essential': True,
        'functional': False,
        'analytics': False,
        'marketing': False,
        'timestamp': datetime.now().isoformat()
    }

    response = make_response(
        redirect(request.referrer or url_for('home'))
    )

    response = set_cookie_consent(
        response,
        consent
    )

    response.delete_cookie(
        app.config['PERSISTENT_CART_COOKIE']
    )

    response.delete_cookie(
        app.config['USER_PREFERENCES_COOKIE']
    )

    return response

# ==============================
# COOKIE SETTINGS
# ==============================

@app.route('/cookie-settings', methods=['GET', 'POST'])
def cookie_settings():

    if request.method == 'POST':

        consent = {
            'essential': True,
            'functional': request.form.get('functional') == 'on',
            'analytics': request.form.get('analytics') == 'on',
            'marketing': request.form.get('marketing') == 'on',
            'timestamp': datetime.now().isoformat()
        }

        response = make_response(
            redirect(url_for('cookie_settings'))
        )

        response = set_cookie_consent(
            response,
            consent
        )

        return response

    return render_template(
        'cookie_settings.html',
        consent=get_cookie_consent(request),
        categories=COOKIE_CATEGORIES
    )

# ==============================
# API COOKIE STATUS
# ==============================

@app.route('/api/cookie-status')
def api_cookie_status():

    return jsonify(
        get_cookie_consent(request)
    )

# ==============================
# CLEAR COOKIES
# ==============================

@app.route('/clear-cookies')
def clear_cookies():

    response = make_response(
        redirect(request.referrer or url_for('home'))
    )

    response.delete_cookie(
        app.config['PERSISTENT_CART_COOKIE']
    )

    response.delete_cookie(
        app.config['USER_PREFERENCES_COOKIE']
    )

    return response

# ==============================
# USER PREFERENCES
# ==============================

@app.route('/set-preferences', methods=['POST'])
def set_preferences():

    preferences = request.get_json(
        silent=True
    ) or {}

    response = make_response(
        jsonify({'success': True})
    )

    response = set_user_preferences(
        response,
        preferences
    )

    return response


@app.route('/get-preferences')
def get_preferences():

    return jsonify(
        get_user_preferences(request)
    )

# ==============================
# BEFORE REQUEST
# ==============================

@app.before_request
def load_persistent_cart():

    if request.path.startswith('/static'):
        return

    consent = get_cookie_consent(request)

    if consent.get('functional'):

        persistent_cart = get_persistent_cart(request)

        if 'cart' not in session and persistent_cart:

            session['cart'] = persistent_cart

            session.modified = True

# ==============================
# AFTER REQUEST
# ==============================

@app.after_request
def save_cart_to_cookie(response):

    consent = get_cookie_consent(request)

    if (
        consent.get('functional')
        and 'cart' in session
        and request.endpoint != 'static'
    ):

        response = set_persistent_cart(
            response,
            session['cart']
        )

    return response

# ==============================
# RUN APP
# ==============================

if __name__ == '__main__':

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )
