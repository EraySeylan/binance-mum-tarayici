import os
import requests
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

MAIL_ADRESI = "cebrailseylan27@gmail.com"
UYGULAMA_SIFRESI = "mcpiytlnzvexesba"

app = Flask(__name__) if 'Flask' in globals() else None
from flask import Flask
app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def analyze_candles():
    try:
        # Binance Futures 24 saatlik verileri alıyoruz
        url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
        res = requests.get(url, headers=HEADERS, timeout=10)
        
        # Eğer fapi engellendiyse Spot alternatifine geç
        if res.status_code != 200:
            url = "https://api.binance.com/api/v3/ticker/24hr"
            res = requests.get(url, headers=HEADERS, timeout=10)
            
        if res.status_code != 200:
            return []

        data = res.json()
        usdt_pairs = [d for d in data if d.get('symbol', '').endswith('USDT') and not d['symbol'].startswith('1000')]
        
        # En çok hareket eden yükselen ve düşenleri seçiyoruz
        top_gainers = sorted(usdt_pairs, key=lambda x: float(x.get('priceChangePercent', 0)), reverse=True)[:10]
        top_losers = sorted(usdt_pairs, key=lambda x: float(x.get('priceChangePercent', 0)))[:10]
        candidates = top_gainers + top_losers
        
        results = []
        is_futures = "fapi" in url

        for item in candidates:
            sym = item['symbol']
            if is_futures:
                k_url = f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}&interval=4h&limit=25"
            else:
                k_url = f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=4h&limit=25"
                
            k_res = requests.get(k_url, headers=HEADERS, timeout=5)
            if k_res.status_code != 200:
                continue
                
            klines = k_res.json()
            if not klines or len(klines) < 2:
                continue

            directions = []
            for k in klines:
                open_p = float(k[1])
                close_p = float(k[4])
                if close_p > open_p:
                    directions.append(1)
                elif close_p < open_p:
                    directions.append(-1)
                else:
                    directions.append(0)

            last_dir = directions[-1]
            if last_dir == 0:
                continue

            streak = 0
            for d in reversed(directions):
                if d == last_dir:
                    streak += 1
                else:
                    break

            last_price = float(klines[-1][4])
            results.append({
                "symbol": sym,
                "price": last_price,
                "streak": streak if last_dir == 1 else -streak
            })

        return results
    except Exception as e:
        print("Hata:", e)
        return []

@app.route('/')
@app.route('/mail-tetikle')
def send_email_report():
    try:
        results = analyze_candles()
        if not results:
            return "Binance baglantisi saglanamadi, tekrar deneniyor...", 500

        artanlar = sorted([r for r in results if r['streak'] > 0], key=lambda x: x['streak'], reverse=True)[:3]
        dusenler = sorted([r for r in results if r['streak'] < 0], key=lambda x: x['streak'])[:3]

        html = """
        <div style="font-family: Arial, sans-serif; background-color: #0d1117; color: #ffffff; padding: 20px; border-radius: 10px; max-width: 500px; margin: auto;">
            <h2 style="color: #58a6ff; text-align: center; border-bottom: 1px solid #30363d; padding-bottom: 10px;">🕯️ 4H Aralıksız Mum Taraması</h2>
            
            <h3 style="color: #238636; margin-top: 20px;">📈 Aralıksız En Çok Yeşil Yanan 3 Parite</h3>
            <table style="width: 100%; text-align: left; border-collapse: collapse; background-color: #161b22; border-radius: 6px;">
                <tr style="border-bottom: 1px solid #30363d; color: #8b949e;">
                    <th style="padding: 10px;">Parite</th>
                    <th style="padding: 10px;">Fiyat</th>
                    <th style="padding: 10px;">Aralıksız Seri</th>
                </tr>
        """
        for c in artanlar:
            price_str = f"${c['price']:.6f}" if c['price'] < 1 else f"${c['price']:.2f}"
            html += f"""
                <tr style="border-bottom: 1px solid #21262d;">
                    <td style="padding: 10px; font-weight: bold; color: #ffffff;">{c['symbol']}</td>
                    <td style="padding: 10px; color: #e3b341;">{price_str}</td>
                    <td style="padding: 10px; color: #3fb950; font-weight: bold;">+{c['streak']} Mum Yeşil</td>
                </tr>
            """

        html += """
            </table>
            
            <h3 style="color: #da3633; margin-top: 25px;">📉 Aralıksız En Çok Kırmızı Yanan 3 Parite</h3>
            <table style="width: 100%; text-align: left; border-collapse: collapse; background-color: #161b22; border-radius: 6px;">
                <tr style="border-bottom: 1px solid #30363d; color: #8b949e;">
                    <th style="padding: 10px;">Parite</th>
                    <th style="padding: 10px;">Fiyat</th>
                    <th style="padding: 10px;">Aralıksız Seri</th>
                </tr>
        """
        for c in dusenler:
            price_str = f"${c['price']:.6f}" if c['price'] < 1 else f"${c['price']:.2f}"
            html += f"""
                <tr style="border-bottom: 1px solid #21262d;">
                    <td style="padding: 10px; font-weight: bold; color: #ffffff;">{c['symbol']}</td>
                    <td style="padding: 10px; color: #e3b341;">{price_str}</td>
                    <td style="padding: 10px; color: #f85149; font-weight: bold;">{abs(c['streak'])} Mum Kırmızı</td>
                </tr>
            """

        html += """
            </table>
            <p style="text-align: center; color: #8b949e; font-size: 12px; margin-top: 20px;">Binance Otomatik Mum Sayıcı</p>
        </div>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "🚨 4H Mum Sayıcı Raporu: Aralıksız Artan/Düşen 3 Parite"
        msg["From"] = MAIL_ADRESI
        msg["To"] = MAIL_ADRESI
        msg.attach(MIMEText(html, "html"))

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(MAIL_ADRESI, UYGULAMA_SIFRESI)
            server.sendmail(MAIL_ADRESI, MAIL_ADRESI, msg.as_string())

        return "Mail basariyla gonderildi!", 200
    except Exception as e:
        return f"Mail gonderilirken hata olustu: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
