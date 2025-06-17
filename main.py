import math
import random
import re #for the password valid
import MySQLdb
import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mail import Mail, Message
from flask_mysqldb import MySQL

app = Flask(__name__, template_folder='templates')
app.secret_key = 'my secret key'

# MySQL database configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'dogtrip_db'


load_dotenv()
# Mail server configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT'))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS') == 'True'
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')

mysql = MySQL(app) #connection
mail = Mail(app)

otp = None  # OTP for password recovery
otp_mail = None  # Email associated with the OTP


@app.route('/')
def home():
    if 'user_id' in session:
        return render_template('home.html', first_name=session['first_name'])
    return render_template('home.html')


@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        password = request.form['password']
        user_type = request.form['user_type']
        phone = request.form['phone']
        default_profile_picture = '/static/images/default_profile_pic.jpg'

        # Password and phone validations
        if len(password) < 8 or not re.search(r'\d', password) or not re.search(r'[A-Za-z]', password):
            flash('Password must be at least 8 characters long and contain at least one letter and one digit.', 'error')
            return render_template('register.html')

        # Phone validation
        if not re.fullmatch(r'05\d{8}', phone):
            flash('Phone number must be exactly 10 digits long.', 'error')
            return render_template('register.html')

        try:
            cur = mysql.connection.cursor()
            # Check if email is in blocked_emails table
            cur.execute("SELECT email FROM blocked_emails WHERE email = %s", (email,))
            is_blocked = cur.fetchone()

            if is_blocked:
                cur.close()
                flash('This email address has been blocked. Registration is not allowed.', 'error')
                return render_template('register.html')

            # Check if email already exists in users table
            cur.execute("SELECT email FROM users WHERE email = %s", (email,))
            existing_user = cur.fetchone()

            if existing_user:
                cur.close()
                flash('An account with this email already exists.', 'error')
                return render_template('register.html')

            # Insert new user into users table
            cur.execute(
                "INSERT INTO users (first_name, last_name, email, password, user_type, phone, profile_picture) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (first_name, last_name, email, password, user_type, phone, default_profile_picture)
            )
            mysql.connection.commit() #save in DB

            user_id = cur.lastrowid

            # Insert a default dog record if the user is a dog_owner
            if user_type == 'dog_owner':
                cur.execute(
                    "INSERT INTO dogs (owner_id, dog_name, breed, age, size, dog_picture) VALUES (%s, %s, %s, %s, %s, %s)",
                    (user_id, 'Unknown', 'Unknown', 0, 'medium', 'images/default_dog.jpg')
                )
                mysql.connection.commit()

            cur.close()
            flash('Registration successful!', 'success')
            return redirect(url_for('register'))

        except Exception as e:
            flash(f'Registration failed: {str(e)}', 'error')
            return render_template('register.html')

    return render_template('register.html')


@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT user_id, first_name, last_name, email, password, user_type FROM users WHERE email = %s",
                    (email,))
        user = cur.fetchone()
        cur.close()

        if user and user[4] == password:
            session['user_id'] = user[0]
            session['first_name'] = user[1]
            session['last_name'] = user[2]
            session['email'] = user[3]
            session['user_type'] = user[5]

            if user[5] == 'dog_walker':
                return redirect(url_for('location_dw'))
            elif user[5] == 'dog_owner':
                return redirect(url_for('location_do'))
            elif user[5] == 'admin':
                return redirect(url_for('admin_dashboard'))
        else:
            return render_template('login.html', error='Invalid email or password')
    return render_template('login.html')


@app.route('/dashboard_dw')
def dashboard_dw():
    if 'user_id' not in session or session['user_type'] != 'dog_walker':
        return redirect(url_for('login'))

    user_id = session['user_id']
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT user_id, first_name, profile_picture FROM users WHERE user_id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()

    if user and user['profile_picture']:
        if user['profile_picture'].startswith('/static/'):
            profile_picture_path = user['profile_picture'][len('/static/'):]
        else:
            profile_picture_path = user['profile_picture']

        profile_picture_url = url_for('static', filename=profile_picture_path)
    else:
        profile_picture_url = url_for('static', filename='images/default_profile_pic.jpg')

    return render_template('dashboard_dw.html', user=user, first_name=session['first_name'], profile_picture_url=profile_picture_url)


@app.route('/dashboard_do')
def dashboard_do():
    if 'user_id' not in session or session['user_type'] != 'dog_owner':
        return redirect(url_for('login'))

    user_id = session['user_id']
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()

    if user and user['profile_picture']:
        if user['profile_picture'].startswith('/static/'):
            profile_picture_path = user['profile_picture'][len('/static/'):]
        else:
            profile_picture_path = user['profile_picture']

        profile_picture_url = url_for('static', filename=profile_picture_path)
    else:
        profile_picture_url = url_for('static', filename='images/default_profile_pic.jpg')

    bio = user.get('bio', '')
    return render_template('dashboard_do.html', user=user,profile_picture_url=profile_picture_url,bio=bio)


@app.route('/services')
def services():
    return render_template('services.html')


