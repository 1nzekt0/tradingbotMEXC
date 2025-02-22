
---

**2. bot.py**

Este es el archivo principal que contiene todo el código del bot. Se ha modificado ligeramente para importar las credenciales desde un archivo de configuración externo.

```python
import requests
import time
import hmac
import hashlib
import urllib.parse
import pandas as pd
from config import API_KEY, API_SECRET  # Importa las credenciales desde config.py

# Configuración de la API de MEXC
api_key = API_KEY
api_secret = API_SECRET

# Función para generar la firma (signature)
def generate_signature(secret, query_string):
    return hmac.new(secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

# Lista de criptomonedas de bajo costo
def get_top_gainers():
    try:
        url = 'https://api.mexc.com/api/v3/ticker/24hr'
        response = requests.get(url).json()
        sorted_tickers = sorted(response, key=lambda x: float(x['priceChangePercent']), reverse=True)
        top_gainers = [ticker['symbol'] for ticker in sorted_tickers if ticker['symbol'].endswith('USDT')][:10]
        return top_gainers
    except Exception as e:
        print(f"Error al obtener los top gainers: {e}")
        return ['DOGEUSDT']

# Función para obtener el saldo disponible en USDT
def get_available_balance():
    try:
        # Parámetros de la solicitud
        timestamp = int(time.time() * 1000)  # Timestamp en milisegundos
        params = {
            'timestamp': timestamp,
        }
        
        # Generar la firma
        query_string = urllib.parse.urlencode(params)
        signature = generate_signature(api_secret, query_string)
        params['signature'] = signature
        
        # Realizar la solicitud
        url = 'https://api.mexc.com/api/v3/account'
        headers = {'X-MEXC-APIKEY': api_key}
        response = requests.get(url, headers=headers, params=params).json()
        
        # Verifica si la respuesta contiene 'balances'
        if 'balances' in response:
            for asset in response['balances']:
                if asset['asset'] == 'USDT':
                    return float(asset['free'])
        return 0
    except Exception as e:
        print(f"Error al obtener el saldo: {e}")
        return 0

# Función para obtener datos históricos
def get_historical_data(symbol, interval='1m', lookback=50):
    try:
        url = f'https://api.mexc.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={lookback}'
        response = requests.get(url).json()
        if not response:
            print(f"No se obtuvieron datos históricos para {symbol}.")
            return None
        
        # Ajusta las columnas según la estructura real de los datos
        data = pd.DataFrame(response, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume'
        ])
        
        data['close'] = data['close'].astype(float)
        data['high'] = data['high'].astype(float)
        data['low'] = data['low'].astype(float)
        data['volume'] = data['volume'].astype(float)
        return data
    except Exception as e:
        print(f"Error al obtener datos históricos para {symbol}: {e}")
        return None

# RSI Manual
def calculate_rsi_manual(data, period=14):
    delta = data['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=period, min_periods=1).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period, min_periods=1).mean()
    rs = gain / (loss + 1e-10)
    data['rsi'] = 100 - (100 / (1 + rs))
    return data

# MACD
def calculate_macd(data, fast=12, slow=26, signal=9):
    data['ema_fast'] = data['close'].ewm(span=fast, adjust=False).mean()
    data['ema_slow'] = data['close'].ewm(span=slow, adjust=False).mean()
    data['macd'] = data['ema_fast'] - data['ema_slow']
    data['macd_signal'] = data['macd'].ewm(span=signal, adjust=False).mean()
    return data

# Bandas de Bollinger
def calculate_bollinger_bands(data, length=20, std_dev=2):
    data['middle_band'] = data['close'].rolling(window=length).mean()
    data['std_dev'] = data['close'].rolling(window=length).std()
    data['upper_band'] = data['middle_band'] + (data['std_dev'] * std_dev)
    data['lower_band'] = data['middle_band'] - (data['std_dev'] * std_dev)
    return data

# ATR (Para Stop-Loss Dinámico)
def calculate_atr(data, period=14):
    data['high-low'] = data['high'] - data['low']
    data['high-close'] = abs(data['high'] - data['close'].shift())
    data['low-close'] = abs(data['low'] - data['close'].shift())
    data['true_range'] = data[['high-low', 'high-close', 'low-close']].max(axis=1)
    data['atr'] = data['true_range'].rolling(window=period).mean()
    return data

# Función para calcular indicadores
def calculate_indicators(data):
    if data is None or len(data) < 26:
        return None
    data = calculate_rsi_manual(data)
    data = calculate_macd(data)
    data = calculate_bollinger_bands(data)
    data = calculate_atr(data)
    return data

# Función para realizar una orden de compra
def place_buy_order(symbol, quantity):
    try:
        timestamp = int(time.time() * 1000)
        params = {
            'symbol': symbol,
            'side': 'BUY',
            'type': 'MARKET',
            'quantity': quantity,
            'timestamp': timestamp
        }
        query_string = urllib.parse.urlencode(params)
        signature = generate_signature(api_secret, query_string)
        params['signature'] = signature
        url = 'https://api.mexc.com/api/v3/order'
        headers = {'X-MEXC-APIKEY': api_key}
        response = requests.post(url, headers=headers, params=params).json()
        return response
    except Exception as e:
        print(f"Error al realizar la orden de compra: {e}")
        return None

# Función para realizar una orden de venta
def place_sell_order(symbol, quantity):
    try:
        timestamp = int(time.time() * 1000)
        params = {
            'symbol': symbol,
            'side': 'SELL',
            'type': 'MARKET',
            'quantity': quantity,
            'timestamp': timestamp
        }
        query_string = urllib.parse.urlencode(params)
        signature = generate_signature(api_secret, query_string)
        params['signature'] = signature
        url = 'https://api.mexc.com/api/v3/order'
        headers = {'X-MEXC-APIKEY': api_key}
        response = requests.post(url, headers=headers, params=params).json()
        return response
    except Exception as e:
        print(f"Error al realizar la orden de venta: {e}")
        return None

# Función de trading
def trading_bot():
    print("Iniciando el bot de trading...")
    open_order = None  # Solo una orden abierta a la vez

    while True:
        try:
            # Obtener el saldo disponible
            available_balance = get_available_balance()
            print(f'Saldo disponible en USDT: {available_balance}')
            
            # Verificar si hay suficiente saldo
            if available_balance < 10:  # Por ejemplo, mínimo 10 USDT para operar
                print("Saldo insuficiente. Esperando...")
                time.sleep(60)  # Esperar 1 minuto antes de revisar nuevamente
                continue

            # Si no hay una orden abierta, buscar un nuevo par para comprar
            if open_order is None:
                # Obtener los top gainers
                symbols = get_top_gainers()
                print(f'Pares actuales: {symbols}')

                # Lógica de trading
                for symbol in symbols:
                    print(f'Procesando {symbol}...')
                    data = get_historical_data(symbol)
                    if data is None:
                        continue
                    data = calculate_indicators(data)
                    if data is not None:
                        current_price = data['close'].iloc[-1]
                        rsi = data['rsi'].iloc[-1]
                        macd = data['macd'].iloc[-1]
                        macd_signal = data['macd_signal'].iloc[-1]
                        upper_band = data['upper_band'].iloc[-1]
                        lower_band = data['lower_band'].iloc[-1]
                        atr = data['atr'].iloc[-1]
                        print(f'Precio actual: {current_price}, RSI: {rsi}, MACD: {macd}, MACD Señal: {macd_signal}, Banda Superior: {upper_band}, Banda Inferior: {lower_band}, ATR: {atr}')
                    
                    # Condiciones de compra
                    buy_condition = (
                        (rsi < 30 and macd > macd_signal and current_price < lower_band * 1.01)  # Compra en sobreventa extrema
                    )
                    
                    if buy_condition:
                        # Calcular la cantidad a comprar (100% del saldo disponible)
                        quantity = available_balance / current_price
                        # Realizar la orden de compra
                        buy_response = place_buy_order(symbol, quantity)
                        if buy_response and 'orderId' in buy_response:
                            open_order = {
                                'symbol': symbol,
                                'buy_price': current_price,
                                'quantity': quantity,
                                'peak_price': current_price  # Precio máximo alcanzado
                            }
                            print(f"Compra realizada: {symbol} a {current_price}")
                            break  # Salir del bucle después de comprar
                
            # Si hay una orden abierta, monitorear para vender
            if open_order is not None:
                symbol = open_order['symbol']
                data = get_historical_data(symbol)
                if data is not None:
                    current_price = data['close'].iloc[-1]
                    # Actualizar el precio máximo alcanzado
                    if current_price > open_order['peak_price']:
                        open_order['peak_price'] = current_price
                    
                    # Vender si el precio baja un 0.25% desde el pico
                    if current_price <= open_order['peak_price'] * 0.9975:  # 0.25% de retroceso
                        # Realizar la orden de venta
                        sell_response = place_sell_order(symbol, open_order['quantity'])
                        if sell_response and 'orderId' in sell_response:
                            profit = ((current_price - open_order['buy_price']) / open_order['buy_price']) * 100
                            print(f"Venta realizada: {symbol} a {current_price} (ganancia neta: {profit:.2f}%)")
                            open_order = None  # Resetear la orden abierta
            
            time.sleep(10)  # Esperar 10 segundos antes de la siguiente iteración
        except Exception as e:
            print(f"Error en el bucle principal: {e}")
            time.sleep(10)

# Ejecutar el bot
if __name__ == "__main__":
    trading_bot()
