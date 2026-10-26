// SPDX-License-Identifier: MIT
'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const args=process.argv.slice(2);
function argument(name){const index=args.indexOf(name);if(index<0||!args[index+1])throw Error('Required: '+name);return args[index+1];}
if(args.includes('--help')){console.log('node generate-edge-items.cjs --solver-repo PATH --output NEWFILE');process.exit(0);}
const requested=path.resolve(argument('--solver-repo')),output=path.resolve(argument('--output'));
if(fs.existsSync(output))throw Error('--output must be a new file');
const browser=[path.join(requested,'browser-wasm'),path.join(requested,'../browser-wasm')].find(dir=>fs.existsSync(path.join(dir,'ui/verify.js'))&&fs.existsSync(path.join(dir,'tests/cases.json')));
if(!browser)throw Error('browser-wasm/ui/verify.js and tests/cases.json not found next to selected solver repository');
const rules=require(path.join(browser,'ui/verify.js'));
const source=path.join(browser,'tests/cases.json');
const cases=JSON.parse(fs.readFileSync(source)).cases;
const ids=['endgame-full-reference-no-pass-s202610255200001','endgame-full-reference-with-pass-s202610255300009','endgame-early-terminal-s202610255400242'];
function bits(board){let b=0n,w=0n;for(let s=0;s<64;s++){if(board[s]==='X')b|=1n<<BigInt(s);if(board[s]==='O')w|=1n<<BigInt(s);}return [b,w];}
function words(board){const [b,w]=bits(board),m=0xffffffffn;return [Number(b&m),Number(b>>32n),Number(w&m),Number(w>>32n)];}
function hex(board){return bits(board).map(x=>x.toString(16).padStart(16,'0')).join(',');}
const items=[];
for(const id of ids){const c=cases.find(c=>c.id===id);const proof=rules.verify(c.reference_moves,c.board,{includeStates:true});
 for(let i=1;i<proof.states.length;i++){const before=proof.states[i-1],after=proof.states[i];if(after.move==='pass')continue;
  const removed=(after.move.charCodeAt(1)-49)*8+after.move.charCodeAt(0)-97;
  items.push({source_case:id,normalized_move_index:i,move:after.move,child:hex(before.board),parent:hex(after.board),n_parent:after.placements,
   mover:before.next_player==='X'?0:1,child_words:words(before.board),parent_words:words(after.board),removed_square:removed,
   child_board:before.board,parent_board:after.board,follows_explicit_forced_pass:before.move==='pass'});
 }}
fs.mkdirSync(path.dirname(output),{recursive:true});
fs.writeFileSync(output,JSON.stringify({scope:'Genuine legal forward edges, usable as one-step reverse candidates. No native Undo process or model required.',source_fixtures_sha256:crypto.createHash('sha256').update(fs.readFileSync(source)).digest('hex'),items},null,2)+'\n');
console.log(JSON.stringify({legal_edges:items.length,after_pass:items.filter(x=>x.follows_explicit_forced_pass).length}));
