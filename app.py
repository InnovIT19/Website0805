from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash
import pyodbc
import base64
import numpy as np
from tensorflow.keras.models import load_model
import cv2
import uuid
import random


app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Ensure to set a secret key for session management

# Configure your database connection here
server = 'DESKTOP-16A7BAU'
database = 'fashion'
username = 'cube_sl'
password = '123'
driver = '{ODBC Driver 17 for SQL Server}'

connection_string = f'DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password}'

@app.route('/')
def welcome():
    return render_template('home.html')

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/user_login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        phone_number = request.form['phone_number']
        gender = request.form['gender']

        if not phone_number or len(phone_number) != 10 or not gender:
            flash('Invalid phone number or gender!', 'danger')
            return redirect(url_for('user_login'))

        try:
            conn = pyodbc.connect(connection_string)
            cursor = conn.cursor()

            cursor.execute('SELECT user_id FROM user2 WHERE PhoneNumber = ? AND Gender = ?', (phone_number, gender))
            result = cursor.fetchone()

            if result:
                user_id = result[0]
                session['user_id'] = user_id

                cursor.execute('DELETE FROM video WHERE user_id = ?', (user_id,))
                conn.commit()

                flash('Login successful! All existing snapshots have been deleted.', 'success')
                return redirect(url_for('index'))  # Redirect to a protected page or dashboard
            else:
                flash('Invalid phone number or gender!', 'danger')

        except Exception as e:
            print(f"Error during login or snapshot deletion: {str(e)}")
            flash('An error occurred. Please try again later.', 'danger')

        finally:
            conn.close()

    user_id = session.get('user_id')
    return render_template('user_login.html', user_id=user_id)

@app.route('/admin_login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM Admins WHERE username = ? AND password = ?', (username, password))
        account = cursor.fetchone()
        conn.close()

        if account:
            session['loggedin'] = True
            session['id'] = account[0]
            session['username'] = account[1]
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Incorrect username/password!', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    flash('You have successfully logged out.', 'success')
    return redirect(url_for('welcome'))


def generate_unique_user_id():
    while True:
        user_id = str(random.randint(100000, 999999))
        with pyodbc.connect(connection_string) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM user2 WHERE user_id = ?", (user_id,))
            count = cursor.fetchone()[0]
            if count == 0:
                return user_id


@app.route('/submit', methods=['POST'])
def submitInput():
    data = request.json
    phone_number = data.get('phone_number')

    if not phone_number or len(phone_number) != 10:
        return jsonify({'error': 'Invalid phone number'}), 400

    user_id = generate_unique_user_id()  # Generate a unique user_id

    try:
        with pyodbc.connect(connection_string) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO user2 (PhoneNumber, user_id) VALUES (?, ?)", (phone_number, user_id))
            conn.commit()

        session['phone_number'] = phone_number
        session['user_id'] = user_id  # Store user_id in session
        return jsonify({'message': 'Registration successful', 'user_id': user_id}), 200
    except Exception as e:
        print(f"Error occurred during registration: {str(e)}")  # Add error logging
        return jsonify({'error': str(e)}), 500


@app.route('/gender', methods=['GET', 'POST'])
def gender():
    if request.method == 'POST':
        data = request.json
        gender = data.get('gender')
        phone_number = data.get('phone_number')

        if not gender:
            return jsonify({'error': 'Gender not provided'}), 400
        if not phone_number or len(phone_number) != 10:
            return jsonify({'error': 'Invalid phone number'}), 400

        try:
            conn = pyodbc.connect(connection_string)
            cursor = conn.cursor()

            cursor.execute("UPDATE user2 SET gender = ? WHERE PhoneNumber = ?", (gender, phone_number))

            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'message': 'Gender updated successfully'}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    else:
        return render_template('gender.html')