@app.route('/aboutus')
def aboutus():
    return render_template('aboutus.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


@app.route('/FAQ')
def faq():
    return render_template('FAQ.html')


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        global otp, otp_email
        email = request.form['email']
        otp_email = email  # Save email to validate later
        otp = random.randint(1000, 9999)  # Generate a 4-digit OTP
        msg = Message(subject='Your OTP Code', sender=app.config['MAIL_USERNAME'], recipients=[email])
        msg.body = f'Your OTP code is {otp}.'
        mail.send(msg)
        flash('A verification code has been sent to your email.')
        return redirect(url_for('verify_reset_code'))
    return render_template('forgot_password.html')


@app.route('/verify_reset_code', methods=['GET', 'POST'])
def verify_reset_code():
    if request.method == 'POST':
        user_otp = request.form['verification_code']
        if otp is not None and otp == int(user_otp):
            return redirect(url_for('reset_password'))
        flash('Invalid OTP. Please try again.','error')
        return redirect(url_for('forgot_password'))
    return render_template('verify_reset_code.html')


@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if new_password == confirm_password:
            cur = mysql.connection.cursor()
            cur.execute("UPDATE users SET password = %s WHERE email = %s", (new_password, otp_email))
            mysql.connection.commit()
            cur.close()
            flash('Password successfully changed.', 'success')
            return redirect(url_for('reset_password'))
        else:
            flash('Passwords do not match. Please try again.', 'error')
    return render_template('reset_password.html')


@app.route('/update_profile', methods=['GET', 'POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user_type = session['user_type']
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == 'POST':
        # Handling the profile picture upload
        if 'profile_pic' in request.files:
            profile_pic = request.files['profile_pic']
            if profile_pic.filename != '':
                pic_filename = f"profile_{user_id}.png" #create
                profile_pic.save(f"static/images/{pic_filename}") #save

                # Update the user's profile picture in the database
                cur.execute("UPDATE users SET profile_picture = %s WHERE user_id = %s", (f'images/{pic_filename}', user_id))

        # Update phone number if provided
        phone_number = request.form.get('phone_number')
        if phone_number:
            cur.execute("UPDATE users SET phone = %s WHERE user_id = %s", (phone_number, user_id))

        # Update bio if provided
        bio = request.form.get('bio')
        if bio:
            cur.execute("UPDATE users SET bio = %s WHERE user_id = %s", (bio, user_id))

        # Handling password update
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if new_password and new_password == confirm_password:
            cur.execute("UPDATE users SET password = %s WHERE user_id = %s", (new_password, user_id))
        elif new_password and new_password != confirm_password:
            flash('Passwords do not match. Please try again.', 'error')
            return redirect(url_for('dashboard_dw' if user_type == 'dog_walker' else 'dashboard_do'))

        mysql.connection.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('dashboard_dw' if user_type == 'dog_walker' else 'dashboard_do'))

    else:
        # Fetch current user data for display in the form
        cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = cur.fetchone()

        # Handle case where bio doesn't exist
        if user and 'bio' not in user:
            user['bio'] = ''

        return render_template('update_profile.html', user=user)


@app.route('/update_dog_profile', methods=['POST'])
def update_dog_profile():
    if 'user_id' not in session or session['user_type'] != 'dog_owner':
        return redirect(url_for('login'))

    user_id = session['user_id']
    cur = mysql.connection.cursor()

    try:
        # Handle dog profile picture upload
        if 'dog_pic' in request.files:
            dog_pic = request.files['dog_pic']
            if dog_pic and dog_pic.filename != '':
                pic_filename = f"dog_{user_id}.jpg"
                pic_path = f"static/images/{pic_filename}"
                dog_pic.save(pic_path)

                # Update dog profile picture in the database
                cur.execute("UPDATE dogs SET dog_picture = %s WHERE owner_id = %s", (f'images/{pic_filename}', user_id))

        # Update other dog profile details
        dog_name = request.form.get('dog_name')
        if dog_name:
            cur.execute("UPDATE dogs SET dog_name = %s WHERE owner_id = %s", (dog_name, user_id))

        dog_breed = request.form.get('dog_breed')
        if dog_breed:
            cur.execute("UPDATE dogs SET breed = %s WHERE owner_id = %s", (dog_breed, user_id))

        dog_age = request.form.get('dog_age')
        if dog_age:
            cur.execute("UPDATE dogs SET age = %s WHERE owner_id = %s", (dog_age, user_id))

        dog_size = request.form.get('dog_size')
        if dog_size:
            cur.execute("UPDATE dogs SET size = %s WHERE owner_id = %s", (dog_size, user_id))

        special_requests = request.form.get('special_requests')
        if special_requests:
            cur.execute("UPDATE dogs SET special_requests = %s WHERE owner_id = %s", (special_requests, user_id))

        mysql.connection.commit()
        flash('Dog profile updated successfully!', 'success')

    except Exception as e:
        mysql.connection.rollback()
        flash(f'Failed to update dog profile: {str(e)}', 'error')

    finally:
        cur.close()

    return redirect(url_for('dog_profile'))


@app.route('/dog_profile')
def dog_profile():
    if 'user_id' not in session or session['user_type'] != 'dog_owner':
        return redirect(url_for('login'))

    user_id = session['user_id']
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT * FROM dogs WHERE owner_id = %s", (user_id,))
    dog = cur.fetchone()
    cur.close()

    return render_template('dog_profile.html', dog=dog)


@app.route('/get_availability/<int:year>/<int:month>')
def get_availability(year, month):
    if 'user_id' not in session:
        return jsonify({}), 401

    walker_id = request.args.get('walker_id')
    user_id = walker_id if walker_id else session['user_id']

    cur = mysql.connection.cursor()
    cur.execute("""
           SELECT available_date, available_type 
           FROM calendar_availability 
           WHERE user_id = %s
             AND YEAR(available_date) = %s
             AND MONTH(available_date) = %s
             AND is_available = 1
       """, (user_id, year, month))

    rows = cur.fetchall()
    cur.close()

    availability = {}
    for row in rows:
        date_str = row[0].strftime('%Y-%m-%d')
        availability[date_str] = row[1]
    return jsonify(availability)


@app.route('/save_availability', methods=['POST'])
def save_availability():
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "User not logged in"}), 401

    user_id = session['user_id']
    changes = request.json
    cur = mysql.connection.cursor()
    try:
        for date_str, availability_type in changes.items():
            if availability_type in ['sitting', 'walking']:
                cur.execute("""
                    INSERT INTO calendar_availability (user_id, available_date, available_type, is_available)
                    VALUES (%s, %s, %s, 1)
                    ON DUPLICATE KEY UPDATE 
                        available_type = VALUES(available_type), 
                        is_available = 1
                """, (user_id, date_str, availability_type))
            else:
                cur.execute("""
                    UPDATE calendar_availability
                    SET is_available = 0
                    WHERE user_id = %s 
                      AND available_date = %s
                """, (user_id, date_str))
        mysql.connection.commit()
        return jsonify({"success": True})
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cur.close()


