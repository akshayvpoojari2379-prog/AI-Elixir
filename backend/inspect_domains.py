import psycopg2
import json

try:
    conn = psycopg2.connect(
        dbname="ai_service_desk",
        user="postgres",
        password="*sleek#",
        host="localhost",
        port="5432"
    )
    cur = conn.cursor()
    
    cur.execute("SELECT domain_name, description, categories FROM operational_domains;")
    rows = cur.fetchall()
    
    for row in rows:
        domain_name, description, categories = row
        print("="*80)
        print(f"Domain Name: {domain_name}")
        print(f"Description: {description}")
        print(f"Categories:\n{json.dumps(categories, indent=2)}")
        print("="*80)
        
    cur.close()
    conn.close()
except Exception as e:
    print("Error connecting to database:", e)
