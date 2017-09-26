# encoding: utf-8

import json
import os
import sys
from collections import OrderedDict

import matplotlib.pyplot as plt
from matplotlib.ticker import Formatter
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from report import Report

sys.path.append(os.path.abspath(".."))
from framework.dataserver import JzDataServer


class MyFormatter(Formatter):
    def __init__(self, dates, fmt='%Y%m'):
        self.dates = dates
        self.fmt = fmt

    def __call__(self, x, pos=0):
        """Return the label for time x at position pos"""
        ind = int(np.round(x))
        if ind >= len(self.dates) or ind < 0:
            return ''

        return self.dates[ind].strftime(self.fmt)


class BaseAnalyzer(object):
    """
    Attributes
    ----------
    _trades : pd.DataFrame
    _configs : dict
    data_server : BaseDataServer
    _universe : set
        All securities that have been traded.
        
    """
    def __init__(self):
        self._trades = None
        self._configs = None
        self.data_server = None
        
        self._universe = []
        self._closes = None
        
    @property
    def trades(self):
        """Read-only attribute"""
        return self._trades
    
    @property
    def universe(self):
        """Read-only attribute"""
        return self._universe
    
    @property
    def configs(self):
        """Read-only attribute"""
        return self._configs
    
    @property
    def closes(self):
        """Read-only attribute, close prices of securities in the universe"""
        return self._closes
    
    def initialize(self, data_server_, file_folder='../output/', ):
        """Read trades from csv file to DataFrame of given data type."""
        self.data_server = data_server_
        
        type_map = {'task_id': str,
                    'entrust_no': str,
                    'entrust_action': str,
                    'security': str,
                    'fill_price': float,
                    'fill_size': int,
                    'fill_date': int,
                    'fill_time': int,
                    'fill_no': str}
        trades = pd.read_csv(file_folder + 'trades.csv', ',', dtype=type_map)
        
        self._init_universe(trades.loc[:, 'security'].values)
        self._init_configs(file_folder)
        self._init_trades(trades)
        self._init_security_price()
    
    def _init_trades(self, df):
        """Add datetime column. """
        df.loc[:, 'fill_dt'] = df.loc[:, 'fill_date'] + df.loc[:, 'fill_time']
        
        res = dict()
        for sec in self.universe:
            res[sec] = df.loc[df.loc[:, 'security'] == sec, :]
        
        self._trades = res
    
    def _init_security_price(self):
        """Get close price of securities in the universe from data server."""
        close_dic = dict()
        for sec in self.universe:
            df, err_msg = self.data_server.daily(sec, "close", self.configs['start_date'], self.configs['end_date'])
            
            df.index = pd.to_datetime(df.loc[:, 'trade_date'], format="%Y%m%d")
            df.drop(['trade_date', 'security'], axis=1, inplace=True)
            close_dic[sec] = df
        
        self._closes = close_dic
    
    def _init_universe(self, securities):
        """Return a set of securities."""
        self._universe = set(securities)
    
    def _init_configs(self, file_folder):
        configs = json.load(open(file_folder + 'configs.json', 'r'))
        self._configs = configs