@app.route('/details_dw', methods=['GET', 'POST'])
def details_dw():
    if 'user_id' not in session or session['user_type'] != 'dog_walker':
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == 'POST':
        has_pet = request.form.get('has_pet', 'No')
        service_types = request.form.getlist('service_type[]')
        is_dog_walker = 'dog_walker' in service_types
        is_dog_sitter = 'dog_sitter' in service_types
        walking_price = request.form.get('walking_price') or None
        sitting_price = request.form.get('sitting_price') or None

        try:
            cursor.execute("""
                INSERT INTO dog_walker_details 
                (walker_id, has_pet, is_dog_walker, is_dog_sitter, walking_price, sitting_price) 
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                has_pet = VALUES(has_pet),
                is_dog_walker = VALUES(is_dog_walker),
                is_dog_sitter = VALUES(is_dog_sitter),
                walking_price = VALUES(walking_price),
                sitting_price = VALUES(sitting_price)
            """, (session['user_id'], has_pet, is_dog_walker, is_dog_sitter, walking_price, sitting_price))

            mysql.connection.commit()
            flash('Details updated successfully!', 'success')
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Failed to update details: {str(e)}', 'error')

        cursor.close()
        return redirect(url_for('details_dw'))

    # Fetch existing data
    cursor.execute('SELECT * FROM dog_walker_details WHERE walker_id = %s', (session['user_id'],))
    details = cursor.fetchone()

    if details is None:
        details = {
            'has_pet': 'No',
            'is_dog_walker': False,
            'is_dog_sitter': False,
            'walking_price': None,
            'sitting_price': None
        }

    cursor.close()
    return render_template('details_dw.html', details=details)


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance between two points on the Earth"""
    R = 6371  # Radius of Earth in km
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def calculate_dynamic_weights(dog_walkers, owner_lat, owner_lon, max_distance=500, max_price=1000):
    """Calculate dynamic weights for distance, rating, and price based on the context"""
    # יצירת רשימת מרחקים לכל המוליכים
    distances = [
        haversine_distance(float(walker['latitude']), float(walker['longitude']), owner_lat, owner_lon)
        for walker in dog_walkers
    ]
    average_distance = sum(distances) / len(distances) if distances else 0

    # Determine weights based on average distance
    if average_distance <= 5:  # All walkers are close
        distance_weight = 0.4
        rating_weight = 0.4
        price_weight = 0.2
    else:  # Walkers are more spread out
        distance_weight = 0.7
        rating_weight = 0.2
        price_weight = 0.1

    return distance_weight, rating_weight, price_weight


def calculate_combined_score(walker_lat, walker_lon, owner_lat, owner_lon, walker_rating, walker_price,
                             distance_weight, rating_weight, price_weight, max_distance=500, max_price=1000):
    """Calculate combined score for a walker based on distance, rating, and price"""
    # Convert inputs to float
    walker_lat = float(walker_lat)
    walker_lon = float(walker_lon)
    owner_lat = float(owner_lat)
    owner_lon = float(owner_lon)
    walker_rating = float(walker_rating)
    walker_price = float(walker_price)

    # Calculate distance
    distance = haversine_distance(walker_lat, walker_lon, owner_lat, owner_lon)
    normalized_distance = min(distance, max_distance) / max_distance
    inverse_distance = 1 - normalized_distance  # Higher score for closer distance

    # Normalize rating (scale from 0 to 1, max rating is 5)
    normalized_rating = walker_rating / 5

    # Normalize price (scale from 0 to 1)
    normalized_price = min(walker_price, max_price) / max_price
    inverse_price = 1 - normalized_price  # Higher score for lower price

    # Combined score
    score = (
        (distance_weight * inverse_distance) +
        (rating_weight * normalized_rating) +
        (price_weight * inverse_price)
    )

    return score, distance


@app.route('/searching_do')
def searching_do():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Get owner location
    cur.execute("""
        SELECT latitude, longitude 
        FROM users 
        WHERE user_id = %s
    """, (session['user_id'],))
    owner = cur.fetchone()
    owner_lat = float(owner['latitude'])
    owner_lon = float(owner['longitude'])

    # Get all dog walkers
    cur.execute("""
        SELECT 
            u.user_id, 
            u.first_name, 
            u.last_name, 
            u.profile_picture, 
            u.latitude, 
            u.longitude, 
            d.walking_price, 
            d.sitting_price, 
            d.is_dog_walker, 
            d.is_dog_sitter,
            COALESCE(r.average_rating, 0) AS average_rating,
            COALESCE(r.rating_count, 0)  AS review_count
        FROM users u
        LEFT JOIN dog_walker_details d ON u.user_id = d.walker_id
        LEFT JOIN walker_ratings r ON u.user_id = r.walker_id
        WHERE u.user_type = 'dog_walker'
        GROUP BY u.user_id
    """)
    dog_walkers = cur.fetchall()
    cur.close()

    # חישוב מקסימום
    max_price = max([float(walker['walking_price']) for walker in dog_walkers if walker['walking_price'] is not None], default=1000)
    if max_price == 0:  # Ensure max_price is not zero
        max_price = 1000

    # לחשב משקלים דינמים
    distance_weight, rating_weight, price_weight = calculate_dynamic_weights(dog_walkers, owner_lat, owner_lon)

    # לחשב ניקוד למוליכי הכלבים
    for walker in dog_walkers:
        walker_price = float(walker['walking_price']) if walker['walking_price'] else max_price
        walker['score'], walker['distance'] = calculate_combined_score(
            float(walker['latitude']), float(walker['longitude']),
            owner_lat, owner_lon,
            float(walker['average_rating']),
            walker_price,
            distance_weight, rating_weight, price_weight,
            max_distance=500,
            max_price=max_price
        )

        # שירותים מוצעים
        services = []
        if walker['is_dog_walker']:
            services.append('Walking')
        if walker['is_dog_sitter']:
            services.append('Sitting')
        walker['services'] = ', '.join(services) if services else 'No services specified'

        # טווח מחירים
        min_price = min(filter(None, [walker['walking_price'], walker['sitting_price']]), default=0)
        max_price_range = max(filter(None, [walker['walking_price'], walker['sitting_price']]), default=0)
        walker['price_range'] = f"${min_price} - ${max_price_range}" if min_price or max_price_range else "Price not specified"

    # Sort dog walkers by score (highest first)
    dog_walkers = sorted(dog_walkers, key=lambda x: x['score'], reverse=True)

    return render_template('searching_do.html', dog_walkers=dog_walkers)


@app.route('/get_walker_details/<int:user_id>')
def get_walker_details(user_id):
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Get walker details
        cur.execute("""
            SELECT 
                u.user_id, 
                u.first_name, 
                u.last_name, 
                u.profile_picture, 
                u.bio, 
                d.walking_price, 
                d.sitting_price, 
                d.is_dog_walker, 
                d.is_dog_sitter,
                COALESCE(AVG(r.rating), 0) as average_rating,
                COUNT(r.rating_id) as review_count
            FROM users u
            LEFT JOIN dog_walker_details d ON u.user_id = d.walker_id
            LEFT JOIN ratings r ON u.user_id = r.walker_id
            WHERE u.user_id = %s
            GROUP BY u.user_id
        """, (user_id,))
        walker = cur.fetchone()

        if not walker:
            cur.close()
            return jsonify({'error': 'Walker not found'}), 404

        # לקבל ביקורת בנפרד
        cur.execute("""
            SELECT 
                r.rating,
                r.comment,
                r.created_at,
                u.first_name,
                u.last_name
            FROM ratings r
            JOIN users u ON r.owner_id = u.user_id
            WHERE r.walker_id = %s
            ORDER BY r.created_at DESC
        """, (user_id,))
        reviews = cur.fetchall()

        # Get available dates
        cur.execute("""
            SELECT available_date, available_type
            FROM calendar_availability
            WHERE user_id = %s AND is_available = 1
        """, (user_id,))
        availability = cur.fetchall()

        cur.close()

        # the response data
        response_data = {
            'user_id': walker['user_id'],
            'first_name': walker['first_name'],
            'last_name': walker['last_name'],
            'profile_picture': walker['profile_picture'],
            'bio': walker['bio'],
            'walking_price': float(walker['walking_price']) if walker['walking_price'] else None,
            'sitting_price': float(walker['sitting_price']) if walker['sitting_price'] else None,
            'is_dog_walker': bool(walker['is_dog_walker']),
            'is_dog_sitter': bool(walker['is_dog_sitter']),
            'average_rating': float(walker['average_rating']),
            'review_count': walker['review_count'],
            'services': [],
            'reviews': [],
            'available_dates': []
        }

        # Add services
        if walker['is_dog_walker']:
            response_data['services'].append('Walking')
        if walker['is_dog_sitter']:
            response_data['services'].append('Sitting')
        response_data['services'] = ', '.join(response_data['services']) if response_data['services'] else 'No services specified'

        #  reviews
        for review in reviews:
            response_data['reviews'].append({
                'rating': float(review['rating']),
                'comment': review['comment'],
                'created_at': review['created_at'].strftime('%Y-%m-%d'),
                'reviewer_name': f"{review['first_name']} {review['last_name']}"
            })

        #  available dates
        for date in availability:
            response_data['available_dates'].append({
                'date': date['available_date'].strftime('%Y-%m-%d'),
                'type': date['available_type']
            })

        return jsonify(response_data)

    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/book_walker/<int:walker_id>', methods=['POST'])
def book_walker(walker_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'You must be logged in to book a walker.'}), 401

    data = request.get_json()
    selected_date = data.get('date')

    if not selected_date:
        return jsonify({'success': False, 'message': 'Please select a date for booking.'}), 400

    try:
        # נבדוק שהיום עדיין פנוי
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT availability_id 
            FROM calendar_availability 
            WHERE user_id = %s 
            AND available_date = %s 
            AND is_available = 1
        """, (walker_id, selected_date))

        if not cur.fetchone():
            cur.close()
            return jsonify({'success': False, 'message': 'Selected date is no longer available.'}), 400

        # נשמור booking בסטטוס Pending
        cur.execute("""
            INSERT INTO bookings (user_id, dog_id, walker_id, booking_date, booking_time, status)
            VALUES (
                %s, 
                (SELECT dog_id FROM dogs WHERE owner_id = %s LIMIT 1),
                %s,
                %s, 
                CURTIME(), 
                'pending'
            )
        """, (session['user_id'], session['user_id'], walker_id, selected_date))

        mysql.connection.commit()
        cur.close()

        # נחזיר תשובה שבקשת ההזמנה נשלחה, והסטטוס ממתין לאישור
        return jsonify({
            'success': True,
            'message': 'Booking request sent to the walker and is pending approval.'
        })

    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'success': False, 'message': f'An error occurred: {str(e)}'}), 500


