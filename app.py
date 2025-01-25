from flask import Flask, render_template, request, redirect, url_for, send_file
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random
import os
import qrcode
from PIL import Image
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads'  # Folder to save payment screenshots
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# Set up Google Sheets API credentials
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name('./credentials_sheets.json', scope)
client = gspread.authorize(creds)

# Open the Google Sheet (Replace 'YourSheetName' with your actual sheet name)
spreadsheet = client.open('Event_passes')
worksheet = spreadsheet.sheet1  # or use .get_worksheet(index) if using a specific sheet

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

        # Save ticket to Google Sheets
        ticket_data = [unique_id, name, email, phone, ", ".join(days), False, '']
        worksheet.append_row(ticket_data)

        return redirect(url_for('payment', unique_id=unique_id, total_amount=total_amount))

    return render_template('buy_ticket.html')

@app.route('/payment/<string:unique_id>/<int:total_amount>', methods=['GET', 'POST'])
def payment(unique_id, total_amount):
    # Find ticket by unique_id in Google Sheets
    cell = worksheet.find(unique_id)
    ticket_data = worksheet.row_values(cell.row)

    if request.method == 'POST':
        # Handle file upload
        file = request.files.get('payment_screenshot')
        if not file:
            return "No file selected. Please upload the payment screenshot."

        if file and allowed_file(file.filename):
            screenshot_filename = f"{unique_id}_payment.{file.filename.rsplit('.', 1)[1].lower()}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], screenshot_filename)
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])
            file.save(file_path)

            # Update Google Sheets with payment screenshot and mark as paid
            worksheet.update_cell(cell.row, 7, file_path)  # Update screenshot path
            worksheet.update_cell(cell.row, 6, True)  # Mark as paid

            return redirect(url_for('download_ticket', unique_id=unique_id))
        else:
            return "Invalid file type. Only images are allowed."

    return render_template('payment.html', ticket_data=ticket_data, total_amount=total_amount)

@app.route('/download_ticket/<string:unique_id>')
def download_ticket(unique_id):
    # Find ticket by unique_id in Google Sheets
    cell = worksheet.find(unique_id)
    ticket_data = worksheet.row_values(cell.row)
    
    if not ticket_data or not ticket_data[5] or not ticket_data[6]:
        return "Unauthorized access! Payment screenshot is required."

    # Generate QR Code
    qr_data = f"Unique ID: {ticket_data[0]}\nDays: {ticket_data[4]}\n"
    qr = qrcode.QRCode()
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_path = f"qr_{unique_id}.png"
    qr_img.save(qr_path)

    # Merge pass and QR
    img1 = Image.open(f"qr_{unique_id}.png")
    img2 = Image.open("./header.png")  # Use your background image here
    w1, h1 = img1.size
    w2, h2 = img2.size
    newHeight = max(h1, h2)
    newWidth = w1 + w2
    newImage = Image.new('RGB', (newWidth, newHeight), (255, 255, 255))
    newImage.paste(img1, (0, (newHeight-h1)//3))
    newImage.paste(img2, (w1, (newHeight-h2)//2))

    # Save the new image temporarily
    image_path = f"pass_{unique_id}.png"
    newImage.save(image_path)

    # Clean up QR Code file
    os.remove(qr_path)

    # Send the generated image as a response for download
    return send_file(image_path, download_name=f'ticket_{unique_id}.png', as_attachment=True)

if __name__=="__main__":
    app.run(host="0.0.0.0")    