@app.route('/submit_phone', methods=['POST'])
def submit_phone_number():
    data = request.json
    phone_number = data.get('phone_number')
    gender = data.get('gender')

    if not phone_number or len(phone_number) != 10:
        return jsonify({'error': 'Invalid phone number'}), 400

    try:
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM user2 WHERE PhoneNumber = ? AND Gender = ?", (phone_number, gender))
        result = cursor.fetchone()

        cursor.close()
        conn.close()

        if result:
            return jsonify({'message': 'Login successful'}), 200
        else:
            return jsonify({'error': 'Invalid phone number or gender'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/material', methods=['GET'])
def material():
    return render_template('material.html')

@app.route('/submit_material', methods=['POST'])
def submit_material():
    data = request.json
    material = data.get('material')
    phone_number = session.get('phone_number')

    if not material:
        return jsonify({'error': 'Material not provided'}), 400

    try:
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()
        cursor.execute("UPDATE user2 SET material = ? WHERE PhoneNumber = ?", (material, phone_number))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'message': 'Material updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/outfitCategory', methods=['GET'])
def outfit_category():
    return render_template('outfitCategory.html')

# Load the trained model
model = load_model("skin_tone_classifier.h5")

categories = ['Black', 'Brown', 'Dark-brown', 'Olive', 'White']
img_size = 128  # This should match the size used during training


@app.route('/capture_video', methods=['GET'])
def capture_video():
    return render_template('capture_video.html')

@app.route('/submit_snapshots', methods=['POST'])
def submit_snapshots():
    data = request.get_json()
    snapshots = data.get('snapshots')
    user_id = session.get('user_id')

    if not user_id:
        return jsonify({'message': 'Failed to retrieve phone number for user'})

    try:
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()

        for snapshot in snapshots:
            img_data = base64.b64decode(snapshot.split(',')[1])
            cursor.execute("INSERT INTO video (user_id, Snapshot) VALUES (?, ?)", user_id, img_data)

        conn.commit()
        # Predict skin tone category based on the last snapshot
        last_snapshot = base64.b64decode(snapshots[-1].split(',')[1])
        img_array = np.asarray(bytearray(last_snapshot), dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        # Resize and normalize image
        img_resized = cv2.resize(img, (img_size, img_size))
        img_normalized = img_resized / 255.0
        img_reshaped = np.reshape(img_normalized, (1, img_size, img_size, 3))

        # Perform prediction
        prediction = model.predict(img_reshaped)
        predicted_class = np.argmax(prediction)
        predicted_tone = categories[predicted_class]

        # Save the predicted skin tone in the session
        session['predicted_tone'] = predicted_tone

        cursor.close()
        conn.close()

        return jsonify({'message': 'Snapshots saved successfully'})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'message': 'Failed to save snapshots'})

import os
import cv2

def load_color_images():
    """Loads color images from the dataset directory."""
    base_path = "static/colors"  # Path to the color dataset
    color_images = {}

    for category in categories:
        category_path = os.path.join(base_path, category)
        color_images[category] = []

        if not os.path.exists(category_path):
            print(f"Warning: Directory does not exist for category '{category}': {category_path}")
            continue

        for file in os.listdir(category_path):
            if file.endswith((".png", ".jpg", ".jpeg")):
                img_path = os.path.join(category_path, file)
                img = cv2.imread(img_path)
                if img is not None:
                    color_images[category].append((file, img))

    return color_images

def recommend_colors_for_skin_tone(predicted_tone):
    """Recommends color images based on the predicted skin tone."""
    color_images = load_color_images()
    recommended_colors = color_images.get(predicted_tone, [])

    return random.sample(recommended_colors, min(10, len(recommended_colors)))  # Changed to 10


