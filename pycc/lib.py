import binascii
import io
import json
import copy
from collections import namedtuple
from copy import deepcopy

from pycctx import *

import pdb

# Hack because komodod expects cc_eval function and pycctx.script also exports it
mk_cc_eval = cc_eval
del globals()['cc_eval']



class TxConstructor:
    def __init__(self, app, spec, params={}):
        self.model = app.get_model(spec['name'])
        self.app = app
        self.spec = deepcopy(spec)
        self.params = params
        self.stack = [] # TODO: phase out in favour of params

    def construct(self):
        def f(l):
            out = []
            groups = []
            specs = self.spec[l]
            model = self.model[l]
            assert len(specs) == len(model), ("number of %s groups differs" % l)
            for (spec, model_i) in zip(specs, model):
                r = model_i.construct(self, spec)
                n = len(r)
                assert n <= 0xff, ("%s group too large (255 max)" % l)
                groups.append(n)
                out.extend(r)
            return (groups, out)

        (input_groups, inputs) = f('inputs')
        (output_groups, outputs) = f('outputs')

        params = [self.spec['name'], (input_groups, output_groups), self.params] + self.stack
        outputs += [TxOut.op_return(encode_params(params))]
        tx =  Tx(
            inputs = tuple(inputs),
            outputs = tuple(outputs)
        )
        tx.set_sapling() if self.app.chain.is_sapling() else tx.set_standard()
        return(tx)

    @property
    def inputs(self):
        return tuple(i if type(i) == list else [i] for i in self.spec['inputs'])


class TxValidator:
    def __init__(self, app, tx):
        self.tx = tx
        self.app = app

        self.stack = decode_params(get_opret(tx))
        self.name = self.stack.pop(0)
        self.model = app.get_model(self.name)
        (self.input_groups, self.output_groups) = self.stack.pop(0)
        self.params = self.stack.pop(0)

    def validate(self):
        spec = {"txid": self.tx.hash, "inputs": [], "outputs": [], "name": self.name}
        def f(groups, l, nodes):
            assert len(groups) == len(self.model[l])
            assert sum(groups) == len(nodes)
            for (n, m) in zip(groups, self.model[l]):
                spec[l].append(m.consume(self, nodes[:n]))
                nodes = nodes[n:]

        f(self.input_groups, 'inputs', self.tx.inputs)
        f(self.output_groups, 'outputs', self.tx.outputs[:-1])

        for validate in self.model.get('validators', []):
            validate(self, spec)
            # FIXME hope to be able to raise exceptions here
            # and have them shown in `sendrawtransaction` response

        return spec

    def get_input_group(self, idx):
        groups = self.input_groups
        assert idx < len(groups), "TODO better message"
        skip = sum(groups[:idx])
        return self.tx.inputs[skip:][:groups[idx]]

    def get_output_group(self, idx):
        groups = self.output_groups
        assert idx < len(groups), "TODO better message"
        skip = sum(groups[:idx])
        return self.tx.outputs[skip:][:groups[idx]]

    def get_group_for_output(self, n_out):
        groups = self.output_groups
        tot = 0
        for (out_m, n) in zip(self.model['outputs'], groups):
            if tot + n > n_out:
                return out_m
            tot += n
        raise AssertionError("Cannot get group for output")


def py_to_hex(data):
    return hex_encode(json.dumps(data, sort_keys=True))

def hex_encode(data):
    if hasattr(data, 'encode'):
        data = data.encode()
    return binascii.hexlify(data).decode()

def hex_decode(data):
    return binascii.unhexlify(data)

def get_opret(tx):
    assert tx.outputs, "opret not present"
    opret = tx.outputs[-1]
    assert opret.amount == 0
    data = opret.script.get_opret_data()
    assert not data is None, "opret not present"
    return data


def encode_params(params):
    return repr(params).encode()

def decode_params(b):
    return eval(b)


# FIXME IN
class Input:
    def __init__(self, script, amount=None):
        self.script = script
        self.amount = amount

    def consume(self, tx, inputs):
        assert len(inputs) == 1
        return self.consume_input(tx, *inputs)

    def consume_input(self, tx, inp):
        return {
            "previous_output": inp.previous_output,
            "script": self.script.consume_input(tx, inp) or {},
            "input_amount": self.amount or {}
        }

    def construct(self, tx, spec):
        return [self.construct_input(tx, spec)]

    def construct_input(self, tx, spec):
        if 'amount' in spec:
            self.amount = spec['amount']
        return TxIn(spec['previous_output'], self.script.construct_input(tx, spec.get('script', {})),input_amount=self.amount)


