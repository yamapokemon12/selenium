"""
Terabox Selenium Service - API HTTP
Deploy no Render.com (grátis)
"""

from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import os

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

def extract_files(share_url):
    """Extrai arquivos usando Selenium"""
    driver = None
    try:
        driver = setup_driver()
        driver.get(share_url)
        
        # Aguardar página carregar (aumentado timeout)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Aguardar conteúdo JavaScript carregar
        import time
        time.sleep(5)  # Aumentado para garantir que JS carregou
        
        # Extrair TUDO que encontrar nas variáveis JavaScript
        all_data = driver.execute_script("""
            // Retornar TODAS as variáveis possíveis para debug
            return {
                __INITIAL_STATE__: window.__INITIAL_STATE__ || null,
                __pageData: window.__pageData || null,
                initData: window.initData || null,
                pageData: window.pageData || null,
                yunData: window.yunData || null,
                locals: window.locals || null,
                templateData: window.templateData || null,
                shareData: window.shareData || null
            };
        """)
        
        # Buscar lista de arquivos em múltiplas estruturas
        files = None
        for key, data in all_data.items():
            if not data:
                continue
            
            # Buscar diferentes estruturas de lista
            for list_key in ['list', 'file_list', 'fileList', 'file', 'files']:
                if list_key in data and isinstance(data[list_key], list) and len(data[list_key]) > 0:
                    files = data[list_key]
                    break
            
            if files:
                break
        
        # Se não encontrou, tentar extrair do HTML
        if not files:
            files = driver.execute_script("""
                const items = document.querySelectorAll('.file-item, [class*="file"], .list-item');
                const result = [];
                items.forEach(item => {
                    const name = item.querySelector('[class*="name"], .filename, [class*="filename"]');
                    const size = item.querySelector('[class*="size"], .filesize');
                    if (name && name.textContent.trim()) {
                        result.push({
                            server_filename: name.textContent.trim(),
                            size: size ? size.textContent.trim() : 'Unknown',
                            isFromDOM: true
                        });
                    }
                });
                return result.length > 0 ? result : null;
            """)
        
        # Retornar arquivos E dados brutos para debug
        return {
            'files': files,
            'raw_data': all_data,
            'page_url': driver.current_url,
            'page_title': driver.title
        }
        
    finally:
        if driver:
            driver.quit()

@app.route('/')
def index():
    return jsonify({
        'service': 'Terabox Selenium Service',
        'status': 'operational',
        'endpoint': '/api?url=TERABOX_URL'
    })

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

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
                'debug': result  # Retornar dados para debug
            }), 404
        
        files = result['files']
        
        # Formatar resposta
        results = []
        for file in files:
            if isinstance(file, dict):
                # Pegar dados completos se disponível
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
            'method': 'selenium',
            'files': results,
            'total': len(results),
            'debug': {
                'page_url': result.get('page_url'),
                'page_title': result.get('page_title'),
                'raw_keys': list(result.get('raw_data', {}).keys())
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
