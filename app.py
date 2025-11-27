from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
import uuid, os, io, csv

# App config
app = Flask(__name__, instance_relative_config=True)
app.secret_key = os.environ.get("FLASK_SECRET", "dev_secret_change_this")

# Ensure instance folder exists (optional, safe)
try:
    os.makedirs(app.instance_path, exist_ok=True)
except Exception:
    pass

# -------------------------------
# 🔥 USE POSTGRESQL ON RENDER
# -------------------------------

db_url = os.environ.get("DATABASE_URL")

# Render sometimes gives postgresql:// but SQLAlchemy requires postgres://
if db_url and db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgres://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Prevent idle connection timeout (important for Render)
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True
}

db = SQLAlchemy(app)

# Run create_all only once
@app.before_first_request
def create_tables():
    db.create_all()

# Models
class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    date = db.Column(db.String(50), nullable=False)
    capacity = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())


class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    buyer_name = db.Column(db.String(200))
    tier = db.Column(db.String(200))
    price = db.Column(db.Integer, default=0)
    redeemable_issued = db.Column(db.Integer, default=0) # Now stores INITIAL redeemable amount
    status = db.Column(db.String(50), default='issued')
    qr_token = db.Column(db.String(100), unique=True, index=True, nullable=False)
    issued_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50))
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'))
    event_id = db.Column(db.Integer)
    amount = db.Column(db.Integer)
    reason = db.Column(db.String(300))
    processed_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    ticket = db.relationship("Ticket", backref="transactions") # ADDED: Relationship to Ticket model

# -------------------------
# CUSTOM FILTERS & FUNCTIONS
# -------------------------
@app.template_filter('rupee')
def format_rupee(value):
    try:
        return f"₹{int(value):,}"
    except:
        return value

# Function to calculate true current balance
def calculate_balance(ticket_id):
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return 0
    # Assuming ticket.redeemable_issued now stores the INITIAL redeemable amount
    initial_redeemable = ticket.redeemable_issued
    total_redeemed_for_ticket = db.session.query(
        func.sum(Transaction.amount)
    ).filter_by(ticket_id=ticket.id, type='redeem').scalar() or 0
    return initial_redeemable - total_redeemed_for_ticket

# Register calculate_balance as a Jinja global function
app.jinja_env.globals.update(calculate_balance=calculate_balance)

# Routes
@app.route('/')
def index():
    events = Event.query.order_by(Event.date).all()

    tickets = Ticket.query.all()

    total_revenue = sum(t.price for t in tickets)

    # Calculate Total Redeemable Issued (sum of initial redeemable amounts)
    total_redeemable_issued_calc = sum(t.redeemable_issued for t in tickets)

    # Sum of current redeemable balances across all tickets (this is what was previously passed as total_redeemable)
    total_redeemable_current_balance = sum(calculate_balance(t.id) for t in tickets)

    # Total redeemed for index page (sum of all redeem transactions)
    total_redeemed = db.session.query(
        func.sum(Transaction.amount)
    ).filter_by(type='redeem').scalar() or 0

    return render_template(
        'index.html',
        events=events,
        total_revenue=total_revenue,
        total_redeemable=total_redeemable_issued_calc, # This will populate "Total Redeemable Issued" in template
        total_redeemed=total_redeemed,
        remaining_balance=total_redeemable_current_balance # This will populate "Remaining Balance" in template
    )

