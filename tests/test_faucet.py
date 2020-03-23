
from pycc.examples import faucet
from pycc import *

app = CCApp(faucet.schema)

def test_1():
    keys = call_hoek('secp256k1KeyPair', {})
    input_addr = "RC4azc7YXeCjFokWoomZJLcKFarrsGWp6A"
    tx = {
        "inputs": [
            {
                "txid": "d21633ba23f70118185227be58a63527675641ad37967e2aa461559f577aec43",
                "idx":0,
                "script": {
                    "address": input_addr
                }
            }
        ],
        "outputs": [
            {
                "amount": 1,
                "script": {
                    "condition": {
                        "type": "eval-sha-256",
                        "code": "5F"
                    }
                }
            },
            {
                "amount": 0,
                "script": {
                    "op_return": hex_encode(b"faucet.create").decode()
                }
            }
        ]
    }

    assert app.consume_tx({}, tx, 0, b"_") == {
        "inputs": [{"address": input_addr}],
        "outputs": [None]
    }