def classify_skin_tone_from_base64(base64_image):
    img_data = base64.b64decode(base64_image.split(',')[1])
    img_array = np.asarray(bytearray(img_data), dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    img_resized = cv2.resize(img, (img_size, img_size))
    img_normalized = img_resized / 255.0
    img_reshaped = np.reshape(img_normalized, (1, img_size, img_size, 3))
    prediction = model.predict(img_reshaped)
    predicted_class = np.argmax(prediction)
    return categories[predicted_class]


@app.route('/get_skin_tone')
def get_skin_tone():
    predicted_tone = session.get('predicted_tone')

    if not predicted_tone:
        return jsonify({'message': 'No skin tone prediction available'}), 400

    recommended_colors = recommend_colors_for_skin_tone(predicted_tone)

    return jsonify({'predicted_tone': predicted_tone, 'recommended_colors': recommended_colors})

@app.route('/outfit')
def outfit():
    try:
        predicted_tone = session.get('predicted_tone')

        if not predicted_tone:
            return "Predicted skin tone not found. Please capture and submit video first."

        recommended_colors = recommend_colors_for_skin_tone(predicted_tone)

        # Prepare data to pass to the template
        color_data = []
        for color_name, color_img in recommended_colors:
            color_name = color_name.split('.')[0]
            _, buffer = cv2.imencode('.jpg', color_img)
            img_base64 = base64.b64encode(buffer).decode('utf-8')
            color_data.append({'name': color_name, 'image': f"data:image/jpeg;base64,{img_base64}"})

        return render_template('outfit.html', predicted_tone=predicted_tone, colors=color_data)

    except Exception as e:
        print(f"Error in /outfit route: {str(e)}")
        return render_template('error.html', error_message=str(e)), 500

@app.route('/outfits')
def get_outfits():
    try:
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()
        cursor.execute('SELECT outfit_id, name, price, outfit_img FROM outfit')
        outfits = cursor.fetchall()
        cursor.close()
        conn.close()

        outfit_list = []
        for outfit in outfits:
            outfit_id = outfit.outfit_id
            name = outfit.name
            price = outfit.price
            outfit_img = base64.b64encode(outfit.outfit_img).decode('utf-8')
            outfit_list.append({'id': outfit_id, 'name': name, 'price': price, 'img': outfit_img})

        return jsonify(outfit_list)

    except Exception as e:
        print(f"Error fetching outfits: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/submit', methods=['POST'])
def submit():
    # Add your logic here for handling the POST request to /submit
    return jsonify({'message': 'Submit endpoint reached successfully'}), 200

@app.route('/feedback', methods=['GET', 'POST'])
def submitFeedback():
    if request.method == 'POST':
        try:
            data = request.json
            color = data.get('color')
            size = data.get('size')
            outfit = data.get('outfit')
            overall_appearance = data.get('overall_appearance')

            conn = pyodbc.connect(connection_string)
            cursor = conn.cursor()

            cursor.execute("INSERT INTO feedback (color, size, outfit, overall_appearance) VALUES (?, ?, ?, ?)",
                           (color, size, outfit, overall_appearance))

            conn.commit()
            cursor.close()
            conn.close()

            return jsonify({'message': 'Feedback submitted successfully'}), 200

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return render_template('feedback.html')

@app.route('/thank')
def thank():
    return render_template('thank.html')

@app.route('/admin_dashboard')
def index():
    if 'loggedin' in session:
        return render_template('admin_dashboard.html')
    else:
        return redirect(url_for('login'))


@app.route('/manage_material', methods=['GET', 'POST'])
def manage_material():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    conn = pyodbc.connect(connection_string)
    cursor = conn.cursor()

    if request.method == 'POST':
        if 'add' in request.form:
            name = request.form['name']
            description = request.form['description']
            if name and description:
                cursor.execute('INSERT INTO MaterialType (name, description) VALUES (?, ?)', (name, description))
                conn.commit()
                flash('Material added successfully!', 'success')
            else:
                flash('Material name and description cannot be empty.', 'error')
        elif 'update' in request.form:
            material_id = request.form['update_material_id']
            new_name = request.form['update_name']
            new_description = request.form['update_description']
            if material_id and new_name and new_description:
                cursor.execute('UPDATE MaterialType SET name = ?, description = ? WHERE material_id = ?',
                               (new_name, new_description, material_id))
                conn.commit()
                flash('Material updated successfully!', 'success')
            else:
                flash('Please provide all fields to update material.', 'error')
        elif 'drop' in request.form:
            material_id = request.form['drop_material_id']
            # Check if the material exists in Inventory table
            cursor.execute('SELECT COUNT(*) FROM Inventory WHERE category_id = ?', (material_id,))
            count = cursor.fetchone()[0]
            if count == 0:
                cursor.execute('DELETE FROM MaterialType WHERE material_id = ?', (material_id,))
                conn.commit()
                flash('Material dropped successfully!', 'success')
            else:
                flash('Cannot delete material because it is referenced in the inventory.', 'error')

        return redirect(url_for('manage_material'))

    cursor.execute('SELECT * FROM MaterialType')
    materials = cursor.fetchall()
    conn.close()

    return render_template('manage_material.html', materials=materials)


@app.route('/manage_inventory', methods=['GET', 'POST'])
def manage_inventory():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    conn = pyodbc.connect(connection_string)
    cursor = conn.cursor()

    if request.method == 'POST':
        if 'add' in request.form:
            category_id = request.form['category_id']
            quantity = request.form['quantity']
            if category_id and quantity:
                cursor.execute('INSERT INTO Inventory (category_id, quantity) VALUES (?, ?)', (category_id, quantity))
                conn.commit()
                flash('Inventory added successfully!', 'success')
            else:
                flash('Category and quantity cannot be empty.', 'error')
        elif 'update_inventory' in request.form:
            inventory_id = request.form['update_inventory_id']
            new_quantity = request.form['update_quantity']
            if inventory_id and new_quantity:
                cursor.execute('UPDATE Inventory SET quantity = ? WHERE inventory_id = ?', (new_quantity, inventory_id))
                conn.commit()
                flash('Inventory updated successfully!', 'success')
            else:
                flash('Please select an inventory item and enter a new quantity.', 'error')
        elif 'drop_inventory' in request.form:
            inventory_id = request.form['drop_inventory_id']
            if inventory_id:
                cursor.execute('DELETE FROM Inventory WHERE inventory_id = ?', (inventory_id,))
                conn.commit()
                flash('Inventory dropped successfully!', 'success')
            else:
                flash('Please select an inventory item to drop.', 'error')

        return redirect(url_for('manage_inventory'))

    # Fetch categories for Add Inventory form
    cursor.execute('SELECT category_id, name FROM Category')
    categories = cursor.fetchall()

    # Fetch inventories for Update and Drop Inventory forms
    cursor.execute('''
        SELECT i.inventory_id, c.name AS category_name, i.quantity
        FROM Inventory i
        JOIN Category c ON i.category_id = c.category_id
    ''')
    inventories = cursor.fetchall()

    conn.close()

    return render_template('manage_inventory.html', categories=categories, inventories=inventories)


@app.route('/manage_category', methods=['GET', 'POST'])
def manage_category():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    conn = pyodbc.connect(connection_string)
    cursor = conn.cursor()

    if request.method == 'POST':
        if 'add' in request.form:
            name = request.form.get('name')
            description = request.form.get('description')
            if name and description:
                cursor.execute('INSERT INTO Category (name, description) VALUES (?, ?)', (name, description))
                conn.commit()
                flash('Category added successfully!', 'success')
            else:
                flash('Category name and description cannot be empty.', 'error')

        elif 'update' in request.form:
            category_id = request.form.get('update_category_id')
            new_name = request.form.get('update_name')
            new_description = request.form.get('update_description')
            if category_id and new_name and new_description:
                cursor.execute('UPDATE Category SET name = ?, description = ? WHERE category_id = ?',
                               (new_name, new_description, category_id))
                conn.commit()
                flash('Category updated successfully!', 'success')
            else:
                flash('Please provide all details for updating the category.', 'error')

        elif 'drop' in request.form:
            category_id = request.form.get('drop_category_id')
            # Check for references in Inventory table
            cursor.execute('SELECT COUNT(*) FROM Inventory WHERE category_id = ?', (category_id,))
            count = cursor.fetchone()[0]
            if count == 0:
                cursor.execute('DELETE FROM Category WHERE category_id = ?', (category_id,))
                conn.commit()
                flash('Category dropped successfully!', 'success')
            else:
                flash('Cannot delete category because it is referenced in the inventory.', 'error')

        elif 'update_inventory' in request.form:
            inventory_id = request.form.get('update_inventory_id')
            new_quantity = request.form.get('update_quantity')
            if inventory_id and new_quantity:
                cursor.execute('UPDATE Inventory SET quantity = ? WHERE inventory_id = ?',
                               (new_quantity, inventory_id))
                conn.commit()
                flash('Inventory updated successfully!', 'success')
            else:
                flash('Please provide all details for updating the inventory.', 'error')

        return redirect(url_for('manage_category'))

    cursor.execute('SELECT * FROM Category')
    categories = cursor.fetchall()

    cursor.execute('''
        SELECT Inventory.inventory_id, Category.name AS category_name, Inventory.quantity
        FROM Inventory
        JOIN Category ON Inventory.category_id = Category.category_id
    ''')
    inventories = cursor.fetchall()

    conn.close()

    return render_template('manage_category.html', categories=categories, inventories=inventories)


if __name__ == '__main__':
    app.run(debug=True)
