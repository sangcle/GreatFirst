from PyQt5.QtWidgets import QApplication, QGraphicsView, QGridLayout
import sys
import finplot as fplt
import pyupbit
from test import BinanceFutureWebsocket

fplt.candle_bull_color = "#FF0000"
fplt.candle_bull_body_color = "#FF0000"
fplt.candle_bear_color = "#0000FF"


class MyWindow(QGraphicsView):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("QGraphicsView")
        layout = QGridLayout()
        self.setLayout(layout)
        self.resize(800, 300)

        fplt.y_pad = 0.07  # pad some extra (for control panel)
        fplt.max_zoom_points = 7
        fplt.autoviewrestore()
        ax, ax_rsi = fplt.create_plot('Complicated Binance Futures Example', rows=2, init_zoom_periods=3000)

        # ax
        # ax = fplt.create_plot(init_zoom_periods=100)

        axo = ax.overlay()
        ax_rsi.hide()
        ax_rsi.vb.setBackgroundColor(None)  # don't use odd background color
        ax.set_visible(xaxis=True)
        ws = BinanceFutureWebsocket()

        self.axs = [ax,ax_rsi] # finplot requres this property

        layout.addWidget(ax.vb.win, 0, 0)

        df = pyupbit.get_ohlcv("KRW-BTC")
        df.rename(columns={'open': "Open", "high": "High", "low": "Low", "close":"Close"}, inplace=True)
        fplt.candlestick_ochl(df[['Open', 'Close', 'High', 'Low']])
        fplt.show(qt_exec=False)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MyWindow()
    win.show()
    app.exec_()