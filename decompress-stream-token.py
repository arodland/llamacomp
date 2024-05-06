#!python

import sys
import json
import requests
import leb128
import zlib
import io

context = []

file = open(sys.argv[1], "rb")
inz = zlib.decompressobj(wbits=-15)
inbuf = b""
exhausted = False
prev_is_ch = False

while True:
    while len(inbuf) < 128 and not exhausted:
        r = file.read(256)
        if r:
            inbuf += inz.decompress(r)
        else:
            inbuf += inz.flush()
            exhausted = True

    if len(inbuf) == 0 and exhausted:
        break

    if len(context) > 512:
        context = context[len(context) - 512:]

    bio = io.BytesIO(inbuf)
    val, n = leb128.u.decode_reader(bio)
    inbuf = inbuf[n:]

    if val >= 128:
        tok = chr(val - 128)
        if prev_is_ch:
            context[-1] += tok
        else:
            context.append(tok)
            prev_is_ch = True
    else:
        r = requests.post('http://localhost:8080/completion',
                          headers={'Content-Type': 'application/json'},
                          data=json.dumps({
                              'prompt': "".join(context),
                              'n_predict': 1,
                              'top_k': 128,
                              'n_probs': 128,
                              # 'cache_prompt': True,
                              'seed': 42,
                              'temperature': 0,
                          })
                          )
        probs = r.json()['completion_probabilities'][0]['probs']
        if len(probs) > 128:
            probs = probs[:128]

        # print(probs)
        tok = probs[val]['tok_str']
        context.append(tok)
        prev_is_ch = False
        # print(f"idx={val} context={context} tok={tok}")

    print(tok, end="", flush=True)