class AlphaAnalyzer(BaseAnalyzer):
    def __init__(self):
        BaseAnalyzer.__init__(self)
        
        self.metrics = dict()
        self.daily = None
        self.returns = None  # OrderedDict
        self.position_change = None  # OrderedDict
        self.account = None  # OrderedDict
        
    @staticmethod
    def _get_avg_pos_price(pos_arr, price_arr):
        """
        Calculate average cost price using position and fill price.
        When position = 0, cost price = security price.
        """
        assert len(pos_arr) == len(price_arr)
        
        avg_price = np.zeros_like(pos_arr, dtype=float)
        avg_price[0] = price_arr[0]
        for i in range(pos_arr.shape[0] - 1):
            if pos_arr[i+1] == 0:
                avg_price[i+1] = 0.0
            else:
                pos_diff = pos_arr[i+1] - pos_arr[i]
                if pos_arr[i] == 0 or (pos_diff) * pos_arr[i] > 0:
                    count = True
                else:
                    count = False
                
                if count:
                    avg_price[i+1] = (avg_price[i] * pos_arr[i] + pos_diff * price_arr[i+1]) * 1. / pos_arr[i+1]
                else:
                    avg_price[i+1] = avg_price[i]
        return avg_price
    
    @staticmethod
    def _process_trades(df):
        """Add various statistics to trades DataFrame."""
        df.index = pd.to_datetime(df.loc[:, 'fill_date'], format="%Y%m%d")
        df.index.name = 'index'
        
        cols_to_drop = ['task_id', 'entrust_no', 'fill_no']
        df.drop(cols_to_drop, axis=1, inplace=True)
        
        fs, fp = df.loc[:, 'fill_size'], df.loc[:, 'fill_price']
        turnover = fs * fp
        
        df.loc[:, 'CumTurnOver'] = turnover.cumsum()
        
        direction = df.loc[:, 'entrust_action'].apply(lambda s: 1 if s == 'buy' else -1)
        
        df.loc[:, 'BuyVolume'] = (direction + 1) / 2 * fs
        df.loc[:, 'SellVolume'] = (direction - 1) / -2 * fs
        df.loc[:, 'CumVolume'] = fs.cumsum()
        df.loc[:, 'CumNetTurnOver'] = (turnover * -direction).cumsum()
        df.loc[:, 'position'] = (fs * direction).cumsum()
        
        df.loc[:, 'AvgPosPrice'] = AlphaAnalyzer._get_avg_pos_price(df.loc[:, 'position'].values, fp.values)
        
        df.loc[:, 'VirtualProfit'] = (df.loc[:, 'CumNetTurnOver'] + df.loc[:, 'position'] * fp)
        
        return df
    
    def process_trades(self):
        self._trades = {k: self._process_trades(v) for k, v in self.trades.items()}
    
    @staticmethod
    def _get_daily(close, trade):
        merge = pd.concat([close, trade], axis=1, join='outer')
        cols = ['close', 'BuyVolume', 'SellVolume',
                'position', 'AvgPosPrice', 'CumNetTurnOver']
        merge = merge.loc[:, cols]
    
        cols_nan_to_zero = ['BuyVolume', 'SellVolume']
        cols_nan_fill = ['close', 'position', 'AvgPosPrice', 'CumNetTurnOver']
        merge.loc[:, cols_nan_fill] = merge.loc[:, cols_nan_fill].fillna(method='ffill')
        merge.loc[:, cols_nan_fill] = merge.loc[:, cols_nan_fill].fillna(0)
        
        merge.loc[:, cols_nan_to_zero] = merge.loc[:, cols_nan_to_zero].fillna(0)
        
        merge.loc[merge.loc[:, 'AvgPosPrice'] < 1e-5, 'AvgPosPrice'] = merge.loc[:, 'close']
    
        merge.loc[:, 'VirtualProfit'] = merge.loc[:, 'CumNetTurnOver'] + merge.loc[:, 'position'] * merge.loc[:, 'close']
        
        return merge
    
    def get_daily(self):
        """Add various statistics to daily DataFrame."""
        daily_dic = dict()
        for sec, df_trade in self.trades.items():
            df_close = self.closes[sec]
            
            daily_dic[sec] = self._get_daily(df_close, df_trade)
            
        self.daily = daily_dic
    
    @staticmethod
    def _to_return(arr):
        """Convert portfolio value to portfolio (linear) return."""
        r = np.empty_like(arr)
        r[0] = 0.0
        r[1:] = arr[1:] / arr[0] - 1
        return r
    
    def get_pos_change_info(self):
        trades = pd.concat(self.trades.values(), axis=0)
        gp = trades.groupby(by=['fill_date'], as_index=False)
        res = OrderedDict()
        account = OrderedDict()
        
        for date, df in gp:
            df_mod = df.loc[:, ['security', 'entrust_action', 'fill_size', 'fill_price',
                                'position', 'AvgPosPrice']]
            df_mod.columns = ['security', 'action', 'size', 'price',
                              'position', 'cost price']
            
            res[str(date)] = df_mod
            
            mv = sum(df_mod.loc[:, 'price'] * df.loc[:, 'position'] * 100.0)
            current_profit = sum(df.loc[:, 'VirtualProfit'])
            cash = self.configs['init_balance'] + current_profit - mv
            
            account[str(date)] = {'market_value': mv, 'cash': cash}
        self.position_change = res
        self.account = account
            
    def get_returns(self):
        vp_list = [df_profit.loc[:, 'VirtualProfit'].copy().rename({'VirtualProfit': sec}) for sec, df_profit in self.daily.items()]
        df_profit = pd.concat(vp_list, axis=1)
        strategy_value = df_profit.sum(axis=1) * 100 + self.configs['init_balance']
        
        benchmark_name = self.configs['benchmark']
        df_bench_value, err_msg = self.data_server.daily(benchmark_name, "close", self.configs['start_date'], self.configs['end_date'])
        df_bench_value.index = pd.to_datetime(df_bench_value.loc[:, 'trade_date'], format="%Y%m%d")
        df_bench_value.index.name = 'index'
        df_bench_value.drop(['trade_date', 'security'], axis=1, inplace=True)

        pnl_return = pd.DataFrame(index=strategy_value.index, data=self._to_return(strategy_value.values))
        bench_return = pd.DataFrame(index=df_bench_value.index, data=self._to_return(df_bench_value.values))
        
        returns = pd.concat([bench_return, pnl_return], axis=1).fillna(method='ffill')
        returns.columns = ['Benchmark', 'Strategy']
        returns.loc[:, 'extra'] = returns.loc[:, 'Strategy'] - returns.loc[:, 'Benchmark']
        # returns.loc[:, 'DD']
        
        start = pd.to_datetime(self.configs['start_date'], format="%Y%d%m")
        end = pd.to_datetime(self.configs['end_date'], format="%Y%d%m")
        years = (end - start).days / 225.
        
        self.metrics['yearly_return'] = returns.loc[:, 'extra'].values[-1] / years
        self.metrics['yearly_vol'] = returns.loc[:, 'extra'].std() * np.sqrt(225.)
        self.metrics['beta'] = np.corrcoef(returns.loc[:, 'Benchmark'], returns.loc[:, 'Strategy'])[0, 1]
        self.metrics['sharpe'] = self.metrics['yearly_return'] / self.metrics['yearly_vol']
        
        self.returns = returns

    def plot_pnl(self, save_folder="."):
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), dpi=300, sharex=True)
        idx0 = self.returns.index
        idx = range(len(idx0))
        ax1.plot(idx, self.returns.loc[:, 'Benchmark'], label='Benchmark')
        ax1.plot(idx, self.returns.loc[:, 'Strategy'], label='Strategy')
        ax1.legend(loc='upper left')
        ax2.plot(idx, self.returns.loc[:, 'extra'], label='Extra Return')
        ax2.legend(loc='upper left')
        ax2.set_xlabel("Date")
        ax2.set_ylabel("Percent")
        ax1.set_ylabel("Percent")
        ax2.xaxis.set_major_formatter(MyFormatter(idx0, '%Y%m'))
        
        plt.tight_layout()
        fig.savefig(save_folder + '/' + 'pnl_img.png')

    def gen_report(self, out_folder='output', selected=[]):
        d = dict()
        d['html_title'] = "Alpha Strategy Backtest Result"
        d['selected_securities'] = selected
        d['props'] = self.configs
        d['metrics'] = self.metrics
        d['position_change'] = self.position_change
        d['account'] = self.account
        
        r = Report(d,
                   'static/report_template.html', 'static/blueprint.css',
                   out_folder=out_folder)
        
        r.generate_html()
        r.output_html('report.html')
        r.output_pdf('report.pdf')


