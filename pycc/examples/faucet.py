
from pycc import *


def validate_faucet_drip(ctx, tx_data):
    # Is there anything to validate?
    pass


schema = {
    "faucet": {
        "create": {
            "inputs": [
                Input(P2PKH())
            ],
            "outputs": [
                Output(CCEval("faucet.drip", 0)),
            ],
        },
        "drip": {
            "inputs": [
                Input(Ref("faucet.create", 0))
            ],
            "outputs": [
                Output(CCEval("faucet.drip", 0), RelativeAmount(0) - 0.1),
                Output(P2PKH())
            ],
            "validate": validate_faucet_drip
        },
    }
}
