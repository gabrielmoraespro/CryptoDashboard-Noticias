from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime
import json
import time
import threading
from functools import lru_cache
import logging
import xml.etree.ElementTree as ET

app = Flask(__name__)
CORS(app)

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache global para dados
cache = {
    'tickers': {},
    'news': [],
    'fear_greed': {},
    'global_metrics': {},
    'trending': [],
    'exchanges': [],
    'defi_protocols': [],
    'last_update': {}
}

# Configurações
COINGECKO_COINS = ['bitcoin', 'ethereum', 'ripple', 'dogecoin', 'solana', 'cardano', 'polkadot', 'polygon']

class CryptoDataAggregator:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CryptoDashboard/1.0'
        })

    def get_coingecko_data(self):
        """Busca dados do CoinGecko"""
        try:
            url = "https://api.coingecko.com/api/v3/coins/markets"
            params = {
                'vs_currency': 'usd',
                'ids': ','.join(COINGECKO_COINS),
                'order': 'market_cap_desc',
                'per_page': 100,
                'page': 1,
                'sparkline': True,
                'price_change_percentage': '1h,24h,7d,30d'
            }
            response = self.session.get(url, params=params, timeout=10)
            return response.json() if response.status_code == 200 else []
        except Exception as e:
            logger.error(f"Erro ao buscar dados CoinGecko: {e}")
            return []

    def get_global_crypto_stats(self):
        """Estatísticas globais do mercado"""
        try:
            url = "https://api.coingecko.com/api/v3/global"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()['data']
                return {
                    'total_market_cap': data.get('total_market_cap', {}).get('usd', 0),
                    'total_volume_24h': data.get('total_volume', {}).get('usd', 0),
                    'bitcoin_dominance': data.get('market_cap_percentage', {}).get('btc', 0),
                    'ethereum_dominance': data.get('market_cap_percentage', {}).get('eth', 0),
                    'active_cryptocurrencies': data.get('active_cryptocurrencies', 0),
                    'markets': data.get('markets', 0)
                }
        except Exception as e:
            logger.error(f"Erro ao buscar estatísticas globais: {e}")
        return {}

    def get_fear_greed_index(self):
        """Índice de Fear & Greed"""
        try:
            url = "https://api.alternative.me/fng/"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()['data'][0]
                return {
                    'value': int(data['value']),
                    'classification': data['value_classification'],
                    'timestamp': data['timestamp']
                }
        except Exception as e:
            logger.error(f"Erro ao buscar Fear & Greed Index: {e}")
        return {}

    def get_trending_coins(self):
        """Moedas em tendência"""
        try:
            url = "https://api.coingecko.com/api/v3/search/trending"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                trending = response.json()['coins']
                return [{
                    'id': coin['item']['id'],
                    'name': coin['item']['name'],
                    'symbol': coin['item']['symbol'],
                    'market_cap_rank': coin['item']['market_cap_rank'],
                    'thumb': coin['item']['thumb']
                } for coin in trending[:7]]
        except Exception as e:
            logger.error(f"Erro ao buscar trending coins: {e}")
        return []

    def get_exchange_rates(self):
        """Taxas de câmbio"""
        try:
            url = "https://api.exchangerate-api.com/v4/latest/USD"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                rates = response.json()['rates']
                return {
                    'USD_BRL': rates.get('BRL', 5.0),
                    'USD_EUR': rates.get('EUR', 0.85),
                    'USD_GBP': rates.get('GBP', 0.75)
                }
        except Exception as e:
            logger.error(f"Erro ao buscar taxas de câmbio: {e}")
        return {}

    def parse_rss_feed(self, url):
        """Parser RSS personalizado"""
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return []
            
            root = ET.fromstring(response.content)
            items = []
            
            # Try RSS format first
            for item in root.findall('.//item'):
                title_elem = item.find('title')
                link_elem = item.find('link')
                pubdate_elem = item.find('pubDate')
                
                if title_elem is not None and link_elem is not None:
                    items.append({
                        'title': title_elem.text or '',
                        'link': link_elem.text or '',
                        'published': pubdate_elem.text if pubdate_elem is not None else ''
                    })
            
            return items[:10]
            
        except Exception as e:
            logger.error(f"Erro ao fazer parse do RSS {url}: {e}")
            return []

    def get_crypto_news(self):
        """Notícias de criptomoedas"""
        news = []
        
        # Lista de feeds RSS
        rss_feeds = [
            {
                'url': 'https://cointelegraph.com/rss',
                'source': 'CoinTelegraph'
            },
            {
                'url': 'https://decrypt.co/feed',
                'source': 'Decrypt'
            }
        ]
        
        for feed_info in rss_feeds:
            try:
                feed_items = self.parse_rss_feed(feed_info['url'])
                for item in feed_items[:3]:
                    news.append({
                        'title': item['title'],
                        'link': item['link'],
                        'published': item['published'],
                        'source': feed_info['source']
                    })
                    
                if len(news) >= 12:
                    break
                    
            except Exception as e:
                logger.error(f"Erro ao buscar notícias de {feed_info['source']}: {e}")
                continue
        
        # Fallback: CryptoCompare API
        if not news:
            try:
                url = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN&sortOrder=latest"
                response = self.session.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get('Data', [])[:10]:
                        news.append({
                            'title': item.get('title', ''),
                            'link': item.get('url', ''),
                            'published': datetime.fromtimestamp(item.get('published_on', 0)).isoformat(),
                            'source': item.get('source_info', {}).get('name', 'CryptoCompare')
                        })
            except Exception as e:
                logger.error(f"Erro ao buscar notícias CryptoCompare: {e}")
        
        return news[:10]

    def get_defi_protocols(self):
        """Top protocolos DeFi"""
        try:
            url = "https://api.llama.fi/protocols"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                protocols = response.json()
                return [{
                    'name': p['name'],
                    'tvl': p['tvl'],
                    'chain': p.get('chain', 'Multi-Chain'),
                    'category': p.get('category', 'DeFi'),
                    'change_1d': p.get('change_1d', 0),
                    'logo': p.get('logo', '')
                } for p in protocols[:10]]
        except Exception as e:
            logger.error(f"Erro ao buscar protocolos DeFi: {e}")
        return []