@app.route('/location_dw', methods=['GET', 'POST'])
def location_dw():
    if 'user_id' not in session or session['user_type'] != 'dog_walker':
        return redirect(url_for('login'))

    if request.method == 'POST':
        data = request.json
        latitude = data['latitude']
        longitude = data['longitude']
        location_name = data['location_name']
        user_id = session['user_id']

        cur = mysql.connection.cursor()
        try:
            cur.execute("""
                UPDATE users 
                SET latitude = %s, longitude = %s, location_name = %s
                WHERE user_id = %s
            """, (latitude, longitude, location_name, user_id))
            mysql.connection.commit()
            cur.close()
            return jsonify({"redirect": url_for('dashboard_dw')})
        except Exception as e:
            cur.close()
            return jsonify({"error": str(e)}), 500

    return render_template('location_dw.html')


@app.route('/location_do', methods=['GET', 'POST'])
def location_do():
    if 'user_id' not in session or session['user_type'] != 'dog_owner':
        return redirect(url_for('login'))

    if request.method == 'POST':
        data = request.json
        latitude = data['latitude']
        longitude = data['longitude']
        location_name = data['location_name']
        user_id = session['user_id']

        cur = mysql.connection.cursor()
        try:
            cur.execute("""
                UPDATE users 
                SET latitude = %s, longitude = %s, location_name = %s
                WHERE user_id = %s
            """, (latitude, longitude, location_name, user_id))
            mysql.connection.commit()
            cur.close()
            return jsonify({"redirect": url_for('location_do')})
        except Exception as e:
            cur.close()
            return jsonify({"error": str(e)}), 500

    return render_template('location_do.html')


