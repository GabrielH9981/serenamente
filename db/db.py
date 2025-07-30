# db.py
import mysql.connector

# def get_db_connection():
#     return mysql.connector.connect(
#         host='localhost',
#         user='root',
#         password='root',
#         database='catalogo_psicologos'
#     )


def get_db_connection():
    return mysql.connector.connect(
        host='sql10.freesqldatabase.com',
        user='sql10792657',
        password='wZBiQYslSB',
        database='sql10792657',
        port=3306
    )