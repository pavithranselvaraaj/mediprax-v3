from flask import Blueprint, request, jsonify, session, redirect, url_for
from ..services.ai_service import suggest_complaint, suggest_medicine

ai_routes = Blueprint('ai', __name__, url_prefix='/ai')

@ai_routes.route('/complaint')
def complaint():
    if 'user_id' not in session:
        return jsonify([])
    return jsonify(suggest_complaint(request.args.get('q', '')))

@ai_routes.route('/medicine')
def medicine():
    if 'user_id' not in session:
        return jsonify([])
    return jsonify(suggest_medicine(request.args.get('q', '')))
