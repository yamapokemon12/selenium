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
        time.sleep(3)
        
        # Extrair dados do JavaScript
        files = driver.execute_script("""
            // Tentar múltiplas fontes de dados
            const sources = [
                window.__INITIAL_STATE__,
                window.__pageData,
                window.initData,
                window.pageData,
                window.yunData,
                window.locals
            ];
            
            for (let data of sources) {
                if (!data) continue;
                
                // Buscar em diferentes estruturas
                if (data.list && Array.isArray(data.list)) {
                    return data.list;
                }
                if (data.file_list && Array.isArray(data.file_list)) {
                    return data.file_list;
                }
                if (data.fileList && Array.isArray(data.fileList)) {
                    return data.fileList;
                }
            }
            return null;
        """)
        
        if not files:
            # Tentar extrair do DOM
            files = driver.execute_script("""
                const items = document.querySelectorAll('.file-item, [class*="file"], .list-item');
                const result = [];
                items.forEach(item => {
                    const name = item.querySelector('[class*="name"], .filename, [class*="filename"]');
                    const size = item.querySelector('[class*="size"], .filesize');
                    if (name && name.textContent.trim()) {
                        result.push({
                            server_filename: name.textContent.trim(),
                            size: size ? size.textContent.trim() : 'Unknown'
                        });
                    }
                });
                return result.length > 0 ? result : null;
            """)
        
        return files
        
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
        files = extract_files(url)
        
        if not files:
            return jsonify({
                'success': False,
                'error': 'No files found'
            }), 404
        
        # Formatar resposta
        results = []
        for file in files:
            if isinstance(file, dict):
                results.append({
                    'file_name': file.get('server_filename', 'Unknown'),
                    'size': file.get('size', 'Unknown'),
                    'size_bytes': file.get('size', 0) if isinstance(file.get('size'), int) else 0,
                    'download_url': file.get('dlink', ''),
                    'path': file.get('path', ''),
                    'fs_id': file.get('fs_id', '')
                })
        
        return jsonify({
            'success': True,
            'method': 'selenium',
            'files': results,
            'total': len(results)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
