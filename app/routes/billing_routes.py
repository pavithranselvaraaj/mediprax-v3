from flask import Blueprint, request, render_template, redirect, url_for, session, flash, jsonify
from ..database import get_db
from datetime import date

billing_routes = Blueprint('billing', __name__, url_prefix='/billing')

def _hid(): return session.get('hospital_id', 1)
def _login(): return 'user_id' in session and 'hospital_id' in session
def _can_write(): return session.get('role') in ('admin','doctor')

def _next_bill_no(db, hid):
    count = db.execute('SELECT COUNT(*) FROM bills WHERE hospital_id=?', (hid,)).fetchone()[0]
    return f"BILL-{hid:02d}-{count+1:05d}"

# ── Bill list ────────────────────────────────────────────────

@billing_routes.route('/')
def bill_list():
    if not _login(): return redirect(url_for('auth.login'))
    hid = _hid()
    db  = get_db()
    q   = request.args.get('q','').strip()
    status = request.args.get('status','')
    page = max(1, request.args.get('page', 1, type=int))
    per_page = 15

    where = "WHERE b.hospital_id=?"
    params = [hid]
    if q:
        where += " AND (p.name LIKE ? OR b.bill_no LIKE ? OR p.uhid LIKE ?)"
        params += [f'%{q}%', f'%{q}%', f'%{q}%']
    if status:
        where += " AND b.payment_status=?"
        params.append(status)

    total = db.execute(f"SELECT COUNT(*) FROM bills b JOIN patients p ON b.patient_id=p.id {where}", params).fetchone()[0]
    bills = db.execute(f'''
        SELECT b.*, p.name AS patient_name, p.uhid AS patient_uhid
        FROM bills b JOIN patients p ON b.patient_id=p.id
        {where} ORDER BY b.id DESC LIMIT ? OFFSET ?
    ''', params + [per_page, (page-1)*per_page]).fetchall()
    total_pages = max(1, (total + per_page - 1) // per_page)

    # Summary stats
    stats = {
        'total_today': db.execute("SELECT COALESCE(SUM(total),0) FROM bills WHERE hospital_id=? AND bill_date=?", (hid, date.today().isoformat())).fetchone()[0],
        'pending':     db.execute("SELECT COUNT(*) FROM bills WHERE hospital_id=? AND payment_status='pending'", (hid,)).fetchone()[0],
        'paid_today':  db.execute("SELECT COALESCE(SUM(paid_amount),0) FROM bills WHERE hospital_id=? AND bill_date=? AND payment_status='paid'", (hid, date.today().isoformat())).fetchone()[0],
    }
    return render_template('billing/bill_list.html',
                           bills=[dict(b) for b in bills], stats=stats,
                           search=q, status_filter=status,
                           page=page, total_pages=total_pages, total=total)

# ── Create bill ───────────────────────────────────────────────

@billing_routes.route('/create/<int:pid>', methods=['GET','POST'])
def create_bill(pid):
    if not _login(): return redirect(url_for('auth.login'))
    if not _can_write():
        flash('Read-only access.', 'danger')
        return redirect(url_for('patients.patient_detail', pid=pid))
    hid = _hid()
    db  = get_db()
    patient = db.execute('SELECT * FROM patients WHERE id=? AND hospital_id=?', (pid,hid)).fetchone()
    if not patient:
        flash('Patient not found.', 'danger')
        return redirect(url_for('patients.patients'))

    if request.method == 'POST':
        f = request.form
        bill_no = _next_bill_no(db, hid)

        # Parse items from form
        descriptions = request.form.getlist('description[]')
        categories   = request.form.getlist('category[]')
        quantities   = request.form.getlist('quantity[]')
        unit_prices  = request.form.getlist('unit_price[]')

        items = []
        subtotal = 0
        for i, desc in enumerate(descriptions):
            if not desc.strip(): continue
            qty   = float(quantities[i]) if i < len(quantities) else 1
            price = float(unit_prices[i]) if i < len(unit_prices) else 0
            amt   = qty * price
            subtotal += amt
            items.append({
                'category':   categories[i] if i < len(categories) else 'Other',
                'description': desc.strip(),
                'quantity':   qty,
                'unit_price': price,
                'amount':     amt,
            })

        discount = float(f.get('discount','0') or 0)
        tax      = float(f.get('tax','0') or 0)
        total    = subtotal - discount + tax
        paid     = float(f.get('paid_amount','0') or 0)

        if paid >= total:
            pstatus = 'paid'
        elif paid > 0:
            pstatus = 'partial'
        else:
            pstatus = 'pending'

        cur = db.execute('''INSERT INTO bills
            (hospital_id,patient_id,visit_id,admission_id,bill_no,bill_date,bill_type,
             subtotal,discount,tax,total,paid_amount,payment_mode,payment_status,notes,created_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [
            hid, pid,
            f.get('visit_id', type=int) or None,
            f.get('admission_id', type=int) or None,
            bill_no, date.today().isoformat(),
            f.get('bill_type','OPD'),
            subtotal, discount, tax, total, paid,
            f.get('payment_mode','Cash'), pstatus,
            f.get('notes','').strip(),
            session['user_id']
        ])
        bill_id = cur.lastrowid
        for item in items:
            db.execute('''INSERT INTO bill_items (bill_id,category,description,quantity,unit_price,amount)
                VALUES (?,?,?,?,?,?)''', [bill_id, item['category'], item['description'],
                item['quantity'], item['unit_price'], item['amount']])
        db.commit()
        from silent_backup import backup; backup()
        flash(f'Bill created: {bill_no}', 'success')
        return redirect(url_for('billing.view_bill', bill_id=bill_id))

    # Load last visit for pre-fill
    last_visit = db.execute(
        'SELECT * FROM visits WHERE patient_id=? AND hospital_id=? ORDER BY id DESC LIMIT 1', (pid,hid)
    ).fetchone()
    # Load open admissions
    open_adm = db.execute(
        "SELECT id, admission_no FROM admissions WHERE patient_id=? AND hospital_id=? AND status='admitted'", (pid, hid)
    ).fetchall()
    return render_template('billing/create_bill.html',
                           patient=dict(patient),
                           last_visit=dict(last_visit) if last_visit else None,
                           open_adm=[dict(a) for a in open_adm])

# ── View / Print bill ─────────────────────────────────────────

@billing_routes.route('/<int:bill_id>')
def view_bill(bill_id):
    if not _login(): return redirect(url_for('auth.login'))
    hid = _hid()
    db  = get_db()
    bill = db.execute('''
        SELECT b.*, p.name AS patient_name, p.uhid AS patient_uhid,
               p.phone AS patient_phone, p.address AS patient_address,
               p.age AS patient_age, p.gender AS patient_gender
        FROM bills b JOIN patients p ON b.patient_id=p.id
        WHERE b.id=? AND b.hospital_id=?
    ''', (bill_id, hid)).fetchone()
    if not bill:
        flash('Bill not found.', 'danger')
        return redirect(url_for('billing.bill_list'))
    items = db.execute('SELECT * FROM bill_items WHERE bill_id=?', (bill_id,)).fetchall()
    return render_template('billing/view_bill.html',
                           bill=dict(bill), items=[dict(i) for i in items],
                           today=date.today().strftime('%d %b %Y'))

# ── Update payment ────────────────────────────────────────────

@billing_routes.route('/<int:bill_id>/payment', methods=['POST'])
def update_payment(bill_id):
    if not _login(): return redirect(url_for('auth.login'))
    if not _can_write():
        flash('Read-only access.', 'danger')
        return redirect(url_for('billing.view_bill', bill_id=bill_id))
    hid    = _hid()
    db     = get_db()
    bill   = db.execute('SELECT * FROM bills WHERE id=? AND hospital_id=?', (bill_id,hid)).fetchone()
    paid   = float(request.form.get('paid_amount','0') or 0)
    mode   = request.form.get('payment_mode','Cash')
    if paid >= bill['total']:
        status = 'paid'
    elif paid > 0:
        status = 'partial'
    else:
        status = 'pending'
    db.execute('UPDATE bills SET paid_amount=?,payment_mode=?,payment_status=? WHERE id=? AND hospital_id=?',
               (paid, mode, status, bill_id, hid))
    db.commit()
    from silent_backup import backup; backup()
    flash('Payment updated.', 'success')
    return redirect(url_for('billing.view_bill', bill_id=bill_id))