class Inputs:
    def __init__(self, script, min=1):
        self.script = script
        self.min = min

    def consume(self, tx, inputs):
        assert len(inputs) >= self.min
        inp = Input(self.script)
        return [inp.consume_input(tx, i) for i in inputs]

    def construct(self, tx, inputs):
        assert len(inputs) >= self.min
        i = Input(self.script)
        return [i.construct_input(tx, inp) for inp in inputs]


class Outputs:
    def __init__(self, script, amount=None, min=1, max=0xff, data=None):
        self.script = script
        self.amount = amount or Amount()
        self.data = data or {}
        self.min = min
        self.max = max

    def consume(self, tx, outputs):
        assert self.min <= len(outputs) <= self.max
        outs = [self._consume_output(tx, o) for o in outputs]
        for out in outs:
            for (i, k) in enumerate(self.data):
                out[k] = self.data[k].consume(tx, tx.params[k][i])
        return outs

    def _consume_output(self, tx, output):
        return {
            "script": self.script.consume_output(tx, output.script) or {},
            "amount": self.amount.consume(tx, output.amount)
        }

    def construct(self, tx, outputs):
        assert type(outputs) == list, "outputs should be a list"
        assert self.min <= len(outputs) <= self.max

        for (k, t) in self.data.items():
            assert k not in tx.params, ('Namespace conflict on "%s"' % k)
            l = tx.params[k] = []
            for out in outputs:
                p = t.construct(tx, out[k])
                l.append(p)

        return [self._construct_output(tx, out) for out in outputs]

    def _construct_output(self, tx, spec):
        return TxOut(
            amount = self.amount.construct(tx, spec.get('amount')),
            script = self.script.construct_output(tx, spec.get('script', {}))
        )


def OptionalOutput(script):
    # TODO: this should maybe be a class so it can have nice error messages an such
    return Outputs(script, min=0, max=1)


class Output(Outputs):
    def __init__(self, *args, **kwargs):
        kwargs.update(dict(min=1, max=1))
        super(Output, self).__init__(*args, **kwargs)

    def construct(self, tx, output):
        return super(Output, self).construct(tx, [output])

    def consume(self, tx, output):
        return super(Output, self).consume(tx, output)[0]



class P2PKH:
    def consume_input(self, tx, inp):
        return inp.script.parse_p2pkh()

    def consume_output(self, tx, script):
        return script.parse_p2pkh()

    def construct_input(self, tx, spec):
        return ScriptSig.from_address(spec['address'])

    def construct_output(self, tx, spec):
        return ScriptPubKey.from_address(spec['address'])


# need SpendByUserArg
# has to be able to be variable at creation of plan, but static afterwards
# plan creation tx will use normal Spendby
# anything able to spend these must check that outputs always go back to the same pubkey



class SpendBy:
    """
    SpendBy ensures that an output is spent by a given type of input

    SpendBy make either use a dynamic or fixed pubkey.
    If it's fixed (provided in constructor), it does not expect to find
    it in tx spec and does not provide it in validated spec.

    """
    def __init__(self, name, pubkey=None):
        self.name = name
        self.pubkey = pubkey

        # TODO: sanity check on structure? make sure that inputs and outputs are compatible
   
    def consume_output(self, tx, script):
        # When checking the output there's nothing to check except the script
        return self._check_cond(tx, script.parse_condition())

    def consume_input(self, tx, inp):
        # Check input script
        r = self._check_cond(tx, inp.script.parse_condition())

        # Check output of parent tx to make sure link is correct
        p = inp.previous_output

        # FIXME had to change convert to bin first, need to be sure this doesn't break anything else
        tx_in = Tx.decode_bin(tx.app.chain.get_tx_confirmed(p[0]))
        input_tx = TxValidator(tx.app, tx_in)
        out_model = input_tx.get_group_for_output(p[1])
        assert self._eq(out_model.script)

        return r

    def construct_output(self, tx, spec):
        return ScriptPubKey.from_condition(self._construct_cond(tx, spec))

    def construct_input(self, tx, spec):
        return ScriptSig.from_condition(self._construct_cond(tx, spec))

    def _eq(self, other):
        # Should compare the pubkey here? maybe it's not neccesary
        return (type(self) == type(other) and
                self.name == other.name and
                self.pubkey == other.pubkey)

    def _check_cond(self, tx, cond):
        pubkey = self.pubkey or tx.stack.pop()
        c = cc_threshold(2,[mk_cc_eval(tx.app.eval_code),cc_threshold(1,[cc_secp256k1(pubkey)])])
        assert c.is_same_condition(cond)
        return {} if self.pubkey else { "pubkey": pubkey }

    def _construct_cond(self, tx, script_spec):
        pubkey = self.pubkey
        if pubkey:
            assert not script_spec.get('pubkey'), "pubkey must not be in both spec and schema"
        else:
            pubkey = script_spec['pubkey']
            tx.stack.append(pubkey)
        # FIXME this is a more efficient condition, but seems bugs in komodod make it unable to be validated
        #cond = cc_threshold(2, [mk_cc_eval(tx.app.eval_code), cc_secp256k1(pubkey)])
        cond = cc_threshold(2,[mk_cc_eval(tx.app.eval_code),cc_threshold(1,[cc_secp256k1(pubkey)])])

        #print(cond.to_py())
        return cond


