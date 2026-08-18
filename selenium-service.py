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
        
        # Habilitar captura de network logs
        driver.execute_cdp_cmd('Network.enable', {})
        
        driver.get(share_url)
        
        # Aguardar página carregar
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Aguardar MAIS TEMPO para AJAX carregar os dados
        import time
        time.sleep(10)  # 10 segundos para garantir AJAX completo
        
        # Tentar clicar em elementos para forçar carregamento
        try:
            driver.execute_script("window.scrollTo(0, 500);")
            time.sleep(2)
        except:
            pass
        
        # Extrair TUDO incluindo requisições de rede
        all_data = driver.execute_script("""
            // Retornar TODAS as variáveis possíveis
            const data = {
                __INITIAL_STATE__: window.__INITIAL_STATE__ || null,
                __pageData: window.__pageData || null,
                initData: window.initData || null,
                pageData: window.pageData || null,
                yunData: window.yunData || null,
                locals: window.locals || null,
                templateData: window.templateData || null,
                shareData: window.shareData || null
            };
            
            // NOVO: Tentar extrair dados de requisições XHR armazenadas
            if (window.performance && window.performance.getEntries) {
                const resources = window.performance.getEntries();
                data.networkRequests = resources
                    .filter(r => r.initiatorType === 'xmlhttprequest' || r.initiatorType === 'fetch')
                    .map(r => r.name);
            }
            
            // NOVO: Procurar em TODOS os objetos globais
            const globalKeys = Object.keys(window);
            const potentialData = {};
            for (let key of globalKeys) {
                if (key.toLowerCase().includes('file') || 
                    key.toLowerCase().includes('share') || 
                    key.toLowerCase().includes('list') ||
                    key.toLowerCase().includes('data')) {
                    try {
                        const value = window[key];
                        if (value && typeof value === 'object') {
                            potentialData[key] = value;
                        }
                    } catch(e) {}
                }
            }
            data.potentialData = potentialData;
            
            // Tentar pegar do HTML (pode estar em script tags)
            const scripts = document.querySelectorAll('script');
            for (let script of scripts) {
                const text = script.textContent;
                
                // Procurar por padrões comuns de dados
                if (text.includes('"list":[') || text.includes('"server_filename"') || text.includes('"dlink"')) {
                    data.scriptContent = text;
                    break;
                }
            }
            
            return data;
        """)
        
        # Buscar lista de arquivos em múltiplas estruturas
        files = None
        source_found = None
        
        # NOVO: Se encontrou scriptContent, tentar parsear JSON dele
        if 'scriptContent' in all_data and all_data['scriptContent']:
            try:
                import re
                import json
                script = all_data['scriptContent']
                
                # Procurar por padrão {"list":[...]}
                match = re.search(r'\{[^{}]*"list"\s*:\s*\[(.*?)\]\s*[,}]', script, re.DOTALL)
                if match:
                    try:
                        # Tentar extrair o objeto completo
                        json_match = re.search(r'\{[^{}]*"list"\s*:\s*\[.*?\].*?\}', script, re.DOTALL)
                        if json_match:
                            data_obj = json.loads(json_match.group(0))
                            if 'list' in data_obj:
                                files = data_obj['list']
                                source_found = 'scriptContent.parsed'
                    except:
                        pass
            except:
                pass
        
        # Buscar em potentialData se ainda não encontrou
        if not files and 'potentialData' in all_data:
            for key, data in all_data['potentialData'].items():
                if not isinstance(data, dict):
                    continue
                
                for list_key in ['list', 'file_list', 'fileList', 'file', 'files', 'items']:
                    if list_key in data:
                        potential_files = data[list_key]
                        if isinstance(potential_files, list) and len(potential_files) > 0:
                            first_item = potential_files[0]
                            if isinstance(first_item, dict) and ('fs_id' in first_item or 'dlink' in first_item or 'server_filename' in first_item):
                                files = potential_files
                                source_found = f"potentialData.{key}.{list_key}"
                                break
                
                if files:
                    break
        
        # Buscar nas variáveis conhecidas se ainda não encontrou
        if not files:
            for key, data in all_data.items():
                if key in ['scriptContent', 'networkRequests', 'potentialData']:
                    continue
                if not data or not isinstance(data, dict):
                    continue
                
                # Buscar diferentes estruturas de lista
                possible_keys = ['list', 'file_list', 'fileList', 'file', 'files', 'items']
                for list_key in possible_keys:
                    if list_key in data:
                        potential_files = data[list_key]
                        if isinstance(potential_files, list) and len(potential_files) > 0:
                            # Verificar se tem dados reais (não só DOM)
                            first_item = potential_files[0]
                            if isinstance(first_item, dict) and ('fs_id' in first_item or 'dlink' in first_item or 'size' in first_item):
                                files = potential_files
                                source_found = f"{key}.{list_key}"
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
            'source_found': source_found,
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
        'endpoints': {
            '/': 'API information',
            '/health': 'Health check',
            '/api': 'Extract files from Terabox URL',
            '/debug': 'Debug endpoint - shows raw page data'
        },
        'usage': {
            'api': '/api?url=TERABOX_URL',
            'debug': '/debug?url=TERABOX_URL'
        }
    })

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/debug')
def debug():
    """Endpoint para debug - retorna dados JavaScript brutos"""
    url = request.args.get('url')
    
    if not url:
        return jsonify({
            'success': False,
            'error': 'Missing URL parameter'
        }), 400
    
    driver = None
    try:
        driver = setup_driver()
        
        # Habilitar network logs
        driver.execute_cdp_cmd('Network.enable', {})
        
        driver.get(url)
        
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        import time
        time.sleep(10)  # Aguardar AJAX
        
        # Scroll para forçar carregamento
        try:
            driver.execute_script("window.scrollTo(0, 500);")
            time.sleep(2)
        except:
            pass
        
        # Extrair TUDO em formato JSON
        all_data = driver.execute_script("""
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
        
        # Pegar HTML completo
        html_content = driver.page_source
        
        # Procurar por dados JSON no HTML
        import re
        json_patterns = [
            r'"list"\s*:\s*\[(.*?)\]',
            r'"server_filename"\s*:\s*"([^"]+)"',
            r'"dlink"\s*:\s*"([^"]+)"',
            r'"fs_id"\s*:\s*(\d+)',
        ]
        
        found_patterns = {}
        for pattern in json_patterns:
            matches = re.findall(pattern, html_content)
            if matches:
                found_patterns[pattern] = len(matches)
        
        return jsonify({
            'success': True,
            'url': url,
            'current_url': driver.current_url,
            'title': driver.title,
            'data': all_data,
            'html_size': len(html_content),
            'patterns_found': found_patterns,
            'html_snippet': html_content[:2000]  # Primeiros 2000 chars do HTML
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
                'raw_keys': list(result.get('raw_data', {}).keys()),
                'source_found': result.get('source_found')
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
