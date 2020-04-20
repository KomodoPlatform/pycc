
from pycc import *


def scarcity(ctx, spec):
    import pdb; pdb.set_trace()


token_link = SpendBy('token.transfer', 0)

schema = {
    "token": {
        "create": {
            "inputs": [
                Input(P2PKH())
            ],
            "outputs": [
                Outputs(token_link, ExactAmount(0)),
                Output(P2PKH())
            ],
        },
        "transfer": {
            "inputs": [
                Inputs(token_link),
                Input(P2PKH())
            ],
            "outputs": [
                Outputs(token_link, ExactAmount(0)),
                Output(P2PKH())
            ],
            "validators": [
                scarcity
            ]
        },
    }
}

