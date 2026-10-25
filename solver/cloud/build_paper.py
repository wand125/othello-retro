"""Build only the article's static, independently checked explanatory data."""
import json, os, subprocess
from pathlib import Path
from endgame_check import INITIAL, flips, legal, replay
ROOT=Path(__file__).resolve().parents[1]

def build():
    examples=json.loads((ROOT/'ui/public-examples.json').read_text())['examples']
    for e in examples:
        assert ''.join(replay(e['moves']))==e['board']
    front={''.join(INITIAL)}; demos=[]; record=examples[0]['moves']
    for depth in range(1,7):
        if depth in (3,5,6):
            target=''.join(replay(record[:depth])); b=sum(1<<i for i,c in enumerate(target) if c=='X');w=sum(1<<i for i,c in enumerate(target) if c=='O')
            p=subprocess.run([str(ROOT/'target/release/othello-retro'),'undo-server'],input=f'{b:016x},{w:016x}\n',text=True,capture_output=True,check=True)
            candidates=[]; color='X' if depth%2 else 'O'
            for token in p.stdout.split():
                qb,qw=(int(x,16) for x in token.split(',')); prev=''.join('X' if qb>>i&1 else 'O' if qw>>i&1 else '-' for i in range(64))
                removed=[i for i in range(64) if prev[i]=='-' and target[i]!='-'];assert len(removed)==1
                s=removed[0]; changed=flips(prev,s,color);assert changed
                f=list(prev)
                for q in [s,*changed]:f[q]=color
                assert ''.join(f)==target
                candidates.append({'board':prev,'move':'abcdefgh'[s%8]+str(s//8+1),'flipped':changed,'square':s,'reachable':prev in front})
            assert any(c['reachable'] for c in candidates)
            demos.append({'depth':depth,'target':target,'color':color,'candidates':candidates,'exhaustive_states':len(front),'reference':record[:depth]})
        nxt=set();color='X' if depth%2 else 'O'
        for board in front:
            for sq,fs in legal(board,color):
                v=list(board)
                for s in [sq,*fs]:v[s]=color
                nxt.add(''.join(v))
        front=nxt
    # Concrete witnesses for compressed passes and the all-64-square guard.
    forced=next(e for e in examples if e['id']=='game-2c8b678b7c02')
    i=forced['moves'].index('pass')
    assert i==57 and forced['moves'][i-1:i+2]==['h8','pass','h2']
    fm=''.join(replay(forced['moves'][:i]));fe=''.join(replay(forced['moves'][:i+2]))
    assert not legal(fm,'O') and [s for s,_ in legal(fm,'X')]==[15]
    bad_mid=''.join(replay(['d3']));bad_end=list(bad_mid);bad_square=37
    changed=flips(bad_end,bad_square,'X');assert changed
    for q in [bad_square,*changed]:bad_end[q]='X'
    bad_end=''.join(bad_end);white=[s for s,_ in legal(bad_mid,'O')]
    assert white==[18,20,34] and all(bad_end[s]=='-' for s in white)
    passes=[{'id':'illegal','title':'相手の合法手を見落とす例','middle':bad_mid,'end':bad_end,'first':'d3','second':'f5','first_square':19,'second_square':37,'opponent_legal':white,'valid':False,'prefix_placements':0},
            {'id':'forced','title':'実棋譜の強制パス','middle':fm,'end':fe,'first':'h8','second':'h2','first_square':63,'second_square':15,'opponent_legal':[],'valid':True,'prefix_placements':56}]
    data={'version':2,'date':'2026-10-25','initial':''.join(INITIAL),'examples':examples,'reverse':demos,'passes':passes}
    depth_file=ROOT/'analysis/retro-depth-examples.json'
    diagnostic=json.loads(depth_file.read_text())
    example=next(e for e in diagnostic['examples'] if e['id']=='retro-depth-5')
    assert diagnostic['status']=='complete'
    assert example['chain_passes_paper_closure_and_initial_unflippable'] is True
    assert example['frontier_counts']==[1,2,6,1,1,0]
    assert example['root_candidate']['board_reachable_from_standard_initial'] is False
    assert ''.join(replay(example['target_reference_moves']))==example['reachable_target']['board']
    for i,edge in enumerate(example['chain_edges_forward_from_index_i_plus_1_to_i']):
        before=list(example['longest_reverse_chain'][i+1]['board']);move=edge['move']
        square=(int(move[1])-1)*8+'abcdefgh'.index(move[0]);changed=flips(before,square,edge['mover']);assert changed
        for q in [square,*changed]:before[q]=edge['mover']
        assert ''.join(before)==example['longest_reverse_chain'][i]['board']
    data['deep']={'example':example,'rules':diagnostic['rules'],
                  'forward_counts':diagnostic['forward_counts'],
                  'dataset_sha256':__import__('hashlib').sha256(depth_file.read_bytes()).hexdigest()}
    chain_file=ROOT/'analysis/retro-depth-historical-chain-curated.json'
    chain=json.loads(chain_file.read_text())
    assert chain['status']=='verified-general-unsat-and11-legal-reverse-edges'
    assert len(chain['nodes'])==12 and len(chain['edges'])==11
    assert [n['stones'] for n in chain['nodes']]==list(range(61,49,-1))
    assert chain['nodes'][0]['board_unreachable'] is True
    assert all(n['board_unreachable'] is None for n in chain['nodes'][1:])
    assert all(n['state_unreachable_given_chain_next_side'] and n['passes_paper_cheap_conditions'] for n in chain['nodes'])
    proof=chain['proof']
    assert proof['solver_result']=='UNSAT' and proof['solver_exit_code']==20
    assert proof['nopass'] is False and proof['pass_window']==0 and proof['target_next_side']=='unrestricted'
    assert proof['free_colors']==0 and proof['selectors'] is False
    assert ''.join(replay(chain['reachable_full_target']['moves']))==chain['reachable_full_target']['board']
    for i,edge in enumerate(chain['edges']):
        before=list(chain['nodes'][i+1]['board']);move=edge['move'];color=edge['mover']
        assert chain['nodes'][i+1]['next_player']==color
        square=(int(move[1])-1)*8+'abcdefgh'.index(move[0]);changed=flips(before,square,color);assert changed
        for q in [square,*changed]:before[q]=color
        assert ''.join(before)==chain['nodes'][i]['board']
        opponent='O' if color=='X' else 'X'
        next_color=opponent if legal(before,opponent) else color if legal(before,color) else None
        assert next_color==chain['nodes'][i]['next_player']
        assert edge['forced_pass_after_move']==(next_color==color)
    data['version']=3
    data['long_chain']={**chain,'dataset_sha256':__import__('hashlib').sha256(chain_file.read_bytes()).hexdigest()}
    (ROOT/'ui/paper-data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'examples':len(examples),'demos':[(d['depth'],len(d['candidates']),sum(c['reachable'] for c in d['candidates'])) for d in demos],'passes':len(passes)}))
if __name__=='__main__':build()