@app.route('/payment/<int:walker_id>')
def payment(walker_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # קבלת תאריך ההזמנה מהשאילתה
    booking_date = request.args.get('booking_date')

    # לבדוק אם קיים תאריך ההזמנה
    if not booking_date:
        flash('No booking date provided', 'error')
        return redirect(url_for('notifications'))

    session['booking_date'] = booking_date

    # Get walker details from database
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute("""
            SELECT first_name, last_name, walking_price, sitting_price
            FROM users u
            LEFT JOIN dog_walker_details d ON u.user_id = d.walker_id
            WHERE u.user_id = %s
        """, (walker_id,))
        walker = cur.fetchone()

    except Exception as e:
        flash('Error retrieving walker details', 'error')
        return redirect(url_for('notifications'))
    finally:
        cur.close()

    if not walker:
        flash('Walker not found', 'error')
        return redirect(url_for('notifications'))

    # Pass walker details + booking date
    return render_template('payment.html',
                           walker=walker,
                           walker_id=walker_id,
                           booking_date=booking_date)


@app.route('/process_payment', methods=['POST'])
def process_payment():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Please login first'})

    data = request.get_json()

    selected_date = data.get('date')
    card_number = data.get('cardNumber', '').replace(' ', '')
    expiry_date = data.get('expiryDate', '')
    cvc = data.get('cvc', '')
    walker_id = data.get('walkerId')

    if not selected_date or selected_date == 'None':
        return jsonify({
            'status': 'error',
            'message': 'No date selected. Please try booking again.'
        })

    if not all([
        len(card_number) == 16 and card_number.isdigit(),
        len(expiry_date) == 5 and expiry_date[2] == '/',
        len(cvc) == 3 and cvc.isdigit(),
        walker_id, selected_date
    ]):
        return jsonify({
            'status': 'error',
            'message': 'Invalid payment details. Please check your input.'
        })

    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        find_booking = """
            SELECT booking_id
            FROM bookings
            WHERE user_id = %s
            AND walker_id = %s
            AND booking_date = %s
            LIMIT 1
        """
        cursor.execute(find_booking, (session['user_id'], walker_id, selected_date))
        row = cursor.fetchone()

        if not row:
            cursor.close()
            return jsonify({
                'status': 'error',
                'message': 'No matching booking found for the provided details.'
            })

        booking_id = row['booking_id']
        cursor.close()

        return jsonify({
            'status': 'success',
            'message': 'Payment successfully processed.',
            'booking_id': booking_id
        })

    except Exception as e:
        mysql.connection.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Payment processing failed. Error: {str(e)}'
        })


