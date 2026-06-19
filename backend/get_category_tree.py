import requests
import base64
import json

DOMAIN = "asianpaints.freshservice.com"
API_KEY = "aX92LyLXHEjWREfmv1Q"

def get_headers():
    auth_str = f"{API_KEY}:X"
    b64_auth = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
    return {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/json"
    }

def main():
    print("Fetching tickets to construct category tree (20 pages)...")
    url = f"https://{DOMAIN}/api/v2/tickets"
    tree = {}
    
    for page in range(1, 21):
        response = requests.get(f"{url}?per_page=100&page={page}", headers=get_headers())
        if response.status_code == 200:
            tickets = response.json().get("tickets", [])
            if not tickets:
                break
            for t in tickets:
                cat = t.get("category")
                sub_cat = t.get("sub_category")
                item = t.get("item_category")
                
                if cat == "Hardware Issues" or (cat and "hardware" in cat.lower()):
                    if cat not in tree:
                        tree[cat] = {}
                    if sub_cat:
                        if sub_cat not in tree[cat]:
                            tree[cat][sub_cat] = set()
                        if item:
                            tree[cat][sub_cat].add(item)
            print(f"Page {page} fetched.")
        else:
            print(f"Error on page {page}: {response.status_code}")
            break
            
    print("\nConstructed Hardware Issues Category Tree:")
    for cat, subcats in tree.items():
        print(f"Category: {cat}")
        for subcat, items in subcats.items():
            print(f"  Subcategory: {subcat}")
            for item in sorted(list(items)):
                print(f"    Item/Issue: {item}")

if __name__ == "__main__":
    main()
