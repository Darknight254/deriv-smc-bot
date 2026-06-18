"""
Deriv API Client
Handles WebSocket connection to Deriv for live market data and trade execution
"""

import asyncio
import json
import logging
from typing import Optional, Callable, Dict, List
from datetime import datetime
import websockets

logger = logging.getLogger(__name__)


class DerivAPIClient:
    """
    WebSocket client for Deriv API
    """

    def __init__(
        self,
        api_token: str,
        app_id: str = "9305",
        api_url: str = "wss://ws.derivws.com/websockets/v3",
    ):
        """
        Initialize Deriv API Client
        
        Args:
            api_token: Deriv API token
            app_id: Deriv app ID
            api_url: WebSocket API URL
        """
        self.api_token = api_token
        self.app_id = app_id
        self.api_url = api_url
        
        self.ws = None
        self.message_id = 0
        self.is_connected = False
        self.request_callbacks: Dict[int, Callable] = {}
        self.subscriptions: Dict[str, Callable] = {}

    async def connect(self) -> bool:
        """
        Establish WebSocket connection to Deriv API
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.ws = await websockets.connect(self.api_url)
            self.is_connected = True
            logger.info("Connected to Deriv API")
            
            # Start message listener
            asyncio.create_task(self._listen_messages())
            
            # Authorize
            await self.authorize()
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to connect to Deriv API: {str(e)}")
            self.is_connected = False
            return False

    async def disconnect(self) -> None:
        """
        Disconnect from Deriv API
        """
        if self.ws:
            await self.ws.close()
            self.is_connected = False
            logger.info("Disconnected from Deriv API")

    async def authorize(self) -> bool:
        """
        Authorize with Deriv API using token
        
        Returns:
            True if authorization successful
        """
        try:
            request = {
                "authorize": self.api_token,
            }
            
            response = await self._send_request(request)
            
            if response.get("authorize"):
                logger.info("Authorized with Deriv API")
                return True
            else:
                logger.error(f"Authorization failed: {response}")
                return False
        
        except Exception as e:
            logger.error(f"Error during authorization: {str(e)}")
            return False

    async def subscribe_ticks(self, symbol: str, callback: Callable) -> None:
        """
        Subscribe to tick updates for a symbol
        
        Args:
            symbol: Trading symbol (e.g., 'R_100')
            callback: Async callback function to handle tick updates
        """
        try:
            request = {
                "ticks": symbol,
                "subscribe": 1,
            }
            
            msg_id = await self._send_request(request)
            self.subscriptions[f"ticks_{symbol}"] = callback
            
            logger.info(f"Subscribed to ticks for {symbol}")
        
        except Exception as e:
            logger.error(f"Error subscribing to ticks: {str(e)}")

    async def subscribe_candles(
        self,
        symbol: str,
        granularity: int,
        callback: Callable,
    ) -> None:
        """
        Subscribe to candle updates
        
        Args:
            symbol: Trading symbol
            granularity: Candle timeframe in seconds (60, 300, 900, etc.)
            callback: Async callback function to handle candle updates
        """
        try:
            request = {
                "candles": symbol,
                "granularity": granularity,
                "subscribe": 1,
            }
            
            msg_id = await self._send_request(request)
            self.subscriptions[f"candles_{symbol}_{granularity}"] = callback
            
            logger.info(f"Subscribed to {granularity}s candles for {symbol}")
        
        except Exception as e:
            logger.error(f"Error subscribing to candles: {str(e)}")

    async def buy_contract(
        self,
        symbol: str,
        amount: float,
        contract_type: str,
        duration: int,
        duration_unit: str = "m",
    ) -> Dict:
        """
        Place a buy order
        
        Args:
            symbol: Trading symbol (e.g., 'R_100')
            amount: Stake amount in currency units
            contract_type: 'CALL' or 'PUT'
            duration: Duration value
            duration_unit: 'm' for minutes, 's' for seconds
        
        Returns:
            Response from Deriv API
        """
        try:
            request = {
                "buy": 1,
                "price": amount,
                "parameters": {
                    "contract_type": contract_type,
                    "currency": "USD",
                    "symbol": symbol,
                    "duration": duration,
                    "duration_unit": duration_unit,
                },
            }
            
            response = await self._send_request(request)
            
            if response.get("buy"):
                logger.info(
                    f"Buy order placed: {symbol} {contract_type} "
                    f"Amount: ${amount} Duration: {duration}{duration_unit}"
                )
            else:
                logger.error(f"Buy order failed: {response}")
            
            return response
        
        except Exception as e:
            logger.error(f"Error placing buy order: {str(e)}")
            return {}

    async def get_contract_details(
        self,
        contract_id: str,
    ) -> Dict:
        """
        Get details of a specific contract
        
        Args:
            contract_id: Contract ID
        
        Returns:
            Contract details from Deriv API
        """
        try:
            request = {
                "proposal": 1,
                "contract_id": contract_id,
            }
            
            response = await self._send_request(request)
            return response
        
        except Exception as e:
            logger.error(f"Error getting contract details: {str(e)}")
            return {}

    async def _send_request(self, request: dict) -> dict:
        """
        Send request to Deriv API
        
        Args:
            request: Request dictionary
        
        Returns:
            Response from API
        """
        if not self.is_connected or not self.ws:
            logger.error("Not connected to Deriv API")
            return {}
        
        try:
            self.message_id += 1
            request["req_id"] = self.message_id
            
            await self.ws.send(json.dumps(request))
            logger.debug(f"Request sent: {request}")
            
            return {}
        
        except Exception as e:
            logger.error(f"Error sending request: {str(e)}")
            return {}

    async def _listen_messages(self) -> None:
        """
        Listen for messages from Deriv API
        """
        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse message: {message}")
        
        except Exception as e:
            logger.error(f"Message listener error: {str(e)}")
            self.is_connected = False

    async def _handle_message(self, data: dict) -> None:
        """
        Handle incoming message from Deriv API
        
        Args:
            data: Parsed message data
        """
        # Handle subscription updates
        if "tick" in data:
            for sub_key, callback in self.subscriptions.items():
                if "ticks" in sub_key:
                    try:
                        await callback(data["tick"])
                    except Exception as e:
                        logger.error(f"Error in tick callback: {str(e)}")
        
        elif "candle" in data:
            for sub_key, callback in self.subscriptions.items():
                if "candles" in sub_key:
                    try:
                        await callback(data["candle"])
                    except Exception as e:
                        logger.error(f"Error in candle callback: {str(e)}")
        
        logger.debug(f"Message handled: {data}")
