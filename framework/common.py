# encoding: UTF-8
from enum import Enum, unique


class ReprEnum(Enum):
    def __repr__(self):
        return "{0:s}_{1:s}".format(self.__class__.__name__,
                                    self._name_)

    def __str__(self):
        return "{0:s}_{1:s}".format(self.__class__.__name__,
                                    self._name_)

    @property
    def full_name(self):
        return str(self)

    @classmethod
    def to_enum(cls, key):
        return cls.__members__.get(key.upper(), None)


class ReprIntEnum(int, ReprEnum):
    """Enum where members are also (and must be) ints"""
    pass


class ReprStrEnum(str, ReprEnum):
    """Enum where members are also (and must be) ints"""
    pass


@unique
class QUOTE_TYPE(ReprIntEnum):
    TICK = 0
    MIN = 1
    FIVEMIN = 5
    QUARTERMIN = 15
    DAILY = 1440
    SPECIALBAR = -1


@unique
class RUN_MODE(ReprIntEnum):
    REALTIME = 0
    BACKTEST = 1


@unique
class EXCHANGE(ReprStrEnum):
    SHENZHEN_STOCK_EXCHANGE = 'SZ'
    SHANGHAI_STOCK_EXCHANGE = 'SH'

    SHANGHAI_FUTURES_EXCHANGE = 'SHF'
    ZHENGZHOU_COMMODITIES_EXCHANGE = 'CZC'
    DALIAN_COMMODITIES_EXCHANGE = 'DCE'

    CHINA_FINANCIAL_FUTURES_EXCHANGE = 'CFE'

    SHANGHAI_GOLD_EXCHANGE = 'SGE'

    CHINA_SECURITY_INDEX = 'CSI'

    HONGKONG_EXCHANGES_AND_CLEARING_LIMITED = 'HK'





@unique
class ORDER_TYPE(ReprStrEnum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"  # convert to market order once security price meet certain conditions.



@unique
class ORDER_ACTION(ReprStrEnum):
    BUY = "buy"
    SELL = "sell"
    SHORT = "short"
    COVER = "cover"
    SELLTODAY = "sellToday"
    SELLYESTERDAY = "sellYesterday"
    COVERYESTERDAY = "coverYesterday"
    COVERTODAY = "coverToday" #TODO not appears in API doc


@unique
class ORDER_STATUS(ReprStrEnum):
    NEW = "new"
    ACCEPTED = "accepted"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@unique
class ORDER_TIME_IN_FORCE(ReprStrEnum):
    FOK = 'fok'
    FAK = 'fak'
    IOC = 'ioc'


"""
RUNMODE_REALTIME = 0
RUNMODE_BACKTEST = 1

QUOTE_TYPE_TICK       = 0    
QUOTE_TYPE_MIN     = 1    
QUOTE_TYPE_FiVEMIN = 5    
QUOTE_TYPE_QUARTERMIN = 15   
QUOTE_TYPE_DAILY      = 1440
QUOTE_TYPE_SPECIALBAR = -1

ORDER_TYPE_LIMITORDER        = "LimitOrder"
ORDER_TYPE_STOPORDER         = "StopOrder"

ORDER_ACTION_BUY             = "Buy"                      
ORDER_ACTION_SELL            = "Sell"                     
ORDER_ACTION_SHORT           = "Short"                    
ORDER_ACTION_COVER           = "Cover"                    
ORDER_ACTION_SELLTODAY       = "SellToday"       
ORDER_ACTION_SELLYESTERDAY   = "SellYesterday"   
ORDER_ACTION_COVERYESTERDAY  = "CoverYesterday"  
ORDER_ACTION_COVERTODAY      = "CoverToday"      
                                                  
ORDER_STATUS_NEW       = "New"                   
ORDER_STATUS_ACCEPTED  = "Accepted"              
ORDER_STATUS_FILLED    = "Filled"                
ORDER_STATUS_CANCELLED = "Cancelled"             
ORDER_STATUS_REJECTED  = "Rejected"              
"""


if __name__ == "__main__":
    """What below are actually unit tests. """

    print "Running test..."

    assert QUOTE_TYPE.TICK == 0
    assert RUN_MODE.BACKTEST == 1
    assert ORDER_ACTION.BUY == 'buy'
    assert ORDER_TYPE.MARKET == 'market'
    assert ORDER_STATUS.FILLED == 'filled'

    print "Test passed."
