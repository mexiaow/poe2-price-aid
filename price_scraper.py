import requests
from bs4 import BeautifulSoup
import json
import sys

def get_price(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 尝试多种选择器
        price_element = soup.select_one('p.font12.color666.m-t5')
        if not price_element:
            price_element = soup.select_one('.good-list-box div:first-child .p-r66 p.font12')
        
        if price_element:
            price_text = price_element.text.strip()
            import re
            match = re.search(r'(\d+\.\d+)', price_text)
            if match:
                return float(match.group(1))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
    
    return 0.0

if __name__ == "__main__":
    if len(sys.argv) > 1:
        url = sys.argv[1]
        price = get_price(url)
        print(price)
    else:
        # 获取所有价格并输出JSON
        prices = {
            "divine": get_price("https://www.dd373.com/s-3hcpqw-c-8rknmp-bwgvrk-nxspw7.html"),
            "exalted": get_price("https://www.dd373.com/s-3hcpqw-c-tqcbc6-bwgvrk-nxspw7.html"),
            "chaos": get_price("https://www.dd373.com/s-3hcpqw-c-henjrw-bwgvrk-nxspw7.html")
        }
        print(json.dumps(prices)) 