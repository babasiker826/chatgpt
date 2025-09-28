from flask import Flask, request, jsonify, render_template
import requests
import time
import logging

# Loglama ayarları
logging.basicConfig(level=logging.DEBUG)
app = Flask(__name__)

# Yeni Nabi API endpoint
NABI_API_URL = "https://nabi-api-1.onrender.com/chat"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat_with_nabi():
    try:
        # JSON verisini al
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Geçersiz JSON verisi'}), 400

        user_message = data.get('message', '').strip()

        if not user_message:
            return jsonify({'success': False, 'message': 'Mesaj boş olamaz'}), 400

        print(f"Alınan mesaj: {user_message}")  # Debug

        # Yeni API'ye istek gönder
        params = {'message': user_message}

        print(f"API'ye istek gönderiliyor: {NABI_API_URL}")  # Debug

        # 30 saniye timeout ile istek gönder
        response = requests.get(NABI_API_URL, params=params, timeout=30)

        print(f"API yanıt kodu: {response.status_code}")  # Debug
        print(f"API yanıt içeriği: {response.text}")  # Debug

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
        print("Timeout hatası oluştu")  # Debug
        return jsonify({
            'success': False,
            'message': 'Yanıt zaman aşımına uğradı. API yanıt vermedi.',
            'timestamp': time.time()
        }), 500

    except requests.exceptions.RequestException as e:
        print(f"Request hatası: {e}")  # Debug
        return jsonify({
            'success': False,
            'message': f'API bağlantı hatası: {str(e)}',
            'timestamp': time.time()
        }), 500

    except Exception as e:
        print(f"Beklenmeyen hata: {e}")  # Debug
        return jsonify({
            'success': False,
            'message': f'Beklenmeyen hata: {str(e)}',
            'timestamp': time.time()
        }), 500

@app.route('/test-api')
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
