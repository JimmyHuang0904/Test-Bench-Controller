from . import db
import json

class Reservation(db.Model):
    uuid = db.Column(db.String(), primary_key=True)
    reservation_info = db.Column(db.String())

    def __reservation_info(self):
        return json.loads(self.reservation_info)

    def creation_date(self):
        return self.__reservation_info().get("creation_date")

    def end_date(self):
        return self.__reservation_info().get("end_date", "")

    def state(self):
        return self.__reservation_info().get("state")

    def user(self):
        return self.__reservation_info().get('info', {}).get('user', {}).get('name')

