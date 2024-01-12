####DISCORD BOT AND IMPORTS####
import asyncio
import datetime
import hashlib
import hmac
import json
from pprint import pprint
import time
import uuid
import discord
import random
import aiohttp
from discord.ext.commands.context import Context
from discord.ext import commands
import requests
bot = discord.Bot(intents=discord.Intents.all())####BINANCE API AND IMPORTS####
from discord.ext import tasks
from binance.client import Client
import os
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv('binance_api_key')
api_secret = os.getenv('binance_api_secret')
binance_client = Client(api_key, api_secret)
server_time = binance_client.get_server_time()
time_difference = server_time['serverTime'] - int(time.time() * 1000)
timestamp = int(time.time() * 1000) + time_difference
##################
admin_ids = [707513459205734470, 572959864423448580]
async def is_admin(ctx):
    if ctx.author.id in admin_ids:
        print(f"{ctx.author.id} used an admin command.")
        return True
    else:
        print(f"{ctx.author.id} tried to use an admin command.")
        await ctx.send("Bạn không được phép sử dụng lệnh này ngốc nghếch.")
        return False
##################
class CoinSelect(discord.ui.Select):
    def __init__(self, ctx, options, variant_price, variant_title, quantity, total_price, order_id):
        super().__init__(placeholder='Select a coin', min_values=1, max_values=1, options=options)
        self.ctx = ctx  
        self.variant_price = variant_price  # Store the variant_price
        self.variant_title = variant_title  # Store the variant_title
        self.quantity = quantity  # Store the quantity
        self.total_price = total_price  # Store the total_price
        self.order_id = order_id
    async def callback(self, interaction: discord.Interaction):
        coin = self.values[0]
        await interaction.response.send_message(f'You selected: {coin}', ephemeral=True)
        if self.ctx.wallet == 'external':
            self.message = await create_payment(self.ctx, interaction, self.variant_title, self.variant_price, self.quantity, self.total_price, coin, self.order_id)
        else:  # wallet == 'binance'
            self.message = await create_binance_payment(self.ctx, interaction, self.variant_title, self.variant_price, self.quantity, self.total_price, coin, self.order_id)


class ProductSelect(discord.ui.Select):
    def __init__(self, ctx, options):
        super().__init__(
            placeholder="Select a product", min_values=1, max_values=1, options=options
        )
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"You selected: {self.values[0]}", ephemeral=True
        )
        await ask_variant(self.ctx, interaction, self.values[0])
class VariantSelect(discord.ui.Select):
    def __init__(self, ctx, options, product_name):
        super().__init__(placeholder='Select a variant', min_values=1, max_values=1, options=options)
        self.ctx = ctx
        self.product_name = product_name

    async def callback(self, interaction: discord.Interaction):
        variant_title = self.values[0]
        await interaction.response.send_message(f"You selected: {variant_title}", ephemeral=True)

        # Read the product details from the JSON file
        with open('keys.json', 'r') as f:
            products = json.load(f)

        # Get the price and stock for the selected variant
        variant = products[self.product_name][variant_title]
        variant_price = variant['price']
        variant_stock = len(variant['keys'])

        quantity, total_price = await ask_quantity(self.ctx, interaction, variant_title, variant_price, variant_stock)
        if quantity is None or total_price is None:
            return

        # Generate a new order ID
        order_id = str(uuid.uuid4())
                
        # Set the order_id in the Context object
        self.ctx.order_id = order_id

        # Ask the user for their wallet type
        wallet_select = WalletSelect(self.ctx, variant_title, variant_price, quantity, total_price, order_id)
        view = discord.ui.View(timeout=None)
        view.add_item(wallet_select)
        await interaction.followup.send("Please select your wallet type:", view=view)
class Context:
    def __init__(self, user, channel_id, order_id=None, wallet=None):
        self.user = user
        self.channel_id = channel_id
        self.order_id = order_id
        self.wallet = wallet


@bot.command(name='buy', help="Buy a product from our shop", aliases=['purchase'], brief="Buy a product", description="Buy a product from our shop")
async def buy(interaction, channel: discord.TextChannel = None):
    if channel is None:
        # If no channel is provided, use the channel where the command was invoked
        channel = interaction.channel

    # Check if the channel name starts with "ticket-"
    if not channel.name.startswith("ticket-"):
        return

    # Create a new context object with the ticket_channel
    ctx = Context(interaction.user, channel.id)

    
    try:
        # Read products from the JSON file
        with open('keys.json', 'r') as f:
            products = json.load(f)

        # Create a list of SelectOptions for the dropdown
        options = [
            discord.SelectOption(label=product, value=product)
            for product in products
        ]

        # Create a Select with the options
        select = ProductSelect(ctx, options)

        # Create a SelectView and add the Select to it
        view = discord.ui.View(timeout=None)
        view.add_item(select)
        view.add_item(CancelButton())

        embed = discord.Embed(title="Product Selection", description="Please select a product from the dropdown below.", color=0xB4610C)
        embed.set_thumbnail(url="https://i.imgur.com/hssTBxK.png")
        embed.add_field(name="**__How to buy__**", value="1. Select a product from the dropdown menu.\n2. Select a variant from the dropdown menu.\n3. Enter the quantity you want to buy.\n4. Select a coin to pay with.\n5. Send the exact amount to the address provided.\n6. Enter your transaction ID (TxID) to receive your keys or wait for the system to automatically verify the recieved ammount.", inline=False)
        embed.add_field(name="**__Payment methods__**", value="We accept the following coins:\nLTC, USDT, ETH, TRX, XMR, SOL", inline=False)
        embed.add_field(name="**__Refund policy__**", value="We do not offer refunds. All sales are final.", inline=False)
        embed.add_field(name="**__Support__**", value="If you have any questions or issues, please contact our support team.", inline=False)
        embed.add_field(name="**__Disclaimer__**", value="We are not responsible for any losses caused by the use of our products. Please use them at your own risk.", inline=False)
        # Send a message with the SelectView and the embed
        await channel.send(embed=embed, view=view)
        
    except Exception as e:
        print(f"Error in buy command: {e}")
    




class CancelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Cancel", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        if interaction.channel.name.startswith("ticket-"):
            await interaction.response.send_message("The channel will be deleted in 10 seconds.")
            bot.loop.create_task(delete_channel_after_delay(interaction.channel.id))
        else:
            await interaction.response.send_message("This channel cannot be deleted.")
