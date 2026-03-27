def generate_whatsapp_link(phone,message):

    phone = phone.replace("+","")

    return f"https://wa.me/{phone}?text={message}"