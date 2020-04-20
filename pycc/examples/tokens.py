
from pycc import *


def scarcity(tx, spec):
    tot_input = tot_output = 0

    for inp in tx.get_input_group(0):
        input_tx = TxValidator(tx.app, tx.app.chain.get_tx_confirmed(inp.previous_output[0]))
        tot_input += input_tx.params['tokenoshi'][inp.previous_output[1]]

    for out in spec['outputs'][0]:
        tot_output += out['tokenoshi']

    assert tot_input >= tot_output



token_link = SpendBy('token.transfer')


tokens = Outputs(
    script = token_link,
    amount = ExactAmount(0),
    data = {"tokenoshi": Amount(min=1)}
)


schema = {
    "token": {
        "create": {
            "inputs": [
                Input(P2PKH())
            ],
            "outputs": [
                tokens,
                OptionalOutput(P2PKH())
            ],
        },
        "transfer": {
            "inputs": [
                Inputs(token_link),
                Input(P2PKH())
            ],
            "outputs": [
                tokens,
                OptionalOutput(P2PKH())
            ],
            "validators": [
                scarcity
            ]
        },
    }
}

