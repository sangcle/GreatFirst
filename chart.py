import sys
import os
from PyQt5 import uic
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter
from PyQt5.QtChart import QLineSeries, QValueAxis, QDateTimeAxis
from PyQt5.QtChart import QCandlestickSeries, QChart, QChartView, QCandlestickSet
from PyQt5.QtCore import Qt, QDateTime
import time
from PyQt5.QtCore import QThread, pyqtSignal
import ccxt
from binance.client import Client

class PriceWorker(QThread):
    dataSent = pyqtSignal(float, float, float, float)

    def __init__(self, ticker):
        super().__init__()
        self.ticker = ticker
        self.alive = True


    def run(self):
        while self.alive:
            # data = ccxt.binance().fetch_ticker(self.ticker)
            servertime = Client().get_server_time()
            print(servertime)
            data = Client().get_klines(symbol=self.ticker, interval='1m', limit=1)[0]
            print(data)
            time.sleep(1)
            if data != None:
                self.dataSent.emit(float(data[1]), float(data[2]), float(data[3]), float(data[4]))

    def close(self):
        self.alive = False

class ChartWidget(QWidget):
    def __init__(self, parent=None, ticker="BTCUSDT"):
        super().__init__(parent)
        uic.loadUi("resource/chart.ui", self)
        self.ticker = ticker
        self.viewLimit = 10

        self.tm = []

        self.priceData = QCandlestickSeries()
        self.priceData.setDecreasingColor(Qt.red)
        self.priceData.setIncreasingColor(Qt.green)
        self.priceChart = QChart()
        self.priceChart.addSeries(self.priceData)
        self.priceChart.legend().hide()

        axisX = QDateTimeAxis()
        axisX.setFormat("hh:mm:ss")
        axisX.setTickCount(4)
        dt = QDateTime.currentDateTime()
        axisX.setRange(dt, dt.addSecs(self.viewLimit))
        axisY = QValueAxis()
        axisY.setVisible(False)

        self.priceChart.addAxis(axisX, Qt.AlignBottom)
        self.priceChart.addAxis(axisY, Qt.AlignRight)
        self.priceData.attachAxis(axisX)
        self.priceData.attachAxis(axisY)
        self.priceChart.layout().setContentsMargins(0, 0, 0, 0)

        self.priceView.setChart(self.priceChart)
        self.priceView.setRenderHints(QPainter.Antialiasing)

        self.pw = PriceWorker(ticker)
        self.pw.dataSent.connect(self.appendData)
        self.pw.start()

    def appendData(self, o, h, l, c):
        if len(self.tm) == self.viewLimit :
            self.priceData.remove(0)
            self.tm.remove(0)
        dt = QDateTime.currentDateTime()
        self.priceData.append(QCandlestickSet(o, h, l, c))
        print(dt.toMSecsSinceEpoch())
        print(type(dt.toMSecsSinceEpoch()))
        self.tm.append(dt.toMSecsSinceEpoch())
        self.__updateAxis()

    def __updateAxis(self):
        pvs = self.tm
        dtStart = QDateTime.fromMSecsSinceEpoch(int(pvs[0]))
        if len(self.priceData) == self.viewLimit :
            dtLast = QDateTime.fromMSecsSinceEpoch(int(pvs[-1]))
        else:
            dtLast = dtStart.addSecs(self.viewLimit)
        ax = self.priceChart.axisX()
        ax.setRange(dtStart, dtLast)

        # ay = self.priceChart.axisY()
        # dataY = [v.y() for v in pvs]
        # ay.setRange(min(dataY), max(dataY))

if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    cw = ChartWidget()
    cw.show()
    exit(app.exec_())