async def ask_variant(ctx, interaction, product_name):
    # Read the product details from the JSON file
    with open('keys.json', 'r') as f:
        products = json.load(f)

    if product := products.get(product_name, {}):
        # Create a list of SelectOptions for the dropdown
        options = [
            discord.SelectOption(
                label=variant, 
                value=variant,
                description=f"Stock: {len(product[variant]['keys'])}\nPrice: {product[variant]['price']} USD"
            )
            for variant in product if len(product[variant]['keys']) > 0
        ]

        # Check if the number of options is within the valid range
        if 1 <= len(options) <= 25:
            # Create a Select with the options
            select = VariantSelect(ctx, options, product_name)

            # Create a SelectView and add the Select to it
            view = discord.ui.View(timeout=None)
            view.add_item(select)
            # Create an embed
            embed = discord.Embed(title="Variant Selection", description="Please select a variant from the dropdown below.", color=0xB4610C)
            embed.set_thumbnail(url="https://i.imgur.com/hssTBxK.png")
            embed.add_field(name="Product", value=product_name, inline=False)

            # Send a message with the SelectView and the embed
            await interaction.followup.send(
                embed=embed, view=view
            )
        else:
            # Send an error message
            await interaction.followup.send(
                "No stock available for this product. Please contact an admin for assistance.", ephemeral=True
            )
            # Send a message to the specified channel
            channel = bot.get_channel(1185703704658194533)  # Replace with your channel ID
            await channel.send(f"@here The stock for {product_name} is out of stock.")
            # Resend the buy message
            await buy(interaction)
    else:
        # Send an error message
        await interaction.followup.send(
            "This product does not exist. Please contact an admin for assistance.", ephemeral=True
        )
        # Resend the buy message
        await buy(interaction)

async def delete_channel_after_delay(channel_id):
   await asyncio.sleep(10)
   await bot.get_channel(channel_id).delete()
class WalletSelect(discord.ui.Select):
    def __init__(self, ctx, variant_title, variant_price, quantity, total_price, order_id):
        options = [
            discord.SelectOption(label='External', value='external'),
            discord.SelectOption(label='Binance', value='binance'),
        ]
        super().__init__(placeholder='Select a wallet', min_values=1, max_values=1, options=options)
        self.ctx = ctx  
        self.variant_price = variant_price  # Store the variant_price
        self.variant_title = variant_title  # Store the variant_title
        self.quantity = quantity  # Store the quantity
        self.total_price = total_price  # Store the total_price
        self.order_id = order_id  # Store the order_id
        self.message = None  # Store the message that contains the embed

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        wallet = self.values[0]
        self.ctx.wallet = wallet
        await interaction.followup.send(f'You selected: {wallet}', ephemeral=True)
            # Delete the old embed if it exists
        if self.message is not None:
            await self.message.delete()
        await ask_coin(self.ctx, interaction, self.variant_title, self.variant_price, self.quantity, self.total_price, self.order_id, wallet)



async def ask_quantity(ctx, interaction, variant_title, variant_price, variant_stock):
    channel = bot.get_channel(ctx.channel_id)
    while True:
        # Create an embed
        embed = discord.Embed(title="Quantity Selection", description="Please reply to this message with the quantity you want to buy.", color=0xB4610C)
        embed.set_thumbnail(url="https://i.imgur.com/hssTBxK.png")
        embed.add_field(name="Variant", value=variant_title, inline=False)
        embed.add_field(name="Price(USD)", value=variant_price, inline=False)
        embed.add_field(name="Stock", value=variant_stock, inline=False)
        embed.set_footer(text="Click the cancel button to cancel the operation at any point!")

        # Create a View with the CancelButton
        view = discord.ui.View(timeout=None)
        view.add_item(CancelButton())

        # Send a message with the View and the embed
        await channel.send(embed=embed, view=view)
        
        await channel.send("Please enter the quantity you want to buy:")

        # Handle the user's response and store the quantity
        try:
            quantity = await get_user_response(ctx)
            print(f"Quantity received: {quantity}")  # Debug print
        except Cancelled:
            await channel.send("The operation was cancelled.")
            return None, None
        
        # Check if the input is a number
        if not quantity.isdigit():
            await interaction.followup.send("Invalid quantity. Please enter a number.")
            continue

        # Check if the requested quantity is available
        if int(quantity) > int(variant_stock):
            await interaction.followup.send(f"Sorry, we don't have enough stock for your request. Available stock: {variant_stock}. Please enter a new quantity.")
            continue

        # Calculate the total price
        total_price = float(variant_price) * int(quantity)
        
        # Generate a new order ID
        order_id = str(uuid.uuid4())
        
        # Set the order_id in the Context object
        ctx.order_id = order_id

        return quantity, total_price       

async def ask_coin(ctx, interaction, variant_title, variant_price, quantity, total_price, order_id, wallet):
    if wallet == 'external':
        coin_options = [
            discord.SelectOption(label='LTC', value='LTC'),
            discord.SelectOption(label='USDT', value='USDT'),
            discord.SelectOption(label='TRX', value='TRX'),
            discord.SelectOption(label='ETH', value='ETH'),
            discord.SelectOption(label='BTC', value='BTC'),
        ]
    else:  # wallet == 'binance'
        coin_options = [
            discord.SelectOption(label='LTC', value='LTC'),
            discord.SelectOption(label='USDT', value='USDT'),
            discord.SelectOption(label='ETH', value='ETH'),
            discord.SelectOption(label='TRX', value='TRX'),
            discord.SelectOption(label='XMR', value='XMR'),
            discord.SelectOption(label='SOL', value='SOL'),
        ]
    coin_select = CoinSelect(ctx, coin_options, variant_price, variant_title, quantity, total_price, order_id)
    view = discord.ui.View(timeout=None)
    view.add_item(coin_select)
    # Create an embed
    embed = discord.Embed(title="Coin and Wallet Selection", description="Choose the coin you would like to use for payment and the wallet you will be using.", color=0xB4610C)
    embed.add_field(name="Variant", value=variant_title, inline=False)
    embed.add_field(name="Quantity", value=quantity, inline=False)
    embed.add_field(name="Total price(USD)", value=total_price, inline=False)
    embed.set_thumbnail(url="https://i.imgur.com/hssTBxK.png")
    # Send a message with the SelectView and the embed
    await interaction.followup.send(embed=embed, view=view)

class Cancelled(Exception):
    pass

