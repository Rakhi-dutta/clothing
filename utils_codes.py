import os
import qrcode
from barcode import Code128
from barcode.writer import ImageWriter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

def generate_barcode(item_id, text):
    filename = f"barcode_{item_id}"
    full_path = os.path.join(UPLOAD_FOLDER, filename)
    barcode_obj = Code128(text, writer=ImageWriter())
    barcode_obj.save(full_path)
    return filename + ".png"

def generate_qr(item_id, text):
    filename = f"qr_{item_id}.png"
    full_path = os.path.join(UPLOAD_FOLDER, filename)
    img = qrcode.make(text)
    img.save(full_path)
    return filename