@app.route('/rating/<int:walker_id>')
def rating(walker_id):
    if 'user_id' not in session:
        return redirect(url_for('login', message="Please log in to rate a walker"))

    try:
        selected_date = request.args.get('date')
        booking_id = request.args.get('booking_id')

        with mysql.connection.cursor(MySQLdb.cursors.DictCursor) as cur:
            cur.execute("""
                SELECT first_name, last_name, profile_picture
                FROM users
                WHERE user_id = %s
            """, (walker_id,))
            walker = cur.fetchone()

        if not walker:
            flash("Dog walker not found", "error")
            return redirect(url_for('searching_do'))

        return render_template(
            'rating.html',
            walker=walker,
            walker_id=walker_id,
            selectedDate=selected_date,
            booking_id=booking_id
        )

    except Exception as e:
        flash("An error occurred. Please try again later.", "error")
        return redirect(url_for('searching_do'))


@app.route('/rate_walker/<int:walker_id>', methods=['POST'])
def rate_walker(walker_id):
    if 'user_id' not in session or session['user_type'] != 'dog_owner':
        flash('Please login first.', 'error')
        return redirect(url_for('login'))

    rating = request.form.get('rating')
    comment = request.form.get('comment')
    booking_id = request.form.get('booking_id')
    selected_date = request.form.get('selected_date')
    owner_id = session['user_id']

    # אם הדירוג או התגובה ריקים
    if not rating or not comment:
        flash('Rating and comment are required', 'error')
        return redirect(url_for('rating',
                                walker_id=walker_id,
                                booking_id=booking_id,
                                date=selected_date))

    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # בדיקה אם כבר קיים דירוג של בעל הכלב עבור ה-Walker
        cur.execute("""
            SELECT rating
            FROM ratings
            WHERE owner_id = %s AND walker_id = %s
        """, (owner_id, walker_id))
        existing_rating = cur.fetchone()

        if existing_rating:
            # עדכון דירוג קיים
            cur.execute("""
                UPDATE ratings
                SET rating = %s, comment = %s
                WHERE owner_id = %s AND walker_id = %s
            """, (rating, comment, owner_id, walker_id))

            # עדכון ממוצע (תוך התחשבות בדירוג הישן)
            cur.execute("""
                UPDATE walker_ratings
                SET average_rating = 
                  (average_rating * rating_count - %s + %s) / rating_count
                WHERE walker_id = %s
            """, (existing_rating['rating'], rating, walker_id))
        else:
            # הוספת דירוג חדש
            cur.execute("""
                INSERT INTO ratings (owner_id, walker_id, rating, comment)
                VALUES (%s, %s, %s, %s)
            """, (owner_id, walker_id, rating, comment))

            # עדכון ממוצע
            cur.execute("""
                INSERT INTO walker_ratings (walker_id, average_rating, rating_count)
                VALUES (%s, %s, 1)
                ON DUPLICATE KEY UPDATE
                  average_rating = ((average_rating * rating_count) + %s) / (rating_count + 1),
                  rating_count = rating_count + 1
            """, (walker_id, rating, rating))

        cur.execute("""
            UPDATE bookings
            SET status = 'completed'
            WHERE booking_id = %s
        """, (booking_id,))

        cur.execute("""
            UPDATE calendar_availability
            SET is_available = 0
            WHERE user_id = %s
              AND available_date = %s
        """, (walker_id, selected_date))

        mysql.connection.commit()
        cur.close()

        flash('Rating submitted successfully!', 'success')
        return redirect(url_for('notifications'))

    except Exception as e:
        mysql.connection.rollback()
        flash(f'Failed to submit rating. Error: {str(e)}', 'error')

        return redirect(url_for('rating',
                                walker_id=walker_id,
                                booking_id=booking_id,
                                date=selected_date))


def expire_old_bookings():
    """
    Mark every booking whose date-time has already passed as 'cancelled'
    (only if it’s still in 'pending' or 'accepted' status).
    Works with the table definition you pasted.
    """
    with mysql.connection.cursor() as cur:
        cur.execute("""
            UPDATE bookings
            SET status = 'cancelled',
                updated_at = NOW()
            WHERE status IN ('pending', 'accepted')
              AND ( booking_date < CURDATE() OR (booking_date = CURDATE() AND booking_time < CURTIME()) 
              )
        """)
        mysql.connection.commit()


