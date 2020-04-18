
from pycc import *


global_addr = {
  "wif": "UsNHJsn9Axq63PwKoUM84RuUByjs83gCWrCixpQ7FGb8ifVQs58a",
  "addr": "RNZgNenJMp9UdxR6exxogjEzqqUT5F7hXC",
  "pubkey": "03997fec500b2405c234724269a59afa0750c3ce10b9240a74deb48b3a852d8b41"
}

schema_link = SpendBy("faucet.drip", 0, pubkey=global_addr['pubkey'])


schema = {
    "faucet": {
        "create": {
            "inputs": [
                Input(P2PKH())
            ],
            "outputs": [
                Output(schema_link)
            ],
        },
        "drip": {
            "inputs": [
                Input(schema_link)
            ],
            "outputs": [
                Output(schema_link, RelativeAmount(0) - 1000),
                Output(P2PKH())
            ]
        },
    }
}


def cc_eval(chain, tx_bin, nIn, eval_code):
    return CCApp(schema, eval_code, chain).cc_eval(tx_bin)
