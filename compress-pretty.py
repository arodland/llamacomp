#!python

import sys
import json
import requests
import leb128
import zlib
from color50 import constants as color

context = []
declen = 0
enclen = 0
ziplen = 0

file = open(sys.argv[1], "r", encoding="UTF-8")
inbuf = ""
exhausted = False
prev_is_ch = False

outf = open(sys.argv[2], "wb")
outz = zlib.compressobj(level=9, wbits=-15)

while True:
    while len(inbuf) < 1024 and not exhausted:
        r = file.read(4096)
        if r:
            inbuf += r
        else:
            exhausted = True

    if len(inbuf) == 0 and exhausted:
        break

    if len(context) > 512:
        context = context[len(context) - 512:]

    r = requests.post('http://localhost:8080/completion',
                      headers={'Content-Type': 'application/json'},
                      data=json.dumps({
                          'prompt': "".join(context),
                          'n_predict': 1,
                          'top_k': 128,
                          'n_probs': 128,
                          'seed': 42,
                          'temperature': 0,
                      })
                      )
    try:
        ds = r.json()
        probs = ds['completion_probabilities'][0]['probs']
        if len(probs) > 128:
            probs = probs[:128]

        matches = [(i, len(probs[i]['tok_str']), probs[i]['tok_str'])
                   for i in range(len(probs)) if inbuf.startswith(probs[i]['tok_str'])]
        if matches[0][0] != 0:
            matches.sort(key=lambda m: m[1], reverse=True)
    except Exception as e:
        matches = []

    if len(matches):
        idx, matchlen, token = matches[0]
        col = color.BRIGHT_GREEN if idx == 0 else color.BRIGHT_BLUE
        print(col + token + color.RESET, end="", flush=True)
        context.append(token)
        prev_is_ch = False
        declen += len(token)
        inbuf = inbuf[matchlen:]
    else:
        ch = inbuf[0]
        cp = ord(ch)
        idx = cp + 128

        print(color.BRIGHT_RED + ch + color.RESET, end="", flush=True)
        if prev_is_ch:
            context[-1] += ch
        else:
            context.append(ch)
            prev_is_ch = True

        declen += 1
        inbuf = inbuf[1:]

    enc = leb128.u.encode(idx)
    zipped = outz.compress(enc)
    enclen += len(enc)
    ziplen += len(zipped)
    # zip_extra = len(outz.copy().flush())
    # zip_total = ziplen + zip_extra

    # print(f"{declen} -> {enclen} -> {zip_total} ({declen / zip_total})")

    outf.write(zipped)
    outf.flush()

zipped = outz.flush()
ziplen += len(zipped)
outf.write(zipped)
print(f"flush: {declen} -> {enclen} -> {ziplen} ({declen / ziplen})")
