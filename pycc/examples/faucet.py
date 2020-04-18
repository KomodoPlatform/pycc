
from pycc import *



schema = {
    "faucet": {
        "create": {
            "inputs": [
                Input(P2PKH())
            ],
            "outputs": [
                Output(SpendBy("faucet.drip", 0)),
            ],
        },
        "drip": {
            "inputs": [
                Input(SpendBy("faucet.drip", 0))
            ],
            "outputs": [
                Output(SpendBy("faucet.drip", 0), RelativeAmount(0) - 1000),
                Output(P2PKH())
            ]
        },
    }
}
