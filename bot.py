from flask import Flask, request, jsonify, render_template
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import requests
import time
import logging
import os
from datetime import datetime, timedelta

# Loglama ayarları
logging.basicConfig(level=logging.DEBUG)
app = Flask(__name__)

# Rate Limiting için secret key
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'ddos-koruma-anahtari-2024')

# Rate Limiter setup
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour", "20 per minute"],
    storage_uri="memory://",
)

# IP bazlı request tracking
request_tracker = {}
BLOCK_DURATION = 3600  # 1 saat block
MAX_REQUESTS_PER_MINUTE = 10
MAX_REQUESTS_PER_HOUR = 100

# Güvenli IP listesi (opsiyonel)
SAFE_IPS = ['127.0.0.1', 'localhost']

# Yeni Nabi API endpoint
NABI_API_URL = "https://nabi-api-1.onrender.com/chat"

def is_ip_blocked(ip):
    """IP'nin blocklanıp blocklanmadığını kontrol et"""
    if ip in request_tracker:
        if request_tracker[ip].get('blocked_until'):
            if datetime.now() < request_tracker[ip]['blocked_until']:
                return True
            else:
                # Block süresi doldu, temizle
                request_tracker[ip]['blocked_until'] = None
                request_tracker[ip]['request_count_minute'] = 0
                request_tracker[ip]['request_count_hour'] = 0
    return False

def track_request(ip):
    """IP için request sayısını takip et"""
    now = datetime.now()
    
    if ip not in request_tracker:
        request_tracker[ip] = {
            'request_count_minute': 0,
            'request_count_hour': 0,
            'first_request_minute': now,
            'first_request_hour': now,
            'blocked_until': None
        }
    
    # Dakikalık limit kontrolü
    if now - request_tracker[ip]['first_request_minute'] > timedelta(minutes=1):
        request_tracker[ip]['request_count_minute'] = 0
        request_tracker[ip]['first_request_minute'] = now
    
    # Saatlik limit kontrolü
    if now - request_tracker[ip]['first_request_hour'] > timedelta(hours=1):
        request_tracker[ip]['request_count_hour'] = 0
        request_tracker[ip]['first_request_hour'] = now
    
    request_tracker[ip]['request_count_minute'] += 1
    request_tracker[ip]['request_count_hour'] += 1
    
    # Limit aşımı kontrolü
    if (request_tracker[ip]['request_count_minute'] > MAX_REQUESTS_PER_MINUTE or 
        request_tracker[ip]['request_count_hour'] > MAX_REQUESTS_PER_HOUR):
        request_tracker[ip]['blocked_until'] = datetime.now() + timedelta(seconds=BLOCK_DURATION)
        return False
    
    return True

@app.before_request
def before_request():
    """Her request öncesi DDoS kontrolü"""
    if request.endpoint in ['chat_with_nabi', 'test_api']:
        client_ip = get_remote_address()
        
        # Güvenli IP'leri kontrol et
        if client_ip in SAFE_IPS:
            return
        
        # IP block kontrolü
        if is_ip_blocked(client_ip):
            app.logger.warning(f"Blocked IP attempted access: {client_ip}")
            return jsonify({
                'success': False,
                'message': 'IP adresiniz geçici olarak bloke edilmiştir. Lütfen daha sonra tekrar deneyin.'
            }), 429
        
        # Request tracking
        if not track_request(client_ip):
            app.logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return jsonify({
                'success': False,
                'message': 'Çok fazla istek gönderdiniz. Lütfen bir süre bekleyin.'
            }), 429

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
@limiter.limit("10 per minute", exempt_when=lambda: get_remote_address() in SAFE_IPS)
def chat_with_nabi():
    try:
        # JSON verisini al
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Geçersiz JSON verisi'}), 400

        user_message = data.get('message', '').strip()

        if not user_message:
            return jsonify({'success': False, 'message': 'Mesaj boş olamaz'}), 400

        # Mesaj uzunluğu kontrolü
        if len(user_message) > 1000:
            return jsonify({'success': False, 'message': 'Mesaj çok uzun'}), 400

        app.logger.info(f"Alınan mesaj: {user_message}")

        # Yeni API'ye istek gönder
        params = {'message': user_message}

        app.logger.info(f"API'ye istek gönderiliyor: {NABI_API_URL}")

        # 30 saniye timeout ile istek gönder
        response = requests.get(NABI_API_URL, params=params, timeout=30)

        app.logger.info(f"API yanıt kodu: {response.status_code}")

        if response.status_code == 200:
            # API yanıtını al
            nabi_response = response.text.strip()

            # Yanıt boş mu kontrol et
            if not nabi_response:
                nabi_response = "Yanıt alınamadı, lütfen tekrar deneyin."

            return jsonify({
                'success': True,
                'message': nabi_response,
                'timestamp': time.time()
            })
        else:
            return jsonify({
                'success': False,
                'message': f'API hatası: {response.status_code} - {response.text}',
                'timestamp': time.time()
            }), 500

    except requests.exceptions.Timeout:
        app.logger.error("Timeout hatası oluştu")
        return jsonify({
            'success': False,
            'message': 'Yanıt zaman aşımına uğradı. API yanıt vermedi.',
            'timestamp': time.time()
        }), 500

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Request hatası: {e}")
        return jsonify({
            'success': False,
            'message': f'API bağlantı hatası: {str(e)}',
            'timestamp': time.time()
        }), 500

    except Exception as e:
        app.logger.error(f"Beklenmeyen hata: {e}")
        return jsonify({
            'success': False,
            'message': f'Beklenmeyen hata: {str(e)}',
            'timestamp': time.time()
        }), 500

@app.route('/test-api')
@limiter.limit("5 per minute", exempt_when=lambda: get_remote_address() in SAFE_IPS)
def test_api():
    """API'yi test etmek için basit bir endpoint"""
    try:
        test_response = requests.get(NABI_API_URL, params={'message': 'merhaba'}, timeout=10)
        return jsonify({
            'status_code': test_response.status_code,
            'response': test_response.text,
            'url': test_response.url
        })
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/status')
def status():
    return jsonify({'status': 'Nabi Yapay Zeka çalışıyor'})

@app.route('/admin/ip-stats')
@limiter.limit("10 per minute", exempt_when=lambda: get_remote_address() in SAFE_IPS)
def ip_stats():
    """IP istatistiklerini görüntüle (admin)"""
    return jsonify(request_tracker)

if __name__ == '__main__':
    # Production modunda debug=False yapın
    app.run(debug=False, host='0.0.0.0', port=5000)