# Instância do agregador
aggregator = CryptoDataAggregator()

def update_cache():
    """Atualiza o cache com dados de todas as APIs"""
    try:
        cache['coingecko_data'] = aggregator.get_coingecko_data()
        cache['global_metrics'] = aggregator.get_global_crypto_stats()
        cache['fear_greed'] = aggregator.get_fear_greed_index()
        cache['trending'] = aggregator.get_trending_coins()
        cache['exchange_rates'] = aggregator.get_exchange_rates()
        cache['news'] = aggregator.get_crypto_news()
        cache['defi_protocols'] = aggregator.get_defi_protocols()
        cache['last_update']['timestamp'] = datetime.now().isoformat()
        
        logger.info("Cache atualizado com sucesso")
    except Exception as e:
        logger.error(f"Erro ao atualizar cache: {e}")

def background_updater():
    """Atualiza o cache em background"""
    while True:
        update_cache()
        time.sleep(300)  # Atualiza a cada 5 minutos

# Inicia o atualizador em background
thread = threading.Thread(target=background_updater, daemon=True)
thread.start()

# Atualização inicial
update_cache()

@app.route('/')
def index():
    return '''<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CryptoPro Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #2563eb;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --text-primary: #f8fafc;
            --text-secondary: #cbd5e1;
            --border: #475569;
            --glass: rgba(30, 41, 59, 0.8);
            --glow: 0 0 20px rgba(37, 99, 235, 0.3);
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: var(--text-primary);
            min-height: 100vh;
        }
        .dashboard { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            background: var(--glass);
            backdrop-filter: blur(10px);
            padding: 20px 30px;
            border-radius: 16px;
            border: 1px solid var(--border);
            box-shadow: var(--glow);
        }
        .header h1 {
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #2563eb, #06b6d4);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .status-badge {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 20px;
            background: var(--success);
            border-radius: 50px;
            font-weight: 500;
        }
        .status-indicator {
            width: 8px;
            height: 8px;
            background: white;
            border-radius: 50%;
            animation: blink 1s infinite;
        }
        @keyframes blink {
            0%, 50% { opacity: 1; }
            51%, 100% { opacity: 0.3; }
        }
        .grid { display: grid; gap: 20px; margin-bottom: 30px; }
        .grid-4 { grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
        .grid-2 { grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); }
        .card {
            background: var(--glass);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 25px;
            border: 1px solid var(--border);
            transition: all 0.3s ease;
        }
        .card:hover {
            transform: translateY(-5px);
            box-shadow: var(--glow);
            border-color: var(--primary);
        }
        .card-title {
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 15px;
            color: var(--text-primary);
        }
        .metric-card { text-align: center; }
        .metric-value {
            font-size: 2.5rem;
            font-weight: 700;
            margin: 10px 0;
        }
        .metric-label {
            color: var(--text-secondary);
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .metric-change {
            margin-top: 10px;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: 500;
            font-size: 0.9rem;
        }
        .positive {
            background: rgba(16, 185, 129, 0.2);
            color: var(--success);
        }
        .negative {
            background: rgba(239, 68, 68, 0.2);
            color: var(--danger);
        }
        .crypto-list {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        .crypto-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 15px;
            background: rgba(51, 65, 85, 0.3);
            border-radius: 12px;
            transition: all 0.3s ease;
        }
        .crypto-item:hover {
            border-color: var(--primary);
            background: rgba(37, 99, 235, 0.1);
            transform: translateX(5px);
        }
        .crypto-info {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        .crypto-icon {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: var(--primary);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            color: white;
        }
        .crypto-details h4 {
            font-weight: 600;
            margin-bottom: 5px;
        }
        .crypto-details p {
            color: var(--text-secondary);
            font-size: 0.9rem;
        }
        .crypto-price { text-align: right; }
        .price {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 5px;
        }
        .loading {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 200px;
            color: var(--text-secondary);
        }
        .spinner {
            width: 40px;
            height: 40px;
            border: 3px solid var(--border);
            border-top: 3px solid var(--primary);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 15px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .news-list {
            display: flex;
            flex-direction: column;
            gap: 15px;
            max-height: 400px;
            overflow-y: auto;
        }
        .news-item {
            padding: 15px;
            background: rgba(51, 65, 85, 0.3);
            border-radius: 12px;
            border-left: 3px solid var(--primary);
            transition: all 0.3s ease;
        }
        .news-item:hover {
            background: rgba(37, 99, 235, 0.1);
            transform: translateX(5px);
        }
        .news-title {
            font-weight: 600;
            margin-bottom: 8px;
            line-height: 1.4;
        }
        .news-meta {
            display: flex;
            justify-content: space-between;
            color: var(--text-secondary);
            font-size: 0.8rem;
        }
        .error-message {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid var(--danger);
            color: var(--danger);
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
            text-align: center;
        }
        @media (max-width: 768px) {
            .dashboard { padding: 15px; }
            .header {
                flex-direction: column;
                gap: 15px;
                text-align: center;
            }
            .header h1 { font-size: 2rem; }
            .grid-4, .grid-2 { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="dashboard">
        <div class="header">
            <h1>🚀 CryptoPro Dashboard</h1>
            <div class="status-badge" id="status-badge">
                <div class="status-indicator"></div>
                <span id="status-text">Conectando...</span>
            </div>
        </div>

        <!-- Métricas Globais -->
        <div class="grid grid-4">
            <div class="card metric-card">
                <div class="metric-label">Market Cap Total</div>
                <div class="metric-value" id="total-market-cap">Carregando...</div>
            </div>
            <div class="card metric-card">
                <div class="metric-label">Volume 24h</div>
                <div class="metric-value" id="total-volume">Carregando...</div>
            </div>
            <div class="card metric-card">
                <div class="metric-label">Bitcoin Dominance</div>
                <div class="metric-value" id="btc-dominance">--%</div>
            </div>
            <div class="card metric-card">
                <div class="metric-label">Active Cryptos</div>
                <div class="metric-value" id="active-cryptos">--</div>
            </div>
        </div>

        <!-- Principais Cryptos e Notícias -->
        <div class="grid grid-2">
            <div class="card">
                <h3 class="card-title">💎 Top Criptomoedas</h3>
                <div class="crypto-list" id="crypto-list">
                    <div class="loading">
                        <div class="spinner"></div>
                        Carregando dados...
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h3 class="card-title">📰 Últimas Notícias</h3>
                <div class="news-list" id="news-list">
                    <div class="loading">
                        <div class="spinner"></div>
                        Carregando notícias...
                    </div>
                </div>
            </div>
        </div>

        <!-- Exchange Rates -->
        <div class="grid grid-4">
            <div class="card metric-card">
                <div class="metric-label">USD/BRL</div>
                <div class="metric-value" id="usd-brl">R$ --</div>
            </div>
            <div class="card metric-card">
                <div class="metric-label">USD/EUR</div>
                <div class="metric-value" id="usd-eur">€ --</div>
            </div>
            <div class="card metric-card">
                <div class="metric-label">USD/GBP</div>
                <div class="metric-value" id="usd-gbp">£ --</div>
            </div>
            <div class="card metric-card">
                <div class="metric-label">Última Atualização</div>
                <div class="metric-value" style="font-size: 1rem;" id="last-update">--:--</div>
            </div>
        </div>
    </div>

    <script>
        class CryptoDashboard {
            constructor() {
                this.data = {};
                this.updateInterval = null;
                this.init();
            }

            async init() {
                await this.loadData();
                this.startAutoUpdate();
            }

            updateStatus(status, message) {
                const badge = document.getElementById('status-badge');
                const text = document.getElementById('status-text');
                
                text.textContent = message;
                
                if (status === 'success') {
                    badge.style.background = 'var(--success)';
                } else if (status === 'error') {
                    badge.style.background = 'var(--danger)';
                } else {
                    badge.style.background = 'var(--warning)';
                }
            }

            async loadData() {
                try {
                    this.updateStatus('loading', 'Carregando...');
                    
                    const response = await fetch('/api/dashboard-data');
                    
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}`);
                    }
                    
                    this.data = await response.json();
                    this.updateAllSections();
                    this.updateStatus('success', 'Live Data');
                    
                } catch (error) {
                    console.error('Erro ao carregar dados:', error);
                    this.updateStatus('error', 'Erro de Conexão');
                    this.showError(error.message);
                }
            }

            updateAllSections() {
                this.updateGlobalMetrics();
                this.updateCryptoList();
                this.updateNews();
                this.updateExchangeRates();
                this.updateLastUpdateTime();
            }

            updateGlobalMetrics() {
                const metrics = this.data.global_metrics || {};
                
                document.getElementById('total-market-cap').textContent = 
                    this.formatCurrency(metrics.total_market_cap || 0);
                
                document.getElementById('total-volume').textContent = 
                    this.formatCurrency(metrics.total_volume_24h || 0);
                
                document.getElementById('btc-dominance').textContent = 
                    (metrics.bitcoin_dominance || 0).toFixed(1) + '%';
                
                document.getElementById('active-cryptos').textContent = 
                    (metrics.active_cryptocurrencies || 0).toLocaleString();
            }

            updateCryptoList() {
                const container = document.getElementById('crypto-list');
                const coins = this.data.coingecko_data || [];
                
                if (coins.length === 0) {
                    container.innerHTML = '<div class="error-message">⚠️ Carregando dados crypto...</div>';
                    return;
                }

                container.innerHTML = coins.slice(0, 8).map(coin => `
                    <div class="crypto-item">
                        <div class="crypto-info">
                            <div class="crypto-icon">
                                ${coin.symbol ? coin.symbol.substring(0, 2).toUpperCase() : '??'}
                            </div>
                            <div class="crypto-details">
                                <h4>${coin.name || 'Unknown'}</h4>
                                <p>#${coin.market_cap_rank || 'N/A'} • ${(coin.symbol || '').toUpperCase()}</p>
                            </div>
                        </div>
                        <div class="crypto-price">
                            <div class="price">$${this.formatNumber(coin.current_price || 0)}</div>
                            <div class="metric-change ${(coin.price_change_percentage_24h || 0) >= 0 ? 'positive' : 'negative'}">
                                ${(coin.price_change_percentage_24h || 0) >= 0 ? '+' : ''}${(coin.price_change_percentage_24h || 0).toFixed(2)}%
                            </div>
                        </div>
                    </div>
                `).join('');
            }

            updateNews() {
                const container = document.getElementById('news-list');
                const news = this.data.news || [];
                
                if (news.length === 0) {
                    container.innerHTML = '<div class="error-message">⚠️ Carregando notícias...</div>';
                    return;
                }

                container.innerHTML = news.slice(0, 6).map(item => `
                    <div class="news-item">
                        <div class="news-title">
                            <a href="${item.link}" target="_blank" style="color: inherit; text-decoration: none;">
                                ${item.title}
                            </a>
                        </div>
                        <div class="news-meta">
                            <span>${item.source}</span>
                            <span>${this.formatDate(item.published)}</span>
                        </div>
                    </div>
                `).join('');
            }

            updateExchangeRates() {
                const rates = this.data.exchange_rates || {};
                
                document.getElementById('usd-brl').textContent = 
                    'R$ ' + (rates.USD_BRL || 0).toFixed(2);
                
                document.getElementById('usd-eur').textContent = 
                    '€ ' + (rates.USD_EUR || 0).toFixed(4);
                
                document.getElementById('usd-gbp').textContent = 
                    '£ ' + (rates.USD_GBP || 0).toFixed(4);
            }

            updateLastUpdateTime() {
                const lastUpdate = this.data.last_update?.timestamp;
                if (lastUpdate) {
                    const date = new Date(lastUpdate);
                    document.getElementById('last-update').textContent = 
                        date.toLocaleTimeString('pt-BR');
                } else {
                    document.getElementById('last-update').textContent = '--:--';
                }
            }

            startAutoUpdate() {
                this.updateInterval = setInterval(() => {
                    this.loadData();
                }, 300000); // 5 minutos
            }

            formatCurrency(value) {
                if (value >= 1000000000000) {
                    return '$' + (value / 1000000000000).toFixed(2) + 'T';
                } else if (value >= 1000000000) {
                    return '$' + (value / 1000000000).toFixed(2) + 'B';
                } else if (value >= 1000000) {
                    return '$' + (value / 1000000).toFixed(2) + 'M';
                } else {
                    return '$' + value.toLocaleString();
                }
            }

            formatNumber(value) {
                if (value >= 1000000000) {
                    return (value / 1000000000).toFixed(2) + 'B';
                } else if (value >= 1000000) {
                    return (value / 1000000).toFixed(2) + 'M';
                } else if (value >= 1000) {
                    return (value / 1000).toFixed(2) + 'K';
                } else {
                    return value.toFixed(2);
                }
            }

            formatDate(dateString) {
                if (!dateString) return '';
                try {
                    const date = new Date(dateString);
                    return date.toLocaleDateString('pt-BR');
                } catch {
                    return '';
                }
            }

            showError(message) {
                document.querySelectorAll('.loading').forEach(el => {
                    el.innerHTML = `<div class="error-message">❌ Erro: ${message}</div>`;
                });
            }
        }

        // Inicializar dashboard
        window.addEventListener('DOMContentLoaded', () => {
            new CryptoDashboard();
        });
    </script>
</body>
</html>'''

