import asyncio
import datetime
from discord.ext import commands
from discord.ext import tasks
import json
import logging
from tabulate import tabulate
import re
import requests

from database import Database

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Load config file.
with open('config.json', 'r') as f:
    config = json.load(f)
ig_token = config['IG_TOKEN']
ig_username = config['IG_USERNAME']
ig_password = config['IG_PASSWORD']
ig_url = config['IG_URL']
channel_id = config['REPORT_CHANNEL']


class Expiry(commands.Converter):
    async def convert(self, ctx, argument):
        argument = argument.upper()[:3]
        months = {
            'JAN': 1,
            'FEB': 2,
            'MAR': 3,
            'APR': 4,
            'MAY': 5,
            'JUN': 6,
            'JUL': 7,
            'AUG': 8,
            'SEP': 9,
            'OCT': 10,
            'NOV': 11,
            'DEC': 12
        }
        try:
            month = months[argument]
        except KeyError:
            error_msg = "'{arg}' is not a valid month.".format(arg=argument)
            raise commands.BadArgument(error_msg)  # No FDs
        today = datetime.date.today()
        current_month = today.month
        current_year = today.year % 100

        if month >= current_month:
            expiry = argument + '-' + str(current_year)
        else:
            expiry = argument + '-' + str(current_year + 1)
        return expiry


class TradeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.url = ig_url
        self.headers = {'X-IG-API-KEY': ig_token, 'Content-Type': "application/json; charset=UTF-8",
                        'Accept': "application/json; charset=UTF-8", 'version': "2"}
        #  log in
        url = self.url + "/session"
        payload = {'identifier': ig_username, 'password': ig_password}
        r = requests.post(url, headers=self.headers, json=payload)
        r.raise_for_status()

        #  Parse response
        self.cst = r.headers['CST']
        self.xst = r.headers['X-SECURITY-TOKEN']
        self.auth_headers = {'CST': r.headers['CST'], 'X-SECURITY-TOKEN': r.headers['X-SECURITY-TOKEN']}

        #  Connect to database and load alerts into memory
        db = Database('trade_db')
        db.create_alert_table()
        db.commit()
        self.alerts = db.select_alerts()
        self.db = db

        #  Run background task
        self.background_task.start()

    def cog_unload(self):
        self.background_task.cancel()
        self.db.close()

    @commands.command()
    async def alert(self, ctx, level: float, expiry: Expiry, strike: int):
        """Set up a new alert."""
        alert = (ctx.message.id, ctx.author.id, level, expiry, strike)
        self.db.insert_alert(*alert)
        self.db.commit()
        self.alerts.append(alert)
        msg = "Price alert added for `{e} {s}p` at ${l}.".format(e=expiry, s=strike, l=level)
        await ctx.send(msg)

    @commands.command()
    async def show(self, ctx):
        """Shows alerts that have been set up."""
        r = self.db.select_my_alerts(ctx.author.id)
        if not r:
            return await ctx.send("No alerts found! Set one up with the alert command.")
        header = ('ID', 'Price', 'Expiry', 'Strike')
        align = ('left', 'decimal', 'right', 'decimal')
        table = tabulate(r, headers=header, tablefmt='psql', colalign=align)
        msg = "```\n" + table + "\n```\n"
        await ctx.send(msg)

    @commands.command()
    async def delete(self, ctx, alert_id):
        """Deletes an alert by id."""
        self.db.delete_my_alert(alert_id, ctx.author.id)
        self.db.commit()
        msg = "Deleted alert {alert_id}.".format(alert_id=alert_id)
        await ctx.send(msg)

    @commands.command(aliases=['p'])
    @commands.cooldown(rate=1, per=30)
    async def put(self, ctx):
        """Returns OTM SPX Put option prices."""
        msg = self.spx_options()
        await ctx.send(msg)

    @commands.command(aliases=['c'])
    @commands.cooldown(rate=1, per=30)
    async def call(self, ctx):
        """Returns OTM SPX Call option prices."""
        msg = self.spx_options('Call')
        await ctx.send(msg)

    def spx_options(self, opt='Put'):
        ticker = "IX.D.SPTRD.DAILY.IP"
        data_daily = self.get_price(ticker)

        strike = int(((data_daily['sell'] + data_daily['buy']) // 200) * 100)
        if not opt == 'Put':
            strike = int(((data_daily['sell'] + data_daily['buy']) // 200) * 100 + 100)

        data = self.search_price("US 500 {strike} {option}".format(strike=strike, option=opt))
        monthly = re.compile(r"OP\.D\.SPX.\.\d\d\d\d[CP]\.IP")
        expiries = [option['expiry'] for option in data if monthly.match(option['epic'])]
        expiries = expiries[:3]
        header = ["Strike"] + expiries
        table = []

        if opt == 'Put':
            otm = strike - 500
            step = -100
        else:  # Call
            otm = strike + 500
            step = 100
        first_iter = True
        for s in range(strike, otm, step):
            prices = []
            if not first_iter:
                data = self.search_price("US 500 {strike} {option}".format(strike=s, option=opt))
            else:
                first_iter = False
            for expiry in expiries:
                price = [option['bid'] for option in data if option['expiry'] == expiry]
                if not price:
                    price = [None]
                prices.extend(price)
            row = [s] + prices
            table.append(row)
        table = tabulate(table, headers=header, tablefmt='psql')
        spx = (data_daily['sell'] + data_daily['buy']) * 100 // 2
        spx = spx / 100
        msg = "SPX {option} options sell price:\n```\n".format(option=opt) + table + "\n```\nSPX: {spx}".format(spx=spx)
        return msg

    def get_price(self, ticker):
        url = self.url + "/markets/" + ticker
        headers = {**self.headers, **self.auth_headers}
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        content = r.json()
        instrument = content['instrument']
        snapshot = content['snapshot']
        data = {
            'name': instrument['name'],
            'expiry': instrument['expiry'],
            'sell': snapshot['bid'],
            'buy': snapshot['offer']
        }
        return data

    def search_price(self, query):
        url = self.url + "/markets"
        headers = {**self.headers, **self.auth_headers, 'version': "1"}
        payload = {'searchTerm': query}
        r = requests.get(url, headers=headers, params=payload)
        r.raise_for_status()
        content = r.json()
        return content['markets']

    @tasks.loop(seconds=300)
    async def background_task(self):
        bot = self.bot
        channel = bot.get_channel(channel_id)
        db = self.db
        alerts = self.alerts
        for alert in alerts[:]:
            expiry = alert[3]
            strike = alert[4]
            data = self.search_price("US 500 {strike} PUT".format(strike=strike))
            result = [option for option in data if option['expiry'] == expiry]
            result = result[0]
            price = result['bid']
            if price > alert[2]:
                name = result['instrumentName']
                msg = "<@!{user_id}> ".format(user_id=alert[1])
                msg = msg + "`{expiry} {strike}p` is at ${price}.".format(expiry=expiry, strike=strike, price=price)
                await channel.send(msg)
                alerts.remove(alert)
                db.delete_alert(alert[0])
                db.commit()
            await asyncio.sleep(1)  # Avoid rate limit
        logger.info('Successfully queried option prices.')

    @background_task.before_loop
    async def before_background_task(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(TradeCog(bot))
    logger.info("Loaded Trade Cog.")
