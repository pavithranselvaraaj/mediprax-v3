from flask import Blueprint,request
from ..models.pharmacy_model import add_bill

pharmacy_routes = Blueprint(
"pharmacy",__name__,url_prefix="/pharmacy")

@pharmacy_routes.route("/",methods=["POST"])
def bill():

    add_bill(request.json)

    return {"status":"bill added"}