@app.route('/create_event', methods=['GET', 'POST'])
def create_event():
    if request.method == 'POST':
        title = request.form['title']
        date = request.form['date']
        capacity = int(request.form['capacity'])
        new_event = Event(title=title, date=date, capacity=capacity)
        db.session.add(new_event)
        db.session.commit()
        flash('Event created successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('create_event.html')

@app.route('/edit_event/<int:event_id>', methods=['GET', 'POST'])
def edit_event(event_id):
    event = Event.query.get_or_404(event_id)
    if request.method == 'POST':
        event.title = request.form['title']
        event.date = request.form['date']
        event.capacity = int(request.form['capacity'])
        db.session.commit()
        flash('Event updated successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('edit_event.html', event=event)

@app.route('/delete_event/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    event = Event.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    flash('Event deleted successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/event_detail/<int:event_id>')
def event_detail(event_id):
    event = Event.query.get_or_404(event_id)
    tickets = Ticket.query.filter_by(event_id=event.id).all()
    # Fetch redemptions for this specific event
    reclaims = Transaction.query.filter_by(event_id=event.id, type='redeem').order_by(Transaction.processed_at.desc()).all()
    return render_template('event_detail.html', event=event, tickets=tickets, reclaims=reclaims)

@app.route('/sell_ticket/<int:event_id>', methods=['GET','POST'])
def sell_ticket(event_id):
    event = Event.query.get_or_404(event_id)

    if request.method == 'POST':
        buyer = request.form.get('buyer_name') or 'Guest'
        tier = request.form.get('tier') or 'Full Cover'
        price = int(request.form.get('price') or 0)
        redeemable = int(request.form.get('redeemable') or price)

        token = str(uuid.uuid4()).replace('-', '')[:12]

        ticket = Ticket(
            event_id=event.id,
            buyer_name=buyer,
            tier=tier,
            price=price,
            redeemable_issued=redeemable, # Store as INITIAL redeemable amount
            qr_token=token
        )
        db.session.add(ticket)
        db.session.commit()

        tx = Transaction(
            type='sale',
            ticket_id=ticket.id,
            event_id=event.id,
            amount=price,
            reason='sale'
        )
        db.session.add(tx)
        db.session.commit()

        flash(f'Ticket sold! QR token: {token}', 'success')
        return redirect(url_for('event_detail', event_id=event.id))

    return render_template('sell_ticket.html', event=event)

@app.route('/ticket/qr/<qr_token>')
def ticket_view(qr_token):
    ticket = Ticket.query.filter_by(qr_token=qr_token).first()
    if not ticket:
        flash('Ticket not found', 'danger')
        return redirect(url_for('index'))

    logs = Transaction.query.filter_by(
        ticket_id=ticket.id, type='redeem'
    ).order_by(Transaction.processed_at.desc()).all()

    return render_template(
        'ticket_view.html',
        ticket=ticket,
        logs=logs
    )

@app.route('/edit_ticket/<int:ticket_id>', methods=['GET', 'POST'])
def edit_ticket(ticket_id):
    t = Ticket.query.get_or_404(ticket_id)

    if request.method == 'POST':
        t.buyer_name = request.form.get('buyer_name')
        t.tier = request.form.get('tier')
        t.price = int(request.form.get('price') or 0)
        t.redeemable_issued = int(request.form.get('redeemable') or t.redeemable_issued) # This will update INITIAL redeemable balance
        db.session.commit()
        flash('Ticket updated', 'success')
        return redirect(url_for('event_detail', event_id=t.event_id))

    return render_template('edit_ticket.html', ticket=t)

@app.route('/redeem/<string:qr_token>', methods=['POST'])
def redeem(qr_token):
    ticket = Ticket.query.filter_by(qr_token=qr_token).first_or_404()
    current_available_balance = calculate_balance(ticket.id) # Use the new function

    amount = int(request.form.get('amount') or 0)
    reason = request.form.get('reason') or ''

    if amount <= 0:
        flash('Enter a valid amount', 'danger')
        return redirect(url_for('ticket_view', qr_token=ticket.qr_token))

    if current_available_balance <= 0:
        flash('No balance left', 'danger')
        return redirect(url_for('ticket_view', qr_token=ticket.qr_token))

    if amount > current_available_balance:
        excess = amount - current_available_balance
        flash(f'Redeem amount exceeds remaining balance by ₹{excess}', 'danger')
        return redirect(url_for('ticket_view', qr_token=ticket.qr_token))

    # Only create the transaction; ticket.redeemable_issued stores initial amount
    tx = Transaction(
        type='redeem',
        ticket_id=ticket.id,
        event_id=ticket.event_id,
        amount=amount,
        reason=reason
    )
    db.session.add(tx)
    db.session.commit()

    # Update ticket status based on recalculation
    if calculate_balance(ticket.id) == 0:
         ticket.status = 'redeemed'
    elif calculate_balance(ticket.id) < ticket.redeemable_issued:
        ticket.status = 'partially_redeemed'
    else:
        ticket.status = 'issued'
    db.session.commit() # Save status change

    flash(f'Redeemed ₹{amount}. New balance ₹{calculate_balance(ticket.id)}', 'success')
    return redirect(url_for('ticket_view', qr_token=ticket.qr_token))

@app.route('/delete_redemption/<int:tx_id>', methods=['POST'])
def delete_redemption(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    ticket = Ticket.query.get(tx.ticket_id) # Get ticket before deleting tx

    db.session.delete(tx)
    db.session.commit()

    # Re-evaluate ticket status after undoing redemption
    if ticket:
        if calculate_balance(ticket.id) > 0:
            ticket.status = 'issued' # Or 'partially_redeemed' if not fully redeemed
        else:
            ticket.status = 'redeemed' # Should not happen if balance > 0
        db.session.commit()

    flash("Redemption removed", "success")
    if ticket: # Check if ticket still exists
        return redirect(url_for('ticket_view', qr_token=ticket.qr_token))
    return redirect(url_for('index')) # Fallback if ticket somehow gone


@app.route('/export_event_full/<int:event_id>')
def export_event_full(event_id):
    event = Event.query.get_or_404(event_id)
    tickets = Ticket.query.filter_by(event_id=event.id).all()

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Ticket ID', 'Event Title', 'Buyer Name', 'Tier', 'Price', 'Redeemable Balance', 'Status', 'QR Token', 'Issued At'])
    for ticket in tickets:
        cw.writerow([
            ticket.id, event.title, ticket.buyer_name, ticket.tier, ticket.price,
            calculate_balance(ticket.id), ticket.status, ticket.qr_token, ticket.issued_at.strftime('%Y-%m-%d %H:%M:%S') # Use calculated balance
        ])
    output = io.BytesIO(si.getvalue().encode('utf-8'))
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name=f"tickets_{event.title}.csv")

# Search by QR token OR Name
@app.route('/ticket/search/<q>')
def ticket_search_token(q):
    # search by QR token exact
    t = Ticket.query.filter(Ticket.qr_token.ilike(f"%{q}%")).first()
    if t:
        return redirect(url_for('ticket_view', qr_token=t.qr_token))
    return ("NOT_FOUND", 404)


@app.route('/search')
def ticket_search_name():
    name = request.args.get("name", "").strip().lower()
    t = Ticket.query.filter(Ticket.buyer_name.ilike(f"%{name}%")).first()
    if t:
        return redirect(url_for('ticket_view', qr_token=t.qr_token))
    flash("Ticket not found", "danger")
    return redirect(url_for('index'))


@app.route('/export_redemptions/<int:event_id>')
def export_redemptions(event_id):
    import io, csv
    event = Event.query.get_or_404(event_id)
    txs = Transaction.query.filter_by(event_id=event.id, type='redeem').all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Ticket ID", "Buyer", "Amount", "Reason", "Timestamp"])

    for tx in txs:
        t = Ticket.query.get(tx.ticket_id)
        writer.writerow([
            tx.ticket_id,
            t.buyer_name if t else "",
            tx.amount,
            tx.reason or "",
            tx.processed_at
        ])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"redemptions_{event_id}.csv"
    )

# Initialize database
@app.before_request
def create_tables():
    db.create_all()

if __name__ == '__main__':
    # Ensure the instance path is created when running directly
    with app.app_context():
        db.create_all()
    app.run(debug=True)
