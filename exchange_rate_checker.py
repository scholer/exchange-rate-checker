# -*- coding: utf-8 -*-
##    Copyright 2015 Rasmus Scholer Sorensen, rasmusscholer@gmail.com
##
##    This file is part of Exchange Rate Checker.
##
##    Exchange Rate Checker is free software: you can redistribute it and/or modify
##    it under the terms of the GNU Affero General Public License as
##    published by the Free Software Foundation, either version 3 of the
##    License, or (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU Affero General Public License for more details.
##
##    You should have received a copy of the GNU Affero General Public License
##    along with this program. If not, see <http://www.gnu.org/licenses/>.

# pylint: disable=C0103, R0914


"""
Currency APIs:
* google, yahoo, openexchangerates, currencylayer, ecb, fixer

* http://free.currencyconverterapi.com/
* http://www.programmableweb.com/api/currency-converter


Overviews of currency APIs:
* http://www.programmableweb.com/category/currency/api
* http://stackoverflow.com/questions/3139879/how-do-i-get-currency-exchange-rates-via-an-api-such-as-google-finance
*

Examples:
* http://query.yahooapis.com/v1/public/yql?q=select%20*%20from%20yahoo.finance.xchange%20where%20pair%20in%20(%22USDMXN)
    &format=json&env=store://datatables.org/alltableswithkeys
* http://free.currencyconverterapi.com/api/v3/convert?q=USD_DKK&compact=y
* http://rate-exchange.appspot.com/currency?from=USD&to=EUR
"""

import os
import glob
import yaml
import requests


SCRIPTDIR = os.path.dirname(__file__)


def get_rate(service="yql", curr1="USD", curr2="DKK", amount=1, **kwargs):
    """
    Get currency exchange rate from base currency :curr1: to currency :curr2:
    using the given service.
    The rate is multiplied by the given amount.
    kwargs, if given, will be added as query parameters to the service when obtaining the exchange rate.
    For instance, if the service requires an 'app_id' parameter, use:
        get_rate(service="openexchangerates", curr1="SEK", curr2="DKK", amount=100, app_id=<your_app_id>):
    """
    if service == "rate-exchange.appspot.com":
        # Doesn't work any more...
        url = "http://rate-exchange.appspot.com/currency"
        params = {'from': curr1,
                  'to': curr2}
        res = requests.get(url, params=params)
        rate = res.json()['rate']
    elif "currencyconverterapi" in service:
        # http://free.currencyconverterapi.com/api/v3/convert?q=USD_DKK&compact=y
        url = "http://free.currencyconverterapi.com/api/v3/convert"
        key = "%s_%s" % (curr1, curr2)
        params = {'q': key,
                  'compact': 'y'}
        res = requests.get(url, params=params)
        rate = res.json()[key]['val']
    elif "yahoo" in service or "yql" in service:
        # http://finance.yahoo.com/currency-converter/#from=USD;to=EUR;amt=1
        # https://query.yahooapis.com/v1/public/yql?q=select%20*%20from%20yahoo.finance.xchange%20where%20pair%20in%20(%22DKKUSD%22%2C%20%22USDDKK%22)&format=json&env=store%3A%2F%2Fdatatables.org%2Falltableswithkeys&callback=
        url = "https://query.yahooapis.com/v1/public/yql"
        query_fmt = 'select * from yahoo.finance.xchange where pair in ("{key}")'
        key = "%s%s" % (curr1, curr2)
        query = query_fmt.format(key=key)
        # format=json&env=store%3A%2F%2Fdatatables.org%2Falltableswithkeys&callback=
        params = {'q': query,
                  'format': 'json',
                  'env': 'store://datatables.org/alltableswithkeys'}
        res = requests.get(url, params=params)
        rate = res.json()['query']['results']['rate']['Rate']
    elif "openexchangerates" in service:
        # https://openexchangerates.org/api/latest.json?app_id=<your_app_id>
        # endpoints: latest.json, historical/YYYY-MM-DD.json, currencies.json, time-series.json
        url = "https://openexchangerates.org/api/latest.json"
        app_id = kwargs['app_id']
        params = {'app_id': app_id}
        res = requests.get(url, params=params)
        data = res.json()
        base = data['base'] # Will always be USD for free accounts
        base_rate = data["rates"][curr2]
        if curr1.lower() != base.lower():
            base_to_curr1 = data["rates"][curr1]
            rate = base_rate/base_to_curr1
        else:
            rate = base_rate
    rate = float(rate)
    return amount*rate


def get_config():
    """ Get a default config. """
    cands = [os.path.expanduser("~/.exchange_rate_config.yaml"),
             os.path.expanduser("~/.config/exchange_rate_config.yaml")]
    examples = glob.glob(os.path.join(SCRIPTDIR, "examples", "*.yaml"))
    cands += examples
    for cand in cands:
        if os.path.isfile(cand):
            return cand


def notify(msg):
    """ Show notification to the user. """
    print(msg)
    input("Press enter to continue...")


def main(args=None):
    """ script main entry point. """
    if args is None:
        args = {}
        args['config'] = get_config()
    configs = []
    if 'config' in args:
        if isinstance(args['config'], str):
            args['config'] = [args['config']]
        for configfn in args['config']:
            with open(configfn) as fp:
                config = yaml.load(fp)
            if isinstance(config, dict):
                configs.append(config)
            else:
                configs.extend(config)
    else:
        configs.append({})
    for config in configs:
        config.update(args)
        curr1, curr2 = config['from'], config['to']
        rate = get_rate(service=config['service'], curr1=curr1, curr2=curr2,
                        amount=config.get('amount', 1), **config.get('service_kwargs', {}))
        action = config.get('action', 'print')
        if "print" in action:
            print("Exchange rate (%s to %s): %s" % (curr1, curr2, rate))
        has_halted = False
        if "notify" in action:
            if "notify_below" in config:
                limit = config["notify_below"]
                if rate < limit:
                    notify("%s to %s exchange rate %s is below preset value of %s" %
                           (curr1, curr2, rate, limit))
                    has_halted = True
            if "notify_above" in config:
                limit = config["notify_above"]
                if rate > limit:
                    notify("%s to %s exchange rate %s is above preset value of %s" %
                           (curr1, curr2, rate, limit))
                    has_halted = True
        if "halt" in action and not has_halted:
            input("Press enter to continue...")


if __name__ == '__main__':
    main()
