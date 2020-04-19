
from pycc import *


token_link = SpendBy('token.transfer', 0)

def no_token_create(ctx, spec):
    import pdb; pdb.set_trace()


schema = {
    "token": {
        "create": {
            "inputs": [
                Input(P2PKH())
            ],
            "outputs": [
                Outputs(token_link, ExactAmount(0))
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
                no_token_create
            ]
        },
    }
}

