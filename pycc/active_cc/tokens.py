from pycctx import *
from pycc import *


class Token:
    def consume(self, tx, spec):
        tot_input = tot_output = 0

        for inp in tx.get_input_group(0):
            input_tx = TxValidator(tx.app, tx.app.chain.get_tx_confirmed(inp.previous_output[0]))
            # This will break because the output index needs to be translated for the group
            # In reality the thing to do is to call validate() to get the spec, but not do I/O
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


outputs = [
    Outputs(
        script = token_link,
        amount = ExactAmount(0),
        data = {"tokenoshi": Amount(min=1)}
    ),
    OptionalOutput(P2PKH())
]


schema = {
    "token": {
        "create": {
            "inputs": [
                Inputs(P2PKH())
            ],
            "outputs": outputs
        },
        "transfer": {
            "inputs": [
                Inputs(token_link),
                Input(P2PKH())
            ],
            "outputs": outputs,
            "token": Token
        },
    }
}


def create(app, global_string='default', create_amount=20000):
    setpubkey = rpc_wrap(app.chain, 'setpubkey')
    myaddr = setpubkey['address']
    mypk = setpubkey['pubkey']
    global_pair = string_keypair(global_string)

    vins, vins_amount = find_inputs(app.chain, [myaddr], create_amount+10000)

    create_tx = app.create_tx_extra_data({
            "name": "token.create",
            "inputs": [vins],
            "outputs": [
                [{'script': {'pubkey': mypk},
                  'tokenoshi': 10}],
                 [{"script": {"address": myaddr}, "amount": create_amount}]]
            
        }, {})

    mywif = rpc_wrap(app.chain, 'dumpprivkey', myaddr)
    create_tx.sign((mywif,))

    return(rpc_success(create_tx.encode())) # just dummies for now to demonstate generic active.py 


def transfer(app):
    return(rpc_success('ok transfer'))


info = {"functions": {"create": create, "transfer": transfer},
                      "eval": b't',
                      "schema": schema,
                      "help": {"create": "pycli tokens create example example example",
                               "transfer": "pycli tokens transfeer example example example"}}