async def get_user_response(ctx):
    def check(m):
        return m.author.id == ctx.user.id and m.channel.id == ctx.channel_id

    print(f"Waiting for a message from {ctx.user.id} in channel {ctx.channel_id}")  # Debug print
    message = await bot.wait_for('message', check=check)
    print(f"Received a message: {message.content}")  # Debug print
    
    if message.content.lower() == '!cancel':
        raise Cancelled
    
    return message.content


def generate_price(total_price, coin_price):
    return total_price / coin_price


     
async def create_payment(ctx, interaction, variant_title, variant_price, quantity, total_price, coin, order_id):
    channel = bot.get_channel(ctx.channel_id)


    
    print(f"Coin: {coin}")  # Add this line
    await bot.get_channel(ctx.channel_id).edit(topic=f"Order ID: {order_id}")

    # Get the current price of the coin in your base currency (e.g., USD)
    if coin == 'USDT':
        coin_price = 1
    else:
        coin_price = binance_client.get_avg_price(symbol=f'{coin}USDT')['price']

    # Generate a unique price variation
    unique_price_variation = generate_price(total_price, float(coin_price))

    # Specify the transaction fees for each coin
    coin_fees = {
        'USDT': 1,
        'LTC': 0.001,
        'ETH': 0.0032,
        'TRX': 1,
        'BTC': 0.00075,
    }
    # Calculate the amount the user needs to send in crypto, including the transaction fee
    crypto_amount = round(unique_price_variation + coin_fees[coin], 5)

    # Specify the address for each coin
    coin_addresses = {
        'USDT': 'TE7L1693VNLqLeW1begEunDyY2GUe6m1Jr',
        'LTC': 'LLaJwR6peFhUaUbmhMyj3sraVAxz3JQHHb',
        'ETH': '0xd10c6cc87e7fdba828df1aa4229ce1733874fe5b',
        'TRX': 'TGZCdKmQWDcsUm7TJBdQ9YmzpgQ9uPquCS',
        'XMR': '87kHE7SW9gFbNFMgRMhJtqjgcyFvTKb3fUCvpYSYnq1URKXKa79rNH29w9TCDykKVsQhgf3XXPmiHEw2y1BvMsLJ7ac4wqE',
        'SOL': 'DUgiggZZaW1rvP2zzuTZ146mF2Kfte1vaYenKhmhGZnN',
    }
    coin_networks = {
        'USDT': 'TRC20',
        'LTC': 'LTC',
        'ETH': 'ERC20',
        'TRX': 'TRC20',
        'XMR': 'XMR',
        'SOL': 'SOL',
    }

    deposit_address = coin_addresses[coin]

    embed = discord.Embed(title="Payment Details", color=0xB4610C)
    embed.add_field(name="Amount with fees", value=str(crypto_amount), inline=False)
    embed.add_field(name="Network", value=str(coin_networks[coin]), inline=False)
    embed.add_field(name="Fee applied", value=str(coin_fees[coin]), inline=False)
    embed.add_field(name="Address", value=str(deposit_address), inline=False)
    embed.set_footer(text="Please send the exact amount to the address above, if you send a different amount your payment will not be processed correctly by our automated system.")
    embed.set_thumbnail(url="https://i.imgur.com/hssTBxK.png")
    
    payment_request_time = time.time()

    # Create the buttons
    verify_with_txid_button = VerifyWithTxidButton(ctx, order_id, crypto_amount, coin, quantity, variant_title, total_price, payment_request_time, deposit_address)
    manual_delivery_button = ManualDeliveryButton(ctx, order_id, crypto_amount, coin, quantity, variant_title, total_price, payment_request_time, verify_with_txid_button)

    view = discord.ui.View(timeout=None)
    view.add_item(verify_with_txid_button)
    view.add_item(CancelButton())
    view.add_item(manual_delivery_button)


    # Send a message with the View
    message = await channel.send(embed=embed, view=view)
    return message

    # Log the transaction as UNPAID
async def create_binance_payment(ctx, interaction, variant_title, variant_price, quantity, total_price, coin, order_id):
    channel = bot.get_channel(ctx.channel_id)


    print(f"Coin: {coin}")  # Add this line
    await bot.get_channel(ctx.channel_id).edit(topic=f"Order ID: {order_id}")

    # Get the current price of the coin in your base currency (e.g., USD)
    if coin == 'USDT':
        coin_price = 1
    else:
        coin_price = binance_client.get_avg_price(symbol=f'{coin}USDT')['price']

    # Generate a unique price variation
    unique_price_variation = round(generate_price(total_price, float(coin_price)), 5)

    # Specify the address for each coin
    coin_addresses = {
        'USDT': 'TGZCdKmQWDcsUm7TJBdQ9YmzpgQ9uPquCS',
        'LTC': 'LUFCDb7zb8AHWHNrrk1s5AwD4oWrKTYN1G',
        'ETH': '0xd10c6cc87e7fdba828df1aa4229ce1733874fe5b',
        'TRX': 'TGZCdKmQWDcsUm7TJBdQ9YmzpgQ9uPquCS',
        'XMR': '87kHE7SW9gFbNFMgRMhJtqjgcyFvTKb3fUCvpYSYnq1URKXKa79rNH29w9TCDykKVsQhgf3XXPmiHEw2y1BvMsLJ7ac4wqE',
        'SOL': 'DUgiggZZaW1rvP2zzuTZ146mF2Kfte1vaYenKhmhGZnN',
        'BTC': '13Truwo4YRsTEKq7m5ieRvSSoisjiL98Aj'
    }
    coin_networks = {
        'USDT': 'TRC20',
        'LTC': 'LTC',
        'ETH': 'ERC20',
        'TRX': 'TRC20',
        'XMR': 'XMR',
        'SOL': 'SOL',
        'BTC': 'BTC'
    }

    deposit_address = coin_addresses[coin]

    embed = discord.Embed(title="Payment Details", color=0xB4610C)
    embed.add_field(name="Amount", value=str(unique_price_variation), inline=False)
    embed.add_field(name="Network", value=str(coin_networks[coin]), inline=False)
    embed.add_field(name="Binance ID", value="425139933", inline=False)
    embed.set_footer(text="Please send the exact amount to the address above, if you send a different amount your payment will not be processed correctly by our automated system.")
    embed.set_thumbnail(url="https://i.imgur.com/hssTBxK.png")
    embed2 = discord.Embed(title="How do i get my Order ID", color=0xB4610C)
    embed2.add_field(name="Step 1", value="After you paid, you will see something similar to the photo below", inline=False)
    file = discord.File("orderid.png", filename="image.png")
    embed2.set_image(url="attachment://image.png")
    embed2.add_field(name="Step 2", value="Copy the Order ID and paste it in the chat.", inline=False)
    embed2.add_field(name="Step 3", value="Wait for the system to verify your payment.", inline=False)
    embed2.add_field(name="Step 4", value="If you have any issues, please contact our support team.", inline=False)
    


    payment_request_time = time.time()

    # Create the buttons
    verify_with_txid_button = VerifyWithTxidButton(ctx, order_id, unique_price_variation, coin, quantity, variant_title, total_price, payment_request_time, deposit_address)
    manual_delivery_button = ManualDeliveryButton(ctx, order_id, unique_price_variation, coin, quantity, variant_title, total_price, payment_request_time, verify_with_txid_button)
    binance_pay_button = BinancePayButton(ctx, order_id, unique_price_variation, coin, quantity, variant_title, total_price, payment_request_time)

    view = discord.ui.View(timeout=None)
    view.add_item(binance_pay_button)
    view.add_item(CancelButton())
    view.add_item(manual_delivery_button)

    # Send a message with the View
    message = await channel.send(embed=embed, view=view)
    await channel.send(file=file, embed=embed2)
    return message  # return the message object

    # Log the transaction as UNPAID
