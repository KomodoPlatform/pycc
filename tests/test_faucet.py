
from pycc.examples import faucet
from pycc import *

app = CCApp(faucet.schema)

keypair = {
    "wif": "UuKZRxAR4KYVSVKxgL8oKuyBku7bVhqbGk9onuaEzkXdaxgytpLB",
    "addr": "RWqrNbM3gUr4A9kX9sMXTRyRbviLsSbjAs",
    "pubKey": "038c3d482cd29f75ce997737705fb5287f022ded66093ee7d929aea100c5ef8a63"
}

input_addr = "RC4azc7YXeCjFokWoomZJLcKFarrsGWp6A"

txid_1 = "d21633ba23f70118185227be58a63527675641ad37967e2aa461559f577aec43"

create_tx = {
    "inputs": [
        {
            "txid": txid_1,
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
                "op_return": py2hex({"tx": "faucet.create"})
            }
        }
    ]
}

drip_tx = {
    "inputs": [
        {
            "txid": txid_1,
            "idx":0,
            "script": {
                "condition": {
                    "type": "eval-sha-256",
                    "code": "5F"
                }
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
            "amount": 0.1,
            "script": {
                "address": input_addr
            }
        },
        {
            "amount": 0,
            "script": {
                "op_return": py2hex({"tx": "faucet.drip"})
            }
        }
    ]
}


def test_validate_create():
    o = app._cc_eval({}, create_tx, 0, b"_")
    assert o == {
        "inputs": [{"address": input_addr, "txid": txid_1, "idx": 0}],
        "outputs": [{"amount": 1}]
    }


def test_validate_drip():
    o = app._cc_eval({}, drip_tx, 0, b'_')
    assert o == {
        "inputs": [{"idx": 0, "txid": txid_1}],
        "outputs": [{"amount": 1}, {"amount": 0.1, "address": input_addr}]
    }

