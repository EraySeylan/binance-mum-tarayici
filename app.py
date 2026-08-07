import os
import requests
import smtplib
import ssl
from flask import Flask
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

MAIL_ADRESI = "cebrailseylan27@gmail.com"
UYGULAMA_SIFRESI = "mcpiytlnzvexesba"

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_candles_and_count():
    try:
        url = "https://api.binance.com/api/v3/ticker/24hr"
        res = requests.get(url, headers=HEADERS, timeout=8)
        if res.status_code != 200:
            return []

        data = res.json()
        usdt_pairs = [d for d in data if d.get('symbol', '').endswith('USDT') and not d['symbol'].endswith('UPUSDT') and not d['symbol'].endswith('DOWNUSDT')]
        
        top_gainers = sorted(usdt_pairs, key=lambda x: float(x.get('priceChangePercent', 0)), reverse=True)[:5]
        top_losers = sorted(usdt_pairs, key=lambda x: float(x.get('priceChangePercent', 0)))[:5]
        candidates = top_gainers + top_losers
        
        results = []
        for item in candidates:
            sym = item['symbol']
            klines_url = f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=4h&limit=15"
            k_res = requests.get(klines_url, headers=HEADERS, timeout=4)
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
        results = fetch_candles_and_count()
        if not results:
            return "OK", 200

        artanlar = sorted([r for r in results if r['streak'] > 0], key=lambda x: x['streak'], reverse=True)[:3]
        dusenler = sorted([r for r in results if r['streak'] < 0], key=lambda x: x['streak'])[:3]

        # Sade Düz Metin Şablonu
        text_content = "=== 4H ARTAN PARITELER ===\n"
        for c in artanlar:
            price_str = f"${c['price']:.6f}" if c['price'] < 1 else f"${c['price']:.2f}"
            text_content += f"{c['symbol']} | Fiyat: {price_str} | Seri: +{c['streak']} Yesil\n"

        text_content += "\n=== 4H AZALAN PARITELER ===\n"
        for c in dusenler:
            price_str = f"${c['price']:.6f}" if c['price'] < 1 else f"${c['price']:.2f}"
            text_content += f"{c['symbol']} | Fiyat: {price_str} | Seri: {abs(c['streak'])} Kirmizi\n"

        msg = MIMEText(text_content, "plain", "utf-8")
        msg["Subject"] = "4H Mum Sayici Raporu"
        msg["From"] = MAIL_ADRESI
        msg["To"] = MAIL_ADRESI

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(MAIL_ADRESI, UYGULAMA_SIFRESI)
            server.sendmail(MAIL_ADRESI, MAIL_ADRESI, msg.as_string())

        return "OK", 200
    except Exception as e:
        return "OK", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