class ManualDeliveryButton(discord.ui.Button):
    def __init__(self, ctx, order_id, crypto_amount, coin, quantity, variant_title, total_price, payment_time, verify_with_txid_button):
        super().__init__(style=discord.ButtonStyle.danger, label="Manual Delivery")
        self.ctx = ctx
        self.order_id = order_id
        self.crypto_amount = crypto_amount
        self.coin = coin
        self.quantity = quantity
        self.variant_title = variant_title
        self.total_price = total_price
        self.payment_time = payment_time
        self.channel = bot.get_channel(ctx.channel_id)
        self.verify_with_txid_button = verify_with_txid_button

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id not in admin_ids:
            await interaction.response.send_message("You are not authorized to use this button.", ephemeral=True)
            return

        # Deliver the keys
        delivered_keys = await deliver_key(self.ctx, self.variant_title, self.quantity, self.order_id, self.total_price, self.crypto_amount, self.coin)

        # Log the transaction
        log_transaction(self.ctx.user.id, self.quantity, self.variant_title, time.time(), self.total_price, 'PAID', self.order_id, None, self.crypto_amount, self.coin, keys=delivered_keys, binanceid=None)

        await interaction.response.send_message("The keys have been delivered.", ephemeral=True)
        await self.channel.send("This channel will be deleted in 2 minutes.")
        await asyncio.sleep(120)
        await self.channel.delete()

        # Disable the VerifyWithTxidButton
        self.verify_with_txid_button.disabled = True
        await interaction.message.edit(view=self.view_instance)

class QuantitySelect(discord.ui.Select):
    def __init__(self, ctx, variant_stock):
        options = [
            discord.SelectOption(label=str(i), value=str(i))
            for i in range(1, variant_stock + 1)
        ]
        super().__init__(placeholder='Select a quantity', min_values=1, max_values=1, options=options)
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        quantity = int(self.values[0])
        await interaction.response.send_message(f"You selected: {quantity}", ephemeral=True)
        self.ctx.quantity = quantity      
        
@bot.command(help="Converts a given amount in USD to LTC", aliases=['ltc'], brief="Converts USD to LTC", name='ltc', description="Converts a given amount in USD to LTC")
async def ltc(ctx, amount: float):
    async with ctx.typing():
        await asyncio.sleep(1)
    # Get the current price of LTC in USD
    ltc_price = binance_client.get_avg_price(symbol='LTCUSDT')['price']

    # Convert the amount to LTC
    ltc_price = float(binance_client.get_avg_price(symbol='LTCUSDT')['price'])
    ltc_amount = amount / ltc_price

    # Send a message with the converted amount
    await ctx.send(f"{amount} USD is approximately {ltc_amount} LTC.")
   


def log_transaction(user_id, key_amount, key_variant, payment_request_time, money_amount, status, order_id, txid, crypto_amount, coin, keys, binanceid):

    if os.stat('transactions.json').st_size == 0:
        transactions = []
    else:
        # Read the existing transactions
        with open('transactions.json', 'r') as f:
            transactions = json.load(f)

    # Find the transaction for the user and update its status
    for transaction in transactions:
        if 'payment_request_time' in transaction and transaction['user_id'] == user_id and transaction['key_variant'] == key_variant and transaction['payment_request_time'] == payment_request_time:
            transaction['status'] = status
            if keys is not None:
                transaction['keys'] = keys
            break
    else:
        # If the transaction is not found, append a new transaction
        transactions.append({
            'user_id': user_id,
            'key_amount': key_amount,
            'key_variant': key_variant,
            'payment_request_time': payment_request_time,
            'money_amount': money_amount,
            'status': status,
            'order_id': order_id,
            'crypto_amount': crypto_amount,
            'coin': coin,
            'keys': keys,
            'txid': txid,
            'binanceid': binanceid
        })

    # Write the transactions back to the file
    with open('transactions.json', 'w') as f:
        json.dump(transactions, f, indent=4)

