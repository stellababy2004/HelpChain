import qrcode


def generate_qr_code(data, file_path):
    qr = qrcode.make(data)
    qr.save(file_path)
    return file_path


def generate_public_url_qr(public_url):
    qr_path = "helpchain_qr.png"
    return generate_qr_code(public_url, qr_path)
