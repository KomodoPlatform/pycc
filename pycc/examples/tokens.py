
from pycc import *


class Token:
    def consume(self, tx, spec):
        tot_input = tot_output = 0

        for inp in tx.get_input_group(0):
            input_tx = TxValidator(tx.app, tx.app.chain.get_tx_confirmed(inp.previous_output[0]))
            # This will break because the output index needs to be translated for the group
            # In reality the thing to do is to call validate() but not do I/O
            # TODO: check token ID on the input
            # TODO: check that input tx has right eval code
            tot_input += input_tx.params['tokenoshi'][inp.previous_output[1]]

        for out in spec['outputs'][0]:
            tot_output += out['tokenoshi']

        assert tot_input >= tot_output
        # return token ID

    def construct(self, tx, token_id):
        tx.params['token'] = token_id


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
            ]
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
            "token": Token
        },
    }
}

