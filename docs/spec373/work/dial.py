"""Uso: dial.py id=corpo,dano,forca,sig ...  (edita _ajustes.yaml, regenera, imprime nada; arena roda a parte)"""
import sys, yaml, os, glob
sys.path.insert(0, 'scripts/bestiario')
import gerar_mecanica as gm
P='data/bestiario/mecanica/_ajustes.yaml'
doc=yaml.safe_load(open(P,encoding='utf-8'))['ajustes']
regs=set()
for a in sys.argv[1:]:
    cid,v=a.split('='); c,d,f,s=[int(x) for x in v.split(',')]
    e=doc.setdefault(cid,{})
    for k,val in zip(('corpo','dano','forca','sig'),(c,d,f,s)):
        if val is None: continue
        e[k]=val
    for fp in glob.glob('data/bestiario/fichas/*.yaml'):
        if f'id: {cid}\n' in open(fp,encoding='utf-8').read(): regs.add(os.path.basename(fp)[:-5])
    e['arena']='SPEC-373 passo manual'
import calibrar
calibrar._gravar(doc)
for r in regs: gm.gerar(r)
