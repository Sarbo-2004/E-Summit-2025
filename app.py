from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import qrcode
import os
import random

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Database Configuration for MySQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://username:password@hostname:3306/database_name'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'  # Folder to save payment screenshots
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)

# Database Model
class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unique_id = db.Column(db.String(10), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    days = db.Column(db.String(50), nullable=False)
    amount_paid = db.Column(db.Boolean, default=False)
    payment_screenshot = db.Column(db.String(120), nullable=True)  # Path to payment screenshot

# Helper function to check file extension
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/buy_ticket', methods=['GET', 'POST'])
def buy_ticket():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        days = request.form.getlist('days')
        total_amount = len(days) * 50

        # Generate numeric unique ID for the ticket
        unique_id = str(random.randint(1000000000, 9999999999))

        # Save ticket to database
        ticket = Ticket(unique_id=unique_id, name=name, email=email, phone=phone, days=", ".join(days))
        db.session.add(ticket)
        db.session.commit()

        return redirect(url_for('payment', ticket_id=ticket.id, total_amount=total_amount))

    return render_template('buy_ticket.html')

@app.route('/payment/<int:ticket_id>/<int:total_amount>', methods=['GET', 'POST'])
def payment(ticket_id, total_amount):
    ticket = Ticket.query.get(ticket_id)
    if request.method == 'POST':
        # Handle file upload
        file = request.files.get('payment_screenshot')  # Use get() to avoid KeyError
        if not file:
            return "No file selected. Please upload the payment screenshot."

        if file and allowed_file(file.filename):
            screenshot_filename = f"{ticket.unique_id}_payment.{file.filename.rsplit('.', 1)[1].lower()}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], screenshot_filename)
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])
            file.save(file_path)

            ticket.payment_screenshot = file_path
            ticket.amount_paid = True
            db.session.commit()
            return redirect(url_for('download_ticket', ticket_id=ticket.id))
        else:
            return "Invalid file type. Only images are allowed."

    return render_template('payment.html', ticket=ticket, total_amount=total_amount)

@app.route('/download_ticket/<int:ticket_id>')
def download_ticket(ticket_id):
    ticket = Ticket.query.get(ticket_id)
    if not ticket or not ticket.amount_paid or not ticket.payment_screenshot:
        return "Unauthorized access! Payment screenshot is required."

    # Generate QR Code
    qr_data = f"Unique ID: {ticket.unique_id}\nDays: {ticket.days}\n"
    qr = qrcode.QRCode()
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_path = f"qr_{ticket.id}.png"
    qr_img.save(qr_path)

    # Generate PDF Ticket
    pdf_path = f"ticket_{ticket.id}.pdf"
    pdf = canvas.Canvas(pdf_path, pagesize=letter)
    pdf.drawString(100, 750, f"Unique ID: {ticket.unique_id}")
    pdf.drawString(100, 730, f"Ticket ID: {ticket.id}")
    pdf.drawString(100, 710, f"Name: {ticket.name}")
    pdf.drawString(100, 690, f"Email: {ticket.email}")
    pdf.drawString(100, 670, f"Phone: {ticket.phone}")
    pdf.drawString(100, 650, f"Days: {ticket.days}")
    pdf.drawImage(qr_path, 100, 500, width=150, height=150)
    pdf.save()

    # Clean up QR Code file
    os.remove(qr_path)

    # Send PDF file as response
    return send_file(pdf_path, download_name=f'ticket_{ticket.id}.pdf', as_attachment=True)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Ensure the database tables are created
    app.run(debug=True)
