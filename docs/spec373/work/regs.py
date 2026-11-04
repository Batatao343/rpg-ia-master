import json,glob
def load(pat):
    out={}
    for f in glob.glob(pat):
        d=json.load(open(f,encoding='utf-8'))
        for k,v in d['criaturas'].items(): out[k]=(v,f)
    return out
b=load('docs/spec373/base/eval/arena-*.json'); n=load('docs/spec373/arena-*.json')
for k in ['enemy_esqueleto_mago','enemy_fantasma','mon_vela_sem_barco']:
    print(k, {c:(round(b[k][0]['cells'][c],3),round(v,3)) for c,v in n[k][0]['cells'].items()}, n[k][0].get('fora') or n[k][0].get('motivos'))
