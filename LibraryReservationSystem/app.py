from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_PATH'] = 10000000
db = SQLAlchemy(app)
migrate = Migrate(app, db)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    copies = db.Column(db.Integer, nullable=False, default=1)
    available = db.Column(db.Boolean, default=True)
    photo = db.Column(db.String(100), nullable=True)

class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    copy_number = db.Column(db.Integer, nullable=False)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['role'] = user.role
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session['role'] != 'user':
        return redirect(url_for('login'))
    books = Book.query.all()
    return render_template('dashboard.html', books=books)

@app.route('/reserve/<int:book_id>')
def reserve(book_id):
    if 'user_id' not in session or session['role'] != 'user':
        return redirect(url_for('login'))
    book = Book.query.get(book_id)
    if book and book.copies > 0:
        book.copies -= 1
        if book.copies == 0:
            book.available = False
        new_reservation = Reservation(user_id=session['user_id'], book_id=book_id, copy_number=book.copies + 1)
        db.session.add(new_reservation)
        db.session.commit()
        receipt = f"Username: {session['user_id']}, Book: {book.title}, Copy Number: {new_reservation.copy_number}"
        return render_template('receipt.html', receipt=receipt)
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('role', None)
    return redirect(url_for('home'))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, role='admin').first()
        if user and check_password_hash(user.password, password):
            session['admin_id'] = user.id
            session['role'] = user.role
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password')
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_id' not in session or session['role'] != 'admin':
        return redirect(url_for('admin_login'))
    books = Book.query.all()
    return render_template('admin_dashboard.html', books=books)

@app.route('/admin/add_book', methods=['GET', 'POST'])
def add_book():
    if 'admin_id' not in session or session['role'] != 'admin':
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        copies = request.form['copies']
        photo = None
        if 'photo' in request.files:
            photo_file = request.files['photo']
            if photo_file.filename != '':
                photo_filename = secure_filename(photo_file.filename)
                photo_file.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))
                photo = photo_filename
        new_book = Book(title=title, author=author, copies=int(copies), available=(int(copies) > 0), photo=photo)
        db.session.add(new_book)
        db.session.commit()
        return redirect(url_for('admin_dashboard'))
    return render_template('add_book.html')

@app.route('/admin/edit_book/<int:book_id>', methods=['GET', 'POST'])
def edit_book(book_id):
    if 'admin_id' not in session or session['role'] != 'admin':
        return redirect(url_for('admin_login'))
    book = Book.query.get(book_id)
    if request.method == 'POST':
        book.title = request.form['title']
        book.author = request.form['author']
        book.copies = int(request.form['copies'])
        book.available = (book.copies > 0)
        if 'photo' in request.files:
            photo_file = request.files['photo']
            if photo_file.filename != '':
                photo_filename = secure_filename(photo_file.filename)
                photo_file.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))
                book.photo = photo_filename
        db.session.commit()
        return redirect(url_for('admin_dashboard'))
    return render_template('edit_book.html', book=book)

@app.route('/admin/manage_books', methods=['GET', 'POST'])
def manage_books():
    if 'admin_id' not in session or session['role'] != 'admin':
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        # Check if the delete button was pressed
        book_id_to_delete = request.form.get('delete')
        if book_id_to_delete:
            book_to_delete = Book.query.get(book_id_to_delete)
            db.session.delete(book_to_delete)
            db.session.commit()
            flash('Book deleted successfully.')
            return redirect(url_for('manage_books'))
        
        # Check if the update button was pressed
        book_id_to_update = request.form.get('update')
        if book_id_to_update:
            book_to_update = Book.query.get(book_id_to_update)
            book_to_update.title = request.form.get(f'title_{book_id_to_update}')
            book_to_update.author = request.form.get(f'author_{book_id_to_update}')
            book_to_update.copies = int(request.form.get(f'copies_{book_id_to_update}'))
            book_to_update.available = book_to_update.copies > 0
            
            # Handle photo update
            photo_file = request.files.get(f'photo_{book_id_to_update}')
            if photo_file and photo_file.filename != '':
                photo_filename = secure_filename(photo_file.filename)
                photo_file.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))
                book_to_update.photo = photo_filename
            
            db.session.commit()
            flash('Book updated successfully.')
            return redirect(url_for('manage_books'))

    books = Book.query.all()
    return render_template('manage_books.html', books=books)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Check if admin already exists
        admin_user = User.query.filter_by(username='HU21CSEN0101297').first()
        if not admin_user:
            admin_user = User(username='HU21CSEN0101297', password=generate_password_hash('1234'), role='admin')
            db.session.add(admin_user)
        
        # Add some initial books if they don't exist
        if not Book.query.first():
            initial_books = [
                Book(title='The Great Gatsby', author='F. Scott Fitzgerald', copies=3),
                Book(title='1984', author='George Orwell', copies=5),
                Book(title='To Kill a Mockingbird', author='Harper Lee', copies=2)
            ]
            db.session.bulk_save_objects(initial_books)
        
        db.session.commit()
        
    app.run(debug=True)