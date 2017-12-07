from . import db

class Reservation(db.Model):
    uuid = db.Column(db.String(), primary_key=True)
    reservation_info = db.Column(db.String())

