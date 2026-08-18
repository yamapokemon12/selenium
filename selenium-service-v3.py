"""
Terabox Selenium Service V3 - Network Interception
Captura requisições de rede para pegar dados da API
"""

from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import os
import time

app = Flask(__name__)

def setup_driver():
    """Configura Chrome headless para Render"""
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Disable automation flags
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Enable performance logging para capturar network
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    
    driver = webdriver.Chrome(options=options)
    
    # Anti-detection scripts
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        '''
    })
    
    return driver

def extract_files_from_network(driver, timeout=30):
    """Captura dados das requisições de rede"""
    start_time = time.time()
    max_time = timeout  # Timeout máximo
    
    while (time.time() - start_time) < max_time:
        # Pegar logs de performance
        try:
            logs = driver.get_log('performance')
        except:
            time.sleep(0.5)
            continue
        
        for log in logs:
            try:
                log_message = json.loads(log['message'])
                message = log_message.get('message', {})
                
                # Procurar por requisições de rede
                if message.get('method') == 'Network.responseReceived':
                    response = message.get('params', {}).get('response', {})
                    url = response.get('url', '')
                    
                    # Procurar pela API de lista de arquivos
                    if '/share/list' in url or '/api/list' in url:
                        # Pegar o response body
                        request_id = message['params']['requestId']
                        try:
                            response_body = driver.execute_cdp_cmd(
                                'Network.getResponseBody',
                                {'requestId': request_id}
                            )
                            
                            body_text = response_body.get('body', '')
                            if body_text:
                                data = json.loads(body_text)
                                
                                # Verificar se tem lista de arquivos
                                if 'list' in data and isinstance(data['list'], list):
                                    return data['list']
                        except:
                            pass
            except:
                pass
        
        time.sleep(0.5)
    
    return None

def extract_files(share_url):
    """Extrai arquivos usando Selenium com Network Interception + COOKIES"""
    driver = None
    try:
        driver = setup_driver()
        
        # Habilitar network interception
        driver.execute_cdp_cmd('Network.enable', {})
        driver.execute_cdp_cmd('Page.enable', {})
        
        # COOKIES DO TERABOX (da API antiga que funcionava)
        cookies_data = {
            'ndut_fmt': '082E0D57C65BDC31F6FF293F5D23164958B85D6952CCB6ED5D8A3870CB302BE7',
            'ndus': 'Y-wWXKyteHuigAhC03Fr4bbee-QguZ4JC6UAdqap',
            '__bid_n': '196ce76f980a5dfe624207',
            'browserid': 'veWFJBJ9hgVgY0eI9S7yzv66aE28f3als3qUXadSjEuICKF1WWBh4inG3KAWJsAYMkAFpH2FuNUum87q',
            'csrfToken': 'wlv_WNcWCjBtbNQDrHSnut2h',
            'lang': 'en',
            'PANWEB': '1'
        }
        
        # Detectar domínio correto
        if '1024terabox.com' in share_url or '1024tera.com' in share_url:
            domain = '.1024tera.com'
            base_url = 'https://www.1024tera.com'
        elif 'terabox.app' in share_url:
            domain = '.terabox.app'
            base_url = 'https://www.terabox.app'
        else:
            domain = '.terabox.com'
            base_url = 'https://www.terabox.com'
        
        # MÉTODO 1: Navegar primeiro SEM cookies para não crashar
        driver.get(share_url)
        
        # Aguardar carregamento inicial
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # MÉTODO 2: Adicionar cookies DEPOIS que página carregar (via JavaScript)
        # Isso evita crashes de timeout no Render
        for name, value in cookies_data.items():
            try:
                driver.execute_script(
                    f"document.cookie = '{name}={value}; path=/; domain={domain}; secure; samesite=lax';"
                )
            except:
                pass
        
        # MÉTODO 3: Recarregar página com cookies ativos
        driver.refresh()
        
        # Aguardar página carregar
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Aguardar e capturar requisições de rede (REDUZIDO de 15s para 10s)
        time.sleep(3)
        
        # Tentar scroll para forçar carregamento
        try:
            driver.execute_script("window.scrollTo(0, 500);")
            time.sleep(1)
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
        except:
            pass
        
        # Capturar dados da rede (TIMEOUT de 10s)
        files_from_network = extract_files_from_network(driver, timeout=10)
        
        if files_from_network:
            return {
                'files': files_from_network,
                'source': 'network_interception',
                'page_url': driver.current_url,
                'page_title': driver.title
            }
        
        # Fallback: tentar extrair do JavaScript
        all_data = driver.execute_script("""
            const data = {
                __INITIAL_STATE__: window.__INITIAL_STATE__ || null,
                yunData: window.yunData || null,
                locals: window.locals || null,
                pageData: window.pageData || null
            };
            
            // Procurar em todos os objetos window
            const globalKeys = Object.keys(window);
            for (let key of globalKeys) {
                if (key.toLowerCase().includes('data') || key.toLowerCase().includes('file')) {
                    try {
                        const value = window[key];
                        if (value && typeof value === 'object' && value.list) {
                            return value.list;
                        }
                    } catch(e) {}
                }
            }
            
            return null;
        """)
        
        if all_data and isinstance(all_data, list):
            return {
                'files': all_data,
                'source': 'javascript_fallback',
                'page_url': driver.current_url,
                'page_title': driver.title
            }
        
        # Se ainda não encontrou, extrair do DOM
        files_from_dom = driver.execute_script("""
            const items = document.querySelectorAll('[class*="file"], [data-file]');
            const result = [];
            items.forEach(item => {
                const name = item.querySelector('[class*="name"], [class*="filename"]');
                if (name && name.textContent.trim()) {
                    result.push({
                        server_filename: name.textContent.trim(),
                        isFromDOM: true
                    });
                }
            });
            return result.length > 0 ? result : null;
        """)
        
        return {
            'files': files_from_dom,
            'source': 'dom_extraction',
            'page_url': driver.current_url,
            'page_title': driver.title
        }
        
    finally:
        if driver:
            driver.quit()

@app.route('/')
def index():
    return jsonify({
        'service': 'Terabox Selenium Service V3',
        'version': '3.0 - Network Interception',
        'status': 'operational',
        'endpoints': {
            '/': 'API information',
            '/health': 'Health check',
            '/api': 'Extract files from Terabox URL (with network capture)',
            '/debug': 'Debug endpoint - shows raw page data'
        }
    })

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'version': '3.0'})

@app.route('/debug')
def debug():
    """Endpoint para debug com network logs"""
    url = request.args.get('url')
    
    if not url:
        return jsonify({
            'success': False,
            'error': 'Missing URL parameter'
        }), 400
    
    driver = None
    try:
        driver = setup_driver()
        driver.execute_cdp_cmd('Network.enable', {})
        
        driver.get(url)
        
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        time.sleep(10)
        
        # Capturar todas as URLs de requisições
        logs = driver.get_log('performance')
        network_urls = []
        
        for log in logs:
            try:
                log_message = json.loads(log['message'])
                message = log_message.get('message', {})
                
                if message.get('method') in ['Network.requestWillBeSent', 'Network.responseReceived']:
                    params = message.get('params', {})
                    if 'request' in params:
                        network_urls.append(params['request']['url'])
                    elif 'response' in params:
                        network_urls.append(params['response']['url'])
            except:
                pass
        
        # Filtrar URLs relevantes
        relevant_urls = [url for url in network_urls if 'share' in url or 'list' in url or 'api' in url]
        
        return jsonify({
            'success': True,
            'url': url,
            'current_url': driver.current_url,
            'title': driver.title,
            'total_network_requests': len(network_urls),
            'relevant_urls': relevant_urls[:20],  # Primeiras 20
            'html_size': len(driver.page_source)
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500
    finally:
        if driver:
            driver.quit()

@app.route('/api')
def api():
    url = request.args.get('url')
    
    if not url:
        return jsonify({
            'success': False,
            'error': 'Missing URL parameter'
        }), 400
    
    try:
        result = extract_files(url)
        
        if not result or not result.get('files'):
            return jsonify({
                'success': False,
                'error': 'No files found',
                'debug': result
            }), 404
        
        files = result['files']
        
        # Formatar resposta
        results = []
        for file in files:
            if isinstance(file, dict):
                results.append({
                    'file_name': file.get('server_filename') or file.get('filename') or file.get('name') or 'Unknown',
                    'size': file.get('size_format') or file.get('size') or 'Unknown',
                    'size_bytes': int(file.get('size', 0)) if isinstance(file.get('size'), int) else 0,
                    'download_url': file.get('dlink') or file.get('download_url') or file.get('url') or '',
                    'path': file.get('path', ''),
                    'fs_id': str(file.get('fs_id', '')),
                    'thumbs': file.get('thumbs', {}),
                    'category': file.get('category', 0),
                    'isdir': file.get('isdir', 0)
                })
        
        return jsonify({
            'success': True,
            'method': 'selenium_v3',
            'source': result.get('source'),
            'files': results,
            'total': len(results),
            'debug': {
                'page_url': result.get('page_url'),
                'page_title': result.get('page_title')
            }
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
