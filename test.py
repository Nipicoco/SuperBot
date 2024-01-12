import time
import asyncio
import aiohttp
from binance.client import Client

async def get_tx_confirmations(coin, txid):
    coin = 'ltc'
    txid = 'fc5f887fa4eef2eb3fc813eb2268edfe38a8907fc1202bda92648eff8d58bee3'
    url = f"https://api.blockcypher.com/v1/{coin}/main/txs/{txid}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('confirmations', 0)
            else:
                return None


async def main():
    while True:
        confirmations = await get_tx_confirmations('ltc', 'fc5f887fa4eef2eb3fc813eb2268edfe38a8907fc1202bda92648eff8d58bee3')
        print(confirmations)
        if confirmations and confirmations >= 6:
            print('Transaction confirmed!')
            break
        await asyncio.sleep(5)
        