

# Example of a PYCC app implementing an asset / colored coin

# The asset transaction has a paramsification (params), which is a JSON object, which is stored in OP_RETURN in output 0.
# The whole transaction can be reconstructed from this params, which makes validation easier. It is
# no longer neccesary to read and scrutinise every aparamst of the transaction manually.

# Also, the protocols (params, transaction) are described using JSON compatible notation.


# There's a CC chain called "assets". Alice wants to create an asset. She constructs
# a "params" as in the "example_CREATE_params", to create her asset with 300 units. She
# calls the function `make_asset_tx` in her client to construct the transaction,
# signs it with her wallet, and sends it to the chain.

# Now alice wants to send units of her asset to Bob. She creates a params as in
# example_TRANSFER_params below, calls `make_asset_tx(params)` with her client, signs the
# tx, and broadcasts it.

from pycc import *


example_pubkey = "0295b0252f9660930fad823041b585c9d4512a2f21f4ab8a2ac550bd01fa4b7f8e"

# To create an asset
example_CREATE_params = {
    "create": {
        "txid": "...",
        "idx": 2,
        "address": "..."
    },
    "vout": [{
        "amount": 300,
        "pubKey": example_pubkey,
    }]
    "asset_id": ""  # Asset ID is hash($create)
}

# To transfer an asset
example_TRANSFER_params = {
    "vin": [{
        "txid": "...",
        "idx": "...",
        "pubKey": example_pubkey,
    }],
    "vout": [{
        "amount": 100,
        "pubKey": example_pubkey,
    }, {
        "amount": 200,
        "pubKey": example_pubkey,
    }],
    "asset_id": "..."
}

# The transaction is reconstructed from the params. The params are also stored in first vout.

def make_asset_tx(params):
    vins = []
    vouts = []

    if params.get('create'):
        # Some arbitrary VIN is required
        vins.append({
            "txid": params['create']['txid'],
            "idx": params['create']['idx'],
            "script": {
                "address": params['create']['address']
            }
        })
    else:
        for vin in params['vin']:
            vins.append({
                "txid": vin['txid'],
                "idx": vin['idx'],
                "script": {
                    "fulfillment": get_asset_cc(vin['pubKey'])
                }
            })

    for vout in params['vout']:
        vouts.append({
            "amount": 1,
            "script": {
                "fulfillment": get_asset_cc(vout['pubKey'])
            }
        })

    vouts.insert(0, {
        "amount": 0,
        "script": {
            # have MAX_OP_RETURN_RELAY (8k) bytes to work with
            "op_return": py_to_hex(params)
        }
    })

    return {"inputs": vins, "outputs": vouts}


# Transaction structure is easy to validate
def validate_asset_tx_structure(tx):
    params = get_tx_params(tx)
    reconstructed = make_asset_tx(params)
    assert tx == reconstructed


# Business logic of transaction validation
# requires fetching upstream transactions
def validate_asset_tx_io(tx):
    params = get_tx_params(tx)

    if params.get('create'):
        # It's a CREATE
        # No need to validate anything really.

    else:

        # Validate structure and asset ID of upstream TX,
        # and validate that money is not being created.

        total_in = 0

        for vin in tx['inputs']:
            utx = fetch_tx(vin['txid'])
            validate_asset_tx_structure(utx)
            assert get_asset_id(utx) == params['asset_id']

            utx_params = get_tx_params(utx)
            total_in += utx_params['vout'][vin['idx']]['amount']

        total_out = sum(vout['amount'] for vout in params['vout'])

        assert total_out <= total_in


def get_asset_id(tx):
    params = get_tx_params(tx)
    return params.get('asset_id') or get_txid(tx)


# Create an asset CC to be signed by a given pubkey.
def get_asset_cc(pubKey):
    return {
        "type": "threshold-sha-256",
        "threshold": 2,
        "subconditions": [
            {
                "type": "secp256k1-sha-256",
                "pubKey": pubKey,
            },
            {
                "type": "eval-sha-256",
                "code": "pycc-asset",
            },
        ]
    }