class Amount():
    def __init__(self, min=0):
        self.min = min

    def consume(self, tx, amount):
        assert type(amount) == int
        assert amount >= self.min
        return amount

    def construct(self, tx, amount):
        assert type(amount) == int
        assert amount >= self.min
        return amount


class ExactAmount:
    def __init__(self, amount):
        self.amount = amount
   
    def consume(self, tx, amount):
        assert amount == self.amount

    def construct(self, tx, amount):
        assert amount is None
        return self.amount


class ExactAmountUserArg:
    def __init__(self, input_idx, diff=0):
        self.input_idx = input_idx
        self.diff = diff

    # FIXME test which of these are *actually* neccesary
    def __sub__(self, other):
        return ExactAmountUserArg(self.input_idx, self.diff - other)

    def __rsub__(self, other):
        return ExactAmountUserArg(self.input_idx, other - self.diff)   

    def __add__(self, other):
        return ExactAmountUserArg(self.input_idx, self.diff + other)

    def __radd__(self, other):
        return ExactAmountUserArg(self.input_idx, other + self.diff)

    def __mul__(self, other):
        return ExactAmountUserArg(self.input_idx, self.diff * other)

    def __neg__(self):
        return ExactAmountUserArg(self.input_idx, self.diff)*-1

    def __int__(self):
        return self.diff
   
    def consume(self, tx, amount):
        txid_in = tx.get_input_group(self.input_idx)[0].previous_output[0] # FIXME why does get_input_group return a tuple????
        tx_in = Tx.decode_bin(tx.app.chain.get_tx_confirmed(txid_in))
        self.diff = decode_params(get_opret(tx_in))[2]['AmountUserArg'] # FIXME hard coded data structure, want a PoC
        assert amount == self.diff
        return self.diff

    def construct(self, tx, amount):
        assert amount is None, "ExactAmountUserArg should have no amount in spec"
        txid_in = tx.spec['inputs'][self.input_idx]['previous_output'][0]
        tx_in = Tx.decode_bin(tx.app.chain.get_tx_confirmed(txid_in))
        self.diff = decode_params(get_opret(tx_in))[2]['AmountUserArg'] # FIXME hard coded, want a PoC
        return self.diff


# FIXME this probably should not have to be a unique class
# try to use __rsub__ __radd__ so we can do something like
# Output(schema_link, RelativeAmount(0) - ExactAmountUserArg(0))
# in the schema
class RelativeAmountUserArg:
    def __init__(self, input_idx, diff=0):
        self.input_idx = input_idx
        self.diff = diff

    def __sub__(self, n):
        return RelativeAmountUserArg(self.input_idx, self.diff - n)

    def __add__(self, n):
        return RelativeAmountUserArg(self.input_idx, self.diff + n)

    def consume(self, tx, amount):
        total = self.diff
        for inp in tx.get_input_group(self.input_idx):
            p = inp.previous_output
            input_tx = tx.app.chain.get_tx_confirmed(p[0])
            input_tx = Tx.decode_bin(input_tx)
            total += input_tx.outputs[p[1]].amount
            user_diff = decode_params(get_opret(input_tx))[2]['AmountUserArg']
            total -= user_diff


        assert total == amount, "TODO: nice error message"
        return amount

    def construct(self, tx, spec):
        assert spec == None, "amount should not be provided for RelativeAmountUserArg"

        r = self.diff


        for inp in as_list(tx.inputs[self.input_idx]):
            p = inp['previous_output']
            input_tx = tx.app.chain.get_tx_confirmed(p[0])
            input_tx = Tx.decode(input_tx.hex())
            r += input_tx.outputs[p[1]].amount
            user_diff = decode_params(get_opret(input_tx))[2]['AmountUserArg']
            r -= user_diff

        assert r >= 0, "cannot construct RelativeInputUserArg: low balance"
        return r


