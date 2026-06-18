"""Drop all MySQL tables for clean migration test"""
import json, pymysql

cfg = json.load(open('database/db_config.json', encoding='utf-8'))
mc = cfg['mysql']
conn = pymysql.connect(host=mc['host'], port=mc['port'], user=mc['user'],
    password=mc['password'], database=mc['database'], charset='utf8mb4')
cur = conn.cursor()
cur.execute("SHOW TABLES")
tables = [r[0] for r in cur.fetchall()]
print(f"Tables in MySQL: {len(tables)}")
for t in tables:
    cur.execute(f"DROP TABLE IF EXISTS `{t}`")
    print(f"  DROPPED {t}")
conn.commit()
conn.close()
print("All MySQL tables dropped.")
