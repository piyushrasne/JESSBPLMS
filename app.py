import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import pandas as pd
import qrcode
import io

app = Flask(__name__)
app.secret_key = 'library_secret_key_2025'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads', 'photos')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
COVERS_FOLDER = os.path.join(app.root_path, 'static', 'uploads', 'covers')
os.makedirs(COVERS_FOLDER, exist_ok=True)
app.config['COVERS_FOLDER'] = COVERS_FOLDER
DATABASE = os.path.join(os.path.dirname(__file__), 'library.db')


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Users table (admin & members)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'member',
            phone TEXT,
            address TEXT,
            membership_date TEXT DEFAULT CURRENT_DATE,
            is_active INTEGER DEFAULT 1,
            profile_photo TEXT,
            seat_number TEXT
        )
    ''')
    
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN profile_photo TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN seat_number TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN year_division TEXT DEFAULT 'FY (First Year B.Sc. IT)'")
    except sqlite3.OperationalError:
        pass

    # Books table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            isbn TEXT UNIQUE,
            category TEXT,
            publisher TEXT,
            year INTEGER,
            total_copies INTEGER DEFAULT 1,
            available_copies INTEGER DEFAULT 1,
            description TEXT,
            added_date TEXT DEFAULT CURRENT_DATE,
            book_cover TEXT
        )
    ''')
    
    try:
        cursor.execute('ALTER TABLE books ADD COLUMN book_cover TEXT')
    except sqlite3.OperationalError:
        pass

    # Transactions table (issue/return)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            issue_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            return_date TEXT,
            fine REAL DEFAULT 0.0,
            status TEXT DEFAULT 'issued',
            fine_paid INTEGER DEFAULT 0,
            FOREIGN KEY (book_id) REFERENCES books(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    try:
        cursor.execute('ALTER TABLE transactions ADD COLUMN fine_paid INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass

    # Audit Logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            target TEXT NOT NULL,
            details TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Notifications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            type TEXT DEFAULT 'info',
            is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Seed admin user
    cursor.execute("SELECT id FROM users WHERE email = 'admin@library.com'")
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO users (name, email, password, role)
            VALUES (?, ?, ?, ?)
        ''', ('Administrator', 'admin@library.com',
              generate_password_hash('admin123'), 'admin'))

    # Seed member user
    cursor.execute("SELECT id FROM users WHERE email = 'member@library.com'")
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO users (name, email, password, role)
            VALUES (?, ?, ?, ?)
        ''', ('Sample Member', 'member@library.com',
              generate_password_hash('member123'), 'member'))

    # Seed fresh B.Sc. IT textbooks
    it_books = [
        ('Python Programming & Data Science', 'Dr. A.K. Sharma', '978-9381234011', 'Programming', 'Nirali Prakashan', 2023, 5, 5, 'Core Python programming, OOP concepts, NumPy, Pandas, and Data Science for B.Sc. IT.', 'python_cover.png'),
        ('Database Management Systems (DBMS & SQL)', 'Raghu Ramakrishnan', '978-0072465631', 'Database', 'McGraw Hill', 2022, 4, 4, 'Relational database fundamentals, Normalization, SQL queries, and indexing.', 'dbms_cover.png'),
        ('Web Technologies (HTML, CSS, JS, React)', 'Jon Duckett', '978-1118871645', 'Web Development', 'Wiley India', 2024, 6, 6, 'Full-stack web design, responsive design, JavaScript ES6+, and React framework.', 'web_cover.png'),
        ('Operating Systems & System Architecture', 'Silberschatz & Galvin', '978-1118063330', 'Systems', 'Wiley', 2021, 4, 4, 'Process synchronization, memory management, file systems, and Linux OS concepts.', 'os_cover.png'),
        ('Data Structures and Algorithms in C/C++', 'Mark Allen Weiss', '978-0132847377', 'Algorithms', 'Pearson Education', 2022, 5, 5, 'Linear and non-linear data structures, Trees, Graphs, Sorting, and Searching.', 'dsa_cover.png'),
        ('Computer Networks & Data Communication', 'Andrew S. Tanenbaum', '978-0132126953', 'Networking', 'Pearson', 2023, 5, 5, 'OSI layers, TCP/IP protocol suite, routing algorithms, and network security.', 'networking_cover.png'),
        ('Software Engineering & Agile Methodologies', 'Ian Sommerville', '978-0133943030', 'Software Engineering', 'Pearson', 2022, 3, 3, 'Software development life cycle, UML diagrams, Agile, Scrum, and Testing.', 'se_cover.png'),
        ('Cloud Computing & DevOps Fundamentals', 'Thomas Erl', '978-0133387520', 'Cloud', 'Prentice Hall', 2023, 4, 4, 'AWS, GCP, Docker containers, Kubernetes, CI/CD pipelines, and serverless.', 'cloud_cover.png'),
        ('Core Java & Object Oriented Programming', 'Herbert Schildt', '978-1260440232', 'Java', 'McGraw Hill', 2023, 5, 5, 'Java SE syntax, multithreading, collections framework, JDBC, and GUI.', 'java_cover.png'),
        ('Cyber Security & Ethical Hacking', 'William Stallings', '978-0134444284', 'Cyber Security', 'Pearson', 2024, 3, 3, 'Cryptography, network defense, ethical hacking tools, and web security.', 'cyber_cover.png')
    ]
    for book in it_books:
        cursor.execute("SELECT id FROM books WHERE isbn = ?", (book[2],))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO books (title, author, isbn, category, publisher, year, total_copies, available_copies, description, book_cover)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', book)

    conn.commit()
    conn.close()


# --- Helpers ---
def log_action(user_id, action, target, details=""):
    if not user_id:
        return
    conn = get_db()
    conn.execute('''
        INSERT INTO audit_logs (user_id, action, target, details)
        VALUES (?, ?, ?, ?)
    ''', (user_id, action, target, details))
    conn.commit()
    conn.close()

# --- Auth Decorators ---
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to continue.', 'warning')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


@app.context_processor
def inject_notifications():
    if 'user_id' in session:
        conn = get_db()
        today = datetime.today().strftime('%Y-%m-%d')
        if session.get('role') == 'member':
            overdue = conn.execute("SELECT b.title FROM transactions t JOIN books b ON t.book_id = b.id WHERE t.user_id = ? AND t.status = 'issued' AND t.due_date < ?", (session['user_id'], today)).fetchall()
            for od in overdue:
                msg = f"Your book '{od['title']}' is overdue!"
                exists = conn.execute("SELECT id FROM notifications WHERE user_id = ? AND message = ? AND date(created_at) = ?", (session['user_id'], msg, today)).fetchone()
                if not exists:
                    conn.execute("INSERT INTO notifications (user_id, message, type) VALUES (?, ?, 'warning')", (session['user_id'], msg))
            conn.commit()
            
        notifs = conn.execute("SELECT * FROM notifications WHERE user_id = ? AND is_read = 0 ORDER BY id DESC LIMIT 5", (session['user_id'],)).fetchall()
        unread_count = len(notifs)
        conn.close()
        return dict(notifications=notifs, unread_count=unread_count)
    return dict(notifications=[], unread_count=0)


# --- Routes ---

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE email = ? AND is_active = 1', (email,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['role'] = user['role']
            session['user_photo'] = user['profile_photo'] if 'profile_photo' in user.keys() else None
            flash(f"Welcome, {user['name']}!", 'success')
            log_action(user['id'], 'LOGIN', 'System', f"User {user['email']} logged in")
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
            
    return render_template('login.html')


@app.route('/logout')
def logout():
    if 'user_id' in session:
        log_action(session['user_id'], 'LOGOUT', 'System', f"User logged out")
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/notifications/read/<int:n_id>', methods=['POST'])
@login_required
def read_notification(n_id):
    conn = get_db()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?", (n_id, session['user_id']))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('dashboard'))


@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    total_books = conn.execute('SELECT COUNT(*) FROM books').fetchone()[0]
    total_members = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'member'").fetchone()[0]
    active_issues = conn.execute("SELECT COUNT(*) FROM transactions WHERE status = 'issued'").fetchone()[0]
    overdue = conn.execute(
        "SELECT COUNT(*) FROM transactions WHERE status = 'issued' AND due_date < ?",
        (datetime.today().strftime('%Y-%m-%d'),)
    ).fetchone()[0]
    total_fines = conn.execute("SELECT COALESCE(SUM(fine), 0) FROM transactions WHERE fine_paid = 1").fetchone()[0]
    pending_fines = conn.execute("SELECT COALESCE(SUM(fine), 0) FROM transactions WHERE fine > 0 AND fine_paid = 0").fetchone()[0]
    recent_transactions = conn.execute('''
        SELECT t.*, b.title as book_title, u.name as member_name
        FROM transactions t
        JOIN books b ON t.book_id = b.id
        JOIN users u ON t.user_id = u.id
        ORDER BY t.id DESC LIMIT 8
    ''').fetchall()
    
    recommended_books = []
    if session.get('role') == 'member':
        fav_cat = conn.execute('''
            SELECT b.category, COUNT(t.id) as borrow_count 
            FROM transactions t
            JOIN books b ON t.book_id = b.id
            WHERE t.user_id = ? AND b.category IS NOT NULL AND b.category != ''
            GROUP BY b.category
            ORDER BY borrow_count DESC LIMIT 1
        ''', (session['user_id'],)).fetchone()
        
        if fav_cat:
            category = fav_cat['category']
            recommended_books = conn.execute('''
                SELECT * FROM books 
                WHERE category = ? AND available_copies > 0 
                AND id NOT IN (SELECT book_id FROM transactions WHERE user_id = ?)
                ORDER BY id DESC LIMIT 4
            ''', (category, session['user_id'])).fetchall()
            
        if not recommended_books:
            recommended_books = conn.execute('''
                SELECT * FROM books WHERE available_copies > 0 ORDER BY id DESC LIMIT 4
            ''').fetchall()
            
    conn.close()
    return render_template('dashboard.html',
                           total_books=total_books,
                           total_members=total_members,
                           active_issues=active_issues,
                           overdue=overdue,
                           total_fines=round(total_fines, 2),
                           pending_fines=round(pending_fines, 2),
                           recent_transactions=recent_transactions,
                           recommended_books=recommended_books,
                           today=datetime.today().strftime('%Y-%m-%d'))


# --- Books ---

@app.route('/books')
@login_required
def books():
    q = request.args.get('q', '')
    cat = request.args.get('category', '')
    conn = get_db()
    query = 'SELECT * FROM books WHERE 1=1'
    params = []
    if q:
        query += ' AND (title LIKE ? OR author LIKE ? OR isbn LIKE ?)'
        params += [f'%{q}%', f'%{q}%', f'%{q}%']
    if cat:
        query += ' AND category = ?'
        params.append(cat)
    query += ' ORDER BY title'
    all_books = conn.execute(query, params).fetchall()
    categories = conn.execute('SELECT DISTINCT category FROM books ORDER BY category').fetchall()
    conn.close()
    return render_template('books.html', books=all_books, categories=categories, q=q, selected_cat=cat)


@app.route('/books/add', methods=['GET', 'POST'])
@admin_required
def add_book():
    if request.method == 'POST':
        title = request.form.get('title')
        author = request.form.get('author')
        isbn = request.form.get('isbn')
        category = request.form.get('category')
        publisher = request.form.get('publisher')
        year = request.form.get('year')
        copies = int(request.form.get('copies', 1))
        description = request.form.get('description')
        
        cover = request.files.get('book_cover')
        cover_filename = None
        if cover and cover.filename != '':
            filename = secure_filename(cover.filename)
            filename = f"book_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            cover.save(os.path.join(app.config['COVERS_FOLDER'], filename))
            cover_filename = filename

        conn = get_db()
        conn.execute('''
            INSERT INTO books (title, author, isbn, category, publisher, year, total_copies, available_copies, description, book_cover)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (title, author, isbn, category, publisher, year, copies, copies, description, cover_filename))
        conn.commit()
        conn.close()
        log_action(session['user_id'], 'ADD_BOOK', f'Book: {title}', f'Added book with ISBN {isbn}')
        flash('Book added successfully!', 'success')
        return redirect(url_for('books'))
    return render_template('add_book.html')


@app.route('/books/import', methods=['POST'])
@admin_required
def import_books():
    if 'excel_file' not in request.files:
        flash('No file uploaded', 'danger')
        return redirect(url_for('books'))
    
    file = request.files['excel_file']
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('books'))
        
    try:
        df = pd.read_excel(file)
        conn = get_db()
        success_count = 0
        
        for index, row in df.iterrows():
            title = str(row.get('Title', '')).strip()
            if not title or title == 'nan':
                continue
                
            author = str(row.get('Author', '')).strip()
            isbn = str(row.get('ISBN', '')).strip()
            category = str(row.get('Category', '')).strip()
            publisher = str(row.get('Publisher', '')).strip()
            
            try:
                year = int(row.get('Year', 0))
            except (ValueError, TypeError):
                year = None
                
            try:
                copies = int(row.get('Copies', 1))
            except (ValueError, TypeError):
                copies = 1
                
            description = str(row.get('Description', '')).strip()
            
            if isbn and isbn != 'nan':
                existing = conn.execute("SELECT id FROM books WHERE isbn = ?", (isbn,)).fetchone()
                if existing:
                    continue
            else:
                isbn = None
            
            conn.execute('''
                INSERT INTO books (title, author, isbn, category, publisher, year, total_copies, available_copies, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (title, author, isbn, category, publisher, year, copies, copies, description))
            success_count += 1
            
        conn.commit()
        conn.close()
        
        log_action(session['user_id'], 'IMPORT_BOOKS', 'System', f"Imported {success_count} books via Excel")
        flash(f'Successfully imported {success_count} books!', 'success')
        
    except Exception as e:
        flash(f'Error importing file: {str(e)}', 'danger')
        
    return redirect(url_for('books'))


@app.route('/books/edit/<int:book_id>', methods=['GET', 'POST'])
@admin_required
def edit_book(book_id):
    conn = get_db()
    book = conn.execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone()
    if not book:
        flash('Book not found.', 'danger')
        conn.close()
        return redirect(url_for('books'))
    if request.method == 'POST':
        title = request.form.get('title')
        author = request.form.get('author')
        isbn = request.form.get('isbn')
        category = request.form.get('category')
        publisher = request.form.get('publisher')
        year = request.form.get('year')
        copies = int(request.form.get('copies', 1))
        description = request.form.get('description')
        issued = book['total_copies'] - book['available_copies']
        new_available = max(0, copies - issued)
        
        cover = request.files.get('book_cover')
        try:
            cover_filename = book['book_cover']
        except IndexError:
            cover_filename = None
            
        if cover and cover.filename != '':
            filename = secure_filename(cover.filename)
            filename = f"book_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            cover.save(os.path.join(app.config['COVERS_FOLDER'], filename))
            cover_filename = filename

        conn.execute('''
            UPDATE books SET title=?, author=?, isbn=?, category=?, publisher=?, year=?, 
            total_copies=?, available_copies=?, description=?, book_cover=? WHERE id=?
        ''', (title, author, isbn, category, publisher, year, copies, new_available, description, cover_filename, book_id))
        conn.commit()
        conn.close()
        log_action(session['user_id'], 'EDIT_BOOK', f'Book ID: {book_id}', f'Updated book details for {title}')
        flash('Book updated successfully!', 'success')
        return redirect(url_for('books'))
    conn.close()
    return render_template('edit_book.html', book=book)


@app.route('/books/delete/<int:book_id>', methods=['POST'])
@admin_required
def delete_book(book_id):
    conn = get_db()
    active = conn.execute("SELECT COUNT(*) FROM transactions WHERE book_id = ? AND status = 'issued'", (book_id,)).fetchone()[0]
    if active > 0:
        flash('Cannot delete book with active issues.', 'danger')
    else:
        conn.execute('DELETE FROM books WHERE id = ?', (book_id,))
        conn.commit()
        log_action(session['user_id'], 'DELETE_BOOK', f'Book ID: {book_id}', 'Deleted book from catalog')
        flash('Book deleted successfully!', 'success')
    conn.close()
    return redirect(url_for('books'))


# --- Members ---

@app.route('/members')
@admin_required
def members():
    q = request.args.get('q', '')
    conn = get_db()
    if q:
        all_members = conn.execute(
            "SELECT * FROM users WHERE role = 'member' AND (name LIKE ? OR email LIKE ?) ORDER BY name",
            (f'%{q}%', f'%{q}%')
        ).fetchall()
    else:
        all_members = conn.execute("SELECT * FROM users WHERE role = 'member' ORDER BY name").fetchall()
    conn.close()
    return render_template('members.html', members=all_members, q=q)


@app.route('/members/add', methods=['GET', 'POST'])
@admin_required
def add_member():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        phone = request.form.get('phone')
        address = request.form.get('address')
        seat_number = request.form.get('seat_number')
        year_division = request.form.get('year_division', 'FY (First Year B.Sc. IT)')
        
        photo = request.files.get('profile_photo')
        photo_filename = None
        if photo and photo.filename != '':
            filename = secure_filename(photo.filename)
            filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            photo_filename = filename

        conn = get_db()
        existing = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if existing:
            flash('Email already registered.', 'danger')
            conn.close()
            return redirect(url_for('add_member'))
        conn.execute('''
            INSERT INTO users (name, email, password, role, phone, address, seat_number, profile_photo, year_division)
            VALUES (?, ?, ?, 'member', ?, ?, ?, ?, ?)
        ''', (name, email, generate_password_hash(password), phone, address, seat_number, photo_filename, year_division))
        conn.commit()
        conn.close()
        log_action(session['user_id'], 'ADD_MEMBER', f'Member: {name}', f'Added member {email}')
        flash('Member added successfully!', 'success')
        return redirect(url_for('members'))
    return render_template('add_member.html')


@app.route('/members/edit/<int:member_id>', methods=['GET', 'POST'])
@admin_required
def edit_member(member_id):
    conn = get_db()
    member = conn.execute('SELECT * FROM users WHERE id = ? AND role = ?', (member_id, 'member')).fetchone()
    if not member:
        flash('Member not found.', 'danger')
        conn.close()
        return redirect(url_for('members'))
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        seat_number = request.form.get('seat_number')
        year_division = request.form.get('year_division', 'FY (First Year B.Sc. IT)')
        is_active = 1 if request.form.get('is_active') else 0
        
        photo = request.files.get('profile_photo')
        photo_filename = member['profile_photo']
        if photo and photo.filename != '':
            filename = secure_filename(photo.filename)
            filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            photo_filename = filename

        conn.execute('''
            UPDATE users SET name=?, email=?, phone=?, address=?, is_active=?, seat_number=?, profile_photo=?, year_division=? WHERE id=?
        ''', (name, email, phone, address, is_active, seat_number, photo_filename, year_division, member_id))
        conn.commit()
        conn.close()
        log_action(session['user_id'], 'EDIT_MEMBER', f'Member ID: {member_id}', f'Updated profile for {name}')
        flash('Member updated successfully!', 'success')
        return redirect(url_for('members'))
    conn.close()
    return render_template('edit_member.html', member=member)


@app.route('/members/card/<int:member_id>')
@admin_required
def print_member_card(member_id):
    conn = get_db()
    member = conn.execute('SELECT * FROM users WHERE id = ?', (member_id,)).fetchone()
    conn.close()
    if not member:
        flash('Member not found.', 'danger')
        return redirect(url_for('members'))
    return render_template('member_card.html', member=member)


@app.route('/members/delete/<int:member_id>', methods=['POST'])
@admin_required
def delete_member(member_id):
    conn = get_db()
    active = conn.execute("SELECT COUNT(*) FROM transactions WHERE user_id = ? AND status = 'issued'", (member_id,)).fetchone()[0]
    if active > 0:
        flash('Cannot delete member with active book issues.', 'danger')
    else:
        conn.execute('DELETE FROM users WHERE id = ?', (member_id,))
        conn.commit()
        log_action(session['user_id'], 'DELETE_MEMBER', f'Member ID: {member_id}', 'Deleted member record')
        flash('Member deleted.', 'success')
    conn.close()
    return redirect(url_for('members'))


# --- Issue & Return ---

@app.route('/transactions')
@login_required
def transactions():
    conn = get_db()
    today = datetime.today().strftime('%Y-%m-%d')
    if session['role'] == 'admin':
        txns = conn.execute('''
            SELECT t.*, b.title as book_title, u.name as member_name
            FROM transactions t
            JOIN books b ON t.book_id = b.id
            JOIN users u ON t.user_id = u.id
            ORDER BY t.id DESC
        ''').fetchall()
    else:
        txns = conn.execute('''
            SELECT t.*, b.title as book_title, u.name as member_name
            FROM transactions t
            JOIN books b ON t.book_id = b.id
            JOIN users u ON t.user_id = u.id
            WHERE t.user_id = ?
            ORDER BY t.id DESC
        ''', (session['user_id'],)).fetchall()
    books_available = conn.execute("SELECT * FROM books WHERE available_copies > 0 ORDER BY title").fetchall()
    members_list = conn.execute("SELECT * FROM users WHERE role = 'member' AND is_active = 1 ORDER BY name").fetchall()
    conn.close()
    return render_template('transactions.html', transactions=txns, books=books_available,
                           members=members_list, today=today)


@app.route('/transactions/issue', methods=['POST'])
@admin_required
def issue_book():
    book_ids = request.form.getlist('book_id')
    user_id = request.form.get('user_id')
    issue_date = datetime.today().strftime('%Y-%m-%d')
    days = request.form.get('days', type=int)
    if not days or days < 1:
        days = 14
    due_date = (datetime.today() + timedelta(days=days)).strftime('%Y-%m-%d')
    
    if not book_ids:
        flash('Please select at least one book.', 'warning')
        return redirect(url_for('transactions'))
        
    conn = get_db()
    success_count = 0
    
    for book_id in book_ids:
        book = conn.execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone()
        if not book or book['available_copies'] < 1:
            continue
            
        existing = conn.execute(
            "SELECT id FROM transactions WHERE book_id=? AND user_id=? AND status='issued'",
            (book_id, user_id)
        ).fetchone()
        if existing:
            continue
            
        conn.execute('''
            INSERT INTO transactions (book_id, user_id, issue_date, due_date) VALUES (?, ?, ?, ?)
        ''', (book_id, user_id, issue_date, due_date))
        conn.execute('UPDATE books SET available_copies = available_copies - 1 WHERE id = ?', (book_id,))
        success_count += 1
        
    conn.commit()
    conn.close()
    
    if success_count > 0:
        log_action(session['user_id'], 'ISSUE_BOOKS', f'User ID {user_id}', f'Issued {success_count} books')
        flash(f'{success_count} Book(s) issued successfully! Due date: {due_date}', 'success')
    else:
        flash('No books could be issued.', 'danger')
        
    return redirect(url_for('transactions'))


@app.route('/transactions/return/<int:txn_id>', methods=['POST'])
@admin_required
def return_book(txn_id):
    conn = get_db()
    txn = conn.execute("SELECT * FROM transactions WHERE id = ? AND status = 'issued'", (txn_id,)).fetchone()
    if not txn:
        flash('Transaction not found.', 'danger')
        conn.close()
        return redirect(url_for('transactions'))
    return_date = datetime.today().strftime('%Y-%m-%d')
    fine = 0.0
    due = datetime.strptime(txn['due_date'], '%Y-%m-%d')
    today = datetime.today()
    if today > due:
        days_late = (today - due).days
        fine = days_late * 5.0
    conn.execute('''
        UPDATE transactions SET return_date=?, fine=?, status='returned' WHERE id=?
    ''', (return_date, fine, txn_id))
    conn.execute('UPDATE books SET available_copies = available_copies + 1 WHERE id = ?', (txn['book_id'],))
    conn.commit()
    conn.close()
    log_action(session['user_id'], 'RETURN_BOOK', f'Txn ID: {txn_id}', f'Returned book ID {txn["book_id"]}')
    if fine > 0:
        flash(f'Book returned. Fine: ₹{fine:.2f}', 'warning')
    else:
        flash('Book returned successfully. No fine!', 'success')
    return redirect(url_for('transactions'))


@app.route('/transactions/add_fine/<int:txn_id>', methods=['POST'])
@admin_required
def add_fine(txn_id):
    fine_amount = request.form.get('fine_amount', type=float)
    if fine_amount is None or fine_amount <= 0:
        flash('Invalid fine amount.', 'danger')
        return redirect(url_for('transactions'))
        
    conn = get_db()
    txn = conn.execute("SELECT * FROM transactions WHERE id = ?", (txn_id,)).fetchone()
    if not txn:
        flash('Transaction not found.', 'danger')
        conn.close()
        return redirect(url_for('transactions'))
        
    new_fine = txn['fine'] + fine_amount
    conn.execute('UPDATE transactions SET fine=? WHERE id=?', (new_fine, txn_id))
    conn.commit()
    conn.close()
    
    log_action(session['user_id'], 'ADD_FINE', f'Txn ID: {txn_id}', f'Added fine of {fine_amount}')
    flash(f'Successfully added ₹{fine_amount:.2f} fine.', 'success')
    return redirect(url_for('transactions'))


@app.route('/transactions/pay_fine/<int:txn_id>', methods=['POST'])
@admin_required
def pay_fine(txn_id):
    conn = get_db()
    txn = conn.execute('''
        SELECT t.*, u.name as member_name 
        FROM transactions t 
        JOIN users u ON t.user_id = u.id 
        WHERE t.id = ?
    ''', (txn_id,)).fetchone()
    
    if not txn:
        flash('Transaction not found.', 'danger')
        conn.close()
        return redirect(url_for('transactions'))
        
    conn.execute('UPDATE transactions SET fine_paid = 1 WHERE id = ?', (txn_id,))
    conn.commit()
    conn.close()
    
    log_action(session['user_id'], 'PAY_FINE', f'Txn ID: {txn_id}', f'Fine of {txn["fine"]} paid by {txn["member_name"]}')
    return render_template('fine_receipt.html', txn=txn, today=datetime.today().strftime('%Y-%m-%d %H:%M:%S'))


@app.route('/transactions/delete_fine/<int:txn_id>', methods=['POST'])
@admin_required
def delete_fine(txn_id):
    conn = get_db()
    txn = conn.execute("SELECT * FROM transactions WHERE id = ?", (txn_id,)).fetchone()
    if not txn:
        flash('Transaction not found.', 'danger')
        conn.close()
        return redirect(url_for('transactions'))
        
    conn.execute('UPDATE transactions SET fine = 0, fine_paid = 0 WHERE id = ?', (txn_id,))
    conn.commit()
    conn.close()
    
    log_action(session['user_id'], 'DELETE_FINE', f'Txn ID: {txn_id}', f'Fine removed for transaction')
    flash('Fine has been removed successfully.', 'success')
    return redirect(url_for('transactions'))


# --- Reports ---

@app.route('/reports')
@admin_required
def reports():
    conn = get_db()
    today = datetime.today().strftime('%Y-%m-%d')
    overdue_books = conn.execute('''
        SELECT t.*, b.title as book_title, u.name as member_name, u.phone
        FROM transactions t
        JOIN books b ON t.book_id = b.id
        JOIN users u ON t.user_id = u.id
        WHERE t.status = 'issued' AND t.due_date < ?
        ORDER BY t.due_date
    ''', (today,)).fetchall()
    
    popular_books = conn.execute('''
        SELECT b.title, b.author, COUNT(t.id) as borrow_count
        FROM transactions t
        JOIN books b ON t.book_id = b.id
        GROUP BY t.book_id
        ORDER BY borrow_count DESC LIMIT 5
    ''').fetchall()
    
    total_fines = conn.execute("SELECT COALESCE(SUM(fine), 0) FROM transactions WHERE fine_paid = 1").fetchone()[0]
    pending_fines = conn.execute("SELECT COALESCE(SUM(fine), 0) FROM transactions WHERE fine > 0 AND fine_paid = 0").fetchone()[0]
    
    paid_receipts = conn.execute('''
        SELECT t.*, b.title as book_title, u.name as member_name
        FROM transactions t
        JOIN books b ON t.book_id = b.id
        JOIN users u ON t.user_id = u.id
        WHERE t.fine_paid = 1 OR t.fine > 0
        ORDER BY t.id DESC
    ''').fetchall()

    monthly = conn.execute('''
        SELECT strftime('%Y-%m', issue_date) as month, COUNT(*) as count
        FROM transactions
        GROUP BY month ORDER BY month DESC LIMIT 6
    ''').fetchall()
    
    cat_stats = conn.execute('''
        SELECT b.category, COUNT(t.id) as cnt
        FROM transactions t
        JOIN books b ON t.book_id = b.id
        GROUP BY b.category ORDER BY cnt DESC
    ''').fetchall()
    conn.close()
    return render_template('reports.html',
                           overdue_books=overdue_books,
                           popular_books=popular_books,
                           total_fines=round(total_fines, 2),
                           pending_fines=round(pending_fines, 2),
                           paid_receipts=paid_receipts,
                           monthly=monthly,
                           cat_stats=cat_stats,
                           today=today)


# --- Audit Logs ---

@app.route('/audit-logs')
@admin_required
def audit_logs():
    conn = get_db()
    logs = conn.execute('''
        SELECT a.*, u.name as user_name 
        FROM audit_logs a
        LEFT JOIN users u ON a.user_id = u.id
        ORDER BY a.id DESC LIMIT 100
    ''').fetchall()
    conn.close()
    return render_template('audit_logs.html', logs=logs)


# --- Project Info ---

@app.route('/info')
@login_required
def info():
    return render_template('info.html')


# --- Profile ---

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        address = request.form.get('address')
        new_password = request.form.get('new_password')
        if new_password:
            conn.execute('UPDATE users SET name=?, phone=?, address=?, password=? WHERE id=?',
                         (name, phone, address, generate_password_hash(new_password), session['user_id']))
        else:
            conn.execute('UPDATE users SET name=?, phone=?, address=? WHERE id=?',
                         (name, phone, address, session['user_id']))
        conn.commit()
        session['user_name'] = name
        flash('Profile updated!', 'success')
        conn.close()
        return redirect(url_for('profile'))
    conn.close()
    return render_template('profile.html', user=user)


# --- API for search autocomplete ---
@app.route('/api/books/search')
@login_required
def api_search_books():
    q = request.args.get('q', '')
    conn = get_db()
    results = conn.execute(
        "SELECT id, title, author FROM books WHERE (title LIKE ? OR author LIKE ?) LIMIT 10",
        (f'%{q}%', f'%{q}%')
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in results])


@app.route('/api/qr/<int:book_id>')
@login_required
def generate_qr(book_id):
    conn = get_db()
    book = conn.execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone()
    conn.close()
    
    if not book:
        return "Book not found", 404
        
    qr_data = f"BOOK_ID:{book_id}|ISBN:{book['isbn'] or 'N/A'}|TITLE:{book['title']}"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    
    return send_file(buf, mimetype='image/png')


@app.route('/transactions/receipt/<int:txn_id>')
@admin_required
def print_receipt(txn_id):
    conn = get_db()
    txn = conn.execute('''
        SELECT t.*, b.title as book_title, u.name as member_name, u.email as member_email
        FROM transactions t 
        JOIN books b ON t.book_id = b.id
        JOIN users u ON t.user_id = u.id 
        WHERE t.id = ?
    ''', (txn_id,)).fetchone()
    conn.close()
    if not txn:
        flash('Receipt not found.', 'danger')
        return redirect(url_for('reports'))
    return render_template('fine_receipt.html', txn=txn, today=datetime.today().strftime('%Y-%m-%d %H:%M:%S'))


# --- Admin Database Management ---

@app.route('/database')
@admin_required
def admin_database():
    conn = get_db()
    tables_raw = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
    tables = [t['name'] for t in tables_raw]
    table_counts = {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}
    
    selected_table = request.args.get('table')
    q = request.args.get('q', '').strip()
    
    if not selected_table or selected_table not in tables:
        selected_table = tables[0] if tables else ''
        
    columns = []
    rows = []
    if selected_table:
        col_info = conn.execute(f'PRAGMA table_info("{selected_table}")').fetchall()
        columns = [c['name'] for c in col_info]
        
        if q and columns:
            where_clause = " OR ".join([f'"{col}" LIKE ?' for col in columns])
            params = [f'%{q}%'] * len(columns)
            rows = conn.execute(f'SELECT * FROM "{selected_table}" WHERE {where_clause} LIMIT 100', params).fetchall()
        else:
            rows = conn.execute(f'SELECT * FROM "{selected_table}" LIMIT 100').fetchall()
            
    conn.close()
    return render_template('database.html', 
                           tables=tables, 
                           table_counts=table_counts, 
                           selected_table=selected_table, 
                           columns=columns, 
                           rows=rows, 
                           q=q)


@app.route('/database/edit/<table_name>/<int:row_id>', methods=['GET', 'POST'])
@admin_required
def admin_database_edit(table_name, row_id):
    conn = get_db()
    valid_tables = [t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
    if table_name not in valid_tables:
        flash('Invalid database table.', 'danger')
        conn.close()
        return redirect(url_for('admin_database'))
        
    col_info = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    columns = [c['name'] for c in col_info]
    pk = 'id' if 'id' in columns else columns[0]
    
    row = conn.execute(f'SELECT * FROM "{table_name}" WHERE "{pk}" = ?', (row_id,)).fetchone()
    
    if not row:
        flash('Row record not found.', 'danger')
        conn.close()
        return redirect(url_for('admin_database', table=table_name))
        
    if request.method == 'POST':
        update_cols = []
        val_list = []
        for col in columns:
            if col == pk:
                continue
            update_cols.append(f'"{col}" = ?')
            val_list.append(request.form.get(col))
        val_list.append(row_id)
        
        sql = f'UPDATE "{table_name}" SET {", ".join(update_cols)} WHERE "{pk}" = ?'
        try:
            conn.execute(sql, val_list)
            conn.commit()
            flash(f'Record #{row_id} in {table_name} updated successfully!', 'success')
            log_action(session['user_id'], 'DB_UPDATE', f'Table: {table_name}', f'Updated row #{row_id}')
        except Exception as e:
            flash(f'Database update error: {str(e)}', 'danger')
        conn.close()
        return redirect(url_for('admin_database', table=table_name))
        
    conn.close()
    return render_template('database_edit.html', table_name=table_name, row_id=row_id, columns=columns, row=row, pk=pk)


@app.route('/database/delete/<table_name>/<int:row_id>', methods=['POST'])
@admin_required
def admin_database_delete(table_name, row_id):
    conn = get_db()
    valid_tables = [t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
    if table_name in valid_tables:
        col_info = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        columns = [c['name'] for c in col_info]
        pk = 'id' if 'id' in columns else columns[0]
        try:
            conn.execute(f'DELETE FROM "{table_name}" WHERE "{pk}" = ?', (row_id,))
            conn.commit()
            flash(f'Record #{row_id} deleted from {table_name}.', 'warning')
            log_action(session['user_id'], 'DB_DELETE', f'Table: {table_name}', f'Deleted row #{row_id}')
        except Exception as e:
            flash(f'Error deleting record: {str(e)}', 'danger')
    conn.close()
    return redirect(url_for('admin_database', table=table_name))


@app.route('/database/query', methods=['POST'])
@admin_required
def admin_database_query():
    sql_query = (request.form.get('sql_query') or request.form.get('query') or '').strip()
    if not sql_query:
        flash('Please enter a valid SQL query.', 'warning')
        return redirect(url_for('admin_database'))
        
    conn = get_db()
    tables_raw = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
    tables = [t['name'] for t in tables_raw]
    table_counts = {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}
    
    query_columns = []
    query_results = []
    
    try:
        if sql_query.lower().startswith('select') or sql_query.lower().startswith('pragma'):
            cursor = conn.execute(sql_query)
            query_columns = [d[0] for d in cursor.description] if cursor.description else []
            query_results = cursor.fetchall()
            flash(f'SQL query executed successfully! Returned {len(query_results)} row(s).', 'success')
        else:
            cursor = conn.execute(sql_query)
            conn.commit()
            flash(f'SQL command executed successfully! Affected {cursor.rowcount} row(s).', 'success')
            log_action(session['user_id'], 'DB_RAW_QUERY', 'System', f'Executed query: {sql_query[:50]}...')
    except Exception as e:
        flash(f'SQL Execution Error: {str(e)}', 'danger')
        
    conn.close()
    return render_template('database.html',
                           tables=tables,
                           table_counts=table_counts,
                           selected_table=tables[0] if tables else '',
                           columns=[],
                           rows=[],
                           sql_query=sql_query,
                           query_columns=query_columns,
                           query_results=query_results)


init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    print("\n" + "="*50)
    print("  Library Management System")
    print(f"  Running at: http://0.0.0.0:{port}")
    print("  Admin Login: admin@library.com / admin123")
    print("  Member Login: member@library.com / member123")
    print("="*50 + "\n")
    app.run(debug=True, host='0.0.0.0', port=port)