def calc_uat_metrics(t1, security):
    cump1 = t1.loc[:, 'VirtualProfit'].values
    profit1 = cump1[-1]
    
    n_trades = t1.loc[:, 'CumVolume'].values[-1] / 2.  # signle
    avg_trade = profit1 / n_trades
    print "profit without commission = {} \nprofit with commission {}".format(profit1, profit1)
    print "avg_trade = {:.3f}".format(avg_trade)
    
    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(16, 8))
    ax1.plot(cump1, label='inst1')
    ax1.set_title("{} PnL in price".format(security))
    ax1.legend(loc='upper left')
    ax1.axhline(0, color='k', lw=1, ls='--')
    ax2.plot(t1.loc[:, 'position'].values)
    ax2.set_title("Position")
    ax2.axhline(0, color='k', lw=1, ls='--')
    
    plt.show()
    return


def plot_trades(df, security="", save_folder="."):
    idx = range(len(df.index))
    price = df.loc[:, 'close']
    bv, sv = df.loc[:, 'BuyVolume'].values, df.loc[:, 'SellVolume'].values
    profit = df.loc[:, 'VirtualProfit'].values
    avgpx = df.loc[:, 'AvgPosPrice']
    bv *= .1
    sv *= .1
    
    fig = plt.figure(figsize=(14, 10), dpi=300)
    ax1 = plt.subplot2grid((4, 1), (0, 0), rowspan=3)
    ax3 = plt.subplot2grid((4, 1), (3, 0), rowspan=1, sharex=ax1)
    
    # fig, (ax1, ax3) = plt.subplots(2, 1, figsize=(16, 18), sharex=True)
    # fig, ax1 = plt.subplots(1, 1, figsize=(16, 6))
    ax2 = ax1.twinx()
    
    ax1.plot(idx, price, label='Price', linestyle='-', lw=1, marker='', color='yellow')
    ax1.scatter(idx, price, label='buy', marker='o', s=bv, color='red')
    ax1.scatter(idx, price, label='sell', marker='o', s=sv, color='green')
    ax1.plot(idx, avgpx, lw=1, marker='', color='green')
    ax1.legend(loc='upper left')
    
    ax2.plot(idx, profit, label='PnL', color='k', lw=1, ls='--', alpha=.4)
    ax2.legend(loc='upper right')
    
    # ax1.xaxis.set_major_formatter(MyFormatter(df.index))#, '%H:%M'))
    
    ax3.plot(idx, df.loc[:, 'position'], marker='D', markersize=3, lw=2)
    ax3.axhline(0, color='k', lw=1)
    
    
    ax1.set_title(security)
    
    fig.savefig(save_folder + '/' + "{}.png".format(security))
    plt.tight_layout()
    return

if __name__ == "__main__":
    import time
    t_start = time.time()
    
    ta = AlphaAnalyzer()
    data_server = JzDataServer()
    
    ta.initialize(data_server, '../output/')
    
    print "process trades..."
    ta.process_trades()
    print "get daily stats..."
    ta.get_daily()
    print "calc strategy return..."
    ta.get_returns()
    print "get position change..."
    ta.get_pos_change_info()

    print "plot..."
    out_foler = "output"
    selected_sec = list(ta.universe)[::3]
    for sec, df in ta.daily.items():
        if sec in selected_sec:
            plot_trades(df, sec, out_foler)
    ta.plot_pnl(out_foler)
    print "generate report..."
    ta.gen_report(out_foler)

    t1 = time.time() - t_start
    print "\ntime lapsed in total: {:.2f}".format(t1)
    
    del data_server, ta
    print "Test passed."
