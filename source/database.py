import logging
import sqlite3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Database:

    def __init__(self, db_file):
        """ create a database connection to a SQLite database """
        try:
            conn = sqlite3.connect(db_file)
        except sqlite3.Error as e:
            logger.critical(e)
            conn = None
        self.conn = conn

    def create_alert_table(self):
        sql = """ create table if not exists Alerts (
            alert_id integer primary key,
            user_id integer not null,
            level real not null,
            expiry text not null,
            strike integer not null
            );"""
        try:
            c = self.conn.cursor()
            c.execute(sql)
        except sqlite3.Error as e:
            logger.warning(e)

    def insert_alert(self, alert_id, user_id, level, expiry, strike):
        sql = """ insert into Alerts
             (alert_id, user_id, level, expiry, strike)
             values (?,?,?,?,?);"""
        try:
            c = self.conn.cursor()
            c.execute(sql, (alert_id, user_id, level, expiry, strike))
        except sqlite3.Error as e:
            logger.warning(e)

    def select_alerts(self):
        sql = """select * from Alerts;"""
        try:
            c = self.conn.cursor()
            c.execute(sql)
            result = c.fetchall()
        except sqlite3.Error as e:
            logger.warning(e)
            result = None
        return result

    def select_my_alerts(self, user_id):
        sql = """select alert_id, level, expiry, strike
        from Alerts where user_id=?;"""
        try:
            c = self.conn.cursor()
            c.execute(sql, (user_id,))
            result = c.fetchall()
        except sqlite3.Error as e:
            logger.warning(e)
            result = None
        return result

    def delete_alert(self, primary_key):
        sql = """delete from Alerts where alert_id=?;"""
        try:
            c = self.conn.cursor()
            c.execute(sql, (primary_key,))
        except sqlite3.Error as e:
            logger.warning(e)

    def delete_my_alert(self, primary_key, user_id):
        sql = """delete from Alerts where alert_id=? and user_id=?;"""
        try:
            c = self.conn.cursor()
            c.execute(sql, (primary_key, user_id))
        except sqlite3.Error as e:
            logger.warning(e)

    def commit(self):
        try:
            self.conn.commit()
        except sqlite3.Error as e:
            logger.warning(e)

    def close(self):
        try:
            self.conn.close()
        except sqlite3.Error as e:
            logger.warning(e)