class BinancePayButton(discord.ui.Button):
    def __init__(self, ctx, order_id, crypto_amount, coin, quantity, variant_title, total_price, payment_time):
        super().__init__(style=discord.ButtonStyle.green, label="Binance Pay")
        self.ctx = ctx
        self.order_id = order_id
        self.crypto_amount = crypto_amount
        self.coin = coin
        self.quantity = quantity
        self.variant_title = variant_title
        self.total_price = total_price
        self.payment_time = payment_time
        self.channel = bot.get_channel(ctx.channel_id)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("Please enter your Binance Pay order ID:")
        self.binance_order_id = await get_user_response(self.ctx)

        # Read the existing transactions
        with open('transactions.json', 'r') as f:
            transactions = json.load(f)

        # Check if the Binance ID is already in the transactions
        for transaction in transactions:
            if 'binanceid' in transaction and transaction['binanceid'] == self.binance_order_id:
                await interaction.channel.send("This Binance ID has already been used. Please contact an admin for assistance.")
                await interaction.channel.send("<@707513459205734470> A user tried to use a Binance ID that has already been used.")  # Replace admin_id with the actual admin's ID
                return

        await self.verify_binance_pay(interaction, self.binance_order_id, self.total_price)

    async def verify_binance_pay(self, interaction, order_id, total_price):
        # Get the current timestamp
        timestamp = int(time.time() * 1000)

        # Create the query string
        query_string = f"timestamp={timestamp}"

        # Create the signature
        signature = hmac.new(api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

        # Create the headers
        headers = {
            'X-MBX-APIKEY': api_key
        }

        # Send the request
        response = requests.get('https://api.binance.com/sapi/v1/pay/transactions', headers=headers, params={
            'timestamp': timestamp,
            'signature': signature
        })

        # Check if the request was successful
        if response.status_code == 200:
            transactions = response.json()['data']

            # Check each transaction
            for transaction in transactions:
                # If the order ID and amount match, deliver the keys and log the transaction
                if transaction['orderId'] == order_id:
                    if transaction['transactionTime'] / 1000 < self.payment_time:
                        await interaction.channel.send("The transaction is older than the payment request. Please send a new payment request.")
                        pprint(transaction)
                        return

                    await interaction.channel.send("Transaction confirmed.")

                    # Deliver the keys
                    delivered_keys = await deliver_key(self.ctx, self.variant_title, self.quantity, self.order_id, self.total_price, self.crypto_amount, self.coin)

                    # Log the transaction
                    log_transaction(self.ctx.user.id, self.quantity, self.variant_title, time.time(), self.total_price, 'PAID', self.order_id, transaction['orderId'], self.crypto_amount, self.coin, keys=delivered_keys, binanceid=self.binance_order_id)

                    # Send a message to the channel
                    await interaction.channel.send("This channel will be deleted in 2 minutes.")
                    await asyncio.sleep(120)
                    await self.channel.delete()

                    return
            else:
                await interaction.followup.send("No order found with the given ID and amount. Please try again in 1 minute.")
        else:
            print("Failed to fetch transactions. Error: ", response.json())
        
async def deliver_key(ctx, variant_title, quantity, order_id, total_price, crypto_amount, coin):
    channel = bot.get_channel(ctx.channel_id)
    with open('keys.json', 'r') as f:
        keys = json.load(f)

    # Get the keys for the variant
    for product in keys.values():
        if variant_title in product:
            variant_keys = product[variant_title]['keys']
            break
    else:
        await channel.send("No keys available for this variant.")
        return

    delivered_keys = []  # List to store the delivered keys

    if variant_keys:
        # Send the keys to the user
        for _ in range(int(quantity)):
            if variant_keys:
                # Add the key to the delivered keys
                delivered_keys.append(variant_keys[0])

                # Remove the sent key
                variant_keys.pop(0)
            else:
                await channel.send("No more keys available for this variant.")
                break

        # Update the keys in the keys dictionary
        for product in keys.values():
            if variant_title in product:
                product[variant_title]['keys'] = variant_keys
                break

        # Update the JSON file
        with open('keys.json', 'w') as f:
            json.dump(keys, f)

        # Create an embed
        embed = discord.Embed(title="Thank you for your purchase!", description="Here are your keys:", color=0xB4610C)
        embed.set_thumbnail(url="https://i.imgur.com/hssTBxK.png")  # Replace with the URL of your thumbnail
        embed.add_field(name="Keys", value="\n".join(delivered_keys), inline=False)
        embed.add_field(name="Note", value="If you need or have lost your keys, you can use the /keys command with your Order ID as a parameter and the bot will send the keys back to you!", inline=False)        
        embed.set_footer(text="Enjoy your product!")
        embed2 = discord.Embed(title="Order Details", color=0xB4610C)
        embed2.add_field(name="Order ID", value=order_id, inline=False)
        embed2.add_field(name="Amount paid", value=str(crypto_amount), inline=False)
        embed2.add_field(name="Coin", value=str(coin), inline=False)
        embed2.add_field(name="Total price(USD)", value=total_price, inline=False)
        embed2.add_field(name="Keys", value="\n".join(delivered_keys), inline=False)
        embed2.set_thumbnail(url="https://i.imgur.com/hssTBxK.png")
        
        # Send the embed
        await channel.send(embed=embed)
        await channel.send(embed=embed2)
        
        embed_order_details = discord.Embed(title="Order Details", color=0xB4610C)
        embed_order_details.add_field(name="Order ID", value=order_id, inline=False)
        embed_order_details.add_field(name="Amount paid", value=str(crypto_amount), inline=False)
        embed_order_details.add_field(name="Coin", value=str(coin), inline=False)
        embed_order_details.add_field(name="Total price(USD)", value=total_price, inline=False)
        embed_order_details.add_field(name="Keys", value="\n".join(delivered_keys), inline=False)
        embed_order_details.set_thumbnail(url="https://i.imgur.com/hssTBxK.png")

        await ctx.user.send(embed=embed_order_details)
    else:
        await channel.send("No keys available for this variant.")

    return delivered_keys


class ChangeQuantityButton(discord.ui.Button):
    def __init__(self, ctx, variant_title, variant_price, variant_stock):
        super().__init__(style=discord.ButtonStyle.secondary, label="Change Quantity")
        self.ctx = ctx
        self.variant_title = variant_title
        self.variant_price = variant_price
        self.variant_stock = variant_stock

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("Okay, let's change the quantity.", ephemeral=True)
        await ask_quantity(self.ctx, interaction, self.variant_title, self.variant_price, self.variant_stock)


@bot.command(name="close", help="Closes the current ticket", aliases=['end'], brief="Closes the current ticket", description="Closes the current ticket")
async def close(ctx):
    if ctx.channel.name.startswith("ticket-"):
        await ctx.send("This channel will be deleted in 10 seconds.")
        await asyncio.sleep(10)
        if ctx.channel is not None:  # Check if the channel exists
            await ctx.channel.delete()
        else:
            print("Channel does not exist or has already been deleted.")
    else:
        await ctx.send("This command can only be used in a ticket channel.")
    return


class ManageProductSelect(discord.ui.Select):
    def __init__(self, ctx, options):
        super().__init__(
            placeholder="Select a product", min_values=1, max_values=1, options=options
        )
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"You selected: {self.values[0]}", ephemeral=True
        )
        await manage_variant(self.ctx, interaction, self.values[0])
