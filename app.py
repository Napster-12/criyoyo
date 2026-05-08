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

from datetime import datetime
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message

# ==============================
# ADMIN AUTH
# ==============================

ADMIN_EMAIL = "admin@criyoyo.com"
ADMIN_PASSWORD = "123456"  # change this later

app = Flask(__name__)

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
app.config['MAIL_PASSWORD'] = 'YOUR_APP_PASSWORD'

app.config['MAIL_DEFAULT_SENDER'] = 'codnellsmall@gmail.com'

mail = Mail(app)

# ==============================
# IN-MEMORY DATABASE
# ==============================

products = []
orders = []

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

            session['admin_logged_in'] = True

            return redirect(url_for('admin'))

        else:
            error = "Invalid admin credentials"

    return render_template('login.html', error=error)

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

    if request.method == 'POST':

        name = request.form.get('name')
        price = request.form.get('price')
        image = request.files.get('image')

        if not name or not price or not image:
            return redirect(url_for('admin'))

        filename = f"{datetime.now().timestamp()}_{secure_filename(image.filename)}"

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        image.save(filepath)

        products.append({
            'id': len(products),
            'name': name,
            'price': float(price),
            'image': '/' + filepath.replace("\\", "/")
        })

        return redirect(url_for('admin'))

    return render_template(
        'admin.html',
        products=products,
        orders=orders
    )

# ==============================
# ADMIN ORDERS
# ==============================

@app.route('/admin/orders')
def admin_orders():

    return render_template(
        'admin.html',
        products=products,
        orders=orders
    )

# ==============================
# UPDATE ORDER STATUS
# ==============================

@app.route('/admin/order/<int:order_id>/status', methods=['POST'])
def update_order_status(order_id):

    new_status = request.form.get('status')

    order = next(
        (o for o in orders if o['id'] == order_id),
        None
    )

    if not order:
        return redirect(url_for('admin_orders'))

    old_status = order['status']

    order['status'] = new_status

    customer_email = order['customer_email']

    try:

        msg = Message(
            subject=f"Order #{order_id} Updated",
            recipients=[customer_email]
        )

        msg.body = f"""
Your order status has changed.

Previous Status:
{old_status}

New Status:
{new_status}

Thank you for shopping with us.
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

            product = next(
                (p for p in products if p['id'] == product_id),
                None
            )

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

    if not user_email:
        return redirect(url_for('checkout'))

    total = 0
    order_items = []

    for product_id in session.get('cart', []):

        product = next(
            (p for p in products if p['id'] == product_id),
            None
        )

        if product:

            total += product['price']

            order_items.append({
                'name': product['name'],
                'price': product['price']
            })

    order = {
        'id': len(orders) + 1,
        'customer_email': user_email,
        'items': order_items,
        'total': total,
        'status': 'Order Placed',
        'created_at': str(datetime.now())
    }

    orders.append(order)

    # ==========================
    # EMAIL ADMIN
    # ==========================

    try:

        admin_msg = Message(
            subject=f"New Order #{order['id']}",
            recipients=['codnellsmall@gmail.com']
        )

        admin_msg.body = f"""
New Order Received

Order ID:
{order['id']}

Customer:
{user_email}

Total:
R{total}

Items:
{', '.join([item['name'] for item in order_items])}
"""

        mail.send(admin_msg)

    except Exception as e:
        print("Admin Email Error:", e)

    # ==========================
    # EMAIL CUSTOMER
    # ==========================

    try:

        user_msg = Message(
            subject=f"Order Confirmation #{order['id']}",
            recipients=[user_email]
        )

        user_msg.body = f"""
Thank you for shopping with CRIYOYO.

Order Number:
{order['id']}

Total:
R{total}

Status:
{order['status']}

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