class RelativeAmount:
    def __init__(self, input_idx, diff=0):
        self.input_idx = input_idx
        self.diff = diff

    def __sub__(self, n):
        return RelativeAmount(self.input_idx, self.diff - n)

    def __add__(self, n):
        return RelativeAmount(self.input_idx, self.diff + n)

    def consume(self, tx, amount):
        total = self.diff
        for inp in tx.get_input_group(self.input_idx):
            p = inp.previous_output
            input_tx = tx.app.chain.get_tx_confirmed(p[0])
            input_tx = Tx.decode_bin(input_tx)
            total += input_tx.outputs[p[1]].amount


        assert total == amount, "TODO: nice error message"
        return amount

    def construct(self, tx, spec):
        assert spec == None, "amount should not be provided for RelativeAmount"

        r = self.diff


        for inp in as_list(tx.inputs[self.input_idx]):
            p = inp['previous_output']
            input_tx = tx.app.chain.get_tx_confirmed(p[0])
            input_tx = Tx.decode(input_tx.hex())
            r += input_tx.outputs[p[1]].amount

        assert r >= 0, "cannot construct RelativeInput: low balance"
        return r


# generic validator to ensure the params listed are the same value as input_idx tx's params
class CarryParams:
    def __init__(self, input_idx, params, spec=None, tx=None):
        self.input_idx = input_idx
        self.params = params
        self.spec = spec
        self.tx = tx

    def __call__(self, tx, spec):
        tx_in_txid = tx.tx.inputs[self.input_idx].previous_output[0]
        tx_in = Tx.decode_bin(tx.app.chain.get_tx_confirmed(tx_in_txid))
        prev_params = decode_params(get_opret(tx_in))
        for i in self.params:
            assert tx.params[i] == prev_params[2][i], ("CarryParmas OP_RETURN error %s not the same as input" % i) 



# set zeros in spec for static: TxPow(0,zeros=1)
# if not set, will use "TxPoW" from input_idx's opret params
class TxPoW:
    def __init__(self, input_idx, zeros=None):
        self.zeros = zeros
        self.input_idx = input_idx

    def __call__(self, tx, spec):
        if not self.zeros:
            txid_in = spec['inputs'][0]['previous_output'][0]
            tx_in = Tx.decode_bin(tx.app.chain.get_tx_confirmed(txid_in))
            prev_params = decode_params(get_opret(tx_in))
            self.zeros = prev_params[2]['TxPoW']
        assert tx.tx.hash.startswith('0'*self.zeros) and tx.tx.hash.endswith('0'*self.zeros)
        return(0)

def as_list(val):
    return val if type(val) == list else [val]

class IntendExcept(Exception):
    pass


######################
# FIXME this whole chunk is not neccesary if rust app or komodod
# can provide a function to take pubkey and eval code as input and output corresponding CC addr
import hashlib
import binascii
import base58


def hash160(hexstr):
    preshabin = binascii.unhexlify(hexstr)
    my160 = hashlib.sha256(preshabin).hexdigest()
    return(hashlib.new('ripemd160', binascii.unhexlify(my160)).hexdigest())


def addr_from_ripemd(prefix, ripemd):
    net_byte = prefix + ripemd
    bina = binascii.unhexlify(net_byte)
    sha256a = hashlib.sha256(bina).hexdigest()
    binb = binascii.unhexlify(sha256a)
    sha256b = hashlib.sha256(binb).hexdigest()
    hmmmm = binascii.unhexlify(net_byte + sha256b[:8])
    final = base58.b58encode(hmmmm)
    return(final.decode())


def addr_from_script(script_hexstr):
    ripemd = hash160(script_hexstr)
    addr = addr_from_ripemd('3c', ripemd)
    return addr


def CCaddr_normal(pubkey, eval_code):
    cond = cc_threshold(2, [mk_cc_eval(eval_code), cc_threshold(1, [cc_secp256k1(pubkey)])])
    spk = cond.encode_condition().hex()
    spk = hex(int(len(spk)/2))[2:] + spk + 'cc'
    return addr_from_script(spk)
######################


######################
# FIXME will move this elsewhere if it's determined this
# is a viable method for handling global keys
# import hashlib
# import binascii
# import base58
import ecdsa


def hash160(hexstr):
    preshabin = binascii.unhexlify(hexstr)
    my160 = hashlib.sha256(preshabin).hexdigest()
    return(hashlib.new('ripemd160', binascii.unhexlify(my160)).hexdigest())