class ManageActionSelect(discord.ui.Select):
    def __init__(self, ctx, product_name, variant_name):
        super().__init__(
            placeholder="Select an action", 
            min_values=1, 
            max_values=1, 
            options=[
                discord.SelectOption(label="Edit keys", value="keys"),
                discord.SelectOption(label="Edit price", value="price")
            ]
        )
        self.ctx = ctx
        self.product_name = product_name
        self.variant_name = variant_name
        

    async def callback(self, interaction: discord.Interaction):
        
        action = self.values[0]
        if action == "keys":
            await interaction.response.send_message(f"You selected: {action}", ephemeral=True)
            await update_keys(self.ctx, interaction, self.product_name, self.variant_name)
        elif action == "price":
            await interaction.response.send_message(f"You selected: {action}", ephemeral=True)
            await update_price(self.ctx, interaction, self.product_name, self.variant_name)
        


class ManageVariantSelect(discord.ui.Select):
    def __init__(self, ctx, options, product_name):
        super().__init__(placeholder='Select a variant', min_values=1, max_values=1, options=options)
        self.ctx = ctx
        self.product_name = product_name

    async def callback(self, interaction: discord.Interaction):
        variant_name = self.values[0]
        with open('keys.json', 'r') as f:
            products = json.load(f)

        # Get the current keys for the selected variant
        current_keys = products[self.product_name][variant_name]['keys']

        # Create a Select with the options
        select = ManageActionSelect(self.ctx, self.product_name, variant_name)

        # Create a View and add the Select to it
        view = discord.ui.View(timeout=None)
        view.add_item(select)
        await interaction.response.send_message(f"You selected: {variant_name}", ephemeral=True)
        # Create an embed
        embed = discord.Embed(title="Stock Management", color=0xB4610C)
        embed.add_field(name=f"Current keys for {self.product_name} - {variant_name}", value=', '.join(current_keys), inline=False)
        embed.add_field(name="Action", value="Please select an action from the dropdown below.", inline=False)
        
        # Send a message with the View and the embed
        await interaction.followup.send(embed=embed, view=view)

async def update_price(ctx, interaction, product_name, variant_name):
   # Ask the user for the new price
   await ctx.send("Please enter the new price:")

   # Handle the user's response and store the price
   while True:
       price_message = await get_user_response(ctx)
       if price_message.isdigit() or ('.' in price_message and price_message.replace('.', '', 1).isdigit()):
           new_price = float(price_message)
           break
       else:
           await ctx.send("Incorrect value. Please enter a number.")

   # Read the product details from the JSON file
   with open('keys.json', 'r') as f:
       products = json.load(f)

   # Update the price for the selected variant
   products[product_name][variant_name]['price'] = new_price

   # Write the updated products back to the JSON file
   with open('keys.json', 'w') as f:
       json.dump(products, f)

   await ctx.send(f"Updated the price for {product_name} - {variant_name}.")

@bot.command(name='add', help="Add a new product to the shop", aliases=['create'], brief="Add a new product", description="Add a new product to the shop", usage="/add <product> <variant> <price> <keys>")
@commands.check(is_admin)
async def add_product(ctx, product: str, variant: str, price: float, keys: str):
    # Split the keys string into a list of keys
    keys_list = keys.split(',')
    await ctx.defer()

    # Read the existing products from the JSON file
    with open('keys.json', 'r') as f:
        products = json.load(f)

    # Add the new product and its variant
    if product not in products:
        products[product] = {}
    products[product][variant] = {
        'price': price,
        'keys': keys_list
    }

    # Write the updated products back to the JSON file
    with open('keys.json', 'w') as f:
        json.dump(products, f, indent=4)

    await ctx.send(f"Added {variant} of {product} with price {price} and keys {keys}")
@bot.command(name='remove', help="Remove a product from the shop", aliases=['delete'], brief="Remove a product", description="Remove a product from the shop", usage="/remove <product>")
@commands.check(is_admin)
async def remove_product(ctx, product: str):
    await ctx.defer()

    # Read the existing products from the JSON file
    with open('keys.json', 'r') as f:
        products = json.load(f)

    # Check if the product exists
    if product in products:
        # Remove the product
        del products[product]

        # Write the updated products back to the JSON file
        with open('keys.json', 'w') as f:
            json.dump(products, f, indent=4)

        await ctx.send(f"Removed {product} from the shop.")
    else:
        await ctx.send(f"{product} does not exist in the shop.")
        
async def update_keys(ctx, interaction, product_name, variant_name):
    # Ask the user for the new keys
    await ctx.send("Please enter the new keys, separated by commas:")

    # Handle the user's response and store the keys
    keys_message = await get_user_response(ctx)
    new_keys = keys_message.split(',')

    # Read the product details from the JSON file
    with open('keys.json', 'r') as f:
        products = json.load(f)

    # Update the keys for the selected variant
    products[product_name][variant_name]['keys'] = new_keys

    # Write the updated products back to the JSON file
    with open('keys.json', 'w') as f:
        json.dump(products, f, indent=4)

    await ctx.send(f"Updated the keys for {product_name} - {variant_name}.")


@bot.command(name="stock", help="Manage the stock of product keys", aliases=['keys'], brief="Manage product keys", description="Manage the stock of product keys")
@commands.check(is_admin)
async def stock(ctx):
    await ctx.defer()

    # Read products from the JSON file
    with open('keys.json', 'r') as f:
        products = json.load(f)

    # Create a list of SelectOptions for the dropdown
    options = [
        discord.SelectOption(label=product, value=product)
        for product in products
    ]

    # Create a Select with the options
    select = ManageProductSelect(ctx, options)

    # Create a SelectView and add the Select to it
    view = discord.ui.View(timeout=None)
    view.add_item(select)


    # Create an embed
    embed = discord.Embed(title="Product Selection", description="Please select a product to manage its stock.", color=0xB4610C)

    # Send a message with the SelectView and the embed
    await ctx.send(embed=embed, view=view)

async def manage_variant(ctx, interaction, product_name):
    # Read the product details from the JSON file
    with open('keys.json', 'r') as f:
        products = json.load(f)

    if product := products.get(product_name, {}):
        # Create a list of SelectOptions for the dropdown
        options = [
            discord.SelectOption(
                label=variant, 
                value=variant,
                description=f"Stock: {len(product[variant]['keys'])}\nPrice: {product[variant]['price']}"
            )
            for variant in product
        ]

        # Create a Select with the options
        select = ManageVariantSelect(ctx, options, product_name)

        # Create a SelectView and add the Select to it
        view = discord.ui.View(timeout=None)
        view.add_item(select)
        # Create an embed
        embed = discord.Embed(title=f"{product_name}", color=0xB4610C)
        for variant, details in product.items():
            embed.add_field(name=variant, value=f"Stock: {len(details['keys'])}\nPrice: {details['price']}", inline=False)

        # Send a message with the SelectView and the embed
        await interaction.followup.send(embed=embed, view=view)
