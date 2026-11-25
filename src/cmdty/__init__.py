"""cmdty: commodity Average Price Options (outright and spreads) with QuantLib: pricing, risk and delta hedging.

Layout
    instruments/  contracts: what is traded (Leg, APO)
    market/       market data and conventions: quotes, curves, vols, calendars
    models/       pricing engines: bachelier, kirk, montecarlo
    risk/         greeks (bump the market, never the trade)
    pricer.py     a model applied to a market snapshot
    portfolio.py  trades read from a YAML file
    hedging/      the hedging bot: daily loop, futures position, P&L
    data/         market data download and estimation (optional extra)
"""
from .instruments import AveragingSchedule, Leg, OptionType, APO, VanillaOption
from .market import (GAL_PER_BBL, DateRange, MarketData, Quote, business_days, cme_calendar,
                     flat_discount_factor, ice_futures_europe_calendar, implied_vol_black76,
                     joint_calendar, nymex_calendar)
from .portfolio import Portfolio, Trade, load_portfolio
from .pricer import Pricer
from .risk import GreekCalculator, Greeks, SpreadGreekCalculator

__all__ = ["Portfolio", "Trade", "load_portfolio", "AveragingSchedule", "Leg", "OptionType", "APO", "VanillaOption", "DateRange", "MarketData", "Quote", "Pricer", "GreekCalculator", "Greeks", "SpreadGreekCalculator", "GAL_PER_BBL",
           "business_days", "cme_calendar", "flat_discount_factor", "ice_futures_europe_calendar",
           "implied_vol_black76", "joint_calendar", "nymex_calendar"]
