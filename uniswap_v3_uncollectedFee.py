from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
import numpy as np

def query_uncollected_fees(tokenId: str) -> dict:
    """
    Returns the uncollected fees for a Uniswap v3 LP given liquidity is provided in an active range.

    Parameters
    ----------
    tokenId: Uniswap v3 NFT token ID

    Returns 
    -------
    dict, containing - 
    price ranges for LP, 
    current price, and, if possible, 
    token real reserves, and
    uncollected fees from LP.
    """
    sample_transport = RequestsHTTPTransport(
      url='https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3',
      verify=True, 
      retries=3)
  
    client = Client(transport=sample_transport)
    gql_string = f"""{{
      positions(where: {{id: {tokenId}}}) {{
        liquidity
        depositedToken0
        depositedToken1
        feeGrowthInside0LastX128
        feeGrowthInside1LastX128
        token0 {{
          symbol
          decimals
        }}
        token1 {{
          symbol
          decimals
        }}
        pool {{
          feeGrowthGlobal0X128
          feeGrowthGlobal1X128
          tick
          sqrtPrice
        }}
        tickLower {{
          tickIdx
          feeGrowthOutside0X128
          feeGrowthOutside1X128
        }}
        tickUpper {{
          tickIdx
          feeGrowthOutside0X128
          feeGrowthOutside1X128
        }}
      }}
    }}"""
    
    query = gql(gql_string)         
    response = client.execute(query)
    
    # tick and positions statistics
    tickLower = int(response['positions'][0]['tickLower']['tickIdx'])
    tickUpper = int(response['positions'][0]['tickUpper']['tickIdx'])
    tickCurrent = int(response['positions'][0]['pool']['tick'])
    liquidity = int(response['positions'][0]['liquidity'])
    token0_deposit = float(response['positions'][0]['depositedToken0'])
    token1_deposit = float(response['positions'][0]['depositedToken1'])

    #token0
    feeGrowthInside0LastX128 = int(response['positions'][0]['feeGrowthInside0LastX128'])
    feeGrowthGlobal0X128 = int(response['positions'][0]['pool']['feeGrowthGlobal0X128'])
    feeGrowthOutside0X128_tickLower = int(response['positions'][0]['tickLower']['feeGrowthOutside0X128'])
    feeGrowthOutside0X128_tickUpper = int(response['positions'][0]['tickUpper']['feeGrowthOutside0X128'])

    #token1
    feeGrowthInside1LastX128 = int(response['positions'][0]['feeGrowthInside1LastX128'])
    feeGrowthGlobal1X128 = int(response['positions'][0]['pool']['feeGrowthGlobal1X128'])
    feeGrowthOutside1X128_tickLower = int(response['positions'][0]['tickLower']['feeGrowthOutside1X128'])
    feeGrowthOutside1X128_tickUpper = int(response['positions'][0]['tickUpper']['feeGrowthOutside1X128'])

    # price computation at lower, current, and upper tick
    decimal_diff = float(response['positions'][0]['token0']['decimals']) - float(response['positions'][0]['token1']['decimals'])

    price_tickUpper = round(1.0001 ** tickUpper * (10 ** decimal_diff), 8)
    price_tickLower = round(1.0001 ** tickLower * (10 ** decimal_diff), 8)
    price_tickCurrent = round(1.0001 ** tickCurrent * (10 ** decimal_diff), 8)    

    # real reserves computation
    token0_real_reserves = (liquidity * (np.sqrt(1.0001 ** tickUpper) - np.sqrt(1.0001 ** tickCurrent)) 
                               / (np.sqrt(1.0001 ** tickUpper) * np.sqrt(1.0001 ** tickCurrent)))
    token0_real_reserves /= 10 ** int(response['positions'][0]['token0']['decimals'])
    token1_real_reserves = liquidity * (np.sqrt(1.0001 ** tickCurrent) -  np.sqrt(1.0001 ** tickLower))
    token1_real_reserves /= 10 ** int(response['positions'][0]['token1']['decimals'])

    print("Price Range for {}-{} LP: {:.8f} - {:.8f} {}/{}".format(response['positions'][0]['token0']['symbol'], 
                                                                   response['positions'][0]['token1']['symbol'],  
                                                                   1 / price_tickUpper, 
                                                                   1 / price_tickLower,
                                                                   response['positions'][0]['token0']['symbol'], 
                                                                   response['positions'][0]['token1']['symbol']))

    print("Current {}/{} Price: {:.8f}".format(response['positions'][0]['token0']['symbol'], 
                                               response['positions'][0]['token1']['symbol'],
                                               1 / price_tickCurrent))

    # check if LP is active and in-range
    if (liquidity != 0):
      if (tickUpper > tickCurrent > tickLower):
        feeCompute_token0 = (feeGrowthGlobal0X128 - feeGrowthOutside0X128_tickLower - feeGrowthOutside0X128_tickUpper - feeGrowthInside0LastX128) / (2 ** 128)
        feeCompute_token1 = (feeGrowthGlobal1X128 - feeGrowthOutside1X128_tickLower - feeGrowthOutside1X128_tickUpper - feeGrowthInside1LastX128) / (2 ** 128)

        feeUncollected_token0 = feeCompute_token0 * liquidity / (10 ** int(response['positions'][0]['token0']['decimals']))
        feeUncollected_token1 = feeCompute_token1 * liquidity / (10 ** int(response['positions'][0]['token1']['decimals']))

        print("The current tick is within the price range!")
        print("Current {} reserve: {:.8f}".format(response['positions'][0]['token0']['symbol'], token0_real_reserves))
        print("Current {} reserve: {:.8f}".format(response['positions'][0]['token1']['symbol'], token1_real_reserves))                                          
        print("Uncollected {} fees: {:.8f}".format(response['positions'][0]['token0']['symbol'], feeUncollected_token0))
        print("Uncollected {} fees: {:.8f}".format(response['positions'][0]['token1']['symbol'], feeUncollected_token1))

        return {'{}/{}_priceTickLower'.format(response['positions'][0]['token0']['symbol'],
                                              response['positions'][0]['token1']['symbol']): price_tickLower, 
                '{}/{}_priceTickUpper'.format(response['positions'][0]['token0']['symbol'], 
                                              response['positions'][0]['token1']['symbol']): price_tickUpper, 
                '{}/{}_priceTickCurrent'.format(response['positions'][0]['token0']['symbol'], 
                                                response['positions'][0]['token1']['symbol']): price_tickCurrent,
                '{}_deposit'.format(response['positions'][0]['token0']['symbol']): token0_deposit,
                '{}_deposit'.format(response['positions'][0]['token1']['symbol']): token1_deposit,
                '{}_realReserve'.format(response['positions'][0]['token0']['symbol']): token0_real_reserves,
                '{}_realReserve'.format(response['positions'][0]['token1']['symbol']): token1_real_reserves,
                '{}_uncollectedFees'.format(response['positions'][0]['token0']['symbol']): feeUncollected_token0,
                '{}_uncollectedFees'.format(response['positions'][0]['token1']['symbol']): feeUncollected_token1}

      # if LP is not within range
      else:
        print("The current tick is outside of the price range!")

        return {'{}/{}_priceTickLower'.format(response['positions'][0]['token0']['symbol'],
                                              response['positions'][0]['token1']['symbol']): price_tickLower, 
                '{}/{}_priceTickUpper'.format(response['positions'][0]['token0']['symbol'], 
                                              response['positions'][0]['token1']['symbol']): price_tickUpper, 
                '{}/{}_priceTickCurrent'.format(response['positions'][0]['token0']['symbol'], 
                                                response['positions'][0]['token1']['symbol']): price_tickCurrent}

    # if no more LP 
    else:
      print("Liquidity provider has exited position!")
      return {'{}/{}_priceTickLower'.format(response['positions'][0]['token0']['symbol'],
                                                response['positions'][0]['token1']['symbol']): price_tickLower, 
              '{}/{}_priceTickUpper'.format(response['positions'][0]['token0']['symbol'], 
                                                response['positions'][0]['token1']['symbol']): price_tickUpper, 
              '{}/{}_priceTickCurrent'.format(response['positions'][0]['token0']['symbol'], 
                                                  response['positions'][0]['token1']['symbol']): price_tickCurrent}

if __name__ == "__main__":
  xyz = query_uncollected_fees(tokenId=226230)
  print(xyz)