@app.route('/api/dashboard-data')
def get_dashboard_data():
    """Endpoint principal com todos os dados do dashboard"""
    return jsonify({
        'coingecko_data': cache.get('coingecko_data', []),
        'global_metrics': cache.get('global_metrics', {}),
        'fear_greed': cache.get('fear_greed', {}),
        'trending': cache.get('trending', []),
        'exchange_rates': cache.get('exchange_rates', {}),
        'news': cache.get('news', []),
        'defi_protocols': cache.get('defi_protocols', []),
        'last_update': cache.get('last_update', {})
    })

@app.route('/api/tickers')
def get_tickers():
    """Endpoint para dados específicos de tickers"""
    return jsonify(cache.get('coingecko_data', []))

@app.route('/api/global-stats')
def get_global_stats():
    """Estatísticas globais do mercado"""
    return jsonify(cache.get('global_metrics', {}))

@app.route('/api/fear-greed')
def get_fear_greed():
    """Índice de Fear & Greed"""
    return jsonify(cache.get('fear_greed', {}))

@app.route('/api/trending')
def get_trending():
    """Moedas em tendência"""
    return jsonify(cache.get('trending', []))

@app.route('/api/news')
def get_news():
    """Notícias de crypto"""
    return jsonify(cache.get('news', []))

@app.route('/api/defi')
def get_defi():
    """Protocolos DeFi"""
    return jsonify(cache.get('defi_protocols', []))

@app.route('/api/exchange-rates')
def get_exchange_rates_endpoint():
    """Taxas de câmbio"""
    return jsonify(cache.get('exchange_rates', {}))

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint não encontrado'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Erro interno do servidor'}), 500

if __name__ == '__main__':
    print("🚀 Iniciando CryptoPro Dashboard...")
    print("📊 Dashboard disponível em: http://localhost:5000")
    print("⚡ APIs integradas: CoinGecko, Alternative.me, DeFiLlama, ExchangeRate")
    print("🔄 Auto-refresh: 5 minutos")
    print("❌ Para parar: Ctrl+C")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)