async def get_tx_confirmations(coin, txid):
    url = f"https://api.blockcypher.com/v1/{coin}/main/txs/{txid}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                return None
            
async def check_tronscan_txid(txid, payment_request_time, channel):
    base_url = "https://apilist.tronscanapi.com/api/transaction-info"
    response = requests.get(f"{base_url}?hash={txid}")
    if response.status_code == 200:
        data = response.json()
        confirmations = data.get('confirmations', 0)
        if confirmations > 1:
            print(f"Success! The transaction has {confirmations} confirmations.")
        else:
            print(f"The transaction has only {confirmations} confirmation(s).")
        
        # Get the timestamp
        timestamp = data.get('timestamp', None)
        if timestamp is not None:
            print(f"The transaction timestamp is {timestamp}")
        else:
            print("Timestamp not found in the transaction data.")
        
        # Check if the transaction timestamp is greater than the payment request time
        if timestamp is not None and timestamp / 1000 < payment_request_time:
            print("The transaction is older than the payment request.")
            await channel.send("The transaction is older than the payment request.")
            return False

        # Check if the to_address is valid
        trc20_info = data.get('trc20TransferInfo', [{}])
        if trc20_info:
            to_address = trc20_info[0].get('to_address', None)
            if to_address == 'TGZCdKmQWDcsUm7TJBdQ9YmzpgQ9uPquCS':
                print("Valid transaction.")
                return True
            elif to_address == 'TE7L1693VNLqLeW1begEunDyY2GUe6m1Jr':
                print("Valid transaction.")
                return True
            else:
                print("Invalid transaction.")
                return False
        else:
            print("TRC20 transfer info not found in the transaction data.")
            await channel.send("TRC20 transfer info not found in the transaction data.")
            return False
    else:
        print(f"Request failed with status code {response.status_code}")
        return False



class VerifyWithTxidButton(discord.ui.Button):
    def __init__(self, ctx, order_id, crypto_amount, coin, quantity, variant_title, total_price, payment_time, deposit_address):
        super().__init__(style=discord.ButtonStyle.green, label="Verify with TxID")
        self.ctx = ctx
        self.order_id = order_id
        self.crypto_amount = crypto_amount
        self.coin = coin
        self.quantity = quantity
        self.variant_title = variant_title
        self.total_price = total_price
        self.payment_time = payment_time
        self.deposit_address = deposit_address
        self.channel = bot.get_channel(ctx.channel_id)
        self.view_instance = discord.ui.View(timeout=None) # Set the timeout to None
        self.view_instance.add_item(self)
        self.payment_request_time = payment_time

    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(title="How to find your TxID", color=0xB4610C)
        embed.set_thumbnail(url="https://i.imgur.com/hssTBxK.png")
        embed.add_field(name="Binance", value="Go to Wallet > Transaction History > Withdraw > Copy Transaction ID (TxID)", inline=False)
        embed.add_field(name="Coinbase", value="Go to Accounts > Select Wallet > Transactions > Transaction Details > Transaction ID", inline=False)
        embed.add_field(name="Kraken", value="Go to Funding > Withdrawal > View > TxID", inline=False)
        embed.set_footer(text="If you are using a different platform, please search for how to find your TxID online.")
        await interaction.response.send_message(embed=embed)
        await self.channel.send("Please enter your transaction ID (TxID):")

        while True:
            txid = await get_user_response(self.ctx)
            with open('transactions.json', 'r') as f:
                try:
                    transactions = json.load(f)
                except json.JSONDecodeError:
                    transactions = []

                for transaction in transactions:
                    if transaction['txid'] == txid and transaction['status'] == 'PAID':
                        await self.channel.send("This transaction ID has already been used. Please contact an admin for assistance.")
                        await self.channel.send("<@572959864423448580> A user tried to use a transaction ID that has already been used.")
                        return

                server_time = binance_client.get_server_time()
                time_difference = server_time['serverTime'] - int(time.time() * 1000)

                timestamp = int(time.time() * 1000) + time_difference
                deposits = binance_client.get_deposit_history(coin=self.coin, status=1, recvWindow=10000, timestamp=timestamp)
                for deposit in deposits:
                    if deposit['txId'] == txid:
                        if deposit['insertTime'] / 1000 < self.payment_request_time:
                            await self.channel.send("The TxID is older than the payment request. Please send a new payment request.")
                            return
                        print(f"Deposit found with TxID {txid} and amount {deposit['amount']}.")
                        await self.channel.send("Transaction verified successfully!")
                        delivered_keys = await deliver_key(self.ctx, self.variant_title, self.quantity, self.order_id, self.total_price, self.crypto_amount, self.coin)
                        log_transaction(self.ctx.user.id, self.quantity, self.variant_title, time.time(), self.total_price, 'PAID', self.order_id, txid, self.crypto_amount, self.coin, keys=delivered_keys, binanceid=None)
                        await self.channel.send("This channel will be deleted in 2 minutes.")
                        await asyncio.sleep(120)
                        await self.channel.delete()
                        return
                    
                
                await self.channel.send("No transaction found with the provided TxID yet, checking blockchain for txid.")
                await asyncio.sleep(5)

                data = await get_tx_confirmations(self.coin.lower(), txid)

                if data is not None:
                    deposit_address_found = False
                    for output in data['outputs']:
                        if self.deposit_address in output['addresses']:
                            deposit_address_found = True
                            await self.channel.send("Transaction verified successfully!")
                            delivered_keys = await deliver_key(self.ctx, self.variant_title, self.quantity, self.order_id, self.total_price, self.crypto_amount, self.coin)
                            log_transaction(self.ctx.user.id, self.quantity, self.variant_title, time.time(), self.total_price, 'PAID', self.order_id, txid, self.crypto_amount, self.coin, keys=delivered_keys, binanceid=None)
                            await self.channel.send("This channel will be deleted in 2 minutes.")
                            await asyncio.sleep(120)
                            await self.channel.delete()
                            return
                    if not deposit_address_found:
                        await self.channel.send("The deposit address was not found in the blockchain data. Please enter a new TxID.")
                else:
                    await self.channel.send("No transaction found with the provided TxID on the blockchain. Checking Tronscan...")
                    
                    result = await check_tronscan_txid(txid, self.payment_request_time, self.channel)
                    if result:
                        
                        delivered_keys = await deliver_key(self.ctx, self.variant_title, self.quantity, self.order_id, self.total_price, self.crypto_amount, self.coin)
                        log_transaction(self.ctx.user.id, self.quantity, self.variant_title, time.time(), self.total_price, 'PAID', self.order_id, txid, self.crypto_amount, self.coin, keys=delivered_keys, binanceid=None)
                        await self.channel.send("This channel will be deleted in 2 minutes.")
                        await asyncio.sleep(120)
                        await self.channel.delete()

                    else:
                        await self.channel.send("The transaction was not found on the blockchain. Pleasewait a few minutes and try verifying again. \nIf the problem persists, contact support for manual verification.")
                        return
                    

