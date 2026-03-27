from reportlab.pdfgen import canvas

def create_prescription(file_name,data):

    c = canvas.Canvas(file_name)

    c.drawString(100,800,"Prescription")

    y=750

    for line in data:
        c.drawString(100,y,line)
        y-=20

    c.save()