@app.route('/notifications')
def notifications():
    if 'user_id' not in session:
        flash('Please log in first','error')
        return redirect(url_for('login'))

    expire_old_bookings()
    user_id = session['user_id']
    user_type = session['user_type']
    selected_date = request.args.get('selected_date')

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if user_type == 'dog_walker':
        query = """
               SELECT b.booking_id,
                      b.walker_id,
                      b.dog_id,
                      b.booking_date,
                      b.booking_time,
                      b.status,
                      u.first_name AS owner_firstname,
                      u.last_name  AS owner_lastname,
                      d.dog_name,
                      d.breed
               FROM bookings b
               JOIN users u ON b.user_id = u.user_id
               JOIN dogs d ON b.dog_id = d.dog_id
               WHERE b.walker_id = %s 
               ORDER BY b.created_at DESC
           """
        cur.execute(query, (user_id,))
        bookings = cur.fetchall()
        cur.close()

        return render_template('notifications.html', bookings=bookings, user_type='dog_walker', selected_date=selected_date)

    elif user_type == 'dog_owner':
        # לשלוף את כל ההזמנות של בעל הכלב (בכל סטטוס)
        query = """
            SELECT b.booking_id,
                   b.walker_id,
                   b.dog_id,
                   b.booking_date,
                   b.booking_time,
                   b.status,
                   w.first_name AS walker_firstname,
                   w.last_name  AS walker_lastname
            FROM bookings b
            LEFT JOIN users w ON b.walker_id = w.user_id
            WHERE b.user_id = %s
            ORDER BY b.created_at DESC
        """
        cur.execute(query, (user_id,))
        bookings = cur.fetchall()
        cur.close()

        return render_template('notifications.html', bookings=bookings, user_type='dog_owner')

    else:
        cur.close()
        return redirect(url_for('home'))


@app.route('/accept_booking/<int:booking_id>', methods=['POST'])
def accept_booking(booking_id):
    if 'user_id' not in session or session['user_type'] != 'dog_walker':
        flash('Unauthorized', 'error')
        return redirect(url_for('notifications'))

    walker_id = session['user_id']
    cur = mysql.connection.cursor()

    try:
        # בדיקה שההזמנה אכן קיימת, שייכת למוליך הנוכחי, ובסטטוס pending
        check_query = """
            SELECT booking_id
            FROM bookings
            WHERE booking_id = %s
              AND walker_id = %s
              AND status = 'pending'
        """
        cur.execute(check_query, (booking_id, walker_id))
        booking = cur.fetchone()
        if not booking:
            flash('No such pending booking found', 'error')
            cur.close()
            return redirect(url_for('notifications'))

        update_query = """
            UPDATE bookings
            SET status = 'accepted'
            WHERE booking_id = %s
        """
        cur.execute(update_query, (booking_id,))
        mysql.connection.commit()

        flash('Booking accepted successfully.', 'success')
        cur.close()
        return redirect(url_for('notifications'))

    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error while accepting booking: {str(e)}', 'error')
        return redirect(url_for('notifications'))


@app.route('/reject_booking/<int:booking_id>', methods=['POST'])
def reject_booking(booking_id):
    if 'user_id' not in session or session['user_type'] != 'dog_walker':
        flash('Unauthorized','error')
        return redirect(url_for('notifications'))

    walker_id = session['user_id']
    cur = mysql.connection.cursor()

    try:
        # בדיקה שההזמנה אכן קיימת ומשויכת למוליך
        check_query = """
            SELECT booking_id FROM bookings
            WHERE booking_id = %s AND walker_id = %s AND status='pending'
        """
        cur.execute(check_query, (booking_id, walker_id))
        booking = cur.fetchone()
        if not booking:
            flash('No such pending booking found','error')
            cur.close()
            return redirect(url_for('notifications'))

        update_query = """
            UPDATE bookings
            SET status='cancelled'
            WHERE booking_id = %s
        """
        cur.execute(update_query, (booking_id,))
        mysql.connection.commit()

        flash('Booking rejected successfully.','success')
        cur.close()
        return redirect(url_for('notifications'))

    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error while rejecting booking: {str(e)}','error')
        return redirect(url_for('notifications'))


@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    return render_template('admin_dashboard.html')


@app.route('/admin/statistics')
def admin_statistics():
    if 'user_id' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    return render_template('admin_statistics.html')


