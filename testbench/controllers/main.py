from flask import Blueprint, render_template, flash, request, redirect, url_for
from flask_login import login_user, logout_user, login_required
from flask_simpleldap import LDAPException

from farm.extensions import cache
from farm.forms import LoginForm
from farm.models.user import User

main = Blueprint('main', __name__)

@main.route('/')
@login_required
@cache.cached(timeout=1000)
def dashboard():
    return render_template('dashboard.html')

@main.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    error = None

    try:
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data).one()
            login_user(user)

            flash("Logged in successfully.", "success")
            return redirect(request.args.get("next") or url_for(".dashboard"))
    except LDAPException as e:
        print(e)
        error = e.message
        print(error)

    return render_template("login.html", form=form, error=error)

@main.route("/logout")
def logout():
    logout_user()
    flash("You have been logged out.", "success")

    return redirect(url_for(".dashboard"))

@main.route("/restricted")
@login_required
def restricted():
    return "You can only see this if you are logged in!", 200

@main.route("/production")
@login_required
def production():
    return render_template('production.html'), 200

@main.route("/status")
def status():
    return render_template('status.html')
