# encoding: UTF-8

import pandas as pd
import pytest
from quantos.data.dataservice import RemoteDataService

from quantos.data.py_expression_eval import Parser


def test_logical_and_or():
    import numpy as np
    
    parser.parse('open + 3 && 1')
    res = parser.evaluate({'open': dfx})
    assert np.all(res.values.flatten())

    parser.parse('open + 3 && 0.0')
    res = parser.evaluate({'open': dfx})
    assert not np.all(res.values.flatten())

    
def test_skew():
    # parser.set_capital('lower')
    expression = parser.parse('Ts_Skewness(open,4)')
    res = parser.evaluate({'close': dfy, 'open': dfx})
    # parser.set_capital('upper')


def test_variables():
    expression = parser.parse('Ts_Skewness(open,4)+close / what')
    res = set(expression.variables()) == {'open', 'close', 'what'}
    
    
def test_product():
    # parser.set_capital('lower')
    expression = parser.parse('Product(open,2)')
    res = parser.evaluate({'close': dfy, 'open': dfx})
    # parser.set_capital('upper')


def test_rank():
    expression = parser.parse('Rank(close)')
    res = parser.evaluate({'close': dfy, 'open': dfx})


def test_tail():
    expression = parser.parse('Tail(close/open,0.99,1.01,1.0)')
    res = parser.evaluate({'close': dfy, 'open': dfx})


def test_step():
    expression = parser.parse('Step(close,10)')
    res = parser.evaluate({'close': dfy, 'open': dfx})


def test_decay_linear():
    expression = parser.parse('Decay_linear(open,2)')
    res = parser.evaluate({'close': dfy, 'open': dfx})


def test_decay_exp():
    expression = parser.parse('Decay_exp(open, 0.5, 2)')
    res = parser.evaluate({'close': dfy, 'open': dfx})


def test_signed_power():
    expression = parser.parse('SignedPower(close-open, 2)')
    res = parser.evaluate({'close': dfx, 'open': dfy})


def test_ewma():
    expr = parser.parse('Ewma(close, 3)')
    res = parser.evaluate({'close': dfx})
    assert abs(res.loc[20170801, '000001.SH'] - 3292.6) < 1e-1


def test_if():
    expr = parser.parse('If(close > 20, 3, -3)')
    res = parser.evaluate({'close': dfx})
    assert res.iloc[0, 0] == 3.
    assert res.iloc[0, 2] == -3.


def test_group_apply():
    import numpy as np
    np.random.seed(369)
    
    n = 20
    
    dic = {c: np.random.rand(n) for c in 'abcdefghijklmnopqrstuvwxyz'[:n]}
    df_value = pd.DataFrame(index=range(n), data=dic)
    
    r = np.random.randint(0, 5, n * df_value.shape[0]).reshape(df_value.shape[0], n)
    cols = df_value.columns.values.copy()
    np.random.shuffle(cols)
    
    df_group = pd.DataFrame(index=df_value.index, columns=cols, data=r)

    parser = Parser()
    expr = parser.parse('GroupApply(Standardize, GroupApply(Cutoff, close, 2.8))')
    res = parser.evaluate({'close': df_value}, df_group=df_group)
    
    assert abs(res.iloc[3, 6] - (-1.53432)) < 1e-5
    assert abs(res.iloc[19, 18] - (-1.17779)) < 1e-5


def test_calc_return():
    expr = parser.parse('Return(close, 2, 0)')
    res = parser.evaluate({'close': dfx})
    assert abs(res.loc[20170808, '000001.SH'] - 0.006067) < 1e-6


@pytest.fixture(autouse=True)
def my_globals(request):
    ds = RemoteDataService()
    
    df, msg = ds.daily("000001.SH, 600030.SH, 000300.SH", start_date=20170801, end_date=20170820,
                       fields="open,high,low,close,vwap,preclose")
    ds.api.close()
    
    multi_index_names = ['trade_date', 'symbol']
    df_multi = df.set_index(multi_index_names, drop=False)
    df_multi.sort_index(axis=0, level=multi_index_names, inplace=True)
    
    dfx = df_multi.loc[pd.IndexSlice[:, :], pd.IndexSlice['close']].unstack()
    dfy = df_multi.loc[pd.IndexSlice[:, :], pd.IndexSlice['open']].unstack()
    
    parser = Parser()
    request.function.func_globals.update({'parser': parser, 'dfx': dfx, 'dfy': dfy})


if __name__ == "__main__":
    ds = RemoteDataService()
    
    df, msg = ds.daily("000001.SH, 600030.SH, 000300.SH", start_date=20170801, end_date=20170820,
                       fields="open,high,low,close,vwap,preclose")
    ds.api.close()
    
    multi_index_names = ['trade_date', 'symbol']
    df_multi = df.set_index(multi_index_names, drop=False)
    df_multi.sort_index(axis=0, level=multi_index_names, inplace=True)
    
    dfx = df_multi.loc[pd.IndexSlice[:, :], pd.IndexSlice['close']].unstack()
    dfy = df_multi.loc[pd.IndexSlice[:, :], pd.IndexSlice['open']].unstack()
    
    parser = Parser()
    
    g = globals()
    g = {k: v for k, v in g.items() if k.startswith('test_') and callable(v)}
    
    for test_name, test_func in g.viewitems():
        print "\nTesting {:s}...".format(test_name)
        # try:
        test_func()
        # print "Successfully tested {:s}.".format(test_name)
        # except Exception, e:
    print "Test Complete."