def addr_from_ripemd(prefix, ripemd):
    net_byte = prefix + ripemd
    bina = binascii.unhexlify(net_byte)
    sha256a = hashlib.sha256(bina).hexdigest()
    binb = binascii.unhexlify(sha256a)
    sha256b = hashlib.sha256(binb).hexdigest()
    hmmmm = binascii.unhexlify(net_byte + sha256b[:8])
    final = base58.b58encode(hmmmm)
    return(final.decode())


def WIF_compressed(byte, raw_privkey):
    extended_key = byte+raw_privkey+'01'
    first_sha256 = hashlib.sha256(binascii.unhexlify(extended_key[:68])).hexdigest()
    second_sha256 = hashlib.sha256(binascii.unhexlify(first_sha256)).hexdigest()
    # add checksum to end of extended key
    final_key = extended_key[:68]+second_sha256[:8]
    # Wallet Import Format = base 58 encoded final_key
    WIF = base58.b58encode(binascii.unhexlify(final_key))
    return(WIF.decode("utf-8"))


# this will take an arbitary string and output a unique keypair+address
# intended to be used for global addresses with publicly known private keys
def string_keypair(key_string):
    privkey = hashlib.sha256(str(key_string).encode('utf-8')).hexdigest()
    try:
        sk = ecdsa.SigningKey.from_string(binascii.unhexlify(privkey), curve=ecdsa.SECP256k1)
    except ecdsa.keys.MalformedPointError:
         # hash again if sha256(key_string) is not on the curve; incredibly unlikely
         # 1 - FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364140
        return(string_keypair(privkey))
    vk = sk.verifying_key
    pk = vk.to_string("compressed").hex()
    addr = addr_from_ripemd('3c', hash160(pk))
    wif = WIF_compressed('bc', privkey)
    return({"wif": wif, "addr": addr, "pubkey": pk})
######################


######################
# I intend to move all of these to lib.py if CC devs agree these are useful
def rpc_wrap(chain, method, *params):
    return(json.loads(chain.rpc(json.dumps({"method": method, "params": list(params), "id": "pyrpc"}))))


def find_input(chain, addresses, amount, CCflag=False):
    if CCflag:
        unspent = rpc_wrap(chain, 'getaddressutxos', {"addresses": addresses}, 1)
    else:
        unspent = rpc_wrap(chain, 'getaddressutxos', {"addresses": addresses})
    for i in unspent:
        # FIXME this is a hacky way to disclude p2pk utxos;
        # will remove this when pycc issue#11 is addressed
        if i['script'].startswith('76') or CCflag:
            if i['satoshis'] >= amount and i['txid'] == '72adabfd62a8dbfd5b894c1fff0e65ed5c260ba78f472309a27bbeed5dc67367': # FIXME TESTING
                vin_tx = load_tx(chain, i['txid'])
                vin = {"previous_output": (i['txid'], i['outputIndex']),
                       "script": {"address": i['address']},
                       "amount": i['satoshis']}
                return vin, vin_tx, i['satoshis']
    raise IntendExcept("find_input: No suitable utxo found")


# this is likely a good candidate for a cpp method in pycc.ccp as it
# could be resource intensive depending on getaddressutxos output
def find_inputs(chain, addresses, minimum, CCflag=False):
    vins = []
    total = 0
    if CCflag:
        unspent = rpc_wrap(chain, 'getaddressutxos', {"addresses": addresses}, 1)
    else:
        unspent = rpc_wrap(chain, 'getaddressutxos', {"addresses": addresses})
    for i in unspent:
        # FIXME this is a hacky way to disclude p2pk utxos;
        # will remove this when pycc issue#11 is addressed
        if i['script'].startswith('76') or CCflag:
            am = i['satoshis']
            total += am
            vins.append({"previous_output": (i['txid'], i['outputIndex']),
                         "script": {"address": i['address']},
                         "amount": i['satoshis']})
            if total >= minimum:
                return vins, total
    raise IntendExcept("find_inputs: No suitable utxo set found")


def load_txes(chain, txids):
    txes = []
    for txid in txid:
            tx = rpc_wrap(chain, 'getrawtransaction', txid)
            txes.append(Tx.decode(tx))
    return(txes)


def load_tx(chain, txid):
    tx_hex = rpc_wrap(chain, 'getrawtransaction', txid)
    return(Tx.decode(tx_hex))


def rpc_error(msg):
    # this will make komodo-cli output a bit prettier for unexpected(non-IntendExcept) exceptions
    msg = str(msg).split('\n')
    return(json.dumps({"error": msg}))


def rpc_success(msg):
    return(json.dumps({"success": str(msg)}))
######################