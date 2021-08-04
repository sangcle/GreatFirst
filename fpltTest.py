from PyQt5.QtWidgets import QApplication, QMainWindow, QGridLayout
from PyQt5.QtWidgets import QComboBox, QCheckBox, QWidget
from functools import lru_cache

import sys
import finplot as fplt
from pyqtgraph import QtGui
import pyqtgraph as pg
import requests

# from wsbinance import BinanceFutureWebsocket

import websocket
from threading import Thread
from time import time as now, sleep
import json
import pandas as pd


class BinanceFutureWebsocket:
    def __init__(self):
        self.url = 'wss://fstream.binance.com/stream'
        self.symbol = None
        self.interval = None
        self.ws = None
        self.df = None

    def reconnect(self, symbol, interval, df):
        '''Connect and subscribe, if not already done so.'''
        self.df = df
        if symbol.lower() == self.symbol and self.interval == interval:
            return
        self.symbol = symbol.lower()
        self.interval = interval
        self.thread_connect = Thread(target=self._thread_connect)
        self.thread_connect.daemon = True
        self.thread_connect.start()

    def close(self, reset_symbol=True):
        if reset_symbol:
            self.symbol = None
        if self.ws:
            self.ws.close()
        self.ws = None

    def _thread_connect(self):
        self.close(reset_symbol=False)
        print('websocket connecting to %s...' % self.url)
        self.ws = websocket.WebSocketApp(self.url, on_message=self.on_message, on_error=self.on_error)
        self.thread_io = Thread(target=self.ws.run_forever)
        self.thread_io.daemon = True
        self.thread_io.start()
        for _ in range(100):
            if self.ws.sock and self.ws.sock.connected:
                break
            sleep(0.1)
        else:
            self.close()
            raise websocket.WebSocketTimeoutException('websocket connection failed')
        self.subscribe(self.symbol, self.interval)
        print('websocket connected')

    def subscribe(self, symbol, interval):
        try:
            data = '{"method":"SUBSCRIBE","params":["%s@kline_%s"],"id":1}' % (symbol, interval)
            self.ws.send(data)
        except Exception as e:
            print('websocket subscribe error:', type(e), e)
            raise e

    def on_message(self, ws, msg):
        df = self.df
        if df is None:
            return
        msg = json.loads(msg)
        if 'stream' not in msg:
            return
        stream = msg['stream']
        if '@kline_' in stream:
            k = msg['data']['k']
            t = k['t']
            t0 = int(df.index[-2].timestamp()) * 1000
            t1 = int(df.index[-1].timestamp()) * 1000
            t2 = t1 + (t1-t0)
            if t < t2:
                # update last candle
                i = df.index[-1]
                df.loc[i, 'Close']  = float(k['c'])
                df.loc[i, 'High']   = max(df.loc[i, 'High'], float(k['h']))
                df.loc[i, 'Low']    = min(df.loc[i, 'Low'],  float(k['l']))
                df.loc[i, 'Volume'] = float(k['v'])
            else:
                # create a new candle
                data = [t] + [float(k[i]) for i in ['o','c','h','l','v']]
                candle = pd.DataFrame([data], columns='Time Open Close High Low Volume'.split()).astype({'Time':'datetime64[ms]'})
                candle.set_index('Time', inplace=True)
                self.df = df.append(candle)

    def on_error(self, error, *args, **kwargs):
        print('websocket error: %s' % error)

class MyWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("QGraphicsView")
        layout = QGridLayout()
        self.setLayout(layout)
        self.resize(800, 300)
        self.ws = BinanceFutureWebsocket()

        plots = {}
        fplt.y_pad = 0.07  # pad some extra (for control panel)
        fplt.max_zoom_points = 7
        fplt.autoviewrestore()
        self.ax, self.ax_rsi = fplt.create_plot('Complicated Binance Futures Example', rows=2, init_zoom_periods=3000)
        self.axo = self.ax.overlay()
        layout.addWidget(self.ax.vb.win, 0, 0)

        self.ax_rsi.hide()
        self.ax_rsi.vb.setBackgroundColor(None)  # don't use odd background color
        self.ax.set_visible(xaxis=True)

        self.symbol = "BTCUSDT"
        self.interval = "1m"

        self.change_asset()
        fplt.timer_callback(self.realtime_update_plot, 1)  # update every second
        fplt.show(qt_exec=False)


    def do_load_price_history(self, symbol, interval):
        url = 'https://www.binance.com/fapi/v1/klines?symbol=%s&interval=%s&limit=%s' % (symbol, interval, 1000)
        print('loading binance future %s %s' % (symbol, interval))
        d = requests.get(url).json()
        df = pd.DataFrame(d, columns='Time Open High Low Close Volume a b c d e f'.split())
        df = df.astype(
            {'Time': 'datetime64[ms]', 'Open': float, 'High': float, 'Low': float, 'Close': float, 'Volume': float})
        return df.set_index('Time')

    def load_price_history(self, symbol, interval):
        '''Use memoized, and if too old simply load the data.'''
        df = self.do_load_price_history(symbol, interval)
        # check if cache's newest candle is current
        t0 = df.index[-2].timestamp()
        t1 = df.index[-1].timestamp()
        t2 = t1 + (t1 - t0)
        if now() >= t2:
            df = self.do_load_price_history(symbol, interval)
        return df

    def calc_plot_data(self, df):
        '''Returns data for all plots and for the price line.'''
        price = df['Open Close High Low'.split()]
        volume = df['Open Close Volume'.split()]
        ma50 = ma200 = vema24 = sar = rsi = stoch = stoch_s = None
        ma50 = price.Close.rolling(50).mean()
        ma200 = price.Close.rolling(200).mean()
        vema24 = volume.Volume.ewm(span=24).mean()
        plot_data = dict(price=price, volume=volume, ma50=ma50, ma200=ma200, vema24=vema24, sar=sar, rsi=rsi, stoch=stoch, stoch_s=stoch_s)
        # for price line
        last_close = price.iloc[-1].Close
        last_col = fplt.candle_bull_color if last_close > price.iloc[-2].Close else fplt.candle_bear_color
        price_data = dict(last_close=last_close, last_col=last_col)
        return plot_data, price_data

    def change_asset(self, *args, **kwargs):
        '''Resets and recalculates everything, and plots for the first time.'''
        # save window zoom position before resetting
        fplt._savewindata(fplt.windows[0])

        self.ws.df = None
        df = self.load_price_history(self.symbol, interval=self.interval)
        self.ws.reconnect(self.symbol, self.interval, df)

        # remove any previous plots
        self.ax.reset()
        self.axo.reset()
        self.ax_rsi.reset()

        # calculate plot data
        data, price_data = self.calc_plot_data(df)

        # plot data
        global plots
        plots = {}
        plots['price'] = fplt.candlestick_ochl(data['price'], ax=self.ax)
        plots['volume'] = fplt.volume_ocv(data['volume'], ax=self.axo)
        if data['ma50'] is not None:
            plots['ma50'] = fplt.plot(data['ma50'], legend='MA-50', ax=self.ax)
            plots['ma200'] = fplt.plot(data['ma200'], legend='MA-200', ax=self.ax)
            plots['vema24'] = fplt.plot(data['vema24'], color=4, legend='V-EMA-24', ax=self.axo)
        if data['rsi'] is not None:
            self.ax.set_visible(xaxis=False)
            self.ax_rsi.show()
            fplt.set_y_range(0, 100, ax=self.ax_rsi)
            fplt.add_band(30, 70, color='#6335', ax=self.ax_rsi)
            plots['sar'] = fplt.plot(data['sar'], color='#55a', style='+', width=0.6, legend='SAR', ax=self.ax)
            plots['rsi'] = fplt.plot(data['rsi'], legend='RSI', ax=self.ax_rsi)
            plots['stoch'] = fplt.plot(data['stoch'], color='#880', legend='Stoch', ax=self.ax_rsi)
            plots['stoch_s'] = fplt.plot(data['stoch_s'], color='#650', ax=self.ax_rsi)
        else:
            self.ax.set_visible(xaxis=True)
            self.ax_rsi.hide()

        # price line
        self.ax.price_line = pg.InfiniteLine(angle=0, movable=False,
                                        pen=fplt._makepen(fplt.candle_bull_body_color, style='.'))
        self.ax.price_line.setPos(price_data['last_close'])
        self.ax.price_line.pen.setColor(pg.mkColor(price_data['last_col']))
        self.ax.addItem(self.ax.price_line, ignoreBounds=True)

        # restores saved zoom position, if in range
        fplt.refresh()


    def realtime_update_plot(self):
        '''Called at regular intervals by a timer.'''
        if self.ws.df is None:
            return

        data, price_data = self.calc_plot_data(self.ws.df)

        # first update all data, then graphics (for zoom rigidity)
        for k in data:
            if data[k] is not None:
                plots[k].update_data(data[k], gfx=False)
        for k in data:
            if data[k] is not None:
                plots[k].update_gfx()

        # place and color price line
        self.ax.price_line.setPos(price_data['last_close'])
        self.ax.price_line.pen.setColor(pg.mkColor(price_data['last_col']))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MyWindow()
    win.show()
    app.exec_()