@bot.command(name="keys", help="Fetches the keys for a given order ID", aliases=['key'], brief="Fetches keys for an order ID", description="Fetches the keys for a given order ID", usage="/keys <order ID>")
async def keys(ctx, order_id: str):
    await ctx.defer()
    async with ctx.typing():
        await asyncio.sleep(0.5)
    # Read the transactions from the JSON file
    with open('transactions.json', 'r') as f:
        if f.read().strip():
            f.seek(0)  # reset file read position
            transactions = json.load(f)
        else:
            transactions = []

    # Find the transaction with the matching order ID and user ID
    for transaction in transactions:
        if transaction['order_id'] == order_id:
            # Check if 'keys' is a list
            if isinstance(transaction.get('keys'), list):
                # Send the keys to the user
                embed = discord.Embed(title="Here are your keys:", color=0xB4610C)
                embed.set_thumbnail(url="https://i.imgur.com/hssTBxK.png")
                embed.add_field(name="Keys", value="\n".join(transaction['keys']), inline=False)
                embed.set_footer(text="Enjoy your product!")
                await ctx.send("Your keys have been sent to you via dm")
                await ctx.author.send(embed=embed)
            else:
                await ctx.send("No keys found for the given order ID.")
            return
    
        

    # If no matching transaction is found, send an error message
    await ctx.send("No keys found for the given order ID.")
@bot.command( help="Purges a given amount of messages", aliases=['clear'], brief="Purges messages", description="Purges a given amount of messages", usage="/purge <amount>")
@commands.has_permissions(manage_messages=True)  # Only allow users with the 'manage_messages' permission to use this command
async def purge(ctx, amount: int):
    await ctx.channel.purge(limit=amount+1)  # +1 to include the purge command itself

class BuyButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.green, label="Buy")

    async def callback(self, interaction: discord.Interaction):
        # Read the current ticket numbers from the JSON file
        with open('tickets.json', 'r') as f:
            ticket_numbers = json.load(f)

        # Generate the new ticket number
        new_ticket_number = f"ticket-{len(ticket_numbers) + 1}"

        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True)
        }

        # Get the category
        category_id = '1185686453070610544'  # Replace with your category ID
        category = discord.utils.get(guild.categories, id=int(category_id))

        # Create the new channel under the category
        ticket_channel = await guild.create_text_channel(name=new_ticket_number, overwrites=overwrites, category=category)

        # Append the new ticket number to the list and write it back to the JSON file
        ticket_numbers.append(new_ticket_number)
        with open('tickets.json', 'w') as f:
            json.dump(ticket_numbers, f)

        # Send a message to the user with a link to the ticket channel
        await interaction.response.send_message(f"Ticket created successfully! [Click here to view your ticket.](https://discord.com/channels/{guild.id}/{ticket_channel.id})", ephemeral=True)

        # Pass the ticket_channel to the buy function
        await buy(interaction, ticket_channel)  # Replace with the name of your buy command 
        
@bot.event
async def on_ready():
    print("Bot is ready and listening!")

    await bot.user.edit(username='SuperBot')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="the market", url="https://www.youtube.com/watch?v=dQw4w9WgXcQ", details="Watching the market", state="Watching the market", emoji={'name': '🛒'}))
    # Read the channel and message IDs from the JSON file
    with open('channel_message_ids.json', 'r') as f:
        ids = json.load(f)
    
    guild = bot.guilds[0]  # Replace with the guild where you want to create the channel

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False)
    }
    if ids['channel_id'] is not None:
    # The channel already exists, get it
        channel = bot.get_channel(ids['channel_id'])
    else:
        # The channel doesn't exist, create it
        category = discord.utils.get(guild.categories, name='Tickets')  # Replace with your category name
        channel = await guild.create_text_channel('How to Buy 🛒', category=category, overwrites=overwrites)

        # Store the channel ID in the JSON file
        ids['channel_id'] = channel.id
        with open('channel_message_ids.json', 'w') as f:
            json.dump(ids, f)
    embed = discord.Embed(title="How to Buy", color=0xB4610C, url="https://www.youtube.com/watch?v=dQw4w9WgXcQ", type="rich")
    embed.add_field(name="**__Disclaimer__**", value="This bot is for CRYPTO transactions only, if you would like to buy via paypal refer to the sellpass shop.", inline=False)

    embed.set_thumbnail(url="https://i.imgur.com/hssTBxK.png")
    embed.set_footer(text="Please note that we do not offer refunds. All sales are final.")
    view = discord.ui.View(timeout=None)
    view.add_item(BuyButton())

    if ids['message_id'] is not None:
        try:
            # The message already exists, edit it
            message = await channel.fetch_message(ids['message_id'])
            await message.edit(embed=embed, view=view)
        except discord.NotFound:
            # The message does not exist, send it
            message = await channel.send(embed=embed, view=view)
            # Store the new message ID in the JSON file
            ids['message_id'] = message.id
            with open('channel_message_ids.json', 'w') as f:
                json.dump(ids, f)
    else:
        # The message doesn't exist, send it
        message = await channel.send(embed=embed, view=view)
        # Store the message ID in the JSON file
        ids['message_id'] = message.id
        with open('channel_message_ids.json', 'w') as f:
            json.dump(ids, f)


        # Store the message ID in the JSON file
        ids['message_id'] = message.id
        with open('channel_message_ids.json', 'w') as f:
            json.dump(ids, f)



bot.run(os.getenv('bot_token'))
