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
        host='sql113.infinityfree.com',
        user='if0_39591777',
        password='bK9WeRBZcl4j',
        database='if0_39591777_XXX'
    )