@app.route('/api/admin/statistics')
def get_statistics_data():
    if 'user_id' not in session or session['user_type'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        #מחזיר את כמות המשתמשים לפי סוג (user_type)
        cur.execute("""
            SELECT user_type, COUNT(*) AS cnt
            FROM users
            GROUP BY user_type
        """)
        user_types_rows = cur.fetchall()

        user_types_data = [
            {
                'name': row['user_type'].replace('_', ' ').capitalize(),
                'value': row['cnt']
            }
            for row in user_types_rows
        ]

        # blocked vs active users
        cur.execute("SELECT COUNT(*) AS blocked_cnt FROM blocked_emails")
        blocked_count = cur.fetchone()['blocked_cnt']

        cur.execute("SELECT COUNT(*) AS total_cnt FROM users")
        total_users = cur.fetchone()['total_cnt']

        user_status_data = [
            {'name': 'Active Users', 'value': total_users - blocked_count},
            {'name': 'Blocked Users', 'value': blocked_count}
        ]

        # total dogs
        cur.execute("SELECT COUNT(*) AS dogs_cnt FROM dogs")
        total_dogs = cur.fetchone()['dogs_cnt']

        # dog sizes
        cur.execute("""
            SELECT size, COUNT(*) AS cnt
            FROM dogs
            GROUP BY size
        """)
        dog_sizes_rows = cur.fetchall()
        dog_sizes_data = [
            {'name': row['size'], 'value': row['cnt']}
            for row in dog_sizes_rows
        ]

        # top 5 breeds
        cur.execute("""
            SELECT breed, COUNT(*) AS cnt
            FROM dogs
            GROUP BY breed
            ORDER BY cnt DESC
            LIMIT 5
        """)
        top_breeds_rows = cur.fetchall()
        top_breeds_data = [
            {'name': row['breed'], 'value': row['cnt']}
            for row in top_breeds_rows
        ]

        # שליפת מיקומי מוליכי כלבים (latitude) ודירוגיהם
        cur.execute("""
            SELECT 
                u.user_id AS walker_id,
                u.latitude,
                COALESCE(r.average_rating, 0) AS avg_rating,
                COALESCE(r.rating_count, 0)   AS rating_count
            FROM users u
            LEFT JOIN walker_ratings r ON u.user_id = r.walker_id
            WHERE u.user_type = 'dog_walker'
        """)
        walker_rows = cur.fetchall()
        cur.close()

        def get_region(lat):
            if lat is None:
                return 'Unknown'
            if lat >= 32.44:
                return 'North'
            elif lat >= 31.81:
                return 'Center'
            else:
                return 'South & JRS'

        region_map = {}

        for row in walker_rows:
            region = get_region(row['latitude'])

            if region not in region_map:
                region_map[region] = {
                    'count_walkers': 0,
                    'sum_ratings': 0.0,
                    'ratings_count': 0
                }
            region_map[region]['count_walkers'] += 1

            avg_rating = float(row['avg_rating'])
            rating_count = int(row['rating_count'])
            region_map[region]['sum_ratings'] += (avg_rating * rating_count)
            region_map[region]['ratings_count'] += rating_count

        total_walkers = sum([region_map[r]['count_walkers'] for r in region_map])
        region_stats = []
        for region_name, vals in region_map.items():
            if vals['ratings_count'] > 0:
                avg_region_rating = vals['sum_ratings'] / vals['ratings_count']
            else:
                avg_region_rating = 0.0

            if total_walkers > 0:
                region_percent = (vals['count_walkers'] / total_walkers) * 100
            else:
                region_percent = 0.0

            region_stats.append({
                'region': region_name,
                'walkers_count': vals['count_walkers'],
                'average_rating': round(avg_region_rating, 2),
                'percentage': round(region_percent, 2)
            })

        region_order = ['North', 'Center', 'South', 'Unknown']
        region_stats_sorted = sorted(
            region_stats,
            key=lambda x: region_order.index(x['region']) if x['region'] in region_order else 99
        )

        return jsonify({
            'user_types': user_types_data,
            'user_status': user_status_data,
            'dog_sizes': dog_sizes_data,
            'top_breeds': top_breeds_data,
            'total_users': total_users,
            'total_dogs': total_dogs,
            'region_stats': region_stats_sorted
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/users')
def admin_users():
    if 'user_id' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT user_id, first_name, last_name, email, user_type FROM users")
    users = cur.fetchall()
    cur.close()
    return render_template('admin_users.html', users=users)


@app.route('/admin/delete_user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    if 'user_id' not in session or session['user_type'] != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'})

    try:
        cur = mysql.connection.cursor()
        # Check if user exists first
        cur.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
        if not cur.fetchone():
            cur.close()
            return jsonify({'success': False, 'message': 'User not found'})

        cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        mysql.connection.commit()
        cur.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/admin/block_user', methods=['POST'])
def block_user():
    if 'user_id' not in session or session['user_type'] != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'})

    try:
        data = request.get_json()

        if not data:
            return jsonify({'success': False, 'message': 'No JSON data received'})

        email = data.get('email')
        user_id = data.get('user_id')

        if not email or user_id is None:
            return jsonify(
                {'success': False, 'message': f'Missing email or user_id. Received: email={email}, user_id={user_id}'})

        cur = mysql.connection.cursor()

        # Check if user exists
        cur.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
        user_exists = cur.fetchone()

        if not user_exists:
            cur.close()
            return jsonify({'success': False, 'message': f'User not found with ID: {user_id}'})

        # Check if email is already blocked
        cur.execute("SELECT email FROM blocked_emails WHERE email = %s", (email,))
        email_blocked = cur.fetchone()

        if email_blocked:
            cur.close()
            return jsonify({'success': False, 'message': f'Email already blocked: {email}'})

        # Add email to blocked_emails table
        cur.execute("INSERT INTO blocked_emails (email) VALUES (%s)", (email,))

        # Remove user from the users table
        cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))

        mysql.connection.commit()
        cur.close()
        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


if __name__ == '__main__':
    app.run(debug=True)
