# SPDX-License-Identifier: MIT
"""Isolated ONNX conversion and exact-input numerical fixtures; no retraining."""
import os
os.environ.update(OTHELLO_DEVICE='cpu',RETRO_HALF='0',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2',RETRO_INFERENCE_OPT='baseline')
from pathlib import Path
import argparse,hashlib,json,sys,time
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--solver-repo',type=Path,required=True,help='Engine root with ml/, or public repository root with solver/ml/')
parser.add_argument('--weights-dir',type=Path,required=True,help='Directory containing the two original Release .pt checkpoints')
parser.add_argument('--output',type=Path,required=True,help='New output directory; must not exist')
parser.add_argument('--legal-edges',type=Path,required=True,help='JSON produced by generate-edge-items.cjs')
args=parser.parse_args()
requested=args.solver_repo.resolve()
ROOT=next((p for p in [requested,requested/'solver'] if (p/'ml/train.py').is_file()),None)
if ROOT is None:parser.error('ml/train.py not found under --solver-repo or its solver/ child')
HERE=args.output.resolve()
if HERE.exists():parser.error('--output must be a new directory')
if not args.legal_edges.is_file():parser.error('--legal-edges is not a file')
sys.path.insert(0,str(ROOT/'ml'))
import numpy as np
import torch
import onnx
from train import Net,planes as single_planes
from search import planes_batch
from inference_opt import optimize

torch.set_num_threads(2)
try:torch.set_num_interop_threads(1)
except RuntimeError:pass
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
models_dir=args.weights_dir.resolve()
expected={'model':'dfb1f2e6a7ad4536415d3df9758c0a2e72af95abb40dfaae3c55f1921aee9820','model_passes':'8c3bc353fc136feb0561263bf75bac0dc7e491d261c124ca408fc100e6ce3c2d'}
items=json.loads(args.legal_edges.read_text())['items']
if len(items)<128:raise ValueError('at least128 legal-edge items required for fixed conversion fixtures')
HERE.mkdir(parents=True,exist_ok=False)
def batch(selected):
 x=planes_batch([(r['child'],r['parent'],r['n_parent'],r['mover']) for r in selected])
 # This second implementation is the original training feature builder.
 y=np.stack([single_planes({'q':r['child'],'parent':r['parent'],'n':r['n_parent'],'c':r['mover']}) for r in selected])
 np.testing.assert_array_equal(x,y)
 return x
batches=[]
for n in [1,16,128]:
 indices=[0] if n==1 else [round(i*(len(items)-1)/(n-1)) for i in range(n)]
 chosen=[items[i] for i in indices];x=batch(chosen)
 batches.append({'id':f'legal-batch-{n}','kind':'legal-reference-reverse-edges','shape':list(x.shape),'input':x.reshape(-1).tolist(),'items':chosen,'expected':{}})
forced=next(r for r in items if r['follows_explicit_forced_pass']);x=batch([forced])
batches.append({'id':'legal-after-forced-pass-batch-1','kind':'legal-reference-reverse-edge-after-pass','shape':list(x.shape),'input':x.reshape(-1).tolist(),'items':[forced],'expected':{}})
rng=np.random.default_rng(20261026)
for n in [1,16,128]:
 x=rng.integers(0,2,size=(n,5,8,8),dtype=np.int32).astype(np.float32)
 batches.append({'id':f'random-binary-batch-{n}','kind':'synthetic-conversion-check-only','shape':list(x.shape),'input':x.reshape(-1).tolist(),'expected':{}})
class Export(torch.nn.Module):
 def __init__(self,net):super().__init__();self.net=net
 def forward(self,planes):return self.net(planes,None)
manifest={'scope':'Model-format conversion and numeric equivalence only; no training, search, model-quality evaluation, repository edit or deployment.',
 'torch':torch.__version__,'numpy':np.__version__,'onnx':onnx.__version__,'python':sys.version.split()[0],'torch_threads':torch.get_num_threads(),
 'nice_observed':os.getpriority(os.PRIO_PROCESS,0),'device':'cpu','dtype':'float32','opset':17,'layout':'NCHW',
 'input':{'name':'planes','shape':['batch',5,8,8]},'output':{'name':'logits','shape':['batch']},
 'license':'CC-BY-4.0','attribution':'wand125','source':'https://github.com/wand125/othello-retro/releases/tag/v0.1.0',
 'changes':'Strict-loaded eval checkpoints cloned;9 Conv-BN pairs folded and graph exported to ONNX. No checkpoint file was written. Channels-last is a runtime layout choice, not a change to logical NCHW input.',
 'source_code_sha256':{p:sha(ROOT/p) for p in ['ml/train.py','ml/search.py','ml/inference_opt.py']},
 'exporter_sha256':sha(__file__),'historical_original_export':{'exporter_sha256': '57558733cd9797489e537d3f31151921216aa2ff935e6392898df1f385efd9df', 'manifest_sha256': '7f3923f933dcbc932ae7f95387ce5a2ef2c6ab605782e3312e641169600014c9', 'numeric_fixtures_sha256': '3835e721ffd1f302a9082e172fc509b5a6cbd325e6098a1e50e290cd56256380', 'scope': 'Historical first isolated export; its original source used fixed local paths. This portable CLI is a new source artifact; graph output identity is checked separately.'},'legal_edges_sha256':sha(args.legal_edges),'models':{}}
for name,digest in expected.items():
 path=models_dir/(name+'.pt');assert sha(path)==digest
 net=Net(False).cpu();net.load_state_dict(torch.load(path,map_location='cpu',weights_only=True),strict=True);net.eval()
 folded=optimize(net,'fused');wrapper=Export(folded).eval();output=HERE/(name+'.fused.onnx')
 started=time.monotonic()
 torch.onnx.export(wrapper,torch.zeros((1,5,8,8)),output,input_names=['planes'],output_names=['logits'],
  dynamic_axes={'planes':{0:'batch'},'logits':{0:'batch'}},opset_version=17,do_constant_folding=True,
  training=torch.onnx.TrainingMode.EVAL,export_params=True)
 graph=onnx.load(str(output));onnx.checker.check_model(graph,full_check=True)
 kinds={n.op_type for n in graph.graph.node};assert 'BatchNormalization' not in kinds
 errors=[]
 with torch.inference_mode():
  for item in batches:
   x=torch.from_numpy(np.asarray(item['input'],dtype=np.float32).reshape(item['shape']))
   original=net(x,None).numpy();fused=folded(x,None).numpy()
   assert original.shape==(item['shape'][0],) and np.isfinite(original).all() and np.isfinite(fused).all()
   np.testing.assert_allclose(fused,original,atol=1e-4,rtol=1e-4)
   error=float(np.max(np.abs(original-fused)));errors.append(error)
   item['expected'][name]={'original':original.tolist(),'fused':fused.tolist(),'max_abs_folding_error':error}
   np.save(HERE/(item['id']+'.input.npy'),x.numpy())
 assert sha(path)==digest
 manifest['models'][name]={'checkpoint_sha256':digest,'checkpoint_bytes':path.stat().st_size,'onnx_file':output.name,'onnx_sha256':sha(output),'onnx_bytes':output.stat().st_size,
  'folded_conv_bn_pairs':folded._inference_opt['fused_conv_bn_pairs'],'ir_version':graph.ir_version,'node_count':len(graph.graph.node),'operators':sorted(kinds),
  'max_abs_pytorch_folding_error':max(errors),'export_seconds':time.monotonic()-started,'checkpoint_unchanged':True}
 print(json.dumps({'model':name,**manifest['models'][name]}),flush=True)
fixtures={'schema_version':1,'input':manifest['input'],'output':manifest['output'],'dtype':'float32','layout':'NCHW',
 'plane_order':['predecessor mover-own','predecessor mover-opponent','predecessor empty','removed placement','color-flipped disc'],
 'flat_index':'((batch*5+channel)*8+row)*8+column; a1=row0,column0',
 'mover':'Explicit0 black/1 white from genuine forward edge. Never infer parity for pass-aware candidates.',
 'plane_formula':'own/opp use predecessor colors from mover viewpoint; empty=1-QB-QW; removed=(PB+PW)-(QB+QW); flipped=clip(abs(PB-QB)-removed,0,1)',
 'tolerance':{'atol':1e-4,'rtol':1e-4,'scope':'FP32 conversion comparison; verify against actual browser runtime. No claim that rankings are bit-identical.'},
 'random_seed':20261026,'batches':batches}
(HERE/'numeric-fixtures.json').write_text(json.dumps(fixtures,ensure_ascii=False,separators=(',',':'))+'\n')
manifest['numeric_fixtures_sha256']=sha(HERE/'numeric-fixtures.json')
manifest['files_sha256']={p.name:sha(p) for p in sorted(HERE.iterdir()) if p.is_file() and p.name!='model-export-manifest.json'}
(HERE/'model-export-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'status':'exported-and-checker-passed','batches':len(batches),'models':2,'numeric_fixtures_sha256':manifest['numeric_fixtures_sha256']}),flush=True)
